"""Sequential saved-source ASR coordinator; README_SEQUENTIAL_ASR_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


class ModeState:
    """GUI-facing state contract; artifacts are distinct immutable revisions."""
    def __init__(self, source_hash):
        self.phase='IDLE';self.source_hash=source_hash;self.primary=None;self.refined=None
    def begin(self, phase):
        allowed={'sherpa':'IDLE','a2':'PRIMARY_READY'}
        if phase not in allowed or self.phase!=allowed[phase]:raise RuntimeError('INVALID_PHASE_TRANSITION')
        self.phase='TRANSCRIBING' if phase=='sherpa' else 'REFINING'
    def complete(self, phase, artifact, source_hash, owner_closed, success):
        expected={'sherpa':'TRANSCRIBING','a2':'REFINING'}
        if self.phase!=expected.get(phase) or not owner_closed or source_hash!=self.source_hash:
            raise RuntimeError('UNSAFE_PHASE_COMPLETION')
        if success and not artifact:raise RuntimeError('MISSING_PHASE_ARTIFACT')
        if phase=='sherpa':
            self.primary=artifact if success else None
            self.phase='PRIMARY_READY' if success else 'PRIMARY_FAILED'
        else:
            self.refined=artifact if success else None
            self.phase='COMPLETE' if success else 'REFINEMENT_FAILED'
    def snapshot(self):return dict(phase=self.phase,source_sha256=self.source_hash,primary=self.primary,refined=self.refined)


def state_checks():
    rejected=0;s=ModeState('fixture')
    for action in [lambda:s.begin('a2'),lambda:s.complete('sherpa','x','fixture',True,True)]:
        try:action()
        except RuntimeError:rejected+=1
        else:raise AssertionError('Illegal transition accepted')
    s.begin('sherpa')
    for kwargs in [dict(source_hash='fixture',owner_closed=False),dict(source_hash='wrong',owner_closed=True)]:
        try:s.complete('sherpa','primary',success=True,**kwargs)
        except RuntimeError:rejected+=1
        else:raise AssertionError('Unsafe completion accepted')
    s.complete('sherpa','primary','fixture',True,True);s.begin('a2');s.complete('a2',None,'fixture',True,False)
    assert s.primary=='primary' and s.refined is None and s.phase=='REFINEMENT_FAILED'
    try:s.begin('a2')
    except RuntimeError:rejected+=1
    else:raise AssertionError('Implicit retry accepted')
    return dict(rejected=rejected,failed_refinement_preserves_primary=True,no_silent_retry=True)


def run(root, admission, on_event=None):
    root=Path(root);source=admission['source_wav'];digest=sha(source)
    state=ModeState(digest);phases=[];states=[];started=time.monotonic()
    def emit(kind, value):
        item=dict(kind=kind,monotonic_ns=time.monotonic_ns(),value=value)
        encoded=(json.dumps(item,separators=(',',':'),allow_nan=False)+'\n').encode()
        path=root/'COORDINATOR_EVENTS.jsonl'
        if (path.stat().st_size if path.exists() else 0)+len(encoded)>2*1024**2:raise RuntimeError('COORDINATOR_OUTPUT_QUOTA')
        with path.open('ab') as f:f.write(encoded)
        if on_event is not None:on_event(item)
    checks=state_checks()
    for phase in ['sherpa','a2']:
        assert sha(source)==digest
        available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
        assert available >= (850 if phase=='sherpa' else 1408)*1024**2
        state.begin(phase);states.append(state.snapshot());emit('state',state.snapshot())
        d=root/phase;d.mkdir();env=os.environ.copy()
        env['LD_LIBRARY_PATH']=str(Path(admission['a2_parent'])/'lib')
        with (d/'process.log').open('xb') as log:
            proc=subprocess.Popen([sys.executable,'-B',str(root/'sequential_asr_child_v1.py'),'--phase',phase],stdout=log,stderr=subprocess.STDOUT,env=env)
            launch=time.monotonic_ns();last=0;count=0;forced=False
            try:
                while True:
                    events=d/'EVENTS.jsonl'
                    if events.exists():
                        with events.open('r') as f:
                            f.seek(last)
                            while True:
                                position=f.tell();line=f.readline()
                                if not line.endswith('\n'):f.seek(position);break
                                emit('publication',dict(backend=phase,event=json.loads(line)));count+=1
                            last=f.tell()
                    code=proc.poll()
                    if code is not None:break
                    if time.monotonic_ns()-launch>180*10**9:raise TimeoutError('PHASE_DEADLINE')
                    time.sleep(.02)
                # Final complete lines may have arrived between the read and poll.
                if events.exists():
                    with events.open('r') as f:
                        f.seek(last)
                        for line in f:assert line.endswith('\n');emit('publication',dict(backend=phase,event=json.loads(line)));count+=1
            finally:
                if proc.poll() is None:
                    forced=True;proc.terminate()
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
            ended=time.monotonic_ns();owner=json.loads((d/'CHILD_OWNER.json').read_text())
            closed=ticks(owner['pid'])!=owner['start_ticks'];assert closed
            result=json.loads((d/'RESULT.json').read_text());success=code==0 and not forced and result['status']=='PHASE_COLLECTED'
            artifact=dict(path=str(d/'RESULT.json'),sha256=sha(d/'RESULT.json'),backend=phase,source_sha256=digest)
            state.complete(phase,artifact,digest,closed,success);states.append(state.snapshot());emit('state',state.snapshot())
            phases.append(dict(phase=phase,owner=owner,launch_ns=launch,reaped_ns=ended,exact_owner_closed=closed,exit_code=code,forced=forced,publications=count,result=artifact))
            if not success:raise RuntimeError('PHASE_FAILED_'+phase)
    assert phases[0]['reaped_ns']<phases[1]['launch_ns'] and state.primary and state.refined
    return dict(status='SEQUENTIAL_ASR_COLLECTED_REVIEW_REQUIRED',phases=phases,states=states,state_checks=checks,
                source_sha256=digest,elapsed_seconds=time.monotonic()-started,capture=False,models_overlap=False,
                gui_integrated=False,diarizer_loaded=False,accuracy_scored=False)
