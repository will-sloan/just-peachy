"""Model-bound gallery and causal track naming. See README_N2.md."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from edge_speech_pipeline.research_identity_v3 import union_intervals


def binding(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def unit(value):
    value=np.asarray(value,dtype=np.float32)
    if value.shape!=(192,) or not np.isfinite(value).all() or np.linalg.norm(value)<1e-8:
        raise ValueError('Expected finite nonzero 192D voice vector')
    return value/np.linalg.norm(value)


class N2Gallery:
    """Explicit gallery admission; never searches or converts another vector space."""
    def __init__(self,document,expected_namespace,selected_ids=None,*,expected_query_domain=None):
        if isinstance(document,(str,Path)):
            document=json.loads(Path(document).read_text(encoding='utf-8'))
        document=deepcopy(document)
        if document.get('schema')!='just-peachy.n2.gallery.v1' or document.get('namespace')!=expected_namespace:
            raise ValueError('Gallery schema/model/preprocessing namespace mismatch; re-extract permitted E audio')
        rows=document['profiles']
        if len(rows)>256 or len({r['profile_id'] for r in rows})!=len(rows):
            raise ValueError('Gallery has duplicate IDs or exceeds 256 profiles')
        calibration=document.get('calibration',{})
        if calibration.get('status')=='CALIBRATED':
            # A status string is not evidence of calibration. Bind every gate
            # to the actual caller's query domain and exact full profile payload.
            fail=lambda reason: ValueError('Unproven CALIBRATED gallery gate: '+reason)
            if calibration.get('schema')!='just-peachy.n2.calibrated-gate.v1' or calibration.get('fit_role')!='C':
                raise fail('explicit C-only calibration schema/role required')
            if not isinstance(expected_query_domain,str) or not expected_query_domain:
                raise fail('caller must supply expected query domain')
            if document.get('query_domain')!=expected_query_domain or calibration.get('query_domain')!=expected_query_domain:
                raise fail('query domain mismatch')
            if calibration.get('namespace')!=expected_namespace:
                raise fail('representation namespace mismatch')
            ids=calibration.get('profile_ids')
            if not isinstance(ids,list) or len(ids)!=len(rows) or set(ids)!={r['profile_id'] for r in rows}:
                raise fail('roster profile IDs mismatch')
            if calibration.get('gallery_profiles_sha256')!=binding(rows):
                raise fail('gallery profile payload hash mismatch')
            provenance=calibration.get('provenance',{})
            if not isinstance(provenance,dict):raise fail('C provenance must be an object')
            expected=dict(fit_role='C',input_domain=expected_query_domain,enrollment_domain=document.get('domain'),
                reference_seconds=document.get('duration_sec'),roster_id=document.get('roster_id'))
            if not isinstance(document.get('domain'),str) or not document.get('domain') or not isinstance(document.get('roster_id'),str) or not document.get('roster_id'):
                raise fail('enrollment domain and roster provenance required')
            duration=document.get('duration_sec')
            if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not np.isfinite(duration) or duration<=0:
                raise fail('positive declared reference duration required')
            if any(provenance.get(key)!=value for key,value in expected.items()):
                raise fail('C/domain/duration/roster provenance mismatch')
            for key in ('window_manifest_sha256','calibration_rows_sha256'):
                digest=provenance.get(key)
                if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
                    raise fail('missing or invalid '+key)
            for key,lower,upper in (('score_threshold',-1.,1.000002),('margin_threshold',0.,2.)):
                value=calibration.get(key)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or not lower<=value<=upper:
                    raise fail('invalid '+key)
            if calibration.get('gate_sha256')!=binding({key:value for key,value in calibration.items() if key!='gate_sha256'}):
                raise fail('calibration gate integrity mismatch')
        if selected_ids is not None:
            if not selected_ids or set(selected_ids)-{r['profile_id'] for r in rows}:
                raise ValueError('Selected roster has missing compatible profiles')
            rows=[r for r in rows if r['profile_id'] in selected_ids]
        self.namespace=deepcopy(expected_namespace)
        self.names=[r['name'] for r in rows];self.ids=[r['profile_id'] for r in rows]
        self.matrix=np.stack([unit(r['vector']) for r in rows]) if rows else np.empty((0,192),np.float32)
        self.matrix.setflags(write=False)
        self.gallery_id='n2:'+binding(document)
        self.calibration=deepcopy(document.get('calibration',{}))
        # A gate calibrated for a different candidate population is not inherited.
        if selected_ids is not None and set(selected_ids)!=set(document.get('calibration',{}).get('profile_ids',[])):
            self.calibration={'status':'UNCALIBRATED_ROSTER_CHANGED'}
        self.receipt=dict(gallery_id=self.gallery_id,namespace=self.namespace,loaded_count=len(rows),
            backend_sha256=self.namespace['model_sha256'],
            personal_ids=self.ids,dimension=192,domain=document.get('domain'),
            duration_sec=document.get('duration_sec'),roster_id=document.get('roster_id'),
            calibration=deepcopy(self.calibration),loader='N2Gallery actual runtime cosine',
            research_only=document.get('research_only',False))
        self.receipt['expected_query_domain']=expected_query_domain
        self.base_versions={};self.environment_bank=[];self.adaptation=None;self.query_count=0

    def score(self,vector):
        self.query_count+=1
        scores=self.matrix@unit(vector)
        order=sorted(range(len(scores)),key=lambda i:(-float(scores[i]),self.ids[i]))
        return [dict(profile_id=self.ids[i],name=self.names[i],cosine=float(scores[i])) for i in order]


class N2NameMap:
    """Per-session evidence; C-bound gates, explicit rejection and contradiction reset.

    Centroids weight each query by newly contributed clean source duration;
    overlapping windows do not multiply enrollment or observation duration.
    Closed roster is reported as an assumption independently of verification.
    """
    def __init__(self,gallery=None,*,closed=False,minimum_unique_sec=1.5):
        self.gallery=gallery;self.closed=closed;self.minimum_unique_sec=minimum_unique_sec
        self.states={};self.calls=0;self.resets=0;self.total_sec=0.

    def sync_tracks(self,active_ids,now):
        for track in list(self.states):
            if track not in active_ids:del self.states[track]

    def resolve(self,decision,event):
        started=time.perf_counter();self.calls+=1
        result=deepcopy(decision)
        track=result.get('tracker_id',result.get('track_id'))
        anonymous=result.get('anonymous_label','Unknown')
        detail=dict(mode='post_association',gallery_loaded=self.gallery is not None,
            gallery_id=self.gallery.gallery_id if self.gallery else None,query_executed=False,
            known_profile_id=None,known_name=None,naming_state='unknown',reason='no_eligible_voice',scores=[])
        if self.gallery is not None and track is not None and event.get('speech',True) and not event.get('overlap',False):
            vector=unit(event['vector']);start=event['source_start_sec'];end=event['source_end_sec']
            clean=union_intervals(event.get('clean_intervals',[[start,end]]))
            if any(a<start-1e-7 or b>end+1e-7 for a,b in clean):raise ValueError('Clean support outside query')
            state=self.states.setdefault(track,dict(intervals=[],weighted=np.zeros(192,np.float32),weight=0.,
                retired_unique_sec=0.,retired_through_sec=-float('inf'),
                name=None,profile_id=None,confirmed_profile_id=None,contradictions=0,version=0))
            current=self.gallery.score(vector)
            prior=next((r for r in current if r['profile_id']==state['confirmed_profile_id']),None)
            gate=getattr(self.gallery,'calibration',{})
            calibrated=gate.get('status')=='CALIBRATED' and gate.get('namespace')==getattr(self.gallery,'namespace',None)
            threshold=float(gate.get('score_threshold',2.)) if calibrated else 2.
            margin_threshold=float(gate.get('margin_threshold',2.)) if calibrated else 2.
            # Current evidence must support any retained name. Two successive
            # contradictions clear accumulated voice memory without recycling ID.
            contradiction=bool(prior and (not current or current[0]['profile_id']!=state['confirmed_profile_id'] or prior['cosine']<threshold))
            state['contradictions']=state['contradictions']+1 if contradiction else 0
            reset=state['contradictions']>=2
            if reset:
                state.update(intervals=[],weighted=np.zeros(192,np.float32),weight=0.,
                    retired_unique_sec=0.,retired_through_sec=-float('inf'),
                    name=None,profile_id=None,confirmed_profile_id=None,contradictions=0)
                state['version']+=1;self.resets+=1
            # Source-ordered evidence can retire old interval detail while
            # retaining its exact duration and an exclusion watermark. A late
            # duplicate cannot contribute that retired audio a second time.
            clean=[(max(a,state['retired_through_sec']),b) for a,b in clean if b>state['retired_through_sec']]
            merged=union_intervals(state['intervals']+clean)
            old=sum(b-a for a,b in state['intervals']);retained=sum(b-a for a,b in merged)
            unique=state['retired_unique_sec']+retained
            added=max(0.,retained-old)
            if added>1e-8:
                state['weighted']+=vector*added;state['weight']+=added
                if len(merged)>512:
                    retired=merged[:-512]
                    state['retired_unique_sec']+=sum(b-a for a,b in retired)
                    state['retired_through_sec']=retired[-1][1]
                state['intervals']=merged[-512:]
            center=unit(state['weighted']) if state['weight'] else vector
            scores=self.gallery.score(center)
            best=scores[0] if scores else None
            margin=(best['cosine']-scores[1]['cosine']) if len(scores)>1 else (2. if best else None)
            matched=bool(best and calibrated and unique>=self.minimum_unique_sec and best['cosine']>=threshold
                and margin>=margin_threshold and current and current[0]['profile_id']==best['profile_id']
                and current[0]['cosine']>=threshold and not contradiction)
            chosen=best if matched or (self.closed and best and unique>=.5) else None
            status='confirmed' if matched else 'closed_assumption' if chosen else 'unknown'
            state.update(name=chosen['name'] if chosen else None,profile_id=chosen['profile_id'] if chosen else None)
            if matched:state['confirmed_profile_id']=best['profile_id']
            detail.update(query_executed=True,scores=scores,current_scores=current,margin=margin,
                unique_clean_sec=unique,new_unique_sec=added,calibration_status=gate.get('status','UNCALIBRATED'),
                verified=matched,closed_roster_assumption=bool(self.closed),contradiction=contradiction,
                contradiction_reset=reset,name_map_version=state['version'],
                known_profile_id=state['profile_id'],known_name=state['name'],naming_state=status,
                reason='calibrated_C_accept' if matched else 'closed_roster_assumption_not_verification' if chosen
                    else 'uncalibrated_reject' if not calibrated else 'insufficient_evidence_or_score_reject')
        result.update(identity=detail,known_profile_id=detail['known_profile_id'],known_name=detail['known_name'],
            naming_state=detail['naming_state'],display_label=detail['known_name'] or ('Unknown' if self.gallery is not None else anonymous),
            identity_compute_sec=time.perf_counter()-started)
        detail['display_label']=result['display_label']
        self.total_sec+=result['identity_compute_sec']
        return result

    def annotate_caption(self,row):
        if not self.closed:return row
        row=deepcopy(row)
        for part in [row,*row.get('segments',[])]:
            part['prototype_closed_group']=True
            if part.get('naming_state')=='closed_assumption' and self.gallery is not None and part.get('known_profile_id') in self.gallery.ids:
                part['closed_display_assignment']=dict(profile_id=part['known_profile_id'],name=part.get('known_name'),
                    reason='N2 explicit closed roster cosine assumption',verified=False,
                    source='actual model-specific voice evidence',adaptation_eligible=False)
        return row

    def snapshot(self):
        return dict(schema='just-peachy.n2.name-map.v1',calls=self.calls,resets=self.resets,compute_sec=self.total_sec,
            active_tracks=len(self.states),gallery_id=self.gallery.gallery_id if self.gallery else None)
