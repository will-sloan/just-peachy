"""Shared monotonic child deadline; README_FIELD_CHILD_DEADLINE_V1.md."""
import math
from pathlib import Path
import signal
import subprocess
import time

SCHEMA='just-peachy.absolute-child-deadline.v1'
FIELDS={'schema','boot_id','issued_ns','soft_ns','hard_ns','grace_ns'}

class DeadlineExpired(TimeoutError):pass

def seconds(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<=0:raise ValueError('Positive finite deadline duration required')
    return int(value*1_000_000_000)

def validate(value,admission,*,require_live=True):
    if type(value) is not dict or set(value)!=FIELDS or value['schema']!=SCHEMA:raise ValueError('Absolute deadline schema')
    if value['boot_id']!=admission['boot_id'] or value['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():raise ValueError('Absolute deadline boot binding')
    if any(type(value[k]) is not int for k in ['issued_ns','soft_ns','hard_ns','grace_ns']):raise ValueError('Integer monotonic deadline required')
    issued,soft,hard,grace=(value[k] for k in ['issued_ns','soft_ns','hard_ns','grace_ns'])
    now=time.monotonic_ns();maximum=seconds(admission['child_deadline_seconds']);max_grace=seconds(admission['child_stop_grace_seconds'])
    if not 0<issued<=now or not issued<soft<hard or hard-soft!=grace:raise ValueError('Absolute deadline order')
    if hard-issued>maximum or grace>max_grace or grace*2>hard-issued:raise ValueError('Absolute deadline exceeds admission')
    if require_live and now>=soft:raise DeadlineExpired('Absolute child deadline expired before work')
    return dict(value)

def create(admission,*,lifetime=None,grace=None):
    duration=seconds(admission['child_deadline_seconds'] if lifetime is None else lifetime)
    cleanup=seconds(admission['child_stop_grace_seconds'] if grace is None else grace)
    now=time.monotonic_ns()
    return validate(dict(schema=SCHEMA,boot_id=admission['boot_id'],issued_ns=now,soft_ns=now+duration-cleanup,hard_ns=now+duration,grace_ns=cleanup),admission)

def remaining(value,*,hard=False):
    return max(0.,(value['hard_ns' if hard else 'soft_ns']-time.monotonic_ns())/1e9)

class ChildAlarm:
    """Soft expiry initiates Python cleanup; parent enforces the common hard end."""
    def __init__(self,value,admission):
        self.value=validate(value,admission);self.armed=False
        if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError('Existing alarm must not be replaced')
        self.previous={s:signal.getsignal(s) for s in [signal.SIGALRM,signal.SIGTERM]}
    def arm(self):
        def expire(signum,frame):
            if getattr(self,'expired',False):return
            self.expired=True;signal.setitimer(signal.ITIMER_REAL,0)
            raise DeadlineExpired('Absolute child soft deadline or parent termination')
        for s in self.previous:signal.signal(s,expire)
        self.armed=True
        delay=remaining(self.value)
        if delay<=0:self.close();raise DeadlineExpired('Absolute child deadline expired before arming')
        signal.setitimer(signal.ITIMER_REAL,delay)
        return self
    def close(self):
        if self.armed:
            signal.setitimer(signal.ITIMER_REAL,0)
            for s,handler in self.previous.items():signal.signal(s,handler)
            self.armed=False

def spawn(command,value,admission,**kwargs):
    validate(value,admission)
    return subprocess.Popen(command,**kwargs)

def supervise(proc,value,admission,*,abort=False):
    """One soft/hard deadline; no phase or wait can restart its allowance."""
    validate(value,admission,require_live=False)
    result=dict(soft_ns=value['soft_ns'],hard_ns=value['hard_ns'],terminate_sent=False,kill_sent=False,abort=abort)
    soft_wait=0. if abort else remaining(value)
    try:proc.wait(timeout=soft_wait)
    except subprocess.TimeoutExpired:
        result['terminate_ns']=time.monotonic_ns();proc.terminate();result['terminate_sent']=True
        grace_wait=min(remaining(value,hard=True),value['grace_ns']/1e9) if abort else remaining(value,hard=True)
        try:proc.wait(timeout=grace_wait)
        except subprocess.TimeoutExpired:
            result['kill_ns']=time.monotonic_ns();proc.kill();result['kill_sent']=True
            # Reaping is separately bounded and is not permission to keep executing.
            proc.wait(timeout=1)
    result.update(returncode=proc.returncode,reaped_ns=time.monotonic_ns(),pid=proc.pid)
    return result
