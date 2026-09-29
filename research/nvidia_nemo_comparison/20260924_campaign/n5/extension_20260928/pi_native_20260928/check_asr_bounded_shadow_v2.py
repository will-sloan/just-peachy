"""Native model-free adversarial checks. See README_ASR_BOUNDED_SHADOW_V2.md."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import hashlib
import json
from pathlib import Path
import resource
import time
from datetime import datetime, timezone


def checks():
    import numpy as np
    from asr_bounded_shadow_v2 import Shadow
    from asr_causal_buffer_v1 import Shadow as Original
    rows=[];zero=np.zeros(320,np.float32);positive=np.full(320,.01,np.float32)
    # Compare actual old/new release decisions before either history is retired.
    for name in ['quiet','missing','failed','padded','energy','burst','late']:
        clock=[0.];old=Original(0,lambda:clock[0]);new=Shadow(0,lambda:clock[0])
        for i in range(400):
            clock[0]=0. if name=='burst' else (i+1)*.02
            for s in [old,new]:
                s.audio(i*320,positive if name=='energy' else zero)
                if name=='padded' and i==70:s.cue(dict(text='fixture',source_start_sec=.8,source_end_sec=1.2))
                if name!='missing':s.progress(320,failed=name=='failed' and i==20)
        if name=='late':
            clock[0]=11.
            for s in [old,new]:s.cue(dict(text='late fixture',source_start_sec=.5,source_end_sec=1.))
        old.finish_shadow();new.finish_shadow()
        keys=['first','last','reason','asr_positive','energy_positive','actual_action','late_positive_support']
        assert [{k:d[k] for k in keys} for d in old.decisions]==[{k:d[k] for k in keys} for d in new.decisions],name
        assert old.ingress_hash.digest()==new.ingress_hash.digest()==new.egress_hash.digest()
        rows.append(dict(name='prior_v1_parity_'+name,passed=True,blocks=400))
    clock=[0.];s=Shadow(0,lambda:clock[0])
    for i in range(1000):s.audio(i,np.zeros(1,np.float32))
    r=s.report();assert r['maximum_pending_entries']==256 and r['maximum_audio_samples']<=48000 and r['reason_samples']['BUFFER_PRESSURE_KEEP']>0
    rows.append(dict(name='tiny_block_metadata_pressure_keeps',passed=True,maximum_pending_entries=r['maximum_pending_entries']))
    clock=[0.];s=Shadow(0,lambda:clock[0])
    for i in range(200):s.cue(dict(text='adversarial future support',source_start_sec=10+i*4,source_end_sec=10.1+i*4))
    assert s.metadata_uncertain and len(s.cues)<=128
    for i in range(250):
        clock[0]=(i+1)*.02;s.audio(i*320,zero);s.progress(320)
    r=s.report();assert r['reason_samples'].get('QUIET_CANDIDATE_UNQUALIFIED',0)==0
    rows.append(dict(name='disjoint_cue_overflow_keeps',passed=True,maximum_cue_intervals=r['maximum_cue_intervals']))
    clock=[0.];s=Shadow(0,lambda:clock[0])
    for i in range(1500):
        clock[0]=(i+1)*.02;s.audio(i*320,zero);s.progress(320)
    assert s.retired_quiet_first is not None and s.evicted_decisions>0
    clock[0]=31.;s.cue(dict(text='very late fixture',source_start_sec=.5,source_end_sec=1.))
    assert s.audit_incomplete and s.late_retired_cues==1
    for i in range(1500,1750):
        clock[0]=31+(i-1499)*.02;s.audio(i*320,zero);s.progress(320)
    r=s.report();assert any(d['reason']=='METADATA_UNCERTAIN_KEEP' for d in r['recent_decisions'])
    rows.append(dict(name='retired_late_cue_visible_and_keeps',passed=True,audit_incomplete=True))
    # Sixty minutes of logical source time, executed as fast as CPU permits.
    clock=[0.];s=Shadow(0,lambda:clock[0]);wall=time.perf_counter();peaks=[]
    for i in range(180000):
        clock[0]=(i+1)*.02;s.audio(i*320,positive if i%500<100 else zero);s.progress(320)
        if i%100==99:s.cue(dict(text='positive fixture',source_start_sec=clock[0]-.4,source_end_sec=clock[0]-.1))
        if i%6000==5999:
            assert len(s.pending)<=256 and s.pending_samples<=48000 and len(s.cues)<=128 and len(s.energy)<=128
            assert len(s.decisions)<=512 and len(s.progress_events)<=32
            peaks.append(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    s.progress(finished=True);r=s.report()
    assert r['received_samples']==r['completed_samples']==57600000
    assert r['ingress_sha256']==r['egress_sha256'] and sum(r['reason_samples'].values())==57600000
    assert r['actual_skipped_samples']==0 and r['evicted_decisions']>0 and r['evicted_progress']>0
    assert len(json.dumps(r))<256*1024
    rows.append(dict(name='sixty_minute_logical_trace_fixed_collections',passed=True,logical_seconds=3600,
        execution_wall_seconds=time.perf_counter()-wall,report=r,sampled_process_peak_rss_bytes=peaks))
    for operation in [lambda:s.audio(57600000,zero),lambda:s.progress(0),lambda:s.cue(dict(text='closed',source_start_sec=0,source_end_sec=1))]:
        try:operation()
        except RuntimeError:pass
        else:raise AssertionError('Closed session accepted input')
    fresh=Shadow(0,lambda:0.)
    try:fresh.audio(1,zero)
    except ValueError:pass
    else:raise AssertionError('Discontinuity accepted')
    try:fresh.audio(0,np.array([float('nan')],np.float32))
    except ValueError:pass
    else:raise AssertionError('Nonfinite input accepted')
    fresh.audio(0,zero);fresh.finish_shadow();assert fresh.received==320 and fresh.completed==0
    rows.append(dict(name='closed_gap_nonfinite_and_fresh_session',passed=True))
    return rows


def main():
    root=Path(__file__).resolve().parent;a=json.loads((root/'ADMISSION.json').read_text())
    assert a['mode']=='model_free' and not a['capture'] and not a['models_loaded']
    assert sorted(os.sched_getaffinity(0))==[2,3] and os.getuid()!=0
    assert resource.getrlimit(resource.RLIMIT_STACK)==(1048576,1048576)
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
    resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,)*2);resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    for row in a['files']:
        with Path(row['path']).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==row['sha256']
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=boot,admission_sha256=hashlib.sha256((root/'ADMISSION.json').read_bytes()).hexdigest())
    with (root/'OWNER.json').open('x') as f:json.dump(owner,f)
    result=dict(status='FAILED_PRESERVED',owner=owner,capture=False,models_loaded=False,actual_skipped_samples=0)
    began=time.perf_counter()
    try:
        result['cases']=checks();result['status']='MODEL_FREE_BOUNDED_SHADOW_COLLECTED_REQUIRES_REVIEW'
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    result['elapsed_seconds']=time.perf_counter()-began;result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    with (root/'RESULT.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:result.get(k) for k in ['status','error','elapsed_seconds','peak_rss_bytes']}))
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__':raise SystemExit(main())
