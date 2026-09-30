"""Outer dispatcher outputs; see README_FIELD_OUTER_BUDGET_V1.md."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
from field_sidecar_budget_v1 import GroupWriter, encoded, validate

GROUPS = {'logs','telemetry','receipts','failure','closure_reserve'}
MAP = {'log':['logs','service.log'], 'resource':['telemetry','resources.jsonl'],
       'result':['receipts','RESULT.json'], 'dispatch':['receipts','DISPATCH_RESULT.json']}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def descriptor(path, expected, admission):
    if sha(path) != expected: raise ValueError('Outer descriptor digest')
    v = json.loads(Path(path).read_bytes())
    if set(v) != {'schema','files','groups','map','directory_reserve_bytes','maximum_directories'}:
        raise ValueError('Outer descriptor fields')
    if v['schema'] != 'field-outer-budget.v1' or v['map'] != MAP or set(v['groups']) != GROUPS:
        raise ValueError('Outer descriptor scope/map')
    if v['files'] != admission['outer_files']: raise ValueError('Outer source pins')
    for row in v['files'].values():
        if sha(row['path']) != row['sha256']: raise ValueError('Outer retained source changed')
    plan = json.loads(Path(v['files']['plan']['path']).read_bytes())
    for name,limits in v['groups'].items():
        validate(limits)
        if any(limits[k]>plan['sidecar_groups'][name][k] for k in limits): raise ValueError('Outer group exceeds plan')
    if type(v['maximum_directories']) is not int or v['maximum_directories'] != 6:
        raise ValueError('Exactly six declared outer directories')
    if type(v['directory_reserve_bytes']) is not int or not 6*65536 <= v['directory_reserve_bytes'] <= plan['filesystem_metadata_reserve_bytes']:
        raise ValueError('Outer directory reservation')
    return v


def create_layout(root, value):
    root = Path(root)
    if root.exists() or root.is_symlink(): raise ValueError('Fresh outer layout required')
    root.mkdir()
    for group in sorted(GROUPS): (root/group).mkdir()


class OuterOutputs:
    """One owner per role; shared GroupWriter locks serialize cross-role writes.

    Failure latches before Stop/diagnostics. Subsequent log blocks are failure
    tails, never silently accepted as ordinary logs. Retention failure is explicit.
    """
    def __init__(self,root,path,expected,admission,role,request_stop):
        self.v = descriptor(path,expected,admission)
        if role not in {'gate','worker','fixture'}: raise ValueError('Outer role')
        self.root=Path(root);self.role=role;self.request_stop=request_stop
        self.writers={name:GroupWriter(self.root/name,limits) for name,limits in self.v['groups'].items()}
        self.failure=None;self.stop_requested=False;self.stop_error=None
        self.failure_raw_enabled=True;self.rejected_bytes=0;self.rejected_blocks=0
        self.retained_rejected_bytes=0;self.rejected_hash=hashlib.sha256()
        self.attempted_receipts=set();self.finished=False;self.finish_outcome=None
        self.resource_rows=0;self.log_bytes=0;self.diagnostic_error=None
        self._layout()

    def _layout(self):
        if {p.name for p in self.root.iterdir()} != GROUPS: raise ValueError('Outer directory membership')
        dirs=[self.root]+[self.root/g for g in GROUPS];size=0
        for p in dirs:
            st=p.lstat()
            if not stat.S_ISDIR(st.st_mode): raise ValueError('Outer real directory required')
            extent=max(st.st_size,st.st_blocks*512)
            if extent>65536: raise ValueError('Outer directory extent ceiling')
            size+=extent
        if size>self.v['directory_reserve_bytes']: raise ValueError('Outer directory reserve')
        return dict(directories=len(dirs),extent_bytes=size,reserved_bytes=self.v['directory_reserve_bytes'])

    def _reject(self,site,raw,exc):
        if self.failure is None:
            self.failure=dict(site=site,error_type=type(exc).__name__,error=str(exc)[:256])
            self.stop_requested=True
            # Request physical Stop before any diagnostic write. Failure here
            # never converts the original publication failure into success.
            try:self.request_stop()
            except Exception as stop_exc:self.stop_error=type(stop_exc).__name__+': '+str(stop_exc)[:256]
        if raw is not None:
            self.rejected_blocks+=1;self.rejected_bytes+=len(raw);self.rejected_hash.update(raw)
            if self.failure_raw_enabled:
                try:
                    self._layout()
                    self.writers['failure'].write(self.role+'-rejected.bin',raw,append=True)
                    self.retained_rejected_bytes+=len(raw)
                except Exception as diagnostic:
                    self.failure_raw_enabled=False
                    self.diagnostic_error=type(diagnostic).__name__+': '+str(diagnostic)[:256]
        return False

    def emit(self,site,value):
        if self.finished: raise RuntimeError('Outer output already finalized')
        if site not in MAP: raise ValueError('Unmapped outer output')
        if site in {'result','dispatch'}:
            if site in self.attempted_receipts: raise RuntimeError('Receipt attempt already consumed')
            self.attempted_receipts.add(site)
        try:
            raw=value if site=='log' else encoded(value)+(b'\n' if site=='resource' else b'')
            if type(raw) is not bytes: raise TypeError('Log blocks must be bytes')
        except Exception as exc:return self._reject(site,None,exc)
        if self.failure is not None:return self._reject(site,raw,RuntimeError('Prior outer output failure'))
        try:
            self._layout();group,name=MAP[site]
            self.writers[group].write(name,raw,append=site in {'log','resource'})
            self._layout()
            if site=='log':self.log_bytes+=len(raw)
            if site=='resource':self.resource_rows+=1
            return True
        except Exception as exc:return self._reject(site,raw,exc)

    def finish(self,work_complete,exit_code):
        if self.finished:return deepcopy(self.finish_outcome)
        if type(work_complete) is not bool or type(exit_code) is not int:raise ValueError('Exact work outcome required')
        result=dict(role=self.role,logical_success=self.failure is None and work_complete and exit_code==0,
                    work_complete=work_complete,exit_code=exit_code,failure=deepcopy(self.failure),
                    stop_requested=self.stop_requested,stop_error=self.stop_error,log_bytes=self.log_bytes,
                    resource_rows=self.resource_rows,rejected_bytes=self.rejected_bytes,rejected_blocks=self.rejected_blocks,
                    retained_rejected_bytes=self.retained_rejected_bytes,rejected_sha256=self.rejected_hash.hexdigest(),
                    raw_retention_complete=self.retained_rejected_bytes==self.rejected_bytes,
                    diagnostic_error=self.diagnostic_error,closure_retained=False)
        self.finished=True
        try:
            self._layout()
            self.writers['closure_reserve'].json(self.role+'-OUTPUT_CLOSURE.json',dict(result,closure_retained=True))
            self._layout();result['closure_retained']=True
        except Exception as exc:
            result.update(logical_success=False,closure_error=type(exc).__name__+': '+str(exc)[:256])
            # Never retry a rejected/partial closure. Work outcome is retained
            # by the caller and must fail its exit/review independently.
        self.finish_outcome=deepcopy(result)
        return deepcopy(result)
