"""Injected headless companion; README_QUALIFICATION_DISPATCH.md."""
import hashlib
import json
from pathlib import Path


def dispatch(payload, baseline):
    # The one helper is verified against the explicit package manifest before
    # loading it; that helper then verifies every package member before launch.
    package = Path(payload['package'])
    manifest_path = package/'PACKAGE_MANIFEST.json'
    raw = manifest_path.read_bytes()
    if len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=payload['package_manifest_sha256']:
        raise ValueError('Explicit package manifest changed')
    manifest=json.loads(raw)
    row=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
    path=package/row['path'];source=path.read_bytes()
    if path.is_symlink() or path.resolve(strict=True)!=path or len(source)>131072 or len(source)!=row['bytes'] or hashlib.sha256(source).hexdigest()!=row['sha256']:
        raise ValueError('Pinned qualification helper differs')
    namespace=dict(__name__='verified_qualification_dispatch',__file__=str(path))
    exec(compile(source,str(path),'exec'),namespace)
    return namespace['launch'](payload,baseline,kind='pipeline')


if 'PAYLOAD' in globals():
    RESULT=dispatch(PAYLOAD,BASELINE)
