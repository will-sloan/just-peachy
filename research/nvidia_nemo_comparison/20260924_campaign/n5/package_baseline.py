"""Make a private offline baseline bundle from exact existing artifacts. README.md."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
PROTOTYPE = HERE.parents[3] / 'prototype'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main(a):
    if a.output.exists():
        raise ValueError('Fresh archive required')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(a.output.parent).free < 76 * 1024**3:
        raise RuntimeError('One GiB working allowance above 75 GiB reserve required')
    receipt = json.loads((CAMPAIGN/'RELEASE_RECEIPT.json').read_text())
    archive = Path(receipt['archive']['archive'])
    if sha(archive) != receipt['archive']['sha256']:
        raise ValueError('Original N1 release changed')
    files = [('app/'+archive.name, archive)]
    with zipfile.ZipFile(archive) as z:
        assets = json.loads(z.read('config/assets.json'))
    for row in assets:
        p = a.models / row['sha256'] / row['filename']
        if p.stat().st_size != row['bytes'] or sha(p) != row['sha256']:
            raise ValueError('Model bytes differ: ' + row['component_id'])
        files.append(('models/'+row['sha256']+'/'+row['filename'], p))
    wheel_receipt = json.loads(a.wheel_receipt.read_text())
    for row in wheel_receipt['files']:
        p = a.wheelhouse / row['filename']
        if sha(p) != row['sha256']:
            raise ValueError('Wheel bytes differ: ' + p.name)
        files.append(('wheelhouse/'+p.name, p))
    for name in ['release.py', 'runtime_lock.py', 'install_pi.sh', 'deploy_pi.ps1']:
        files.append(('bootstrap/'+name, PROTOTYPE/'release_tools'/name))
    files += [('bootstrap/verify_bundle.py', HERE/'verify_bundle.py'),
              ('install-offline.sh', HERE/'install-offline.sh'),
              ('INSTALL_CM5.md', HERE/'INSTALL_CM5.md'),
              ('ENROLLMENT_COMPATIBILITY.md', HERE/'ENROLLMENT_COMPATIBILITY.md'),
              ('LICENSE_LEDGER.md', HERE/'LICENSE_LEDGER.md')]
    manifest = dict(schema='n5-private-offline-baseline-v1',
                    status='PREPARED_NOT_ARM64_FUNCTIONALLY_TESTED',
                    application_version=receipt['archive']['version'],
                    application_archive='app/'+archive.name, application_sha256=sha(archive),
                    source_commit=receipt['source_commit'], source_tag=receipt['tag'],
                    common_ui_source_sha256=receipt['common_ui_source_sha256'],
                    baseline_only=True, N4_selected=False, CM5_HARDWARE_NOT_TESTED=True,
                    distribution='Private local offline use; do not upload this model-containing archive to Git',
                    files=[dict(path=n, bytes=p.stat().st_size, sha256=sha(p)) for n,p in files])
    # Already-compressed wheels and model payloads: store for bounded CPU use.
    with zipfile.ZipFile(a.output, 'x', compression=zipfile.ZIP_STORED) as z:
        for row, (name,p) in zip(manifest['files'], files):
            data = p.read_bytes()
            if hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('Input changed during packaging')
            z.writestr(name, data)
        z.writestr('BUNDLE_MANIFEST.json', json.dumps(manifest, indent=2)+'\n')
    # Read back every ZIP member against the same manifest before reporting success.
    with zipfile.ZipFile(a.output) as z:
        if set(z.namelist()) != {r['path'] for r in manifest['files']} | {'BUNDLE_MANIFEST.json'}:
            raise ValueError('Archive member inventory differs')
        for row in manifest['files']:
            if hashlib.sha256(z.read(row['path'])).hexdigest() != row['sha256']:
                raise ValueError('Archive read-back mismatch')
    result = dict(status=manifest['status'], archive=str(a.output.resolve()), bytes=a.output.stat().st_size,
                  sha256=sha(a.output), file_count=len(manifest['files'])+1, wheel_count=len(wheel_receipt['files']),
                  model_assets=len(assets), readback='ALL_MEMBER_HASHES_PASS', manifest=manifest)
    a.output.with_suffix('.receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'manifest'}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['models', 'wheelhouse', 'wheel-receipt', 'output']:
        p.add_argument('--'+key, type=Path, required=True)
    main(p.parse_args())
