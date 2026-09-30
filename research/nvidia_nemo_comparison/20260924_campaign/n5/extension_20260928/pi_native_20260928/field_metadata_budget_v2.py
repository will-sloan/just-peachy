"""Preflighted metadata batches; README_FIELD_STORAGE_REPAIR_V1.md."""
import hashlib
import json
import math
from pathlib import Path
import re
from field_sidecar_budget_v1 import GroupWriter, encoded, validate


def finite_float(token):
    value=float(token)
    if not math.isfinite(value):raise ValueError('Nonfinite decoded control number')
    return value


class StageFailure(RuntimeError):
    def __init__(self,published,cause):
        self.published=published
        super().__init__('STAGE_PARTIAL_PRESERVED: '+type(cause).__name__+': '+str(cause)[:256])


def preflight(batch,limits):
    if type(batch) is not dict or set(batch)!={'code','control'} or set(limits)!=set(batch):
        raise ValueError('Exact code/control batch required')
    maxima={'code':dict(maximum_bytes=2*1024**2,maximum_file_bytes=512*1024,maximum_files=64,maximum_write_bytes=512*1024,minimum_free_bytes=5*1024**3),
            'control':dict(maximum_bytes=1024**2,maximum_file_bytes=65536,maximum_files=16,maximum_write_bytes=65536,minimum_free_bytes=5*1024**3)}
    manifest={}
    for group,files in batch.items():
        b=validate(limits[group])
        if any(b[k]>maxima[group][k] for k in b):raise ValueError('Metadata allocation exceeded')
        if type(files) is not dict or not files:raise ValueError('Nonempty staged group required')
        if len(files)>b['maximum_files']:raise ValueError('Stage file count')
        total=0
        for name,raw in files.items():
            if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',name) or name.endswith('.pending'):
                raise ValueError('Stage flat name')
            if type(raw) is not bytes:raise ValueError('Stage exact bytes')
            if len(raw)>min(b['maximum_file_bytes'],b['maximum_write_bytes']):raise ValueError('Stage file/write ceiling')
            total+=len(raw);manifest[group+'/'+name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if total>b['maximum_bytes']:raise ValueError('Stage group bytes')
    if 'ADMISSION.json' not in batch['control']:raise ValueError('Final admission marker required')
    if set(batch['control']) & CONTROL_NAMES:raise ValueError('Runtime control names are reserved')
    control=limits['control']
    if len(batch['control'])+len(CONTROL_NAMES)>control['maximum_files']:
        raise ValueError('Runtime control file reservation')
    if sum(len(raw) for raw in batch['control'].values())+len(CONTROL_NAMES)*control['maximum_file_bytes']>control['maximum_bytes']:
        raise ValueError('Runtime control byte reservation')
    # Parse every control JSON before any directory/file publication.
    for name,raw in batch['control'].items():
        if name.endswith('.json'):
            json.loads(raw.decode('utf-8'),parse_float=finite_float,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite control JSON')))
    return manifest


def publish_batch(root,batch,limits,writer_class=GroupWriter,extra_directories=()):
    manifest=preflight(batch,limits);root=Path(root)
    allowed=('outer','outer/closure_reserve','outer/failure','outer/logs','outer/receipts','outer/telemetry')
    if extra_directories not in ((),allowed):raise ValueError('Exact declared outer layout required')
    if root.exists() or root.is_symlink():raise ValueError('Stage destination already exists')
    # Three (fixture) or nine (actual capsule) directories reserve64KiB each.
    root.mkdir();published=[]
    try:
        for group in ['code','control']:(root/group).mkdir()
        for name in extra_directories:(root/name).mkdir()
        writers={g:writer_class(root/g,limits[g]) for g in batch}
        order=sorted(k for k in manifest if k!='control/ADMISSION.json')+['control/ADMISSION.json']
        for key in order:
            dirs=[root,root/'code',root/'control']+[root/name for name in extra_directories]
            if any(p.is_symlink() or not p.is_dir() for p in dirs):raise ValueError('Stage directory type')
            if sum(max(p.stat().st_size,p.stat().st_blocks*512) for p in dirs)>len(dirs)*65536:raise ValueError('Stage directory extent reserve')
            group,name=key.split('/')
            writers[group].write(name,batch[group][name])
            if hashlib.sha256((root/group/name).read_bytes()).hexdigest()!=manifest[key]['sha256']:raise ValueError('Stage readback mismatch')
            published.append(key)
        return dict(manifest=manifest,published=published,admission_last=published[-1]=='control/ADMISSION.json')
    except Exception as exc:raise StageFailure(published,exc) from exc


CONTROL_NAMES={'OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json'}


def control_write(root,name,value,limits):
    if name not in CONTROL_NAMES:raise ValueError('Unmapped runtime control')
    raw=encoded(value)
    # Runtime controls share the same exact control-group budget as stage.
    return GroupWriter(Path(root)/'control',limits).write(name,raw)
