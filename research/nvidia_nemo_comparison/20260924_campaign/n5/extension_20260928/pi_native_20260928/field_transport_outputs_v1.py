"""Transport/config/TRACE routes; README_FIELD_TRANSPORT_OUTPUTS_V1.md."""
import hashlib,json,os
from pathlib import Path
from field_sidecar_budget_v1 import GroupWriter,encoded,validate
import field_child_deadline_v1 as deadlines

class OutputFailure(RuntimeError):
    def __init__(self,receipt):self.receipt=receipt;super().__init__('TRANSPORT_OUTPUT_FAILURE:'+receipt['name'])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load(path,expected=None):
    path=Path(path)
    if expected is not None and sha(path)!=expected:raise ValueError('Transport config changed')
    cfg=json.loads(path.read_text());required={'schema','capture','output_root','admission_path','admission_sha256','plan_path','plan_sha256','groups','deadline','source_module','source_factory','source_mode','backpressure_seconds'}
    if set(cfg)!=required or cfg['schema']!='transport-output-fixture.v1' or cfg['capture'] is not False:raise ValueError('No-capture transport config required')
    root=Path(cfg['output_root'])
    if path!=root/'config/CONFIG.json' or not root.is_absolute() or root.is_symlink():raise ValueError('Transport output root')
    if sha(cfg['admission_path'])!=cfg['admission_sha256'] or sha(cfg['plan_path'])!=cfg['plan_sha256']:raise ValueError('Transport admission/plan pin')
    a=json.loads(Path(cfg['admission_path']).read_text());plan=json.loads(Path(cfg['plan_path']).read_text())
    if a['capture'] is not False or a['maximum_active_children']!=1:raise ValueError('Fixture child admission')
    for row in a['files']:
        if sha(row['path'])!=row['sha256']:raise ValueError('Bound transport source changed')
    if (cfg['source_module'],cfg['source_factory'])!=('field_transport_empty_fixture_v1','create') or cfg['backpressure_seconds']!=1 or cfg['source_mode'] not in ['empty','wait']:raise ValueError('Only bound empty factory admitted')
    if set(cfg['groups'])!={'source','control','failure','closure_reserve','trace','config'}:raise ValueError('Transport output groups')
    for k,v in cfg['groups'].items():
        validate(v)
        if any(v[n]>plan['sidecar_groups'][k][n] for n in v):raise ValueError('Transport group exceeds plan')
    deadlines.validate(cfg['deadline'],a)
    return cfg,a,Outputs(root,cfg['groups'],plan)

class Outputs:
    def __init__(self,root,groups,plan):
        self.root=Path(root);self.plan=plan;self.groups={k:GroupWriter(self.root/k,v) for k,v in groups.items()};self.serial=0;self.layout()
    def layout(self):
        dirs=[self.root]+list(self.root.iterdir())
        if len(dirs)!=7 or any(not p.is_dir() or p.is_symlink() for p in dirs):raise ValueError('Transport flat group layout')
        size=sum(p.stat().st_size for p in dirs)
        if len(dirs)>self.plan['maximum_directories'] or size+65536>self.plan['filesystem_metadata_reserve_bytes']:raise ValueError('Transport directory reserve')
        return dict(directories=len(dirs),observed_directory_bytes=size)
    def failure(self,name,raw,exc):
        self.serial+=1;prefix='transport-failure-'+str(os.getpid())+'-'+str(self.serial)
        row=dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),error_type=type(exc).__name__,error=str(exc)[:256],raw_retained=False)
        try:
            self.groups['failure'].write(prefix+'.bin',raw);row.update(raw_retained=True,raw_path=prefix+'.bin')
            self.groups['failure'].json(prefix+'.json',row);row['receipt_retained']=True
        except Exception as e:row.update(receipt_retained=False,secondary_error=type(e).__name__+': '+str(e)[:256])
        return row
    def source(self,name,value):
        if name not in {'CHILD_OWNER.json','CHILD_READY.json','CHILD_RESULT.json'}:raise ValueError('Unmapped transport write')
        raw=encoded(value)
        try:self.layout();return self.groups['source'].write(name,raw)
        except (OSError,ValueError,RuntimeError) as exc:raise OutputFailure(self.failure(name,raw,exc)) from exc
    def trace(self,value):
        raw=encoded(value)+b'\n'
        try:self.layout();return self.groups['trace'].write('TRACE.jsonl',raw,append=True)
        except (OSError,ValueError,RuntimeError) as exc:raise OutputFailure(self.failure('TRACE.jsonl',raw,exc)) from exc
