"""Owned native metadata helper for xvf_readiness.py. README_XVF_READINESS.md."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import time

TOOL = '/home/peachyprototype/JustPeachy/tools/native_xvf_usb/bin/xvf_host'
TOOL_SHA256 = '8cc5eebcb499faa61278c9378f7fcb92c6063a437176218404e56e610265e982'
CAMPAIGN = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
PIN_PATHS = (TOOL, '/home/peachyprototype/JustPeachy/data/live_config.json',
    '/home/peachyprototype/JustPeachy/install/current.json', '/home/peachyprototype/JustPeachy/data/settings.json',
    '/home/peachyprototype/.config/kanshi/config')


def identity(pid=None):
    pid = os.getpid() if pid is None else pid
    return dict(pid=pid, start_ticks=int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def owner_closed(owner):
    if (not isinstance(owner, dict) or set(owner) != {'pid', 'start_ticks', 'boot_id'} or
        type(owner['pid']) is not int or owner['pid'] <= 0 or type(owner['start_ticks']) is not int or owner['start_ticks'] <= 0 or
        not isinstance(owner['boot_id'], str) or re.fullmatch('[0-9a-f-]{36}', owner['boot_id']) is None):
        raise ValueError('Exact native owner identity required')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != owner['boot_id']:
        return True
    try:
        return identity(owner['pid']) != owner
    except (FileNotFoundError, ProcessLookupError):
        return True


def bounded(path, maximum=65536):
    path = Path(path); before = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_size > maximum or before.st_nlink != 1:
        raise ValueError('Bounded real single-link recovery input required')
    raw = path.read_bytes(); after = path.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('Recovery input changed during read')
    return raw


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def put(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()+b'\n'
    if len(raw) > 65536: raise ValueError('Finite recovery receipt bound')
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw): raise OSError('Short recovery receipt')
        stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw: raise OSError('Recovery receipt readback failed')
    fd = os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def streams_closed():
    paths = list(Path('/proc/asound').glob('card*/pcm*c/sub*/status'))
    if not paths or len(paths) > 64 or any(path.read_text().strip() != 'closed' for path in paths):
        raise RuntimeError('Every capture stream must be closed before maintenance')


def closed_runtime_owners(root):
    count = 0; digest = hashlib.sha256()
    roots = ((root/'launches', '*/worker/REGISTERED_OWNER.json'),
             (root/'recordings/sessions', '*/work/source/REGISTERED_OWNER.json'))
    for directory, pattern in roots:
        for path in sorted(directory.glob(pattern)):
            count += 1
            if count > 4096: raise ValueError('Runtime owner census exceeds its finite maintenance bound')
            raw = bounded(path); value = strict(raw); owner = value.get('owner', value)
            if not owner_closed(owner): raise RuntimeError('Another recorded microphone/model worker remains live')
            digest.update(str(path.relative_to(root)).encode()+b'\0'+hashlib.sha256(raw).digest())
    return dict(records=count, path_and_content_sha256=digest.hexdigest(), every_exact_owner_closed=True)


def unit_checks(request):
    raw = bounded(request['unit_ownership'])
    if hashlib.sha256(raw).hexdigest() != request['unit_ownership_sha256']:
        raise ValueError('Owned GUI unit receipt changed')
    receipt = strict(raw)
    keys = {'unit', 'owner', 'main_pid', 'invocation_id', 'control_group',
            'runtime_max_seconds', 'deadline_monotonic', 'idle_timeout_seconds'}
    extra = {'address_space', 'stack', 'qualification_kind', 'recording_model_scope'}
    modern_gui = set(receipt) == keys | extra
    if modern_gui:
        for name in ('address_space', 'stack'):
            value = receipt[name]
            if type(value) is not list or len(value) != 2 or any(type(item) is not int for item in value):
                raise ValueError('Exact actual integer model resource pairs required')
        if (receipt['address_space'] != [1024**3, 1024**3]
                or receipt['stack'] != [1024**2, 1024**2]
                or receipt['qualification_kind'] != 'gui'
                or receipt['recording_model_scope'] is not True
                or re.fullmatch(r'jp-v29-classic-ui-check-[0-9]{2}\.service', request['unit']) is None):
            raise ValueError('Extended readiness scope is limited to the exact modern GUI envelope')
    manual = receipt.get('lifetime_policy') == 'manual_stop_storage_guarded'
    if manual:
        if (set(receipt) != keys | {'lifetime_policy'}
                or receipt.get('runtime_max_seconds') is not None
                or receipt.get('deadline_monotonic') is not None
                or type(receipt.get('idle_timeout_seconds')) is not int
                or receipt['idle_timeout_seconds'] != 300):
            raise ValueError('Exact manual-Stop storage-guarded GUI lifetime required')
    else:
        deadline, runtime = receipt.get('deadline_monotonic'), receipt.get('runtime_max_seconds')
        finite_schema = (modern_gui or set(receipt) == keys or
                         (set(receipt) == keys | {'lifetime_policy'}
                          and receipt.get('lifetime_policy') == 'finite_qualification'))
        if (not finite_schema or type(deadline) not in (int, float) or not math.isfinite(deadline)
                or type(runtime) not in (int, float) or not math.isfinite(runtime) or runtime <= 0
                or deadline-time.monotonic() < 60):
            raise ValueError('Finite owned GUI lifetime cannot cover microphone recovery')
    if (receipt.get('unit') != request['unit'] or receipt.get('owner') != request['manager_owner'] or
        type(receipt.get('main_pid')) is not int or receipt['main_pid'] != request['manager_owner']['pid']
        or owner_closed(request['manager_owner'])):
        raise ValueError('Current native GUI ownership or remaining lifetime is insufficient')
    shown = subprocess.run(['systemctl', '--user', 'show', request['unit'],
        '--property=MainPID,InvocationID,ControlGroup,ActiveState,AllowedCPUs,CPUQuotaPerSecUSec,TasksMax,RuntimeMaxUSec'],
        capture_output=True, text=True, check=True, timeout=3)
    props = dict(line.split('=', 1) for line in shown.stdout.splitlines() if '=' in line)
    if (props.get('ActiveState') != 'active' or props.get('MainPID') != str(receipt['main_pid']) or
        props.get('InvocationID') != receipt['invocation_id'] or props.get('ControlGroup') != receipt['control_group'] or
        props.get('AllowedCPUs') not in ('2-3', '2,3') or props.get('CPUQuotaPerSecUSec') != '2s' or props.get('TasksMax') != '64'):
        raise ValueError('Actual native shared unit differs from its CPU/task ownership envelope')
    if ((manual and props.get('RuntimeMaxUSec') != 'infinity') or
            (not manual and props.get('RuntimeMaxUSec') in (None, '', 'infinity'))):
        raise ValueError('Actual GUI service lifetime differs from the explicit owned lifetime policy')
    if not manual:
        value = props['RuntimeMaxUSec']
        units = {'us': .000001, 'ms': .001, 's': 1, 'min': 60, 'h': 3600, 'd': 86400}
        tokens = re.findall(r'([0-9]+(?:\.[0-9]+)?)(us|ms|min|s|h|d)', value)
        if (not tokens or ''.join(number+unit for number, unit in tokens) != value.replace(' ', '')
                or not math.isclose(sum(float(number)*units[unit] for number, unit in tokens), runtime,
                                    rel_tol=1e-9, abs_tol=1e-6)):
            raise ValueError('Actual finite GUI runtime limit differs from its ownership receipt')
    group = receipt['control_group']
    if (not group.startswith('/user.slice/') or '..' in group.split('/') or '\\' in group or
        not any(line.endswith(':'+group) for line in Path('/proc/self/cgroup').read_text().splitlines())):
        raise ValueError('Helper is outside the exact owned GUI cgroup')
    pids = (Path('/sys/fs/cgroup'+group)/'cgroup.procs').read_text().split()
    if not pids or len(pids) > 64 or set(map(int, pids)) - {os.getpid(), receipt['main_pid']}:
        raise RuntimeError('An additional owned model/source process prevents maintenance')
    return props


def snapshot(out):
    pins = {}
    for directory in ('before', 'restore'): (out/directory).mkdir()
    for index, name in enumerate(PIN_PATHS):
        raw = bounded(name, 2*1024**2 if name == TOOL else 65536)
        pin = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if name == TOOL and pin != dict(bytes=1773304, sha256=TOOL_SHA256):
            raise ValueError('Previously exercised XVF control tool pin differs')
        if name.endswith('/kanshi/config') and pin['sha256'] != 'c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b':
            raise ValueError('Retained saved display270 configuration differs')
        for directory in ('before', 'restore'):
            path = out/directory/str(index)
            with path.open('xb') as stream:
                if stream.write(raw) != len(raw): raise OSError('Short independent recovery copy')
                stream.flush(); os.fsync(stream.fileno())
            if path.read_bytes() != raw: raise OSError('Independent recovery restore readback differs')
        pins[name] = pin
    put(out/'RESTORE_COPIES.json', dict(pins=pins, index=list(PIN_PATHS), independent_readbacks=True,
        volatile_state_restorable=False))
    return pins


def check_pins(pins):
    for name, pin in pins.items():
        raw = bounded(name, 2*1024**2)
        if len(raw) != pin['bytes'] or hashlib.sha256(raw).hexdigest() != pin['sha256']:
            raise ValueError('Recovery tool/config/install/settings/display changed')


def native_main(out, gate):
    os.sched_setaffinity(0, {3})
    resource.setrlimit(resource.RLIMIT_AS, (128*1024**2, 128*1024**2))
    resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2*1024**2, 2*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    def interrupted(signum, frame): raise TimeoutError('Finite readiness helper signal '+str(signum))
    signal.signal(signal.SIGALRM, interrupted); signal.signal(signal.SIGTERM, interrupted); signal.alarm(45)
    if os.read(gate, 1) != b'1': raise RuntimeError('Actual helper owner was not acknowledged')
    os.close(gate)
    owned = identity(); put(out/'REGISTERED_OWNER.json', owned)
    # Early actual identity above precedes request and project-source reads.
    request = strict(bounded(out/'REQUEST.json')); leases = []; commands = []; pins = None
    result = dict(status='FAILED_PRESERVED', owner=owned, capture_opened=False, models_loaded=False,
        audio_qualified=False, readiness_verified=False, fault_sha256=request.get('fault_sha256'))
    try:
        if (request.get('schema') != 'just-peachy.xvf-readiness.v1' or request.get('maximum_output_bytes') != 16*1024**2 or
            type(request.get('reserve_bytes')) is not int or request['reserve_bytes'] < 5*1024**3 or
            not time.monotonic() < request.get('expires_monotonic', 0) <= time.monotonic()+60 or
            out.name != request['fault_sha256'] or re.fullmatch('[0-9a-f]{64}', out.name) is None or
            out.parent != Path(request['data_root'])/'recovery'):
            raise ValueError('Exact bounded readiness request required')
        source = bounded(__file__, 131072)
        if hashlib.sha256(source).hexdigest() != request['helper_sha256']:
            raise ValueError('Pinned readiness helper source differs')
        module_path = Path(__file__).with_name('xvf_readiness.py'); module_raw = bounded(module_path, 131072)
        if hashlib.sha256(module_raw).hexdigest() != request['module_sha256']:
            raise ValueError('Pinned readiness sequence source differs')
        spec = importlib.util.spec_from_file_location('verified_xvf_readiness', module_path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        fault_raw = bounded(request['fault_path']); closed_raw = bounded(request['closed_path'], 262144)
        fault = strict(fault_raw); closed = strict(closed_raw)
        if (hashlib.sha256(fault_raw).hexdigest() != request['fault_sha256'] or
            hashlib.sha256(closed_raw).hexdigest() != request['closed_sha256'] or not module.qualifying_fault(fault) or
            closed.get('nested_source', {}).get('physical_receipt') != fault or
            closed.get('registered_owner') != request['worker_owner'] or fault.get('owner') != request['source_owner'] or
            request['source_owner'].get('boot_id') != owned['boot_id'] or request['worker_owner'].get('boot_id') != owned['boot_id'] or
            not owner_closed(request['worker_owner']) or not owner_closed(request['source_owner'])):
            raise ValueError('Previous exact closed source fault/owners changed')
        result['actual_unit_properties'] = unit_checks(request)
        if shutil.disk_usage(out).free < request['reserve_bytes']+request['maximum_output_bytes']:
            raise OSError('Independent recovery reserve would cross the storage floor')
        memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
        result['initial_available_ram'] = int(memory['MemAvailable'].split()[0])*1024
        if result['initial_available_ram'] < 850*1024**2: raise MemoryError('Initial available RAM below850MiB')
        for name in (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock', Path('/home/peachyprototype/JustPeachy/data/xvf-hardware.lock')):
            if name.is_symlink(): raise ValueError('Real existing lease required')
            handle = name.open('rb')
            try: fcntl.flock(handle, fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BaseException: handle.close(); raise
            leases.append(handle)
        streams_closed(); result['prior_runtime_owners'] = closed_runtime_owners(Path(request['data_root']))
        if (out/'RESTART_INTENT.json').exists(): raise RuntimeError('This exact fault already has a consumed intent; no retry')
        pins = snapshot(out); check_pins(pins)
        resource.setrlimit(resource.RLIMIT_FSIZE, (65536, 65536))
        def command(name, arguments=()):
            if (name, arguments) not in (('VERSION', ()), ('BLD_MSG', ()), ('AEC_MIC_ARRAY_TYPE', ()), ('TEST_CORE_BURN', ('0',))) or len(commands) >= 7:
                raise ValueError('Exact seven-command recovery ceiling required')
            if time.monotonic()+4 >= request['expires_monotonic']: raise TimeoutError('Recovery deadline expired')
            streams_closed(); check_pins(pins)
            if shutil.disk_usage(out).free < request['reserve_bytes']: raise OSError('Recovery storage floor crossed')
            memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line)
            if int(memory['MemAvailable'].split()[0])*1024 < 192*1024**2: raise MemoryError('Recovery192MiB stop floor')
            index = len(commands)+1; paths = [out/('COMMAND_%02d.%s' % (index, suffix)) for suffix in ('stdout', 'stderr')]
            read_gate, write_gate = os.pipe(); child = None; tool_owner = None; timed_out = False
            try:
                with paths[0].open('xb') as stdout, paths[1].open('xb') as stderr:
                    child = subprocess.Popen([sys.executable, '-B', __file__, '--control', str(read_gate), name, *arguments],
                        stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, pass_fds=(read_gate,))
                    os.close(read_gate); read_gate = None
                    tool_owner = identity(child.pid)
                    put(out/('COMMAND_%02d_OWNER.json' % index), tool_owner)
                    os.write(write_gate, b'1'); os.close(write_gate); write_gate = None
                    try: child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        if identity(child.pid) != tool_owner: raise RuntimeError('Control process identity changed before cleanup')
                        child.kill(); child.wait(timeout=2)
                    stdout.flush(); stderr.flush(); os.fsync(stdout.fileno()); os.fsync(stderr.fileno())
            finally:
                if read_gate is not None: os.close(read_gate)
                if write_gate is not None: os.close(write_gate)
                if child is not None and child.poll() is None: child.kill(); child.wait(timeout=2)
            blobs = [bounded(path) for path in paths]
            row = dict(command=name, arguments=list(arguments), owner=tool_owner, exit_code=child.returncode,
                timeout=timed_out, directly_reaped=True, exact_owner_gone=owner_closed(tool_owner),
                stdout=blobs[0].decode('utf-8', 'replace') if len(blobs[0]) <= 4096 else '',
                stderr=blobs[1].decode('utf-8', 'replace') if len(blobs[1]) <= 4096 else '',
                output_files=[dict(path=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) for path, raw in zip(paths, blobs)])
            commands.append(row); put(out/('COMMAND_%02d.json' % index), row)
            if not row['exact_owner_gone'] or any(len(raw) > 4096 for raw in blobs): raise RuntimeError('Control output/closure invalid; no retry')
            return row
        result.update(module.recovery_sequence(command, lambda name, value: put(out/name, value), time.sleep, request['fault_sha256']))
        streams_closed(); check_pins(pins)
        result['readiness_verified'] = result['status'] == 'NO_SEND_CURRENT_AEC_READABLE' or result.get('post_aec_readable') is True
        if not result['readiness_verified']: raise RuntimeError('AEC remains unreadable after the one maintenance send')
        result['files_unchanged'] = True
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc)[:2048])
    finally:
        for handle in reversed(leases): fcntl.flock(handle, fcntl.LOCK_UN); handle.close()
        result['leases_released'] = True; result['commands'] = commands
        result['maintenance_sends_attempted'] = int((out/'RESTART_INTENT.json').exists())
        result['maintenance_sends'] = sum(row['command'] == 'TEST_CORE_BURN' for row in commands)
        put(out/'RECOVERY.json', result); signal.alarm(0)
    return 0 if result.get('readiness_verified') and not result.get('error') else 1


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == '--control':
        gate = int(sys.argv[2]); name = sys.argv[3]; arguments = tuple(sys.argv[4:])
        if (name, arguments) not in (('VERSION', ()), ('BLD_MSG', ()), ('AEC_MIC_ARRAY_TYPE', ()), ('TEST_CORE_BURN', ('0',))):
            raise ValueError('Only the retained bounded control commands are permitted')
        if os.read(gate, 1) != b'1': raise RuntimeError('Control identity acknowledgment missing')
        os.close(gate); os.execv(TOOL, [TOOL, '-u', 'i2c', name, *arguments])
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True); parser.add_argument('--gate', type=int, required=True)
    args = parser.parse_args(); sys.exit(native_main(Path(args.output), args.gate))
