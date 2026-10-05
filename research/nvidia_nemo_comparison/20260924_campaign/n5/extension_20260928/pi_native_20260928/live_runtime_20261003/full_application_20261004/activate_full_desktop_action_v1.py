"""Activate one restored portrait launcher; README_CLASSIC_ACTIVATION.md."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat

HOME = Path('/home/peachyprototype')
CAMPAIGN = HOME/'JustPeachy/research/nemotron-20260928'
DATA = HOME/'JustPeachy/data/runtime-v29'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read(path, maximum=262144):
    path = Path(path); before = path.lstat()
    if (path.is_symlink() or path.resolve(strict=True) != path or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1 or before.st_size > maximum):
        raise ValueError('Canonical bounded single-link input required: '+str(path))
    raw = path.read_bytes(); after = path.lstat()
    fields = lambda row: (row.st_dev,row.st_ino,row.st_size,row.st_mtime_ns,row.st_ctime_ns)
    if fields(before) != fields(after) or len(raw) != before.st_size:
        raise RuntimeError('Activation input changed during read')
    return raw


def write(path, raw, mode=0o600):
    if len(raw) > 262144: raise ValueError('Activation metadata bound')
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw): raise OSError('Short activation write')
        stream.flush(); os.fsync(stream.fileno())
    os.chmod(path, mode)
    if read(path) != raw: raise OSError('Activation backup/restore readback differs')
    fd = os.open(path.parent, os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def inventory(root, manifest_sha):
    raw = read(root/'PACKAGE_MANIFEST.json')
    if hashlib.sha256(raw).hexdigest() != manifest_sha: raise ValueError('Exact repaired manifest required')
    value = json.loads(raw); expected = {'PACKAGE_MANIFEST.json'}; total = 0
    for row in value['files']:
        name = row['path']; relative = Path(name)
        if (relative.is_absolute() or '..' in relative.parts or '\\' in name or name in expected
                or type(row['bytes']) is not int or not 0 <= row['bytes'] <= 2*1024**2):
            raise ValueError('Exact bounded unique inventory required')
        member = read(root/relative, 2*1024**2); total += len(member); expected.add(name)
        if len(member) != row['bytes'] or hashlib.sha256(member).hexdigest() != row['sha256']:
            raise ValueError('Repaired package member changed: '+name)
    actual = set()
    for index, path in enumerate(root.rglob('*'), 1):
        if index > 2048 or path.is_symlink(): raise ValueError('Bounded real package tree required')
        if path.is_file(): actual.add(path.relative_to(root).as_posix())
    if actual != expected or total > 16*1024**2: raise ValueError('Full repaired membership differs')
    return value


def activate(payload, baseline):
    if baseline['boot_id'] != payload['expected_boot_id']: raise ValueError('Fresh activation boot differs')
    package = Path(payload['package'])
    if (package.parent != CAMPAIGN or re.fullmatch('field-runtime-v29-build-21', package.name) is None
            or payload['data_root'] != str(DATA)):
        raise ValueError('Exact new package and preserved recording store required')
    inventory(package, payload['package_manifest_sha256'])
    binding = json.loads(read(package/'BINDING.json'))
    accepted = read(package/'PRODUCTION_ACCEPTANCE.json')
    if (binding['target'] != str(package) or binding['authorization_kind'] != 'production'
            or binding['native_launch_enabled'] is not True
            or hashlib.sha256(accepted).hexdigest() != binding['production_acceptance_sha256']):
        raise ValueError('Reviewed new content acceptance required')
    proof_raw = read(payload['native_check_path'])
    if hashlib.sha256(proof_raw).hexdigest() != payload['native_check_sha256']:
        raise ValueError('Exact independently copied native check required')
    proof = json.loads(proof_raw)
    if (proof.get('package_manifest_sha256') != payload['package_manifest_sha256']
            or proof.get('boot_id') != baseline['boot_id'] or proof.get('status') != 'PASS'
            or proof.get('actual_portrait_ui') is not True or proof.get('capture_function_passed') is not True
            or proof.get('workers_closed') is not True):
        raise ValueError('Fresh actual portrait/capture/closure proof required before shortcut activation')
    autostart = HOME/'.config/autostart/just-peachy.desktop'
    autostart_raw = read(autostart,16384)
    if (hashlib.sha256(autostart_raw).hexdigest() != payload['autostart_sha256']
            or b'Hidden=true\n' not in autostart_raw or b'X-GNOME-Autostart-enabled=false\n' not in autostart_raw):
        raise ValueError('Existing disabled login startup must be preserved')
    rows = payload['previous_desktop']
    if (len(rows) != 1 or {row['path'] for row in rows} !=
            {str(HOME/'Desktop/Just Peachy.desktop')}):
        raise ValueError('Exactly the observed owned shortcut required')
    previous = {}
    for row in rows:
        path = Path(row['path']); raw = read(path, 16384)
        if hashlib.sha256(raw).hexdigest() != row['sha256']: raise ValueError('Owned shortcut changed')
        previous[path] = raw
    evidence = Path(payload['evidence_root'])
    if evidence.parent != CAMPAIGN or re.fullmatch('field-runtime-v29-classic-activation-[0-9a-f]{32}', evidence.name) is None:
        raise ValueError('Fresh exact activation evidence path required')
    if evidence.exists(): raise FileExistsError('Never reuse a failed activation root')
    if shutil.disk_usage(CAMPAIGN).free < 5*1024**3+16*1024**2:
        raise OSError('Independent activation allocation would cross the disk floor')
    evidence.mkdir(mode=0o700)
    (evidence/'before').mkdir(); (evidence/'restore').mkdir(); (evidence/'archived-shortcuts').mkdir()
    for path, raw in previous.items():
        write(evidence/'before'/path.name, raw)
        write(evidence/'restore'/path.name, raw)
    write(evidence/'before/LOGIN_AUTOSTART.desktop',autostart_raw)
    write(evidence/'restore/LOGIN_AUTOSTART.desktop',autostart_raw)
    # Code/models/calibration/history are not modified. The only active writes
    # below are the one explicitly named owned Desktop entry.
    if any(any(c.isspace() for c in str(p)) for p in (binding['python'], package, DATA)):
        raise ValueError('Exact launcher paths must contain no whitespace')
    raw = ('[Desktop Entry]\nType=Application\nName=Just Peachy\n'
        'Comment=Choose a backend, then open the familiar caption application\n'
        'Exec='+binding['python']+' -B '+str(package/'native_scope.py')+' --binding '+str(package/'BINDING.json')+
        ' --manifest-sha256 '+payload['package_manifest_sha256']+' --data-root '+str(DATA)+'\n'
        'Terminal=false\nIcon=audio-input-microphone\nCategories=AudioVideo;\nStartupNotify=false\n').encode()
    destination = HOME/'Desktop/Just Peachy.desktop'
    pending = destination.with_name('.just-peachy-classic-'+evidence.name[-32:]+'.pending')
    write(pending, raw, 0o755)
    for path, expected in previous.items():
        if read(path, 16384) != expected: raise RuntimeError('Desktop entry changed before atomic activation')
    os.replace(pending, destination)
    fd = os.open(destination.parent, os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    if read(destination,16384) != raw: raise OSError('New chooser shortcut readback failed')
    if read(autostart,16384) != autostart_raw:
        raise RuntimeError('Login startup changed during activation')
    result = dict(status='CLASSIC_SHORTCUT_ACTIVATED', boot_id=baseline['boot_id'],
        package=str(package), package_manifest_sha256=payload['package_manifest_sha256'],
        data_root=str(DATA), desktop=str(destination), desktop_sha256=hashlib.sha256(raw).hexdigest(),
        desktop_base64=base64.b64encode(raw).decode(), evidence_root=str(evidence),
        archived_shortcut=None,
        independent_before_restore_readbacks=True, application_started=False, capture_off=True,
        login_autostart_disabled=True, autostart_sha256=payload['autostart_sha256'],
        rollback_package_preserved=True, recordings_and_galleries_unchanged=True,
        backups=[dict(path=str(path),sha256=hashlib.sha256(old).hexdigest(),base64=base64.b64encode(old).decode())
                 for path,old in previous.items()])
    write(evidence/'ACTIVATION.json', encoded(result))
    return result


if 'PAYLOAD' in globals(): RESULT = activate(PAYLOAD, BASELINE)
