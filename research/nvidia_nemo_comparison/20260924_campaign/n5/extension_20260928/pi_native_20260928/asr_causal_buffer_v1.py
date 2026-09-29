"""Bounded shadow audio queue; never controls D1. See README_ASR_CAUSAL_V1.md."""
from collections import deque
import hashlib
import math
import time
import numpy as np
from asr_shadow_v1 import Shadow as PreviousShadow


class Shadow(PreviousShadow):
    def __init__(self, origin, clock=time.perf_counter):
        super().__init__(origin)
        self.clock=clock; self.pending=deque(); self.pending_samples=0
        self.capacity_samples=48000; self.maximum_samples=0; self.received=0
        self.completed=0; self.health_failed=False; self.asr_finished=False
        self.decisions=[]; self.progress_events=[]; self.causal_seconds=0.
        self.ingress_hash=hashlib.sha256(); self.egress_hash=hashlib.sha256()

    def _now(self):
        return self.clock()-self.origin

    def _release(self, now, forced=None):
        row,audio=self.pending.popleft(); self.pending_samples-=len(audio)
        a,b=row['first']/16000,row['last']/16000
        ap=any(c['last_sec']+1>a and max(0,c['first_sec']-1)<b for c in self.cues)
        ep=any(e['energy_positive'] and e['last']/16000+.4>a and max(0,e['first']/16000-.2)<b for e in self.blocks)
        healthy=not self.health_failed and self.completed>=row['last']+16000
        reason=forced or ('ASR_POSITIVE' if ap else 'ENERGY_POSITIVE' if ep else 'MISSING_PROGRESS_KEEP' if not healthy else 'QUIET_CANDIDATE_UNQUALIFIED')
        self.egress_hash.update(audio.tobytes())
        self.decisions.append(dict(first=row['first'],last=row['last'],decided=now,
            deadline=b+3.,reason=reason,asr_positive=ap,energy_positive=ep,
            completed_samples=self.completed,health_failed=self.health_failed,
            actual_action='KEEP_ALL_SHADOW',late_positive_support=False))

    def _expire(self, now):
        while self.pending and now>=self.pending[0][0]['last']/16000+3.:
            self._release(now)

    def audio(self, first, audio):
        began=time.perf_counter(); x=np.asarray(audio,dtype=np.float32)
        # This diagnostic admits the producer's 20ms blocks, including short EOF.
        if x.ndim!=1 or not 0<len(x)<=320 or not np.isfinite(x).all():
            raise ValueError('Unadmitted/nonfinite shadow block')
        with self.lock:
            if first!=self.received:raise ValueError('Shadow source discontinuity')
            now=self._now(); self._expire(now)
            while self.pending_samples+len(x)>self.capacity_samples:
                self._release(now,'BUFFER_PRESSURE_KEEP')
            rms=float(np.sqrt(np.mean(x.astype(np.float64)**2)))
            db=20*math.log10(rms) if rms else -300.
            row=dict(first=first,last=first+len(x),observed=now,rms_dbfs=db,energy_positive=db>=-55.)
            self.blocks.append(row); self.pending.append((row,x.copy()))
            self.ingress_hash.update(x.tobytes()); self.received+=len(x)
            self.pending_samples+=len(x); self.maximum_samples=max(self.maximum_samples,self.pending_samples)
            self.causal_seconds+=time.perf_counter()-began

    def cue(self, payload):
        began=time.perf_counter()
        if not str(payload.get('text') or payload.get('display_text') or '').strip():return
        a,b=float(payload['source_start_sec']),float(payload['source_end_sec'])
        if not (math.isfinite(a) and math.isfinite(b) and 0<=a<=b):raise ValueError('Bad cue interval')
        with self.lock:
            now=self._now()
            self.cues.append(dict(first_sec=a,last_sec=b,observed=now,event_id=payload.get('event_id'),final=bool(payload.get('final')),publication_monotonic_sec=payload.get('publication_monotonic_sec'),revision_window_not_phonetic=True))
            # A late cue cannot change a past decision. Keep a visible audit flag.
            for row in self.decisions:
                if row['reason']=='QUIET_CANDIDATE_UNQUALIFIED' and b+1>row['first']/16000 and max(0,a-1)<row['last']/16000:
                    row['late_positive_support']=True
            self._expire(now); self.causal_seconds+=time.perf_counter()-began

    def progress(self, samples=0, failed=False, finished=False):
        began=time.perf_counter()
        with self.lock:
            if not isinstance(samples,int) or samples<0 or self.completed+samples>self.received:
                raise ValueError('ASR completion exceeds contiguous source')
            self.completed+=samples; self.health_failed|=failed; self.asr_finished|=finished
            now=self._now(); self.progress_events.append(dict(observed=now,completed_samples=self.completed,failed=self.health_failed,finished=self.asr_finished))
            self._expire(now); self.causal_seconds+=time.perf_counter()-began

    def finish_shadow(self):
        with self.lock:
            while self.pending:self._release(self._now(),'EOF_KEEP')
            assert self.pending_samples==0 and self.ingress_hash.digest()==self.egress_hash.digest()

    def report(self, samples):
        self.finish_shadow()
        # Preserve the independently reviewed prior shadow-policy comparison.
        prior=super().report(samples)
        prior['causal_buffer']=dict(status='ONLINE_BOUNDED_SHADOW_ONLY',capacity_samples=self.capacity_samples,
            capacity_audio_bytes=self.capacity_samples*4,maximum_samples=self.maximum_samples,
            pending_samples=self.pending_samples,received_samples=self.received,completed_samples=self.completed,
            asr_finished=self.asr_finished,health_failed=self.health_failed,ingress_sha256=self.ingress_hash.hexdigest(),
            egress_sha256=self.egress_hash.hexdigest(),delay_seconds=3.,asr_lookahead_seconds=1.,
            progress_is_completion_not_speech_truth=True,work_seconds=self.causal_seconds,
            decisions=self.decisions,progress=self.progress_events,actual_skipped_samples=0,
            late_positive_frames=sum(d['late_positive_support'] for d in self.decisions),
            diagnostic_metadata_bounded_by_admitted_short_run=True,production_endurance_qualified=False)
        return prior


