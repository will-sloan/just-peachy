"""Bounded deterministic observation coordinator. See README_NOISE.md."""
from copy import deepcopy
import math,time,threading

RATE=16000


class NoiseCoordinator:
    """Evidence is correlated; no noise probability, name or caption veto."""
    def __init__(self,route='bypass'):
        self.route=route;self.observations={};self.lock=threading.Lock();self.fallback=None
    def observe(self,kind,start,end,value,provenance,available=None):
        if not 0<=start<=end:return
        with self.lock:
            self.observations[kind]=dict(source_start_sample=round(start*RATE),source_end_sample=round(end*RATE),
                available_monotonic_sec=time.perf_counter() if available is None else available,
                value=deepcopy(value),provenance=provenance,state='observed')
    def event(self,kind,end,payload):
        start=payload.get('receptive_start_sec',payload.get('source_start_sec',end))
        if not all(type(x) in (int,float) and math.isfinite(x) for x in (start,end)):return
        if kind=='research_segmentation':
            value={k:payload[k] for k in ('speech','overlap','speech_fraction','overlap_fraction','speech_probability','overlap_probability') if k in payload and not isinstance(payload[k],(list,dict))}
            self.observe('speech_overlap',start,end,value,'existing Pyannote publication; posterior/gate, not independent probability')
        elif kind=='research_embedding':
            value={k:payload.get(k) for k in ('rms','clipping_fraction','clean_fraction','evidence_kind')}
            admission=payload.get('admission') or {}
            value['admission']={k:admission.get(k) for k in ('admitted','reason','clean_intervals','selected_rms')}
            self.observe('voice_quality',start,end,value,'existing ReDimNet admitted audio window; no new embedding requested')
        elif kind in ('research_asr_observation','transcript_partial','transcript_final'):
            self.observe('asr_progress',start,end,dict(final=payload.get('final','final' in kind),characters=len(payload.get('text',''))),
                'ordinary Sherpa progress; missing words are not a noise detector')
    def snapshot(self,source_sample=0,backlog_sec=0.):
        now=time.perf_counter();end=source_sample/RATE
        with self.lock:observed=deepcopy(self.observations)
        rows={}
        for kind in ('waveform','speech_overlap','asr_progress','voice_quality','beam'):
            row=observed.get(kind)
            if row is None:row=dict(state='unknown',source_start_sample=None,source_end_sample=None,available_monotonic_sec=None,value=None,provenance='not observed')
            else:
                row['age_sec']=now-row['available_monotonic_sec']
                row['state']='fresh' if row['age_sec']<=2. and row['source_end_sample']<=source_sample else 'stale_or_ahead_of_consumer'
                if kind=='beam' and not row['value'].get('valid'):row['state']='invalid'
            rows[kind]=row
        overlap=rows['speech_overlap'];wave=rows['waveform'];reasons=[]
        if overlap['state']=='fresh' and overlap['value'].get('overlap'):reasons.append('overlap: no clean-reference update; retain existing gate')
        if wave['state']=='fresh' and wave['value'].get('clipped_fraction',0)>.005:reasons.append('clipping: mark uncertainty; no gain repair')
        if backlog_sec>.5:reasons.append('helper backlog: yield optional enhancement to core captions')
        if self.fallback:reasons.append('enhancer unavailable: continuous raw captions; enhanced identity suspended until next Start')
        return dict(route=self.route,source_cursor_sample=source_sample,observations=rows,
            actions=reasons or ['observe only; retain normal scheduler'],backlog_sec=backlog_sec,
            fallback=deepcopy(self.fallback),noise_probability=None,identity_authority=False,
            policy='No caption suppression, no new thresholds; low volume, missing words and accent are not proof of noise')
