"""Pinned external common helper for immutable08 backup. README_BACKUP_EXTERNAL.md."""
import base64
import hashlib
import json
import os
from pathlib import Path

COMMON_SHA256='103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8'
COMMON_BYTES=20362
SCHEMA='just-peachy.external-backup-common.v1'


def external_bytes(payload):
    value=payload.get('external_backup_common',{})
    if (value.get('schema')!=SCHEMA or value.get('sha256')!=COMMON_SHA256 or
        value.get('bytes')!=COMMON_BYTES or type(value.get('base64')) is not str or len(value['base64'])>32768):
        raise ValueError('Exact reviewed external common source required')
    raw=base64.b64decode(value['base64'],validate=True)
    if len(raw)!=COMMON_BYTES or hashlib.sha256(raw).hexdigest()!=COMMON_SHA256:
        raise ValueError('External common byte/hash pin differs')
    compile(raw,'<pinned-external-backup-common>','exec')
    return raw


def wrapper_overlay(source):
    anchor=' sys.path.insert(0,str(package))\n'
    if source.count(anchor)!=1:raise ValueError('Exact08 shared wrapper import boundary required')
    addition=""" sys.path.insert(0,str(package))
 overlay=out/'backup_reconciliation.py'
 if overlay.is_symlink() or overlay.resolve(strict=True)!=overlay or overlay.stat().st_size!=20362 or hashlib.sha256(overlay.read_bytes()).hexdigest()!='103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8':raise ValueError('Exact external backup common changed')
 spec=importlib.util.spec_from_file_location('backup_reconciliation',overlay)
 common=importlib.util.module_from_spec(spec);sys.modules['backup_reconciliation']=common;spec.loader.exec_module(common)
"""
    result=source.replace(anchor,addition);compile(result,'<owned-external-backup-wrapper>','exec')
    return result


def dispatch(payload,baseline):
    common_raw=external_bytes(payload);package=Path(payload['package'])
    manifest_raw=(package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(manifest_raw)>262144 or hashlib.sha256(manifest_raw).hexdigest()!=payload['package_manifest_sha256']:
        raise ValueError('Exact immutable package manifest required')
    manifest=json.loads(manifest_raw)
    row=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
    path=package/row['path'];source=path.read_bytes()
    if path.resolve(strict=True)!=path or len(source)!=row['bytes'] or hashlib.sha256(source).hexdigest()!=row['sha256']:
        raise ValueError('Pinned shared backup dispatch helper differs')
    helper=dict(__name__='verified_external_backup_dispatch',__file__=str(path))
    exec(compile(source,str(path),'exec'),helper)
    ordinary_wrapper=helper['wrapper_source'];ordinary_put=helper['put']
    helper['wrapper_source']=lambda settings:wrapper_overlay(ordinary_wrapper(settings))
    def put(path,value):
        if path.name=='JOB.json':
            value.update(external_backup_common_sha256=COMMON_SHA256,external_backup_schema=SCHEMA)
        ordinary_put(path,value)
        if path.name=='BACKUP_SCOPE.json':
            for name in ('backup_reconciliation.py','EXTERNAL_COMMON.py.backup','EXTERNAL_COMMON.py.restore'):
                target=path.parent/name
                with target.open('xb') as stream:
                    if stream.write(common_raw)!=len(common_raw):raise OSError('Short independent external helper copy')
                    stream.flush();os.fsync(stream.fileno())
                if target.read_bytes()!=common_raw:raise OSError('External common independent readback differs')
            ordinary_put(path.parent/'EXTERNAL_COMMON.json',dict(schema=SCHEMA,bytes=COMMON_BYTES,sha256=COMMON_SHA256,
                package_unmodified=True,backup_scope_extension='exact observed current rc5 release'))
    helper['put']=put
    return helper['launch'](payload,baseline,kind='backup')


if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)
