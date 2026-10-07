"""Bounded diagnostic snapshots around unchanged model loaders. README_MODEL_LOAD_TRACE.md."""
import json
import os
from pathlib import Path
import threading
import time


def memory_snapshot():
    import resource
    def fields(name):
        with Path(name).open() as stream:
            raw=stream.read(65537)
        if len(raw)>65536:raise ValueError('Bounded proc memory snapshot')
        return dict(line.split(':',1) for line in raw.splitlines() if ':' in line)
    status=fields('/proc/self/status');memory=fields('/proc/meminfo')
    def size(rows,key):return int(rows[key].split()[0])*1024 if key in rows else None
    try:rollup=fields('/proc/self/smaps_rollup')
    except (FileNotFoundError,PermissionError):rollup={}
    return dict(pid=os.getpid(),monotonic=time.monotonic(),rss_bytes=size(status,'VmRSS'),
        rss_peak_bytes=size(status,'VmHWM'),pss_bytes=size(rollup,'Pss'),
        virtual_bytes=size(status,'VmSize'),virtual_peak_bytes=size(status,'VmPeak'),
        swap_bytes=size(status,'VmSwap'),pss_swap_bytes=size(rollup,'SwapPss'),
        available_ram_bytes=size(memory,'MemAvailable'),total_ram_bytes=size(memory,'MemTotal'),
        threads=int(status['Threads'].strip()),address_space=list(resource.getrlimit(resource.RLIMIT_AS)),
        allocator_environment={name:os.environ.get(name) for name in
            ('MALLOC_ARENA_MAX','MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')},
        scope='current process; system available is separate; no aggregate physical-closure claim')


class ModelLoadTrace:
    def __init__(self,path,*,snapshot=memory_snapshot,interval=1.0,maximum_bytes=1024**2):
        if not 0<interval<=1 or not 4096<=maximum_bytes<=1024**2:raise ValueError('Bounded diagnostic policy')
        self.path=Path(path);self.snapshot=snapshot;self.interval=interval;self.maximum_bytes=maximum_bytes
        self.stream=self.path.open('xb',buffering=0);self.lock=threading.Lock()
        self.bytes=0;self.closed=False;self.active=None

    def record(self,stage,event,**details):
        row=dict(schema='just-peachy.model-load-memory.v1',stage=stage,event=event,
            memory=self.snapshot(),**details)
        raw=(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        with self.lock:
            if self.closed or len(raw)>8192 or self.bytes+len(raw)>self.maximum_bytes:
                raise RuntimeError('Model-load diagnostics exceeded finite allocation or are closed')
            if self.stream.write(raw)!=len(raw):raise OSError('Short model memory snapshot write')
            os.fsync(self.stream.fileno());self.bytes+=len(raw)

    def call(self,stage,function,*args,**kwargs):
        if self.active is not None:raise RuntimeError('One model loader per diagnostic trace')
        self.record(stage,'before')
        stop=threading.Event();errors=[]
        def observe():
            while not stop.wait(self.interval):
                try:self.record(stage,'during')
                except BaseException as exc:errors.append(repr(exc));return
        thread=threading.Thread(target=observe,name='v29-model-memory',daemon=True)
        self.active=thread;thread.start();failure=None
        try:
            return function(*args,**kwargs)
        except BaseException as exc:
            failure=exc
            raise
        finally:
            stop.set();thread.join(2)
            if thread.is_alive():
                # Preserve ownership; callers cannot report diagnostic closure.
                raise RuntimeError('Model memory sampler remains owned')
            self.active=None
            try:
                self.record(stage,'failed' if failure is not None else 'after',
                    error=None if failure is None else repr(failure)[:1024],sampling_errors=errors)
            except BaseException as diagnostic_error:
                if failure is None:raise
                failure.add_note('Model-load diagnostic failure: '+repr(diagnostic_error)[:1024])
            if errors and failure is None:raise RuntimeError('Model memory sampling failed: '+errors[0])

    def close(self):
        if self.active is not None and self.active.is_alive():raise RuntimeError('Model memory sampler remains owned')
        with self.lock:
            if self.closed:return
            self.stream.flush();os.fsync(self.stream.fileno());self.stream.close();self.closed=True
