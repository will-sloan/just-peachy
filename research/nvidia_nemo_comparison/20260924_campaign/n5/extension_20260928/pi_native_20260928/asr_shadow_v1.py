"""Native positive-cue shadow observer. See README_ASR_SHADOW_V1.md."""
import math,threading,time
import numpy as np

class Shadow:
    def __init__(self,origin):
        self.origin=origin;self.blocks=[];self.cues=[];self.lock=threading.Lock();self.observer_seconds=0.
    def audio(self,first,audio):
        began=time.perf_counter();x=np.asarray(audio,dtype=np.float64)
        rms=float(np.sqrt(np.mean(x*x)));db=20*math.log10(rms) if rms>0 else -300.
        row=dict(first=first,last=first+len(x),observed=time.monotonic()-self.origin,rms_dbfs=db,energy_positive=db>=-55.)
        with self.lock:self.blocks.append(row);self.observer_seconds+=time.perf_counter()-began
    def cue(self,payload):
        began=time.perf_counter()
        if not str(payload.get('text') or payload.get('display_text') or '').strip():return
        a=float(payload['source_start_sec']);b=float(payload['source_end_sec']);observed=time.monotonic()-self.origin
        assert 0<=a<=b and math.isfinite(observed)
        row=dict(first_sec=a,last_sec=b,observed=observed,event_id=payload.get('event_id'),final=bool(payload.get('final')),publication_monotonic_sec=payload.get('publication_monotonic_sec'),revision_window_not_phonetic=True)
        with self.lock:self.cues.append(row);self.observer_seconds+=time.perf_counter()-began
    def report(self,samples):
        start=time.perf_counter();blocks=list(self.blocks);cues=list(self.cues)
        assert blocks and blocks[0]['first']==0 and blocks[-1]['last']==samples
        assert all(a['last']==b['first'] for a,b in zip(blocks,blocks[1:]))
        def decide(a,b):
            deadline=b+2.;known=[q for q in cues if q['observed']<=deadline]
            asr=any(q['last_sec']+1>a and max(0,q['first_sec']-1)<b for q in known)
            energy=any(q['observed']<=deadline and q['energy_positive'] and q['last']/16000+.4>a and max(0,q['first']/16000-.2)<b for q in blocks)
            hindsight=any(q['last_sec']+1>a and max(0,q['first_sec']-1)<b for q in cues)
            return dict(first_sec=a,last_sec=b,decision_deadline_sec=deadline,asr_positive=asr,energy_positive=energy,asr_only_negative_control_skip=not asr,union_diagnostic_skip=not(asr or energy),late_asr_support=hindsight and not asr,actual_action='KEEP_ALL_SHADOW')
        frames=[decide(q['first']/16000,q['last']/16000) for q in blocks]
        # Current delayed native geometry:264coarse frames *80ms; final partial explicit.
        total=samples/16000;whole=[];a=0.
        while a<total:
            b=min(a+21.12,total);whole.append(decide(a,b));a=b
        def skipped(rows,key):return sum(q['last_sec']-q['first_sec'] for q in rows if q[key])
        return dict(status='NATIVE_ONLINE_CUES_POSTSESSION_CAUSAL_SHADOW_REPLAY',samples=samples,audio_seconds=total,pre_roll_seconds=1.,post_roll_seconds=1.,decision_delay_seconds=2.,energy_dbfs=-55.,energy_pre_seconds=.2,energy_post_seconds=.4,energy_source='converted source20ms RMS; not validated VAD',ASR_watermark_available=False,missing_health_would_retain=True,buffer_audio_lower_bound_bytes=2*16000*4,buffer_implemented=False,actual_audio_skipped=0,model_compute_saved_measured=False,blocks=blocks,cues=cues,frames=frames,whole_chunks=whole,ASR_only_negative_control_skip_seconds=skipped(frames,'asr_only_negative_control_skip'),union_diagnostic_skip_seconds=skipped(frames,'union_diagnostic_skip'),whole_chunk_diagnostic_skip_seconds=skipped(whole,'union_diagnostic_skip'),late_ASR_frame_count=sum(q['late_asr_support'] for q in frames),maximum_positive_cue_end_lag_seconds=max((q['observed']-q['last_sec'] for q in cues),default=None),observer_seconds=self.observer_seconds,postsession_policy_seconds=time.perf_counter()-start,accuracy_scored=False,strict_deployable_skip_qualified=False)
