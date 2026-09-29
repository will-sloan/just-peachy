"""Unintegrated bounded ASR shadow; never skips audio. See README_ASR_BOUNDED_SHADOW_V2.md."""
from collections import Counter, deque
import hashlib
import math
import threading
import time
import numpy as np


class Shadow:
    capacity_samples=48000
    pending_limit=256
    interval_limit=128
    decision_limit=512
    progress_limit=32

    def __init__(self, origin, clock=time.perf_counter):
        self.origin=origin;self.clock=clock;self.lock=threading.RLock()
        self.pending=deque();self.cues=[];self.energy=[]
        self.decisions=deque(maxlen=self.decision_limit)
        self.progress_events=deque(maxlen=self.progress_limit)
        self.received=self.completed=self.pending_samples=0
        self.maximum_samples=self.maximum_pending=0
        self.maximum_cues=self.maximum_energy=0
        self.health_failed=self.asr_finished=self.closed=False
        self.metadata_uncertain=False;self.audit_incomplete=False
        self.retired_quiet_first=self.retired_quiet_last=None
        self.evicted_decisions=self.evicted_progress=self.late_retired_cues=0
        self.last_now=-math.inf;self.work_seconds=0.
        self.reasons=Counter();self.ingress_hash=hashlib.sha256();self.egress_hash=hashlib.sha256()
        self.decision_hash=hashlib.sha256()

    def _now(self):
        now=self.clock()-self.origin
        if not math.isfinite(now) or now<self.last_now:raise ValueError('Invalid shadow clock')
        self.last_now=now
        return now

    def _open(self):
        if self.closed:raise RuntimeError('Shadow is closed; start a fresh session')

    def _floor(self):
        return (self.pending[0][0] if self.pending else self.received)/16000

    def _prune(self):
        floor=self._floor()
        self.cues=[(a,b) for a,b in self.cues if b>floor]
        self.energy=[(a,b) for a,b in self.energy if b>floor]

    def _interval(self, target, first, last):
        if last<=self._floor():return
        merged=[]
        for a,b in sorted([*target,(first,last)]):
            if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(merged[-1][1],b))
            else:merged.append((a,b))
        if len(merged)>self.interval_limit:
            self.metadata_uncertain=True  # Lost support never licenses omission.
            merged=merged[-self.interval_limit:]
        target[:]=merged

    def _release(self, now, forced=None):
        first,last,audio=self.pending.popleft();self.pending_samples-=len(audio)
        a,b=first/16000,last/16000
        ap=any(y>a and x<b for x,y in self.cues)
        ep=any(y>a and x<b for x,y in self.energy)
        healthy=not self.health_failed and self.completed>=last+16000
        reason=forced or ('METADATA_UNCERTAIN_KEEP' if self.metadata_uncertain or self.audit_incomplete else
                'ASR_POSITIVE' if ap else 'ENERGY_POSITIVE' if ep else
                'MISSING_PROGRESS_KEEP' if not healthy else 'QUIET_CANDIDATE_UNQUALIFIED')
        self.egress_hash.update(audio.tobytes());self.reasons[reason]+=last-first
        self.decision_hash.update(f'{first}:{last}:{reason}:{int(ap)}:{int(ep)}\n'.encode())
        if len(self.decisions)==self.decision_limit:
            retired=self.decisions[0];self.evicted_decisions+=1
            if retired['reason']=='QUIET_CANDIDATE_UNQUALIFIED':
                self.retired_quiet_first=retired['first'] if self.retired_quiet_first is None else min(self.retired_quiet_first,retired['first'])
                self.retired_quiet_last=retired['last'] if self.retired_quiet_last is None else max(self.retired_quiet_last,retired['last'])
        self.decisions.append(dict(first=first,last=last,decided=now,reason=reason,
            asr_positive=ap,energy_positive=ep,actual_action='KEEP_ALL_SHADOW',late_positive_support=False))
        self._prune()

    def _expire(self, now):
        while self.pending and now>=self.pending[0][1]/16000+3.:self._release(now)

    def audio(self, first, audio):
        began=time.perf_counter();x=np.asarray(audio,dtype=np.float32)
        if x.ndim!=1 or not 0<len(x)<=320 or not np.isfinite(x).all():raise ValueError('Bad shadow audio')
        with self.lock:
            self._open()
            if type(first) is not int or first!=self.received:raise ValueError('Shadow source discontinuity')
            now=self._now();self._expire(now)
            while self.pending and (self.pending_samples+len(x)>self.capacity_samples or len(self.pending)>=self.pending_limit):
                self._release(now,'BUFFER_PRESSURE_KEEP')
            rms=float(np.sqrt(np.mean(x.astype(np.float64)**2)))
            last=first+len(x)
            if rms and 20*math.log10(rms)>=-55.:
                self._interval(self.energy,max(0,first/16000-.2),last/16000+.4)
            self.pending.append((first,last,x.copy()));self.received=last;self.pending_samples+=len(x)
            self.ingress_hash.update(x.tobytes())
            self.maximum_samples=max(self.maximum_samples,self.pending_samples);self.maximum_pending=max(self.maximum_pending,len(self.pending))
            self.maximum_energy=max(self.maximum_energy,len(self.energy));self.work_seconds+=time.perf_counter()-began

    def cue(self, payload):
        if not str(payload.get('text') or payload.get('display_text') or '').strip():return
        began=time.perf_counter();a=float(payload['source_start_sec']);b=float(payload['source_end_sec'])
        if not(math.isfinite(a) and math.isfinite(b) and 0<=a<=b):raise ValueError('Bad cue interval')
        with self.lock:
            self._open();now=self._now();first=max(0,a-1);last=b+1
            for row in self.decisions:
                if row['reason']=='QUIET_CANDIDATE_UNQUALIFIED' and last>row['first']/16000 and first<row['last']/16000:row['late_positive_support']=True
            if self.retired_quiet_first is not None and last>self.retired_quiet_first/16000 and first<self.retired_quiet_last/16000:
                self.audit_incomplete=True;self.late_retired_cues+=1
            self._interval(self.cues,first,last)
            self.maximum_cues=max(self.maximum_cues,len(self.cues));self._expire(now);self.work_seconds+=time.perf_counter()-began

    def progress(self, samples=0, failed=False, finished=False):
        began=time.perf_counter()
        with self.lock:
            self._open()
            if type(samples) is not int or samples<0 or self.completed+samples>self.received:raise ValueError('Bad ASR progress')
            self.completed+=samples;self.health_failed|=failed;self.asr_finished|=finished
            now=self._now()
            if len(self.progress_events)==self.progress_limit:self.evicted_progress+=1
            self.progress_events.append(dict(observed=now,completed_samples=self.completed,failed=self.health_failed,finished=self.asr_finished))
            self._expire(now);self.work_seconds+=time.perf_counter()-began

    def finish_shadow(self):
        with self.lock:
            if self.closed:return
            now=self._now()
            while self.pending:self._release(now,'EOF_KEEP')
            assert self.pending_samples==0 and self.ingress_hash.digest()==self.egress_hash.digest()
            self.closed=True

    def report(self, samples=None):
        self.finish_shadow()
        assert samples is None or samples==self.received
        return dict(status='BOUNDED_MODEL_FREE_SHADOW_ONLY',received_samples=self.received,completed_samples=self.completed,
            ingress_sha256=self.ingress_hash.hexdigest(),egress_sha256=self.egress_hash.hexdigest(),decision_sha256=self.decision_hash.hexdigest(),
            actual_skipped_samples=0,reason_samples=dict(self.reasons),metadata_uncertain=self.metadata_uncertain,audit_incomplete=self.audit_incomplete,
            maximum_audio_samples=self.maximum_samples,maximum_pending_entries=self.maximum_pending,
            maximum_cue_intervals=self.maximum_cues,maximum_energy_intervals=self.maximum_energy,
            retained_decisions=len(self.decisions),retained_progress=len(self.progress_events),
            evicted_decisions=self.evicted_decisions,evicted_progress=self.evicted_progress,late_retired_cues=self.late_retired_cues,
            recent_decisions=list(self.decisions),recent_progress=list(self.progress_events),work_seconds=self.work_seconds,
            model_inference_qualified=False,production_endurance_qualified=False)
