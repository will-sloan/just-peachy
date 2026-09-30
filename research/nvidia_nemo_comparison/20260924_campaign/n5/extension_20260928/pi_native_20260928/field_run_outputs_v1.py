"""Shared, producer-reserved sidecars; README_FIELD_ARCHIVE_STOP_V1.md."""
from copy import deepcopy
import hashlib
import threading
from pathlib import Path
from field_sidecar_budget_v1 import GroupWriter, encoded, BudgetExceeded

KIB=1024
PRODUCERS=('entry','source','transport','presentation','worker','gate','stage','archive','native','launcher')
GROUPS=('failure','closure','telemetry')


def slots():
    result={g:{} for g in GROUPS}
    for producer in PRODUCERS:
        result['failure'][producer+'.bin']=(64*KIB,64*KIB,False)
        result['failure'][producer+'.json']=(8*KIB,8*KIB,False)
        result['closure'][producer+'.json']=(32*KIB,32*KIB,False)
    result['telemetry']['presentation.jsonl']=(256*KIB,8*KIB,True)
    result['telemetry']['gate.jsonl']=(256*KIB,8*KIB,True)
    return result


def allocation():
    groups={g:dict(maximum_bytes=sum(v[0] for v in entries.values()),
                   maximum_file_bytes=max(v[0] for v in entries.values()),
                   maximum_write_bytes=max(v[1] for v in entries.values()),
                   maximum_files=len(entries),minimum_free_bytes=5*1024**3)
            for g,entries in slots().items()}
    return dict(schema='field-producer-slots.v1',groups=groups,slots=slots(),
                directory_reserve_bytes=4*65536,
                reserved_bytes=sum(v['maximum_bytes'] for v in groups.values())+4*65536,
                whole_run_integrated=False)


class SlotGroup(GroupWriter):
    def __init__(self,root,budget,mapping):
        super().__init__(root,budget)
        self.mapping=deepcopy(mapping);self.request=None;self.serial=threading.RLock()

    def _inventory(self,d):
        rows=super()._inventory(d)
        for name,size in rows.items():
            key=name[:-8] if name.endswith('.pending') else name
            if key not in self.mapping or size>self.mapping[key][0]:
                raise BudgetExceeded('Unmapped or oversized producer slot')
        if self.request is not None:
            name,raw,append=self.request
            if (rows.get(name,0) if append else 0)+len(raw)>self.mapping[name][0]:
                raise BudgetExceeded('Producer slot exhausted; other reservations remain unavailable')
        return rows

    def write(self,name,raw,*,append=False,replace=False):
        if name not in self.mapping:raise ValueError('Unknown producer slot')
        cap,write_cap,stream=self.mapping[name]
        if type(append) is not bool or replace is not False or append!=stream:
            raise ValueError('Fixed producer publication mode')
        if type(raw) is not bytes or len(raw)>write_cap:raise BudgetExceeded('Producer write limit')
        with self.serial:
            self.request=(name,raw,append)
            try:return super().write(name,raw,append=append)
            finally:self.request=None

    def snapshot(self):
        with self.serial:return super().snapshot()


class RunOutputs:
    """One owner per producer. Shared lock protects checks and actual writes."""
    def __init__(self,root):
        self.root=Path(root);self.plan=allocation();self.failures={};self.closures={}
        self.lock=threading.RLock()
        if self.root.exists() or self.root.is_symlink():raise ValueError('Fresh shared sidecars required')
        self.root.mkdir()
        for group in GROUPS:(self.root/group).mkdir()
        self.groups={g:SlotGroup(self.root/g,self.plan['groups'][g],slots()[g]) for g in GROUPS}
        self.layout()

    def layout(self):
        if {p.name for p in self.root.iterdir()}!=set(GROUPS):raise ValueError('Shared layout changed')
        dirs=[self.root]+[self.root/g for g in GROUPS]
        if any(p.is_symlink() or not p.is_dir() for p in dirs):raise ValueError('Shared directory type')
        size=sum(max(p.stat().st_size,p.stat().st_blocks*512) for p in dirs)
        if size>self.plan['directory_reserve_bytes']:raise BudgetExceeded('Shared directory reserve')
        return size

    def publish(self,producer,kind,raw):
        if producer not in PRODUCERS or kind not in ('raw','failure','closure','telemetry'):
            raise ValueError('Unknown producer/channel')
        group={'raw':'failure','failure':'failure','closure':'closure','telemetry':'telemetry'}[kind]
        name=producer+('.bin' if kind=='raw' else '.jsonl' if kind=='telemetry' else '.json')
        self.layout()
        return self.groups[group].write(name,raw,append=kind=='telemetry')

    def fail(self,producer,reason,request_stop,raw=None):
        if producer not in PRODUCERS:raise ValueError('Unknown failure producer')
        with self.lock:
            if producer in self.failures:return deepcopy(self.failures[producer])
            row=dict(error=type(reason).__name__+': '+str(reason)[:512],stop_requested=False,
                     raw_bytes=None if raw is None else len(raw),raw_sha256=None if raw is None else hashlib.sha256(raw).hexdigest(),
                     raw_retained=False,receipt_retained=False)
            self.failures[producer]=row
            # The Stop signal happens before any diagnostic filesystem operation.
            try:request_stop();row['stop_requested']=True
            except Exception as exc:row['stop_error']=type(exc).__name__+': '+str(exc)[:256]
            if raw is not None:
                if len(raw)<=64*KIB:
                    try:self.publish(producer,'raw',raw);row['raw_retained']=True
                    except Exception as exc:row['raw_retention_error']=type(exc).__name__+': '+str(exc)[:256]
                else:row['raw_retention_error']='RAW_EXCEEDS_RESERVED_SLOT'
            try:self.publish(producer,'failure',encoded({**row,'receipt_retained':True}));row['receipt_retained']=True
            except Exception as exc:row['receipt_error']=type(exc).__name__+': '+str(exc)[:256]
            return deepcopy(row)

    def finish(self,producer,value):
        with self.lock:
            if producer in self.closures:raise RuntimeError('Closure already attempted; preserve outcome')
            self.closures[producer]=dict(retained=False)
            self.publish(producer,'closure',encoded(value))
            self.closures[producer]['retained']=True
