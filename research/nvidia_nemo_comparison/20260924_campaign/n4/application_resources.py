"""Bounded host application observations. See README_APPLICATION_RESOURCES.md."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import threading
import time

from common import bind, freeze
from resources import process_tree

PHASES = ('bootstrap', 'gui_ready', 'gallery_ready', 'starting', 'running', 'draining', 'closed')
FIELDS = ('rss_sum_bytes_not_unique_physical', 'unique_set_size_sum_bytes',
          'private_commit_sum_bytes', 'pss_sum_bytes')
MAX_IDENTITIES = 256


def identity(row):
    pid, created = row.get('pid'), row.get('create_time')
    if type(pid) is not int or pid <= 0 or type(created) not in (int, float) or not math.isfinite(created):
        raise ValueError('Exact process identity unavailable')
    return pid, created


def encoded(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False).encode('utf-8') + b'\n'


def observe(owner, known):
    """Read the root tree plus previously discovered exact children after reparenting.

    Never signal a process. Missing/exited identities are explicit, never zero
    memory. Children that start and exit between samples can still be missed.
    """
    import psutil
    primary = process_tree(owner['pid'], owner['create_time'])
    if primary['status'] != 'ALIVE':
        return dict(status=primary['status'], processes=[], retired=[], complete=False)
    rows = {}; incomplete = []; retired = []
    def add(tree):
        for row in tree.get('processes', []):
            if 'memory_info_bytes' not in row:
                incomplete.append(row); continue
            key = identity(row)
            if key in rows and rows[key] != row:
                # First observation wins; do not sum one process twice.
                continue
            rows[key] = row
    add(primary)
    for key in known:
        if key in rows or key == identity(owner):
            continue
        old = process_tree(*key)
        if old['status'] == 'ALIVE':
            add(old)
        else:
            retired.append(dict(pid=key[0], create_time=key[1], status=old['status']))
    values = list(rows.values())
    def total(fn):
        items = [fn(row) for row in values]
        return sum(items) if items and all(type(n) is int and n >= 0 for n in items) else None
    return dict(status='ALIVE', processes=values, incomplete_processes=incomplete, retired=retired,
        complete=not incomplete and identity(owner) in rows,
        rss_sum_bytes_not_unique_physical=total(lambda r:r['memory_info_bytes'].get('rss')),
        unique_set_size_sum_bytes=total(lambda r:r.get('unique_set_size_bytes')),
        private_commit_sum_bytes=total(lambda r:r['memory_info_bytes'].get('private')),
        pss_sum_bytes=total(lambda r:r.get('proportional_set_size_bytes')),
        thread_count_sum=total(lambda r:r.get('threads')),
        host_available_bytes=psutil.virtual_memory().available)


class ResourceLedger:
    """Finite aggregate state; raw samples stream to a private bounded file."""
    def __init__(self, owner):
        self.owner = dict(owner); identity(owner)
        self.owners = {}; self.phases = {}; self.samples = 0; self.incomplete = 0
        self.last_time = None; self.max_gap = 0.; self.max_duration = 0.; self.max_processes = 0

    def accept(self, row):
        began, ended = row['began_monotonic_sec'], row['ended_monotonic_sec']
        if not all(type(t) in (int,float) and math.isfinite(t) for t in (began,ended)) or ended < began:
            raise ValueError('Invalid resource sample clock')
        if self.last_time is not None:
            if began < self.last_time: raise ValueError('Resource clock moved backwards')
            self.max_gap = max(self.max_gap, began-self.last_time)
        tree = row['tree']
        if tree['status'] != 'ALIVE': raise ValueError('Application root exited or PID was reused')
        keys = [identity(p) for p in tree['processes']]
        if len(set(keys)) != len(keys): raise ValueError('Duplicate process would double count memory')
        if len(set(self.owners)|set(keys)) > MAX_IDENTITIES: raise ValueError('Process census bound exceeded')
        if tree['complete'] and identity(self.owner) not in keys: raise ValueError('Complete tree omitted application root')
        for process, key in zip(tree['processes'], keys):
            cpu = process['cpu_seconds']; total = cpu['user']+cpu['system']
            if type(total) not in (int,float) or not math.isfinite(total) or total < 0:
                raise ValueError('CPU counter unavailable or invalid')
            prev = self.owners.get(key)
            if prev and total < prev['last_cpu_seconds']: raise ValueError('CPU counter regressed for same process identity')
            if prev is None:
                prev = dict(pid=key[0],create_time=key[1],first_seen=began,first_cpu_seconds=total,
                    last_cpu_seconds=total,last_seen=ended,samples=0,last_observation='ALIVE')
                self.owners[key] = prev
            prev.update(last_cpu_seconds=total,last_seen=ended,samples=prev['samples']+1,last_observation='ALIVE')
        for retired in tree.get('retired', []):
            key = identity(retired)
            if key in self.owners:self.owners[key]['last_observation'] = retired['status']
        # A sample spanning a phase transition remains in the raw log but cannot
        # be assigned to either phase for first/last memory or phase peaks.
        phase = row['phase_at_start'] if row['phase_at_start']==row['phase_at_end'] else 'transition'
        if phase not in (*PHASES,'transition'):raise ValueError('Unknown application phase')
        summary = self.phases.setdefault(phase,dict(samples=0,complete_samples=0,first=None,last=None,peaks={}))
        summary['samples'] += 1
        complete = tree['complete'] and all(p.get('memory_info_bytes') for p in tree['processes'])
        if complete:
            values = {name:tree.get(name) for name in (*FIELDS,'thread_count_sum')}
            for v in values.values():
                if v is not None and (type(v) is not int or v < 0):raise ValueError('Invalid memory or thread counter')
            entry=dict(monotonic_sec=began,**values)
            if summary['first'] is None:summary['first']=entry
            summary['last']=entry;summary['complete_samples']+=1
            for name,value in values.items():
                if value is not None:summary['peaks'][name]=max(summary['peaks'].get(name,0),value)
        else:self.incomplete += 1
        self.samples+=1;self.last_time=began;self.max_duration=max(self.max_duration,ended-began)
        self.max_processes=max(self.max_processes,len(keys))

    def summary(self):
        return deepcopy(dict(samples=self.samples,incomplete_samples=self.incomplete,phases=self.phases,
            sampled_owners=list(self.owners.values()),maximum_processes_in_sample=self.max_processes,
            maximum_sample_start_gap_sec=self.max_gap,maximum_sample_duration_sec=self.max_duration,
            observed_cpu_delta_seconds_lower_bound=sum(p['last_cpu_seconds']-p['first_cpu_seconds'] for p in self.owners.values())))


class ApplicationResources:
    """In-process observer; inherits application affinity and owns only its thread.

    No inference or GUI imports, target control, global process enumeration, or
    automatic controlled/whole-stack acceptance. Runner supplies lifecycle marks.
    """
    def __init__(self, output, *, interval=.5, max_seconds=3600, max_bytes=32*1024**2):
        import psutil
        if not .1 <= interval <= 10 or not 0 < max_seconds <= 3600 or not 1024 <= max_bytes <= 64*1024**2:
            raise ValueError('Bounded resource sampling required')
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=False)
        p=psutil.Process();self.owner=dict(pid=p.pid,create_time=p.create_time())
        self.interval=interval;self.max_seconds=max_seconds;self.max_bytes=max_bytes
        self.ledger=ResourceLedger(self.owner);self.phase=PHASES[0];self.phase_index=0
        self.lock=threading.RLock();self.stop_event=threading.Event();self.thread=None
        self.stream=(self.output/'SAMPLES.jsonl').open('xb');self.written=0;self.error=None
        self.started=None;self.closed=False;self.result=None;self.marks=[]

    def _write(self, row):
        data=encoded(row)
        if len(data)>1024**2 or self.written+len(data)>self.max_bytes:
            raise ValueError('Resource evidence byte bound exceeded; preserve prefix')
        self.stream.write(data);self.stream.flush();self.written+=len(data)

    def mark(self, phase):
        with self.lock:
            if self.started is None or self.closed or self.error is not None:raise ValueError('Resource observer is not active')
            if phase not in PHASES or PHASES.index(phase)!=self.phase_index+1:
                raise ValueError('Lifecycle marks must be consecutive and unique')
            row=dict(kind='phase',phase=phase,monotonic_sec=time.perf_counter())
            try:self._write(row)
            except Exception as exc:
                self.error=type(exc).__name__+': '+str(exc);self.stop_event.set();raise
            self.phase=phase;self.phase_index+=1;self.marks.append(row)

    def start(self):
        if self.started is not None or self.closed:raise ValueError('Fresh observer required')
        self.started=time.perf_counter()
        with self.lock:
            row=dict(kind='phase',phase=self.phase,monotonic_sec=self.started)
            self._write(row);self.marks.append(row)
        self.thread=threading.Thread(target=self._run,name='n4-resource-observer',daemon=True);self.thread.start()
        return self

    def _sample(self):
        with self.lock:phase=self.phase;known=list(self.ledger.owners)
        began=time.perf_counter();tree=observe(self.owner,known);ended=time.perf_counter()
        with self.lock:
            row=dict(kind='sample',phase_at_start=phase,phase_at_end=self.phase,
                began_monotonic_sec=began,ended_monotonic_sec=ended,tree=tree)
            # Seal raw evidence first, including failed/incomplete observations.
            self._write(row);self.ledger.accept(row)

    def _run(self):
        try:
            while not self.stop_event.is_set():
                began=time.perf_counter()
                if began-self.started>=self.max_seconds:raise TimeoutError('Resource observation deadline reached')
                self._sample()
                self.stop_event.wait(max(0,self.interval-(time.perf_counter()-began)))
        except Exception as exc:
            with self.lock:self.error=type(exc).__name__+': '+str(exc)
            self.stop_event.set()

    def close(self):
        if self.closed:return self.result
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(10)
            if self.thread.is_alive():raise RuntimeError('Resource observer did not exit; evidence remains incomplete')
        # One final post-drain sample, still including this observer's overhead.
        if self.started is not None and self.error is None:
            try:self._sample()
            except Exception as exc:self.error=type(exc).__name__+': '+str(exc)
        self.stream.close();self.closed=True
        result=self.ledger.summary();complete_phases=[m['phase'] for m in self.marks]==list(PHASES)
        status='OBSERVED_HOST_RESOURCES' if self.error is None and self.started is not None and result['samples'] else 'FAILED_PRESERVED'
        result.update(status=status,owner=self.owner,phase_marks=self.marks,all_lifecycle_marks_present=complete_phases,
            interval_sec=self.interval,elapsed_sec=time.perf_counter()-self.started if self.started is not None else None,
            observer_thread_exited=self.thread is None or not self.thread.is_alive(),error=self.error,
            evidence=bind(self.output/'SAMPLES.jsonl'),observer_bytes=self.written,
            gpu_visibility_environment=os.environ.get('CUDA_VISIBLE_DEVICES'),
            gpu_allocator_allocated_bytes=None,gpu_allocator_reserved_bytes=None,gpu_device_usage_bytes=None,
            controlled_whole_stack_qualified=False,target_qualified=False,integrated_N4_cells=0,
            limitations=['Sampling misses unsampled peaks and short-lived children; CPU deltas are observed lower bounds.',
                'RSS sums double-count shared pages; USS omits shared pages; private commit is not resident memory.',
                'Linux PSS remains separate; WSL/cgroup or external workers are not inferred from a Windows tree.',
                'Observer CPU/memory is included. Cold-load, cache and weight attribution require runner phase evidence.',
                'Lifecycle marks describe caller intent, not successful source/model/GUI operation or controlled isolation.',
                'No GPU allocator/device measurements or CM5 timing/physical RAM qualification is inferred.'])
        freeze(self.output/'RESULT.json',result);self.result=result;return result
