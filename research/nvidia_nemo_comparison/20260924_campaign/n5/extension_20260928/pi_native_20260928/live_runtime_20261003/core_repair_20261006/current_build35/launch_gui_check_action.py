"""Injected full native GUI workflow; README_NATIVE_GUI_DRIVER.md."""
import hashlib
import json
from pathlib import Path


def dispatch(payload,baseline):
    package=Path(payload['package']);raw=(package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=payload['package_manifest_sha256']:
        raise ValueError('Exact bounded GUI package manifest required')
    row=next(row for row in json.loads(raw)['files'] if row['path']=='launch_raw_qualification_action.py')
    path=package/row['path'];source=path.read_bytes()
    if path.is_symlink() or path.resolve(strict=True)!=path or len(source)>131072 or len(source)!=row['bytes'] or hashlib.sha256(source).hexdigest()!=row['sha256']:
        raise ValueError('Pinned GUI dispatch helper differs')
    namespace=dict(__name__='verified_gui_dispatch',__file__=str(path))
    exec(compile(source,str(path),'exec'),namespace)
    return namespace['launch'](payload,baseline,kind='gui')


if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)
