"""Build a small offline reconnection companion; README_RECONNECT_COMPANION_V1.md."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOCAL = ROOT.parent / 'local' / 'n5'
REMOTE = 'https://github.com/will-sloan/just-peachy.git'
REF = 'refs/heads/codex/n1-foundation-20260924'
SOURCES = (
    'PI_RECONNECT_QUICKSTART_V1.md', 'pi_storage_preflight_v1.py',
    'README_PI_STORAGE_PREFLIGHT_V1.md', 'INSTALL_CM5.md',
    'UPDATE_ROLLBACK.md', 'ARTIFACT_INDEX.json',
    'NATIVE_STREAM_SHORT_FINDINGS_V3.md',
    'realtime_validation_v1/REAL_WORLD_HOLDOUT_V1.md',
)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode('utf-8')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, timeout=45).decode().strip()


def build(output):
    output = output.resolve()
    require(output.is_relative_to(LOCAL.resolve()) and not output.exists(),
            'Use a fresh private N5 directory')
    qualification = json.loads((HERE / 'PI_STORAGE_PREFLIGHT_CHECK_V1.json').read_text())
    for item in qualification['code']:
        data = Path(item['path']).read_bytes()
        require(len(data) == item['bytes'] and sha(data) == item['sha256'],
                'Qualified preflight source changed')
    from pi_storage_preflight_v1 import pin_windows, inspect_bundle, space_plan
    pin_windows()
    require(all(shutil.disk_usage(d + ':/').free > limit * 1024**3 + 1024**2
                for d, limit in [('C', 50), ('G', 75)]), 'Campaign free-space floor')
    require(git('remote', 'get-url', 'origin') == REMOTE and
            git('symbolic-ref', 'HEAD') == REF, 'Wrong campaign remote or branch')
    require(not git('status', '--porcelain'), 'Commit and back up selected sources first')
    head = git('rev-parse', 'HEAD')
    require(git('ls-remote', 'origin', REF).split() == [head, REF], 'Remote HEAD differs')
    files = {}
    for name in SOURCES:
        path = HERE / name
        data = path.read_bytes()
        committed = subprocess.check_output(
            ['git', 'show', head + ':' + path.relative_to(ROOT).as_posix()],
            cwd=ROOT, timeout=45)
        require(data == committed and len(data) < 128 * 1024, 'Unbacked or oversized companion source')
        require(path.name not in files, 'Companion basename collision')
        files[path.name] = data
    index = json.loads(files['ARTIFACT_INDEX.json'])
    artifact = next(a for a in index['artifacts']
                    if a['name'] == 'just-peachy-baseline-cm5-offline-v1.zip')
    inventory = inspect_bundle(Path(artifact['path']), artifact['sha256'])
    require(inventory['archive']['bytes'] == artifact['bytes'] and
            inventory['baseline_only'] and not inventory['N4_selected'], 'Unexpected baseline scope')
    space = space_plan(inventory, overhead_bytes=536870912)
    files['BASELINE_INVENTORY.json'] = encoded(dict(
        inventory=inventory, space=space, target_storage_observed=False,
        archive_included_in_companion=False, installation_performed=False))
    manifest = dict(status='RECONNECTION_COMPANION_ONLY_NOT_TARGET_ACCEPTANCE',
        created_utc=datetime.now(timezone.utc).isoformat(), source_commit=head,
        remote=REMOTE, ref=REF, baseline_archive=artifact,
        files=[dict(path=n, bytes=len(d), sha256=sha(d)) for n, d in sorted(files.items())],
        models_included=False, audio_included=False, Pi_contacted=False,
        N4_accepted=False, N5_complete=False)
    files['COMPANION_MANIFEST.json'] = encoded(manifest)
    require(sum(map(len, files.values())) < 1024**2, 'Companion payload exceeds 1 MiB')
    output.mkdir()
    archive = output / 'just-peachy-pi-reconnect-companion-v1.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
    with zipfile.ZipFile(archive) as z:
        require(set(z.namelist()) == set(files), 'Companion inventory differs')
        for name, data in files.items():
            require(z.read(name) == data, 'Companion readback mismatch')
    result = dict(status=manifest['status'], source_commit=head,
        archive=dict(path=str(archive), bytes=archive.stat().st_size, sha256=sha(archive.read_bytes())),
        files=len(files), readback='ALL_MEMBERS_MATCH', baseline=inventory,
        baseline_member_hashes_verified=inventory['member_hashes_verified'],
        required_available_bytes_with_reserve=space['required_available_bytes_with_reserve'],
        baseline_copied_or_modified=False, Pi_contacted=False, installation_performed=False,
        N4_accepted=False, N5_complete=False)
    (output / 'RESULT.json').write_bytes(encoded(result))
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
