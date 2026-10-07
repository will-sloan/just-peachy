"""Guarded fresh staging and separate desktop activation. See README_PACKAGE.md."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import tarfile
import time
import uuid

TARGET = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29'
MAX_PACKAGE = 16*1024**2
MAX_ARCHIVE = 2*1024**2


def allowed_target(value):
    return bool(re.fullmatch(re.escape(TARGET)+r'(?:-build-[0-9]+)?', str(value)))


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


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


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or path.as_posix() != name:
        raise ValueError('Unsafe package path')
    return path.parts


def real_parent(path):
    if path.is_symlink() or path.parent.resolve(strict=True) != path.parent:
        raise ValueError('Destination requires a real existing canonical parent')


def write(path, raw, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.chmod(path, mode)
    if path.read_bytes() != raw:
        raise OSError('Package/backup readback failed')


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def check_native():
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise RuntimeError('Native stage/activation requires CM5 Linux; never run on the PC')


def validate_payload(raw, expected_archive_sha256, expected_manifest_sha256):
    if len(raw) > MAX_ARCHIVE or sha(raw) != expected_archive_sha256:
        raise ValueError('Bounded exact package archive required')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        for member in archive:
            safe_name(member.name)
            if not member.isfile() or member.name in files or member.size > 2*1024**2 or len(files) >= 512:
                raise ValueError('Only unique bounded regular files may be staged')
            files[member.name] = archive.extractfile(member).read()
            if sum(map(len, files.values())) > MAX_PACKAGE:
                raise ValueError('Expanded package exceeds declared bound')
    manifest_raw = files.pop('PACKAGE_MANIFEST.json')
    if sha(manifest_raw) != expected_manifest_sha256:
        raise ValueError('Package manifest SHA mismatch')
    manifest = strict(manifest_raw)
    if manifest.get('schema') != 'just-peachy.v29.package.v1' or not allowed_target(manifest.get('target')):
        raise ValueError('Wrong candidate target/schema')
    rows = manifest['files']
    if len(rows) != len(files) or {row['path'] for row in rows} != set(files):
        raise ValueError('Complete exact package inventory required')
    for row in rows:
        safe_name(row['path'])
        raw = files[row['path']]
        if row['bytes'] != len(raw) or row['sha256'] != sha(raw):
            raise ValueError('Package member SHA mismatch: ' + row['path'])
    files['PACKAGE_MANIFEST.json'] = manifest_raw
    return manifest, files


def verify_tree(root, expected_manifest_sha256):
    raw = (root/'PACKAGE_MANIFEST.json').read_bytes()
    if sha(raw) != expected_manifest_sha256:
        raise ValueError('Staged manifest changed')
    manifest = strict(raw)
    expected = {row['path']: row for row in manifest['files']}
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in staged candidate')
        if path.is_file():
            name = path.relative_to(root).as_posix()
            actual.add(name)
            if name == 'PACKAGE_MANIFEST.json':
                continue
            row = expected.get(name)
            if row is None or path.stat().st_size != row['bytes'] or sha(path.read_bytes()) != row['sha256']:
                raise ValueError('Staged candidate changed: ' + name)
    if actual != set(expected) | {'PACKAGE_MANIFEST.json'}:
        raise ValueError('Staged inventory differs')
    return manifest


def stage_archive(archive_base64, archive_sha256, manifest_sha256, target=None):
    """Pure entry for the separately guarded native inspector; no launch/desktop write."""
    check_native()
    if len(archive_base64) > (MAX_ARCHIVE*4//3+4):
        raise ValueError('Encoded package exceeds declared bound')
    manifest, files = validate_payload(base64.b64decode(archive_base64, validate=True), archive_sha256, manifest_sha256)
    root = Path(manifest['target'])
    if target is not None and str(root) != str(target):
        raise ValueError('Explicit target differs from exact manifest')
    real_parent(root)
    if root.exists():
        raise FileExistsError('Never overwrite an existing candidate; inspect it explicitly')
    if shutil.disk_usage(root.parent).free < 5*1024**3 + sum(map(len, files.values())):
        raise OSError('Candidate staging requires the existing 5 GiB disk floor')
    temporary = root.with_name('.field-runtime-v29-stage-'+uuid.uuid4().hex)
    temporary.mkdir(mode=0o700, exist_ok=False)
    # Interrupted/failed staging is retained for inspection; never broad-delete.
    for name, raw in sorted(files.items()):
        write(temporary.joinpath(*safe_name(name)), raw)
    verify_tree(temporary, manifest_sha256)
    if root.exists():
        raise FileExistsError('Candidate appeared during staging')
    os.rename(temporary, root)
    fsync_dir(root.parent)
    verify_tree(root, manifest_sha256)
    return dict(status='STAGED_ONLY', target=str(root), manifest_sha256=manifest_sha256,
        files=len(files), native_launch_enabled=manifest['native_launch_enabled'],
        models_copied=False, galleries_copied=False, desktop_changed=False, process_started=False)


def activate(root, manifest_sha256, desktop, previous_sha256, baseline, baseline_sha256):
    check_native()
    root, desktop, baseline = Path(root), Path(desktop), Path(baseline)
    if not allowed_target(root):
        raise ValueError('Wrong native candidate root')
    verify_tree(root, manifest_sha256)
    binding = strict((root/'BINDING.json').read_bytes())
    if binding.get('native_launch_enabled') is not True or binding.get('authorization_kind')!='production':
        raise ValueError('Desktop activation requires separate explicit production acceptance')
    acceptance_raw=(root/'PRODUCTION_ACCEPTANCE.json').read_bytes()
    if sha(acceptance_raw)!=binding.get('production_acceptance_sha256'):
        raise ValueError('Production acceptance pin changed')
    # Exact package bytes were verified above; this module has no native imports.
    import importlib.util
    spec=importlib.util.spec_from_file_location('checked_release_authorization',root/'release_authorization.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    acceptance=module.validate_acceptance(strict(acceptance_raw),binding)
    if acceptance['previous_desktop_sha256']!=previous_sha256 or sha(baseline.read_bytes())!=baseline_sha256:
        raise ValueError('Accepted previous launcher or current activation baseline differs')
    full_backup=acceptance['full_backup']
    backup_manifest=(root/'PRODUCTION_BACKUP_MANIFEST.json').read_bytes()
    backup_complete=(root/'PRODUCTION_BACKUP_COMPLETE.json').read_bytes()
    completion=strict(backup_complete)
    if (sha(backup_manifest)!=full_backup['manifest_sha256'] or sha(backup_complete)!=full_backup['completion_sha256']
        or completion.get('kind')!='COMPLETE' or not completion.get('closure',{}).get('closed')
        or not completion.get('closure',{}).get('exact_owner_gone') or not completion.get('closure',{}).get('cgroup_empty')
        or completion.get('manifest_sha256')!=sha(encoded(strict(backup_manifest)))):
        raise ValueError('Accepted full backup completion proof changed')
    if shutil.disk_usage(root.parent).free<5*1024**3+131072:
        raise OSError('Activation must preserve the existing 5 GiB disk floor')
    if desktop.parent != Path.home()/'Desktop' or desktop.suffix != '.desktop':
        raise ValueError('One explicit Desktop launcher only')
    real_parent(desktop)
    if not desktop.is_file() or desktop.is_symlink():
        raise ValueError('Existing regular desktop launcher required for an exact backup')
    old = desktop.read_bytes()
    if len(old) > 65536 or sha(old) != previous_sha256:
        raise ValueError('Prior desktop launcher changed')
    backup = root.parent/('field-runtime-v29-desktop-backup-'+uuid.uuid4().hex)
    backup.mkdir(mode=0o700)
    write(backup/(desktop.name+'.backup'), old, desktop.stat().st_mode & 0o777)
    write(backup/(desktop.name+'.restore'), old, desktop.stat().st_mode & 0o777)
    command = (binding['python']+' -B '+str(root/'native_scope.py')+' --binding '+str(root/'BINDING.json')+
               ' --manifest-sha256 '+manifest_sha256+
               ' --data-root '+str(Path.home()/'JustPeachy/data/runtime-v29'))
    if any(character in command for character in ('\n','\r','"','%','\\')) or ' ' in str(root):
        raise ValueError('Unexpected desktop command path characters')
    new = ('[Desktop Entry]\nType=Application\nName=Just Peachy\nComment=Runtime v29 candidate\nExec='+command+
           '\nTerminal=false\nCategories=AudioVideo;\nStartupNotify=false\n').encode()
    write(backup/'ACTIVATION_PLAN.json', encoded(dict(desktop=str(desktop), previous_sha256=previous_sha256,
        next_sha256=sha(new), manifest_sha256=manifest_sha256, baseline_sha256=baseline_sha256,
        backup=str(backup), autostart=False, process_started=False)))
    staged = desktop.with_name('.'+desktop.name+'.'+uuid.uuid4().hex)
    write(staged, new, 0o755)
    if sha(desktop.read_bytes()) != previous_sha256:
        raise ValueError('Prior desktop launcher changed before atomic activation')
    os.replace(staged, desktop); fsync_dir(desktop.parent)
    if desktop.read_bytes() != new:
        raise OSError('Activated desktop launcher readback failed; exact backup retained')
    return dict(status='DESKTOP_ACTIVATED_NOT_STARTED', desktop=str(desktop), backup=str(backup),
                previous_sha256=previous_sha256, current_sha256=sha(new), autostart=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='action', required=True)
    stage = sub.add_parser('stage')
    stage.add_argument('--archive', type=Path, required=True)
    stage.add_argument('--archive-sha256', required=True)
    stage.add_argument('--manifest-sha256', required=True)
    activation = sub.add_parser('activate')
    activation.add_argument('--target', default=TARGET)
    activation.add_argument('--manifest-sha256', required=True)
    activation.add_argument('--desktop', required=True)
    activation.add_argument('--previous-sha256', required=True)
    activation.add_argument('--baseline', required=True)
    activation.add_argument('--baseline-sha256', required=True)
    args = ap.parse_args()
    check_native()
    # Standalone CLI also registers before package/baseline reads. The guarded
    # inspector calls stage_archive directly under its own existing early owner.
    import resource
    import signal
    os.sched_setaffinity(0, {3})
    resource.setrlimit(resource.RLIMIT_AS, (128*1024**2, 128*1024**2))
    resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32*1024**2, 32*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0,0))
    signal.alarm(55)
    owner_dir = Path(TARGET).parent/('v29-installer-'+uuid.uuid4().hex)
    owner_dir.mkdir(mode=0o700)
    write(owner_dir/'REGISTERED_OWNER.json', encoded(dict(pid=os.getpid(),
        start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), cpu=3)))
    if args.action == 'stage':
        if args.archive.stat().st_size > MAX_ARCHIVE:
            raise ValueError('Bounded archive required')
        result = stage_archive(base64.b64encode(args.archive.read_bytes()).decode(), args.archive_sha256, args.manifest_sha256)
    else:
        result = activate(args.target, args.manifest_sha256, args.desktop, args.previous_sha256,
                          args.baseline, args.baseline_sha256)
    print(encoded(result).decode())


if __name__ == '__main__':
    main()
