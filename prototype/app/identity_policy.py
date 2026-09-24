"""Existing C088 resolver with explicit closed-roster assumption and diagnostics.

No personal reference adaptation. Anonymous association remains the native S6/S7
tracker. Acoustic names retain their gates; closed display fallback is separate.
See README_ROSTER.md for internal published-name schema and limitations.
"""
from collections import OrderedDict
from copy import deepcopy
from itertools import islice
import math
import threading
import time
import numpy as np
from edge_speech_pipeline.research_identity_v3 import ResearchIdentityResolver


class DiagnosticTracker:
    """Expose the actual delivered cue's age without querying it again."""
    def __init__(self,target):self.target=target
    def __getattr__(self,name):return getattr(self.target,name)
    def update(self,vector,start,end,now,**kwargs):
        result=self.target.update(vector,start,end,now,**kwargs);cue=kwargs.get('spatial')
        result['prototype_spatial']=dict(age_sec=now-cue.available_at_sec if cue is not None else None,
            reliability=cue.reliability if cue is not None else None,available=cue is not None,
            age_clock='policy input availability minus delivered cue availability')
        return result


class PrototypeIdentityResolver(ResearchIdentityResolver):
    def __init__(self,settings,gallery,*,closed=False,clock=None):
        super().__init__(settings,gallery);self.closed=closed;self.clock=clock;self.assignments=OrderedDict()
        self._assignment_lock=threading.RLock()

    def resolve(self,decision,event):
        began=time.perf_counter()
        now=self.clock() if self.clock else event['available_at_sec']
        vector=np.asarray(event.get('vector',[]),dtype=np.float32)
        start,end=event.get('source_start_sec'),event.get('source_end_sec')
        numbers=all(type(v) in (int,float) and math.isfinite(v) for v in (start,end,now))
        clean=event.get('clean_intervals',[])
        clean_valid=bool(clean) and numbers and all(len(x)==2 and start<=x[0]<x[1]<=end for x in clean)
        fresh=numbers and 0<=now-end<=2.
        valid=bool(fresh and clean_valid and event.get('speech') is True and event.get('overlap') is False
            and vector.shape==(192,) and np.isfinite(vector).all() and np.linalg.norm(vector)>1e-8
            and decision.get('tracker_id',decision.get('track_id',decision.get('cluster_id'))) is not None and decision.get('reason')!='audio_gate_reject')
        result=super().resolve(decision,event if not self.closed or valid else {**event,'speech':False})
        d=result['identity']
        assignment='accepted' if d.get('naming_state')=='confirmed' else 'pending' if d.get('naming_state')=='tentative' or not d.get('query_executed') else 'rejected'
        if self.closed:
            # Query the current voice, never coerce raw scores or mutate a profile.
            # One selected voice is explicitly a user assumption, not recognition.
            if valid and self.gallery is not None and self.gallery.ids:
                scores=self.gallery.score(vector/float(np.linalg.norm(vector)));best=scores[0]
                accepted=assignment=='accepted' and d.get('query_executed') is True and d.get('known_profile_id')==best['profile_id']
                self.comparisons+=len(scores)
                if not d.get('query_executed'):self.query_calls+=1
                assignment='accepted' if accepted else 'forced'
                d.update(open_policy_reason=d.get('reason'),open_policy_naming_state=d.get('naming_state'),
                    open_policy_scores=deepcopy(d.get('scores',[])),scores=scores,top1_score=best['cosine'],
                    top2_score=scores[1]['cosine'] if len(scores)>1 else None,
                    margin=best['cosine']-scores[1]['cosine'] if len(scores)>1 else None,
                    query_executed=True,known_profile_id=best['profile_id'],known_name=best['name'],
                    naming_state='confirmed',display_label=best['name'],name_is_displayed=True,
                    candidate_profile_id=best['profile_id'],candidate_name=best['name'],
                    reason='closed_group_voice_accepted' if accepted else 'closed_group_user_assumption',
                    one_selected_person_assumption=len(scores)==1,name_evidence_available_at_sec=now)
                result.update(display_label=best['name'],known_profile_id=best['profile_id'],known_name=best['name'],naming_state='confirmed')
                result['name_revision']=dict(track_id=result['tracker_id'],replacement_label=best['name'],
                    replacement_known_name=best['name'],replacement_known_profile_id=best['profile_id'],
                    replacement_naming_state='confirmed',reason=d['reason'],evidence_id=event['event_id'],available_at_sec=event['available_at_sec'])
            else:
                # Never reuse an assumed name across silence, overlap, stale/missing evidence.
                assignment='unavailable';anonymous=result.get('anonymous_label','Unknown')
                d.update(known_profile_id=None,known_name=None,naming_state='unresolved',display_label=anonymous,
                    reason='closed_group_no_fresh_clean_voice',name_is_displayed=False)
                result.update(known_profile_id=None,known_name=None,naming_state='unresolved',display_label=anonymous)
                result.pop('name_revision',None)
        cue=decision.get('cue') or {}
        d.update(assignment=assignment,forced=assignment=='forced',closed_group_assumption=self.closed,
            personal_reference_update=False,score_threshold=self.settings.score_threshold,margin_threshold=self.settings.margin_threshold,
            minimum_unique_sec=self.settings.minimum_unique_sec,minimum_disjoint_count=self.settings.minimum_disjoint_count,
            evidence_kind=event.get('evidence_kind'),evidence_duration_sec=end-start if numbers else None,clean_duration_sec=sum(b-a for a,b in clean) if clean_valid else 0.,
            valid_fresh_voice=valid,evidence_age_sec=now-end if numbers else None,speech=event.get('speech'),overlap=event.get('overlap'),
            score_meaning='raw cosine, not probability; closed current query, open aggregate query',
            evidence_event_id=event.get('event_id'),spatial=deepcopy(cue),spatial_availability=deepcopy(decision.get('prototype_spatial',{})))
        if len(d.get('scores',[]))==1:d['next_candidate_margin']=None
        else:d['next_candidate_margin']=d.get('margin')
        eid=event.get('event_id')
        if eid:
            with self._assignment_lock:
                self.assignments[eid]=dict(assignment=assignment,profile_id=d.get('known_profile_id'),
                    forced=d['forced'],available_at_sec=now,source_start_sec=start,source_end_sec=end,
                    track_id=result.get('tracker_id'))
                while len(self.assignments)>4096:self.assignments.popitem(last=False)
        elapsed=time.perf_counter()-began
        self.total_sec+=max(0,elapsed-result['identity_compute_sec']);result['identity_compute_sec']=elapsed
        return result

    def _closed_display_choice(self,part,row):
        """An explicit roster assumption, never an acoustic decision or fake score."""
        if not self.closed or self.gallery is None or not self.gallery.ids:return None
        names=dict(zip(self.gallery.ids,self.gallery.names));chosen=part.get('known_profile_id')
        basis='historical_name_voice_unavailable';event_ids=[]
        if chosen not in names:
            chosen=self.gallery.ids[0];basis='roster_default_no_voice_match'
            start,end=row.get('source_start_sec'),row.get('source_end_sec')
            if all(type(v) in (int,float) and math.isfinite(v) for v in (start,end)) and 0<=start<end:
                eligible=[]
                # Bound display work. No extra embedding/model/gallery query.
                for eid,e in islice(reversed(self.assignments.items()),64):
                    a,b=e['source_start_sec'],e['source_end_sec']
                    if e['profile_id'] not in names or e['assignment'] not in ('accepted','forced'):continue
                    if not all(type(v) in (int,float) and math.isfinite(v) for v in (a,b)) or b>end:continue
                    overlapping=max(start,a)<min(end,b)
                    recent=0<=start-b<=2.
                    if not (overlapping or recent):continue
                    same_track=part.get('track_id') is not None and part['track_id']==e.get('track_id')
                    eligible.append(((same_track,overlapping,b),eid,e))
                if eligible:
                    _,eid,e=max(eligible,key=lambda item:item[0]);chosen=e['profile_id'];event_ids=[eid]
                    basis='same_utterance_voice_winner' if e['source_end_sec']>start else 'recent_voice_winner'
        return dict(profile_id=chosen,name=names[chosen],assignment='closed_assumed',basis=basis,
            evidence_ids=event_ids,acoustic_confidence=None,voice_identity_verified=False,
            scope='Closed-group display assumption; utterance-level continuity, not word alignment or enrollment evidence')

    def annotate_caption(self,payload):
        # ASR presentation and speaker delivery can run on different threads.
        with self._assignment_lock:return self._annotate_caption(payload)

    def _annotate_caption(self,payload):
        row=deepcopy(payload)
        for part in [row,*row.get('segments',[])]:
            part['prototype_closed_group']=self.closed
            part.pop('closed_display_assignment',None)
            if not part.get('known_profile_id') or part.get('naming_state')!='confirmed' or part.get('voice_available') is False:
                choice=self._closed_display_choice(part,row)
                if choice is not None:part['closed_display_assignment']=choice
            if not part.get('known_profile_id'):continue
            ids=list(part.get('evidence_ids') or [])
            if part.get('identity_input_event_id'):ids.append(part['identity_input_event_id'])
            evidence=[self.assignments[e] for e in ids if e in self.assignments
                and self.assignments[e]['profile_id']==part['known_profile_id']]
            assignment=('forced' if any(e['forced'] for e in evidence) else 'accepted') if evidence else ('assumed_unlinked' if self.closed else 'accepted')
            part['prototype_assignment']=assignment
            part['prototype_assignment_evidence_ids']=[e for e in ids if e in self.assignments]
            part['prototype_identity_scope']='historical caption span, not word-by-word source certainty'
        return row
