"""Guarded production desktop activation; README_GUARDED_ACTIVATION.md."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import time

BASE = Path('/home/peachyprototype/JustPeachy')
CAMPAIGN = BASE/'research/nemotron-20260928'
MIB = 1024**2
IMPORTS = ('profiles', 'optional_refiner_admission', 'release_authorization', 'optional_refiner_dispatch')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: raise ValueError('Duplicate activation field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def sha(raw): return hashlib.sha256(raw).hexdigest()


def read(path, maximum=262144):
    path = Path(path); before = path.lstat()
    if (path.resolve(strict=True) != path or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1 or before.st_size > maximum):
        raise ValueError('Canonical bounded single-link activation input required')
    with path.open('rb') as stream: raw = stream.read(maximum+1)
    after = path.stat()
    stable = lambda row: (row.st_dev,row.st_ino,row.st_size,row.st_mtime_ns,row.st_ctime_ns,row.st_mode,row.st_nlink)
    if len(raw) > maximum or stable(after) != stable(before):
        raise ValueError('Activation input changed while reading')
    return raw


def write(path, raw):
    if len(raw) > 2*MIB: raise ValueError('Activation metadata file cap')
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw): raise OSError('Short activation evidence write')
        stream.flush(); os.fsync(stream.fileno())
    if read(path, 2*MIB) != raw: raise OSError('Activation evidence readback differs')
    if os.name != 'nt':
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)


def inventory(package, expected_sha):
    raw = read(package/'PACKAGE_MANIFEST.json')
    if sha(raw) != expected_sha: raise ValueError('Exact production manifest required')
    manifest = strict(raw); rows = manifest.get('files')
    if (manifest.get('schema') != 'just-peachy.v29.package.v1' or manifest.get('target') != str(package)
            or not isinstance(rows, list) or not 1 <= len(rows) <= 512):
        raise ValueError('Exact bounded production inventory required')
    expected = {'PACKAGE_MANIFEST.json'}; total = 0
    for row in rows:
        name = row['path']; relative = PurePosixPath(name)
        if (not name or relative.is_absolute() or relative.as_posix() != name
                or '..' in relative.parts or '\\' in name or name in expected
                or type(row['bytes']) is not int or not 0 <= row['bytes'] <= 2*MIB):
            raise ValueError('Unsafe production inventory member')
        expected.add(name); total += row['bytes']
        if total > 16*MIB: raise ValueError('Production package allocation exceeded')
        value = read(package.joinpath(*relative.parts), 2*MIB)
        if len(value) != row['bytes'] or sha(value) != row['sha256']:
            raise ValueError('Production inventory hash changed')
    actual = set(); count = 0
    for directory, children, files in os.walk(package, followlinks=False):
        count += 1 + len(children) + len(files)
        if count > 2048: raise ValueError('Production tree membership bound')
        for name in children + files:
            if (Path(directory)/name).is_symlink(): raise ValueError('Production tree symlink')
        actual.update((Path(directory)/name).relative_to(package).as_posix() for name in files)
    if actual != expected: raise ValueError('Production file membership changed')
    return manifest


def module_bytes(package, manifest, name):
    rows = [row for row in manifest['files'] if row['path'] == name+'.py']
    if len(rows) != 1: raise ValueError('Unique pinned import required: '+name)
    raw = read(package/(name+'.py'), 131072); row = rows[0]
    if (len(raw), sha(raw)) != (row['bytes'], row['sha256']):
        raise ValueError('Pinned import changed: '+name)
    return raw


class VerifiedImports:
    """Canonical package imports with previous module/path state restored."""
    def __init__(self, package, manifest):
        self.package = package; self.manifest = manifest; self.prior = {}; self.paths = None
        self.origins = {}

    def __enter__(self):
        self.paths = list(sys.path)
        try:
            for name in IMPORTS:
                old = sys.modules.get(name)
                if old is not None and Path(getattr(old, '__file__', '')).resolve() != self.package/(name+'.py'):
                    raise ValueError('Existing project import has a different origin: '+name)
                self.prior[name] = old
            sys.path.insert(0, str(self.package))
            for name in IMPORTS:
                raw = module_bytes(self.package, self.manifest, name)
                path = self.package/(name+'.py')
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec); sys.modules[name] = module
                exec(compile(raw, str(path), 'exec'), module.__dict__)
                if Path(module.__file__).resolve(strict=True) != path:
                    raise ValueError('Loaded import origin changed: '+name)
                self.origins[name] = dict(path=str(path), bytes=len(raw), sha256=sha(raw))
            return self
        except BaseException:
            self.__exit__(None, None, None); raise

    def __exit__(self, *args):
        if self.paths is not None: sys.path[:] = self.paths
        for name, old in self.prior.items():
            if old is None: sys.modules.pop(name, None)
            else: sys.modules[name] = old


def production_evidence(package, manifest, payload):
    binding = strict(read(package/'BINDING.json'))
    acceptance_raw = read(package/'PRODUCTION_ACCEPTANCE.json')
    if (binding.get('target') != str(package) or binding.get('authorization_kind') != 'production'
            or binding.get('native_launch_enabled') is not True
            or sha(acceptance_raw) != binding.get('production_acceptance_sha256')
            or sha(acceptance_raw) != payload['production_acceptance_sha256']):
        raise ValueError('Explicit pinned production acceptance required')
    acceptance = sys.modules['release_authorization'].validate_acceptance(strict(acceptance_raw), binding)
    backup = acceptance['full_backup']; rows_raw = read(package/'PRODUCTION_BACKUP_MANIFEST.json', 2*MIB)
    complete_raw = read(package/'PRODUCTION_BACKUP_COMPLETE.json', 2*MIB)
    if (sha(rows_raw) != backup['manifest_sha256'] or sha(complete_raw) != backup['completion_sha256']
            or sha(rows_raw) != payload['backup_manifest_sha256']
            or sha(complete_raw) != payload['backup_completion_sha256']):
        raise ValueError('Accepted current-release backup pins differ')
    rows = strict(rows_raw); completion = strict(complete_raw)
    if (not isinstance(rows, list) or not 1 <= len(rows) <= 4096 or completion.get('kind') != 'COMPLETE'
            or completion.get('manifest_sha256') != sha(encoded(rows))
            or completion.get('files') != len(rows)
            or not all(completion.get('closure', {}).get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty'))):
        raise ValueError('Exact complete closed-source backup required')
    selected = [row for row in rows if row.get('source') == payload['desktop']]
    if (len(selected) != 1 or selected[0]['sha256'] != payload['previous_desktop_sha256']
            or acceptance['previous_desktop_sha256'] != payload['previous_desktop_sha256']):
        raise ValueError('Selected previous launcher must belong to accepted full backup')
    return binding, acceptance, selected[0]


def readback_payload(outer):
    """Recover the exact small native files from the already closed host result."""
    result = outer['action_result']; fields = result['baseline_fields']
    if (outer.get('utility_pid_absent_after_ssh') is not True or result.get('status') != 'DESKTOP_ACTIVATED_NOT_STARTED'
            or result['inspector_reference'] != outer['utility_owner'] or not isinstance(fields,list)
            or len(fields) > 128 or len(set(fields)) != len(fields)
            or any(name not in outer or name in ('action_result','native_writes') for name in fields)):
        raise ValueError('Complete exact closed inspector result required')
    baseline = encoded({name:outer[name] for name in fields})
    if (len(baseline),sha(baseline)) != (result['baseline_bytes'],result['baseline_sha256']):
        raise ValueError('Fresh baseline transport differs')
    root = PurePosixPath(result['evidence_root']); backup = PurePosixPath(result['backup'])
    desktop = PurePosixPath(result['desktop'])
    campaign = PurePosixPath(CAMPAIGN.as_posix())
    if (root.parent != campaign or backup.parent != campaign or desktop.parent != PurePosixPath('/home/peachyprototype/Desktop')
            or desktop.suffix != '.desktop'
            or re.fullmatch(r'field-runtime-v29-activation-[0-9a-f]{32}',root.name) is None
            or re.fullmatch(r'field-runtime-v29-desktop-backup-[0-9a-f]{32}',backup.name) is None):
        raise ValueError('Exact activation artifact roots required')
    files = {str(root/'BASELINE.json'):baseline,str(root/'BASELINE.restore.json'):baseline}
    rows = result['readback_files']
    expected={str(backup/(desktop.name+suffix)) for suffix in ('.backup','.restore')}
    expected.update((str(backup/'ACTIVATION_PLAN.json'),str(desktop)))
    expected.update(str(root/name) for name in ('INSPECTOR_REFERENCE.json','IMPORTS.json','ACTIVATION_INTENT.json'))
    if not isinstance(rows,list) or len(rows)!=7 or {row['path'] for row in rows}!=expected:
        raise ValueError('Complete exact activation readback membership required')
    for row in rows:
        path = PurePosixPath(row['path'])
        if (path.as_posix()!=row['path'] or '..' in path.parts or '\\' in row['path']
                or row['path'] in files or path.parent not in (root,backup)
                and row['path'] != result['desktop']): raise ValueError('Unexpected activation artifact path')
        raw = base64.b64decode(row['base64'],validate=True)
        if len(raw)>65536 or (len(raw),sha(raw))!=(row['bytes'],row['sha256']):
            raise ValueError('Independent activation artifact pin differs')
        files[row['path']] = raw
    native_result = dict(result); pin = native_result.pop('activation_result_record')
    raw = encoded(native_result)
    if (len(raw),sha(raw)) != (pin['bytes'],pin['sha256']): raise ValueError('Activation result readback pin differs')
    files[str(root/'ACTIVATION_RESULT.json')] = raw
    if sum(map(len,files.values())) > 16*MIB: raise ValueError('Activation metadata total exceeded')
    return files


def host_readback_main():
    import psutil
    me=psutil.Process();me.cpu_affinity([14])
    import argparse
    ap=argparse.ArgumentParser(description='Read back a completely closed guarded activation; no SSH')
    ap.add_argument('--operation',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    output=args.output.absolute();operation=args.operation.absolute()
    if (output.parent!=private or output.parent.resolve(strict=True)!=output.parent
            or re.fullmatch(r'desktop-activation-[0-9]{2}-readback-[0-9]{2}',output.name) is None):
        raise ValueError('Fresh private activation readback output required')
    output.mkdir()
    write(output/'REGISTERED_OWNER.json',encoded(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    if (operation.parent!=private or operation.resolve(strict=True)!=operation
            or re.fullmatch(r'operation-desktop-activation-[0-9]{2}',operation.name) is None):
        raise ValueError('Exact guarded activation operation required')
    for drive,gib in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<gib*1024**3+16*MIB:raise OSError('Host activation readback reserve unavailable')
    own=read(Path(__file__).resolve(strict=True),131072)
    if read(operation/'ACTION.py.backup',131072)!=own or read(operation/'ACTION.py.restore',131072)!=own:
        raise ValueError('Exact executed action and independent restore required')
    raw=read(operation/'dispatch/RESULT.json');outer=strict(raw)
    closure=strict(read(operation/'dispatch/NATIVE_CLOSURE.json',16384))
    owner=strict(read(operation/'dispatch/NATIVE_OWNER.json',16384))
    if (closure.get('owner')!=owner or owner!=outer['utility_owner'] or closure.get('exact_pid_absent') is not True
            or closure.get('natural_returncode')!=0):raise ValueError('Actual natural inspector closure required')
    files=readback_payload(outer);manifest=[]
    for source,value in files.items():
        target=output/'native'/Path(*PurePosixPath(source).parts[1:]);target.parent.mkdir(parents=True,exist_ok=True)
        write(target,value);manifest.append(dict(source=source,path=target.relative_to(output).as_posix(),bytes=len(value),sha256=sha(value)))
    write(output/'RESULT.json.backup',raw);write(output/'RESULT.json.restore',raw)
    write(output/'VERIFY.json',encoded(dict(status='COMPLETE_ACTIVATION_METADATA_READBACK',files=manifest,
        native_inspector=owner,closure=closure,source_result_sha256=sha(raw),native_actions=False)))
    print(json.dumps(dict(status='COMPLETE_ACTIVATION_METADATA_READBACK',files=len(files),output=str(output))))


def dispatch(payload, baseline):
    import fcntl
    import resource
    owner = dict(pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    if (baseline.get('utility_owner') != owner or baseline.get('boot_id') != owner['boot_id']
            or payload['boot_id'] != owner['boot_id'] or not time.time() < payload['expires_unix'] <= time.time()+600
            or any(baseline.get(key) for key in ('current_project_processes','active_recorded_owners','live_manager_owners','held_research_leases'))):
        raise ValueError('Actual current inspector identity and fresh closed baseline required')
    if (payload.get('maximum_output_bytes') != 16*MIB
            or resource.getrlimit(resource.RLIMIT_FSIZE) != (32*MIB,32*MIB)):
        raise ValueError('Existing 16 MiB metadata and exact 32 MiB inspector file limits required')
    package = Path(payload['package']); desktop = Path(payload['desktop']); evidence = Path(payload['evidence_root'])
    if (package.parent != CAMPAIGN or re.fullmatch(r'field-runtime-v29-build-[0-9]{2}',package.name) is None
            or desktop.parent != Path('/home/peachyprototype/Desktop') or desktop.suffix != '.desktop'
            or evidence.parent != CAMPAIGN or re.fullmatch(r'field-runtime-v29-activation-[0-9a-f]{32}',evidence.name) is None):
        raise ValueError('Exact candidate, existing desktop, and fresh owned evidence paths required')
    for path in (package, desktop, evidence.parent):
        if path.resolve(strict=True) != path: raise ValueError('Canonical activation paths required')
    if evidence.exists() or evidence.is_symlink(): raise FileExistsError('Preserve previous activation evidence')
    if shutil.disk_usage(CAMPAIGN).free < 5*1024**3 + 16*MIB: raise OSError('Native floor plus independent activation metadata unavailable')
    baseline_raw = encoded(baseline)
    if len(baseline_raw) > 262144: raise ValueError('Fresh baseline metadata cap')
    if len(json.dumps(baseline).encode())+65536>262144:
        raise ValueError('Native inspector stdout must fit baseline plus activation result before mutation')
    manifest = inventory(package, payload['package_manifest_sha256'])
    installer_raw = module_bytes(package, manifest, 'install_candidate')
    installer = dict(__name__='verified_activation_installer', __file__=str(package/'install_candidate.py'))
    exec(compile(installer_raw, installer['__file__'], 'exec'), installer)
    installer['check_native']()
    leases = []
    try:
        for path in (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock', BASE/'data/xvf-hardware.lock'):
            lease=path.open('rb'); fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB); leases.append(lease)
        with VerifiedImports(package, manifest) as imported:
            binding, acceptance, selected = production_evidence(package, manifest, payload)
            prior = read(desktop,65536)
            if (len(prior),sha(prior)) != (selected['identity']['bytes'],payload['previous_desktop_sha256']):
                raise ValueError('Current desktop bytes differ from accepted previous bytes')
            evidence.mkdir(mode=0o700)
            for name in ('BASELINE.json','BASELINE.restore.json'): write(evidence/name,baseline_raw)
            write(evidence/'INSPECTOR_REFERENCE.json',encoded(dict(schema='just-peachy.activation-inspector-reference.v1',
                inspector=owner,baseline_sha256=sha(baseline_raw),new_process=False)))
            write(evidence/'IMPORTS.json',encoded(imported.origins))
            write(evidence/'ACTIVATION_INTENT.json',encoded(dict(payload=payload,baseline_sha256=sha(baseline_raw),
                inspector=owner,capture=False,process_started=False)))
            result = installer['activate'](package,payload['package_manifest_sha256'],desktop,
                payload['previous_desktop_sha256'],evidence/'BASELINE.json',sha(baseline_raw))
            backup = Path(result['backup'])
            if backup.parent != CAMPAIGN or re.fullmatch(r'field-runtime-v29-desktop-backup-[0-9a-f]{32}',backup.name) is None:
                raise ValueError('Unexpected installer backup root')
            copies=[read(backup/(desktop.name+suffix),65536) for suffix in ('.backup','.restore')]
            plan=read(backup/'ACTIVATION_PLAN.json',65536); current=read(desktop,65536)
            if copies != [prior,prior] or sha(current) != result['current_sha256']:
                raise ValueError('Independent desktop restore/current readback failed')
            small = [(backup/(desktop.name+'.backup'),copies[0]),(backup/(desktop.name+'.restore'),copies[1]),
                (backup/'ACTIVATION_PLAN.json',plan),(desktop,current)]
            for name in ('INSPECTOR_REFERENCE.json','IMPORTS.json','ACTIVATION_INTENT.json'):
                small.append((evidence/name,read(evidence/name,65536)))
            result.update(evidence_root=str(evidence),baseline_sha256=sha(baseline_raw),baseline_bytes=len(baseline_raw),
                baseline_transport='canonical exact listed fields from outer RESULT',baseline_fields=sorted(baseline),
                inspector_reference=owner,verified_imports=imported.origins,metadata_maximum_bytes=16*MIB,
                readback_files=[dict(path=str(path),bytes=len(raw),sha256=sha(raw),base64=base64.b64encode(raw).decode()) for path,raw in small],
                process_started=False,capture_started=False)
            if len(encoded(result)) > 32768: raise ValueError('Bounded activation result transport')
            final_raw=encoded(result)
            write(evidence/'ACTIVATION_RESULT.json',final_raw)
            inventory(package,payload['package_manifest_sha256'])
            result['activation_result_record']=dict(bytes=len(final_raw),sha256=sha(final_raw))
            return result
    except BaseException as exc:
        if evidence.is_dir() and not (evidence/'FAILURE.json').exists():
            write(evidence/'FAILURE.json',encoded(dict(error=repr(exc)[:4096],inspector=owner,rollback_automatic=False)))
        raise
    finally:
        for lease in reversed(leases): fcntl.flock(lease,fcntl.LOCK_UN); lease.close()


if 'PAYLOAD' in globals(): RESULT = dispatch(PAYLOAD, BASELINE)
elif __name__=='__main__':host_readback_main()
