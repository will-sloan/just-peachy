"""Injected full-app one-hour replay action. See README_FULL_APP_SOAK.md."""
import hashlib
import json
from pathlib import Path


def dispatch(payload,baseline):
    if (payload.get('schema')!='just-peachy.full-app-hour-admission.v1' or payload.get('reviewed') is not True
            or not isinstance(payload.get('reviewer'),str) or not 1<=len(payload['reviewer'])<=128):
        raise ValueError('Explicit reviewed full-application hour admission required')
    package=Path(payload['package'])
    raw=(package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=payload['package_manifest_sha256']:
        raise ValueError('Exact frozen package manifest required')
    manifest=json.loads(raw)
    row=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
    path=package/row['path'];source=path.read_bytes()
    if path.is_symlink() or path.resolve(strict=True)!=path or len(source)>131072 or len(source)!=row['bytes'] or hashlib.sha256(source).hexdigest()!=row['sha256']:
        raise ValueError('Pinned shared owned-unit helper changed')
    namespace=dict(__name__='verified_full_app_hour_dispatch',__file__=str(path))
    exec(compile(source,str(path),'exec'),namespace)
    return namespace['launch'](payload,baseline,kind='full_app_hour')


if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)