def model_free_checks():
    """Native adversarial scheduling checks; no model/device/real-speech claims."""
    def case(health=True,positive=False,energy=False,burst=False,failure=False):
        clock=[0.]; s=Shadow(0,lambda:clock[0])
        for i in range(250):
            clock[0]=0. if burst else (i+1)*.02
            s.audio(i*320,np.full(320,.01 if energy else 0.,np.float32))
            if positive and i==50:s.cue(dict(text='fixture',source_start_sec=.8,source_end_sec=1.2))
            if health:s.progress(320,failed=failure and i==20)
        s.finish_shadow();return s,clock
    rows=[]
    s,_=case(health=False);assert all(d['reason']!='QUIET_CANDIDATE_UNQUALIFIED' for d in s.decisions)
    rows.append(dict(name='missing_health_keeps',pass_case=True))
    s,_=case(failure=True);assert all(d['reason']!='QUIET_CANDIDATE_UNQUALIFIED' for d in s.decisions)
    rows.append(dict(name='failed_health_keeps',pass_case=True))
    s,c=case();assert any(d['reason']=='QUIET_CANDIDATE_UNQUALIFIED' for d in s.decisions)
    c[0]=8.;s.cue(dict(text='late fixture',source_start_sec=.5,source_end_sec=1.))
    assert any(d['late_positive_support'] for d in s.decisions)
    rows.append(dict(name='late_cue_visible_all_audio_retained',pass_case=True))
    s,_=case(positive=True);assert all(d['reason']!='QUIET_CANDIDATE_UNQUALIFIED' for d in s.decisions if d['first']/16000<2.2)
    rows.append(dict(name='one_second_padding_keeps',pass_case=True))
    s,_=case(energy=True);assert all(d['reason']!='QUIET_CANDIDATE_UNQUALIFIED' for d in s.decisions)
    rows.append(dict(name='dense_energy_fallback_keeps',pass_case=True))
    s,_=case(burst=True);assert s.maximum_samples<=48000 and any(d['reason']=='BUFFER_PRESSURE_KEEP' for d in s.decisions)
    assert s.pending_samples==0 and s.ingress_hash.digest()==s.egress_hash.digest()
    rows.append(dict(name='burst_bounded_fail_open_and_EOF',pass_case=True))
    try:s.audio(0,np.zeros(320,np.float32))
    except ValueError:pass
    else:raise AssertionError('Gap accepted')
    fresh=Shadow(0,lambda:0.);fresh.audio(0,np.zeros(320,np.float32));fresh.finish_shadow()
    assert fresh.received==320 and fresh.completed==0
    rows.append(dict(name='discontinuity_rejected_fresh_session_resets',pass_case=True))
    return rows
