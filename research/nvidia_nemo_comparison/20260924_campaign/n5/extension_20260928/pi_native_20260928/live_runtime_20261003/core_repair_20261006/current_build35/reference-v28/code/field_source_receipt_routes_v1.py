"""Bound source receipt routes; README_FIELD_SOURCE_RECEIPTS_V1.md."""
import hashlib,json
from pathlib import Path
from field_sidecar_budget_v1 import GroupWriter,encoded,validate

NAMES={'PRE_ROUTE_SNAPSHOT.json','POST_ROUTE_SNAPSHOT.json','SOURCE_START.json','SOURCE_START_FAILURE.json','ROUTE_STOP.json','BRIDGE_STOP.json','BRIDGE_CLOSE.json'}
class ReceiptFailure(RuntimeError):
    def __init__(self,receipt):
        self.receipt=receipt
        super().__init__('SOURCE_RECEIPT_NOT_PUBLISHED: '+receipt['name'])

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validate_descriptor(path,expected,plan_path):
    path=Path(path)
    if sha(path)!=expected:raise ValueError('Receipt descriptor hash')
    v=json.loads(path.read_text())
    if set(v)!={'schema','scope','plan_sha256','files','groups','mapped_names'} or v['schema']!='source-receipts.v1' or v['scope']!='no-capture-qualification':raise ValueError('Receipt descriptor schema/scope')
    if v['plan_sha256']!=sha(plan_path) or v['mapped_names']!=sorted(NAMES):raise ValueError('Receipt map/plan')
    plan=json.loads(Path(plan_path).read_text())
    if set(v['groups'])!={'source','failure','closure_reserve'}:raise ValueError('Receipt groups')
    for name,budget in v['groups'].items():
        validate(budget)
        ceiling=plan['sidecar_groups'][name]
        if any(budget[k]>ceiling[k] for k in budget) or budget['minimum_free_bytes']!=ceiling['minimum_free_bytes']:raise ValueError('Receipt budget exceeds plan')
    if type(v['files']) is not dict or not v['files']:raise ValueError('Receipt source pins')
    for name,h in v['files'].items():
        if Path(name).name!=name or sha(path.parent/name)!=h:raise ValueError('Receipt source identity')
    return v,plan

class ReceiptRoutes:
    def __init__(self,root,descriptor,expected,plan_path):
        v,self.plan=validate_descriptor(descriptor,expected,plan_path)
        self.root=Path(root);self.failures=[];self.serial=0
        # This qualification layout owns three flat groups only. It is not an
        # assertion that every future archive/source/host directory is guarded.
        if self.root.exists():raise ValueError('Fresh receipt layout required')
        self.root.mkdir()
        for name in v['groups']:(self.root/name).mkdir()
        self.groups={name:GroupWriter(self.root/name,b) for name,b in v['groups'].items()}
        self.layout()
    def layout(self):
        paths=[self.root]+list(self.root.iterdir())
        if len(paths)!=4 or any(not p.is_dir() or p.is_symlink() for p in paths):raise ValueError('Receipt layout changed')
        size=sum(p.stat().st_size for p in paths)
        if len(paths)>self.plan['maximum_directories'] or size+65536>self.plan['filesystem_metadata_reserve_bytes']:raise ValueError('Receipt directory reserve')
        return dict(directories=len(paths),observed_directory_bytes=size,reserved_growth_bytes=65536)
    def failure(self,name,raw,exc):
        self.serial+=1
        row=dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),error_type=type(exc).__name__,error=str(exc)[:256],raw_retained=False)
        prefix='failure-'+str(self.serial)
        try:
            self.layout()
            self.groups['failure'].write(prefix+'.bin',raw)
            row['raw_retained']=True;row['raw_path']=prefix+'.bin'
            self.groups['failure'].json(prefix+'.json',row)
            row['receipt_retained']=True
        except Exception as secondary:
            row['receipt_retained']=False;row['secondary_error']=type(secondary).__name__+': '+str(secondary)[:256]
        self.failures.append(row)
        return row
    def source(self,name,value):
        if name not in NAMES:raise ValueError('Unmapped source receipt')
        raw=encoded(value)
        try:
            self.layout()
            return self.groups['source'].write(name,raw)
        except (OSError,ValueError,RuntimeError) as exc:
            raise ReceiptFailure(self.failure(name,raw,exc)) from exc
    def closure(self,value):
        self.layout()
        return self.groups['closure_reserve'].json('SOURCE_CLOSURE.json',value)
