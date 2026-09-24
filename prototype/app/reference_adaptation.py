"""Bounded, explicit-confirmation reference bank; no inference. See README_ADAPTATION.md."""
from collections import Counter
from copy import deepcopy
import hashlib,json,math,threading,time,uuid
import numpy as np

RATE=16000
WEIGHT=.10
MAX_PENDING=16
MAX_PERSON=4
MAX_STORED=6
SCORE_FLOOR=.5128856897354127  # retained C088 base-voice gate
MARGIN=.03
FEATURE='session-reference-enrichment-v1'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def domain(route):
    # Legacy O0/O1 and task10 references used these one fixed configurations.
    return {**{k:route.get(k) for k in ('tap','sample_rate','gain_policy','preprocessing','waveform_domain','enhancement','enhancement_sha256')},
        'beam_stream':route.get('beam_stream','xvf_'+str(route.get('tap'))),
        'enhancement_config':route.get('enhancement_config','dpdfnet-stateful-16k-hop160-v1' if route.get('enhancement') else 'bypass')}

def base_version(row):
    return digest({k:row[k] for k in ('id','backend_sha256','preprocessing','references')})

def normalized(value):
    v=np.asarray(value,np.float32)
    if v.shape!=(192,) or not np.isfinite(v).all() or np.linalg.norm(v)<1e-8:raise ValueError('Invalid reference vector')
    return (v/np.linalg.norm(v)).astype(np.float32)

class BaseAnchors:
    """Detached full roster. Neither bank scores nor assumed labels enter this."""
    def __init__(self,gallery):
        self.ids=gallery.ids[:];self.names=gallery.names[:];self.matrix=gallery.matrix.copy();self.matrix.setflags(write=False)
        self.route=domain(gallery.receipt['route']);self.versions=deepcopy(gallery.base_versions)
        self.version=digest(dict(versions=self.versions,domain=self.route))
    def scores(self,vector):
        values=self.matrix@normalized(vector)
        return sorted([dict(person_id=i,name=n,cosine=float(v)) for i,n,v in zip(self.ids,self.names,values)],key=lambda r:(-r['cosine'],r['person_id']))
    def agrees(self,scores,person):
        return bool(scores and scores[0]['person_id']==person and scores[0]['cosine']>=SCORE_FLOOR
            and scores[0]['cosine']-(scores[1]['cosine'] if len(scores)>1 else -1.)>=MARGIN)

