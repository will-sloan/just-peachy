"""Finite shared native GUI/model/source service envelope. See README_PACKAGE.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import uuid


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def identity(pid=None):
    pid = os.getpid() if pid is None else pid
    return dict(pid=pid, start_ticks=int(Path('/proc', str(pid), 'stat').read_text().rsplit(')',1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def alive(owner):
    try:
        return identity(owner['pid']) == owner
    except (FileNotFoundError, ProcessLookupError):
        return False


def write(path, value):
    raw = encoded(value)
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise OSError('Owner/closure readback failed')


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def verified_inventory(root, manifest_sha256):
    """Verify all cooperative runtime bytes before importing project modules."""
    root = Path(root).resolve(strict=True)
    manifest_path = root/'PACKAGE_MANIFEST.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 262144:
        raise ValueError('Bounded regular package manifest required')
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest_sha256:
        raise ValueError('Explicit runtime package manifest SHA mismatch')
    manifest = strict(raw)
    rows = manifest['files']
    if manifest.get('schema') != 'just-peachy.v29.package.v1' or not 1 <= len(rows) <= 512:
        raise ValueError('Explicit bounded runtime inventory required')
    expected = set()
    total = 0
    from pathlib import PurePosixPath
    for row in rows:
        name = row['path']; relative = PurePosixPath(name)
        if (relative.is_absolute() or relative.as_posix() != name or '..' in relative.parts
            or '\\' in name or name in expected or type(row['bytes']) is not int
            or not 0 <= row['bytes'] <= 2*1024**2):
            raise ValueError('Unsafe or duplicate runtime inventory member')
        expected.add(name); total += row['bytes']
        if total > 16*1024**2:
            raise ValueError('Runtime package exceeds its declared bound')
        path = root.joinpath(*relative.parts)
        if path.is_symlink() or path.resolve(strict=True) != path or path.stat().st_size != row['bytes']:
            raise ValueError('Runtime package path/extent changed')
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Runtime package source changed: ' + name)
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in runtime package')
        if path.is_file():
            name = path.relative_to(root).as_posix()
            if name not in expected and name != 'PACKAGE_MANIFEST.json':
                raise ValueError('Unlisted runtime package member')
            actual.add(name)
    if actual != expected | {'PACKAGE_MANIFEST.json'}:
        raise ValueError('Runtime package file set changed')
    return manifest


def verified_binding(args):
    binding_path = Path(args.binding)
    root = Path(__file__).resolve(strict=True).parent
    if binding_path != root/'BINDING.json' or binding_path.is_symlink():
        raise ValueError('Binding must be inside this exact immutable runtime')
    manifest = verified_inventory(root, args.manifest_sha256)
    binding = strict(binding_path.read_bytes())
    if binding.get('target') != str(root) or manifest.get('target') != str(root):
        raise ValueError('Runtime root differs from its manifest target')
    if binding.get('native_launch_enabled') is True:
        if binding.get('authorization_kind')=='production':
            # Inventory and this exact module were verified before this import.
            from release_authorization import authorization
            authorization(binding)
            return binding
        raw = (root/'NATIVE_ADMISSION.json').read_bytes()
        admission = strict(raw)
        if (hashlib.sha256(raw).hexdigest() != binding.get('admission_sha256')
            or admission.get('schema') != 'just-peachy.v29-reviewed-native-admission.v1'
            or admission.get('reviewed') is not True or admission.get('native_launch_enabled') is not True
            or admission.get('target') != str(root)
            or admission.get('candidate_content_sha256') != binding.get('candidate_content_sha256')
            or admission.get('expires_unix',0) <= time.time()
            or admission.get('boot_id') != identity()['boot_id']):
            raise ValueError('Native qualification admission expired or changed')
    return binding


def properties(unit):
    result = subprocess.run(['systemctl','--user','show',unit,
        '--property=ActiveState,SubState,InvocationID,ControlGroup,MainPID,AllowedCPUs,CPUQuotaPerSecUSec,TasksMax,RuntimeMaxUSec,Result,ExecMainStatus'],
        check=True, capture_output=True, text=True, timeout=5)
    return dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)


def cgroup_empty(control_group):
    """Exact owned cgroup disappearance or kernel recursive-population proof."""
    if (not control_group.startswith('/user.slice/') or '..' in control_group.split('/')
        or '\\' in control_group):
        raise ValueError('Unexpected owned user service cgroup')
    path = Path('/sys/fs/cgroup'+control_group)/'cgroup.events'
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return True
    if len(raw) > 4096:
        raise ValueError('Unexpected cgroup event extent')
    return dict(line.split() for line in raw.splitlines()).get('populated') == '0'


def bootstrap(directory, *, inside_service=False):
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise RuntimeError('Native envelope requires CM5 Linux')
    import resource
    os.sched_setaffinity(0, {3})
    # An independent systemd service does not inherit the external helper's
    # 128 MiB hard limit. Inside, the soft UI limit may be raised only by the
    # already bounded worker, up to its declared 768 MiB hard ceiling.
    memory = (256*1024**2, 768*1024**2) if inside_service else (128*1024**2, 128*1024**2)
    resource.setrlimit(resource.RLIMIT_AS, memory)
    resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))
    # RLIMIT_FSIZE is an absolute file length, not future disk consumption.
    # Existing history can exceed the currently free bytes. The hard ceiling is
    # physical filesystem capacity; every SQLite write checks real free space.
    ceiling = shutil.disk_usage(directory.parent).total - 5*1024**3 if inside_service else 32*1024**2
    if ceiling < 32*1024**2:
        raise OSError('Frontend file ceiling must preserve the existing 5 GiB floor')
    resource.setrlimit(resource.RLIMIT_FSIZE, (32*1024**2, ceiling))
    resource.setrlimit(resource.RLIMIT_CORE, (0,0))
    import threading
    threading.stack_size(1024**2)
    sys.dont_write_bytecode = True
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    directory.mkdir(parents=False, exist_ok=False)
    owner = identity()
    write(directory/'REGISTERED_OWNER.json', owner)
    if inside_service:
        expected={'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072'}
        observed={key:os.environ.get(key) for key in expected}
        write(directory/'ENVELOPE.json',dict(owner=owner,allocator_environment=observed,
            address_space=list(resource.getrlimit(resource.RLIMIT_AS)),stack=list(resource.getrlimit(resource.RLIMIT_STACK)),
            file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE))))
        if observed!=expected:raise RuntimeError('Retained allocator environment must be set before native exec')
    return owner


def inside(args, passthrough):
    root = Path(args.inside)
    owner = bootstrap(root/'main', inside_service=True)
    verified_binding(args)
    receipt_path = root/'UNIT_OWNERSHIP.json'
    deadline = time.monotonic()+20
    while not receipt_path.exists():
        if time.monotonic() > deadline:
            raise TimeoutError('External service owner acknowledgment did not arrive')
        time.sleep(.05)
    receipt = json.loads(receipt_path.read_bytes())
    state = properties(args.unit)
    if (receipt['owner'] != owner or receipt['main_pid'] != owner['pid']
        or receipt['unit'] != args.unit or receipt['invocation_id'] != os.environ.get('INVOCATION_ID')
        or receipt['control_group'] != state['ControlGroup'] or state['InvocationID'] != receipt['invocation_id']
        or state['MainPID'] != str(owner['pid'])):
        raise ValueError('Exact external service ownership mismatch')
    group = Path('/proc/self/cgroup').read_text()
    if not any(line.endswith(':'+receipt['control_group']) for line in group.splitlines()):
        raise ValueError('Launcher is outside the shared service cgroup')
    # Project imports happen only after the recorded actual owner is acknowledged.
    result = 1
    failure = None
    failure_diagnostic = None
    try:
        if args.entrypoint=='raw_qualification.py':
            import raw_qualification
            admission_path=root/'RAW_ADMISSION.json'
            raw=admission_path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=receipt.get('raw_admission_sha256'):
                raise ValueError('Exact fresh raw admission changed after unit acknowledgment')
            sys.argv=[str(Path(__file__).with_name(args.entrypoint)),'--binding',args.binding,
                '--binding-sha256',hashlib.sha256(Path(args.binding).read_bytes()).hexdigest(),
                '--admission',str(admission_path),'--admission-sha256',receipt['raw_admission_sha256'],
                '--unit',args.unit,'--unit-ownership',str(receipt_path),'--owner-directory',str(root/'raw-qualification')]
            if passthrough:raise ValueError('Raw qualification accepts only its pinned template and fixed source policy')
            result=raw_qualification.main()
        else:
            import launcher
            sys.argv = [str(Path(__file__).with_name('launcher.py')), '--binding', args.binding,
                '--data-root', args.data_root, '--unit', args.unit, '--unit-ownership', str(receipt_path),
                '--maximum-session-seconds', str(args.maximum_session_seconds),
                '--max-drain-seconds', str(args.max_drain_seconds),
                '--max-backlog-seconds', str(args.max_backlog_seconds)] + passthrough
            if args.developer_soak:
                sys.argv.append('--developer-soak')
            result = launcher.main()
        result = 0 if result is None else int(result)
        return result
    except BaseException as error:
        failure = type(error).__name__+': '+str(error)
        from storage_support import error_facts
        failure_diagnostic = getattr(error,'storage_diagnostic',None) or error_facts(error,operation='native service entrypoint')
        print(encoded(failure_diagnostic).decode(),file=sys.stderr,flush=True)
        raise
    finally:
        # Retains the real headless exit code even if systemd immediately
        # garbage-collects its inactive transient service after process exit.
        try:
            write(root/'SERVICE_EXIT.json', dict(owner=owner, unit=args.unit,
                invocation_id=receipt['invocation_id'], exit_code=result, error=failure,
                error_diagnostic=failure_diagnostic,package_manifest_sha256=args.manifest_sha256))
        except BaseException as receipt_error:
            # A failed recording filesystem cannot prevent reporting the primary
            # error or process exit; absent exit receipt remains a failed closure.
            print('Service exit receipt failed: '+repr(receipt_error),file=sys.stderr,flush=True)
            if failure is None:
                raise


def duration_seconds(value):
    units = {'us': .000001, 'ms': .001, 's': 1, 'min': 60, 'h': 3600, 'd':86400}
    tokens = re.findall(r'([0-9]+(?:\.[0-9]+)?)(us|ms|min|s|h|d)', value)
    if not tokens or ''.join(number+unit for number,unit in tokens) != value.replace(' ',''):
        raise ValueError('Unrecognized finite systemd duration')
    return sum(float(number)*units[unit] for number,unit in tokens)


def raw_template(args,binding):
    if args.entrypoint!='raw_qualification.py':return None
    if not args.raw_admission_template or not args.raw_admission_template_sha256:
        raise ValueError('Explicit reviewed SHA-pinned raw qualification template required')
    path=Path(args.raw_admission_template)
    if path.is_symlink() or path.stat().st_size>65536:raise ValueError('Bounded real raw template')
    raw=path.read_bytes();value=strict(raw)
    if (hashlib.sha256(raw).hexdigest()!=args.raw_admission_template_sha256
        or value.get('schema')!='just-peachy.raw-qualification-template.v1'
        or value.get('reviewed') is not True or value.get('duration_seconds')!=5
        or value.get('target')!=binding['target']
        or value.get('binding_sha256')!=hashlib.sha256(Path(args.binding).read_bytes()).hexdigest()
        or value.get('package_manifest_sha256')!=args.manifest_sha256
        or value.get('boot_id')!=identity()['boot_id'] or value.get('expires_unix',0)<=time.time()):
        raise ValueError('Exact fresh raw qualification template does not match')
    root=Path(args.binding).parent
    for name in ('installed_source.py','raw_capture.py','source_batch.py'):
        if value.get(name[:-3]+'_sha256')!=hashlib.sha256((root/name).read_bytes()).hexdigest():
            raise ValueError('Raw template module pin changed')
    return value


def source_owners(data_root, created_after):
    # Only this iteration's freshly created registered source receipts qualify.
    results = []
    sessions = Path(data_root)/'recordings'/'sessions'
    if not sessions.exists():
        return results
    for session in sessions.iterdir():
        if session.is_symlink() or not session.is_dir():
            continue
        receipt = session/'work/source/REGISTERED_OWNER.json'
        if receipt.is_file() and not receipt.is_symlink() and receipt.stat().st_mtime >= created_after:
            if receipt.stat().st_size > 65536:
                raise ValueError('Oversized source owner receipt')
            owner = json.loads(receipt.read_bytes())['owner']
            results.append(dict(path=str(receipt), owner=owner, exact_owner_gone=not alive(owner)))
    return results


def outside(args, passthrough):
    base = Path(args.data_root)
    if base.is_symlink() or base.parent.resolve(strict=True) != base.parent:
        raise ValueError('Explicit real existing data parent required')
    base.mkdir(exist_ok=True)
    owners = base/'unit-owners'
    if owners.is_symlink():
        raise ValueError('Unit owner root must not be a symlink')
    owners.mkdir(exist_ok=True)
    root = owners/uuid.uuid4().hex
    owner = bootstrap(root)
    created = time.time()
    import signal
    upper_lifetime = args.maximum_session_seconds + args.max_drain_seconds + 120 + 60 + 1800 + 240
    if not 0 < upper_lifetime <= 100000:
        raise ValueError('Finite external wrapper deadline required')
    def alarm_handler(signum, frame):
        write(root/'OUTER_DEADLINE.json', dict(owner=owner, deadline_seconds=upper_lifetime,
            outcome='INCOMPLETE_CLOSURE', service_backstop_independently_armed=True))
        raise TimeoutError('External wrapper finite lifetime exceeded')
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(upper_lifetime)
    binding = verified_binding(args)
    template=raw_template(args,binding)
    from profiles import SessionPolicy
    policy = SessionPolicy(maximum_session_seconds=args.maximum_session_seconds,
        developer_soak=args.developer_soak, max_drain_seconds=args.max_drain_seconds,
        max_backlog_seconds=args.max_backlog_seconds)
    policy.validate()
    # A user can perform multiple short sessions; the containing GUI is still
    # finite. Headless qualification has no idle UI allowance.
    headless='--headless' in passthrough or args.entrypoint!='launcher.py'
    # Headless startup/import gets a separate 150-second allowance; Manager
    # still reserves the complete policy deadline plus 150 seconds at Start.
    manual_service = False
    if not headless and binding.get('authorization_kind') == 'production':
        from release_authorization import authorization
        _, approved = authorization(binding)
        manual_service = approved['limits'].get('manual_stop_storage_policy') is True
    lifetime = None if manual_service else (int(policy.total_deadline_seconds+300) if headless else max(7200,int(policy.total_deadline_seconds+450)))
    # Manager admits Start only when the entire session plus closure fits this
    # fixed backstop. Idle GUI timeout is separate and never stops a worker.
    signal.alarm(240 if manual_service else lifetime+240)
    binding_path = Path(args.binding)
    if binding_path.is_symlink() or binding_path.stat().st_size > 262144:
        raise ValueError('Bounded real binding required')
    if Path(binding['python']).resolve(strict=True) != Path(sys.executable).resolve(strict=True):
        raise ValueError('Envelope must run in the pinned installed interpreter')
    os.environ['ALSA_CONFIG_PATH'] = binding['alsa_config']
    unit = 'jp-v29-'+uuid.uuid4().hex+'.service'
    child = [binding['python'], '-B', str(Path(__file__).resolve()), '--inside', str(root),
        '--unit', unit, '--binding', args.binding, '--data-root', args.data_root,
        '--manifest-sha256', args.manifest_sha256,
        '--entrypoint',args.entrypoint,
        '--maximum-session-seconds', str(args.maximum_session_seconds),
        '--max-drain-seconds', str(args.max_drain_seconds),
        '--max-backlog-seconds', str(args.max_backlog_seconds)] + passthrough
    if args.developer_soak:
        child.append('--developer-soak')
    command = ['systemd-run','--user','--quiet','--unit='+unit,'--service-type=exec',
        '--property=AllowedCPUs=2-3','--property=CPUQuota=200%','--property=TasksMax=64',
        '--property=RuntimeMaxSec='+('infinity' if manual_service else str(lifetime)),'--property=TimeoutStopSec=150',
        '--property=KillMode=control-group','--property=SendSIGKILL=yes',
        '--property=MemoryAccounting=yes','--property=CPUAccounting=yes',
        '--property=Environment=PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1',
        '--setenv=ALSA_CONFIG_PATH='+binding['alsa_config']]
    for key,value in {'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072'}.items():
        command.append('--setenv='+key+'='+value)
    for key in ('DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','XAUTHORITY'):
        if key in os.environ:
            command.append('--setenv='+key+'='+os.environ[key])
    write(root/'SERVICE_REQUEST.json', dict(unit=unit, owner=owner, policy=policy.validate(),
        runtime_max_seconds=lifetime, command=command+child,
        binding_sha256=hashlib.sha256(binding_path.read_bytes()).hexdigest()))
    launched_at=time.monotonic()
    subprocess.run(command+child, check=True, stdin=subprocess.DEVNULL, timeout=20)
    deadline = time.monotonic()+20
    while not (root/'main/REGISTERED_OWNER.json').exists():
        if time.monotonic() > deadline:
            raise TimeoutError('Service main owner not registered; finite systemd backstop remains armed')
        time.sleep(.05)
    main_owner = json.loads((root/'main/REGISTERED_OWNER.json').read_bytes())
    state = properties(unit)
    if (state['ActiveState'] != 'active' or state['AllowedCPUs'] not in ('2-3','2,3')
        or state['CPUQuotaPerSecUSec'] != '2s' or state['TasksMax'] != '64'
        or (state['RuntimeMaxUSec'] != 'infinity' if manual_service else duration_seconds(state['RuntimeMaxUSec']) != lifetime)
        or state['MainPID'] != str(main_owner['pid']) or not alive(main_owner)
        or not state['InvocationID'] or not state['ControlGroup']):
        raise ValueError('Actual unique service envelope did not verify; native imports remain gated')
    receipt = dict(unit=unit, invocation_id=state['InvocationID'], control_group=state['ControlGroup'],
        main_pid=main_owner['pid'], owner=main_owner, runtime_max_seconds=lifetime,
        deadline_monotonic=None if manual_service else launched_at+lifetime,idle_timeout_seconds=300,
        lifetime_policy='manual_stop_storage_guarded' if manual_service else 'finite_qualification')
    if template is not None:
        if template['expires_unix']<=time.time():raise ValueError('Raw template expired while creating owned unit')
        admission=dict(status='RAW_NATIVE_QUALIFICATION_ADMITTED',duration_seconds=5,
            binding_sha256=template['binding_sha256'],installed_source_sha256=template['installed_source_sha256'],
            raw_capture_sha256=template['raw_capture_sha256'],source_batch_sha256=template['source_batch_sha256'],
            unit=unit,invocation_id=state['InvocationID'],
            boot_id=main_owner['boot_id'],issued_unix=time.time(),expires_unix=min(template['expires_unix'],time.time()+300),
            template_sha256=args.raw_admission_template_sha256,owner=main_owner)
        write(root/'RAW_ADMISSION.json',admission)
        receipt['raw_admission_sha256']=hashlib.sha256(encoded(admission)).hexdigest()
    write(root/'UNIT_OWNERSHIP.json', receipt)
    deadline = None if manual_service else time.monotonic()+lifetime+180
    if manual_service:
        signal.alarm(0)  # Startup remains bounded; active conversation safety is per-worker.
    while manual_service or time.monotonic() < deadline:
        try:
            state = properties(unit)
        except subprocess.CalledProcessError as error:
            state = dict(ActiveState='unavailable', query_error=str(error))
        if ((state['ActiveState'] in ('inactive','failed') or cgroup_empty(receipt['control_group']))
            and not alive(main_owner)):
            break
        time.sleep(.5)
    sources = source_owners(base, created)
    service_exit = None
    if (root/'SERVICE_EXIT.json').is_file():
        service_exit = strict((root/'SERVICE_EXIT.json').read_bytes())
        if (service_exit.get('owner') != main_owner or service_exit.get('unit') != unit
            or service_exit.get('invocation_id') != receipt['invocation_id']
            or service_exit.get('package_manifest_sha256') != args.manifest_sha256):
            raise ValueError('Durable service exit identity changed')
    closure = dict(unit=unit, ownership=receipt, final_properties=state,
        main_exact_owner_gone=not alive(main_owner), sources=sources,
        all_registered_source_owners_gone=all(row['exact_owner_gone'] for row in sources),
        unit_stopped=state['ActiveState'] in ('inactive','failed') or cgroup_empty(receipt['control_group']),
        physical_stream_qualification='REQUIRES_SOURCE_CLOSE_RECEIPT', external_owner=owner,
        service_exit=service_exit)
    write(root/'UNIT_CLOSURE.json', closure)
    if not closure['unit_stopped'] or not closure['main_exact_owner_gone'] or not closure['all_registered_source_owners_gone']:
        raise RuntimeError('Owned service/process closure incomplete; receipt retained')
    return 0 if service_exit and service_exit.get('exit_code') == 0 and not service_exit.get('error') else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binding', required=True)
    ap.add_argument('--manifest-sha256', required=True)
    ap.add_argument('--data-root', required=True)
    ap.add_argument('--maximum-session-seconds', type=int, default=300)
    ap.add_argument('--developer-soak', action='store_true')
    ap.add_argument('--max-drain-seconds', type=int, default=120)
    ap.add_argument('--max-backlog-seconds', type=int, default=120)
    ap.add_argument('--inside')
    ap.add_argument('--unit')
    ap.add_argument('--entrypoint',choices=('launcher.py','raw_qualification.py'),default='launcher.py')
    ap.add_argument('--raw-admission-template')
    ap.add_argument('--raw-admission-template-sha256')
    args, passthrough = ap.parse_known_args()
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise RuntimeError('Native envelope is prepared only; no PC UI/model launch')
    os.sched_setaffinity(0, {2,3})
    return inside(args, passthrough) if args.inside else outside(args, passthrough)


if __name__ == '__main__':
    raise SystemExit(main())