class SessionBank:
    def __init__(self,base,session_id,*,collect=False,persisted=()):
        self.base=base;self.session_id=str(session_id);self.collect=collect;self.enabled=False
        self.frozen=None;self.candidates=[];self.persisted=deepcopy(list(persisted));self.rejected=Counter()
        self.lock=threading.RLock();self.compute_sec=0.;self.query_compute_sec=0.;self.query_count=0;self.last_match=None
        self.last_publication=-1.;self.last_start=-1
        self.log_match=None
        self.source_id=None;self.source_offset=0
    def freeze(self,reason):
        with self.lock:self.frozen=self.frozen or str(reason)
    def discard(self):
        with self.lock:
            self.candidates.clear();self.collect=False;self.enabled=False
            # A safety freeze cannot be cleared by discarding or toggling; fresh Start required.
    def observe(self,event,audio,route,provenance=None):
        tick=time.perf_counter()
        try:
            with self.lock:return self._observe(event,audio,route,provenance or {})
        finally:self.compute_sec+=time.perf_counter()-tick
    def _observe(self,event,audio,route,provenance):
        def reject(reason):self.rejected[reason]+=1;return None
        if not self.collect or self.frozen:return None
        if domain(route)!=self.base.route:self.freeze('reference_domain_mismatch');return reject('domain')
        if event.get('overlap') or event.get('music'):self.freeze('overlap_or_music');return reject('overlap_or_music')
        if event.get('evidence_kind')!='mature':return reject('not_mature')
        if len(self.candidates)>=MAX_PENDING:return reject('candidate_cap')
        start=event.get('source_start_sec');end=event.get('source_end_sec')
        clock=[start,end,event.get('publication_monotonic_sec'),event.get('consumer_monotonic_sec'),event.get('publication_source_cursor_sec')]
        if not all(type(v) in (float,int) and math.isfinite(v) for v in clock):self.freeze('clock_missing_or_nonfinite');return reject('clock')
        a,b=round(start*RATE),round(end*RATE)
        pub,consumer,cursor=clock[2:]
        if (not 0<=a<b or abs(start*RATE-a)>1e-4 or abs(end*RATE-b)>1e-4 or not 1.<=end-start<=4.
            or not 0<=consumer-pub<=2. or not 0<=cursor-end<=2. or pub<self.last_publication or a<self.last_start):
            self.freeze('clock_or_freshness_failure');return reject('clock')
        self.last_publication=pub;self.last_start=a
        x=np.asarray(audio,np.float32)
        if x.shape!=(b-a,) or not np.isfinite(x).all():self.freeze('source_window_unavailable');return reject('source')
        waveform=hashlib.sha256(x.astype('<f4').tobytes()).hexdigest()
        source_id=self.source_id or 'epoch:'+digest(self.session_id)
        source_a,source_b=a+self.source_offset,b+self.source_offset
        previous=[c for c in self.candidates+self.persisted if c['domain']==self.base.route]
        if any(c['waveform_sha256']==waveform or (c['source_id']==source_id and max(source_a,c['source_start_sample'])<min(source_b,c['source_end_sample'])) for c in previous):return reject('duplicate_or_overlapping_window')
        admission=event.get('admission') or {};clean=event.get('clean_intervals') or [];usable=0.;previous=start
        for pair in clean:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2:return reject('invalid_clean_support')
            left,right=pair
            if not all(type(v) in (int,float) and math.isfinite(v) for v in pair) or not previous<=left<right<=end:return reject('invalid_clean_support')
            usable+=right-left;previous=right
        clipping=float(np.mean(np.abs(x)>=.999));rms=float(np.sqrt(np.mean(x.astype(np.float64)**2)))
        if not admission.get('admitted') or not event.get('speech') or usable/(end-start)<.8 or clipping>.005 or rms<.002:return reject('quality')
        try:vector=normalized(event.get('normalized_embedding'))
        except (TypeError,ValueError):return reject('invalid_embedding')
        scores=self.base.scores(vector)
        if not scores:return reject('no_base_anchors')
        c=dict(id=str(uuid.uuid4()),session_id=self.session_id,event_id=str(event.get('event_id',''))[:160],
            source_id=source_id,source_start_sample=source_a,source_end_sample=source_b,
            start_sample=a,end_sample=b,clean_intervals=deepcopy(clean),usable_sec=usable,waveform_sha256=waveform,
            window_sha256=digest(dict(session=self.session_id,start=a,end=b,waveform=waveform)),
            vector=vector.tolist(),vector_sha256=hashlib.sha256(vector.astype('<f4').tobytes()).hexdigest(),
            domain=deepcopy(self.base.route),gallery_version=self.base.version,base_version=None,person_id=None,
            base_scores=scores[:2],confirmation=None,quality=dict(overlap=False,clipping=clipping,rms=rms,clean_fraction=usable/(end-start),
                noise='unknown; no music/noise classifier',music='not independently classified'),
            timing=dict(publication_monotonic_sec=pub,consumer_monotonic_sec=consumer,source_cursor_sec=cursor),
            provenance=deepcopy(provenance))
        if len(json.dumps(c,allow_nan=False))>24000:return reject('oversized_provenance')
        self.candidates.append(c);return deepcopy(c)
    def confirm(self,identifier,person_id,*,consent=False):
        with self.lock:
            if not consent:raise ValueError('A participating user must confirm the actual speaker')
            if self.frozen:raise ValueError('References frozen: '+self.frozen)
            c=next(c for c in self.candidates if c['id']==identifier)
            if not self.base.agrees(c['base_scores'],person_id):
                self.freeze('strong_base_voice_conflict');raise ValueError('Original voice anchors disagree or margin is insufficient; nothing added')
            if sum(r['person_id']==person_id for r in self.candidates if r['id']!=identifier)>=MAX_PERSON:raise ValueError('Session cap: four references per person')
            c.update(person_id=person_id,base_version=self.base.versions[person_id],
                confirmation=dict(kind='explicit_user',confirmed_unix=time.time(),quality_attested=True,
                    statement='I heard this one person, without other speech or music; not inferred from a seat/name/text label'))
    def entries(self):
        return [c for c in self.persisted+self.candidates if c.get('confirmation') and c.get('gallery_version')==self.base.version
            and c.get('domain')==self.base.route and c.get('base_version')==self.base.versions.get(c.get('person_id'))]
    def match(self,vector,ordinary):
        tick=time.perf_counter()
        with self.lock:
            if not self.enabled or self.frozen:return ordinary
            entries=self.entries();base_scores=self.base.scores(vector);v=normalized(vector)
            grouped={}
            for c in entries:grouped.setdefault(c['person_id'],[]).append(c)
            rows=[];weights={};used={}
            for row in ordinary:
                selected=grouped.get(row['profile_id'],[])[-MAX_STORED:]
                w=WEIGHT if selected else 0.;weights[row['profile_id']]=w;used[row['profile_id']]=[c['id'] for c in selected]
                cosine=float(np.mean([np.asarray(c['vector'],np.float32)@v for c in selected])) if selected else row['cosine']
                rows.append(dict(row,cosine=(1-w)*row['cosine']+w*cosine))
            rows.sort(key=lambda r:(-r['cosine'],r['name']))
            # Never promote a new winner or rescue a query rejected by full-roster base evidence.
            allowed=bool(rows and ordinary and rows[0]['profile_id']==ordinary[0]['profile_id'] and self.base.agrees(base_scores,rows[0]['profile_id']))
            result=rows if allowed else ordinary
            elapsed=time.perf_counter()-tick;self.query_compute_sec+=elapsed;self.query_count+=1
            self.last_match=dict(enabled=True,applied=allowed and any(weights.values()),weight_cap=WEIGHT,
                query_index=self.query_count,query_vector_sha256=hashlib.sha256(v.astype('<f4').tobytes()).hexdigest(),
                effective_weights=weights if allowed else {k:0. for k in weights},candidate_ids=used,
                baseline=deepcopy(ordinary),result=deepcopy(result),base_gallery_version=self.base.version,compute_sec=elapsed,
                reason='bounded blend' if allowed else 'full-roster base conflict/weakness; original scores retained')
            if self.log_match:self.log_match(deepcopy(self.last_match))
            return result
    def snapshot(self):
        with self.lock:
            compatible_ids={c['id'] for c in self.entries()}
            return dict(collect=self.collect,enabled=self.enabled,frozen=self.frozen,session_id=self.session_id,
                usable_sec=sum(c['usable_sec'] for c in self.candidates),confirmed_sec=sum(c['usable_sec'] for c in self.candidates if c['confirmation']),
                candidates=[{k:deepcopy(v) for k,v in c.items() if k not in ('vector','base_scores','provenance')}|
                    dict(best_base=deepcopy(c['base_scores'][0]),base_margin=c['base_scores'][0]['cosine']-c['base_scores'][1]['cosine'] if len(c['base_scores'])>1 else None) for c in self.candidates],
                compatible_saved=sum(c['id'] in compatible_ids for c in self.persisted),rejected=dict(self.rejected),
                compute_sec=self.compute_sec,query_compute_sec=self.query_compute_sec,query_count=self.query_count,last_match=deepcopy(self.last_match))
