"""Bounded S6B anonymous tracking policies. See README_RESEARCH_TRACKING_V2.md.

Only arrived audio embeddings, spans and delivered observations enter this
module. Scores labelled posterior are tempered engineering hypotheses, not
calibrated identity probabilities. No model or source-reference file is read.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field, fields
import math
from types import SimpleNamespace
import numpy as np


MODES = ('original_common', 'one_person', 'all_unknown', 'voice', 'angle', 'static', 'sustained', 'decay',
         'adaptive', 'innovation', 'folded', 'conflict_reject', 'bayes', 'hsmm',
         'global_assignment', 'dual_memory', 'multiprototype', 'quarantine', 'delay_graph')
SPATIAL_ONLY = frozenset(('angle','static','sustained','decay','adaptive','innovation','folded','conflict_reject'))


@dataclass(frozen=True)
class S6BTrackingConfig:
    mode: str = 'voice'
    cues_enabled: bool = False
    cosine_threshold: float = .35
    ambiguity_margin: float = .03
    prototype_update_threshold: float = .50
    commit_evidence_sec: float = 1.
    commit_disjoint_count: int = 2
    max_tracks: int = 16
    max_window_sec: float = 3.
    direction_max_age_sec: float = .25
    direction_match_deg: float = 25.
    direction_change_deg: float = 35.
    direction_persistence_sec: float = .75
    direction_continuity_gap_sec: float = 1.25
    minimum_spatial_reliability: float = .20
    spatial_weight: float = .12
    position_decay_sec: float = 12.
    conflict_cosine_floor: float = .20
    reliable_voice_cosine: float = .65
    innovation_drift_deg: float = 8.
    innovation_threshold_deg: float = 50.
    innovation_decay: float = .75
    bearing_sigma_deg: float = 20.
    bearing_uncertainty_deg: float = 50.
    sensor_quarantine_enabled: bool = False
    contradiction_count: int = 2
    recovery_count: int = 2
    quarantine_hold_sec: float = 1.
    update_escrow_enabled: bool = False
    escrow_agreement_cosine: float = .70
    escrow_timeout_sec: float = 3.
    temporal_temperature: float = .15
    continuity_prior: float = .75
    posterior_min_confidence: float = .50
    hypothesis_count: int = 8
    hypothesis_horizon: int = 8
    hsmm_min_duration_sec: float = .75
    hsmm_max_duration_sec: float = 5.
    hsmm_duration_bins: int = 8
    hsmm_switch_penalty: float = .25
    global_max_groups: int = 4
    global_group_cosine: float = .70
    global_group_max_age_sec: float = 4.
    global_beam_width: int = 16
    global_consistency_weight: float = .15
    global_continuity_weight: float = .05
    voice_learning_rate: float = .15
    slow_voice_learning_rate: float = .04
    location_learning_rate: float = .65
    dormancy_sec: float = 5.
    reentry_cosine: float = .55
    max_prototypes: int = 3
    prototype_novelty_cosine: float = .75
    rollback_margin: float = .06
    revision_enabled: bool = True
    revision_horizon_sec: float = 2.
    max_revision_records: int = 32
    revision_confidence: float = .75
    revision_margin: float = .10
    graph_max_nodes: int = 8
    graph_switch_cost: float = .20
    original_embedding_window_sec: float = .5

    def __post_init__(self):
        if self.mode not in MODES: raise ValueError('unknown S6B tracker mode')
        for name in ('cues_enabled','sensor_quarantine_enabled','update_escrow_enabled','revision_enabled'):
            if type(getattr(self,name)) is not bool: raise ValueError(name+' must be boolean')
        bounds={'commit_disjoint_count':(1,32),'max_tracks':(1,256),'contradiction_count':(1,16),
                'recovery_count':(1,16),'hypothesis_count':(1,32),'hypothesis_horizon':(2,32),
                'hsmm_duration_bins':(2,32),'global_max_groups':(2,8),'global_beam_width':(1,64),
                'max_prototypes':(1,4),'max_revision_records':(2,128),'graph_max_nodes':(2,16)}
        for name,(low,high) in bounds.items():
            value=getattr(self,name)
            if type(value) is not int or not low<=value<=high: raise ValueError(name+' outside bounded integer range')
        for f in fields(self):
            v=getattr(self,f.name)
            if isinstance(v,(int,float)) and not isinstance(v,bool) and not math.isfinite(v):raise ValueError(f.name+' must be finite')
        for name in ('cosine_threshold','prototype_update_threshold','conflict_cosine_floor','reliable_voice_cosine',
                     'escrow_agreement_cosine','global_group_cosine','reentry_cosine','prototype_novelty_cosine','revision_confidence'):
            if not -1<=getattr(self,name)<=1:raise ValueError(name+' must be a cosine')
        if not self.conflict_cosine_floor<=self.cosine_threshold<=self.prototype_update_threshold<=self.reliable_voice_cosine:
            raise ValueError('require conflict floor <= association <= update <= reliable voice')
        for name in ('ambiguity_margin','minimum_spatial_reliability','spatial_weight','innovation_decay','continuity_prior',
                     'posterior_min_confidence','voice_learning_rate','slow_voice_learning_rate','location_learning_rate','rollback_margin','revision_margin',
                     'global_consistency_weight','global_continuity_weight'):
            if not 0<=getattr(self,name)<=1:raise ValueError(name+' must be in [0,1]')
        if not 0<self.continuity_prior<1 or self.temporal_temperature<=0:raise ValueError('temporal probabilities/temperature must be positive and nondegenerate')
        for name in ('commit_evidence_sec','max_window_sec','direction_max_age_sec','direction_match_deg','direction_change_deg',
                     'direction_persistence_sec','direction_continuity_gap_sec','position_decay_sec','innovation_threshold_deg',
                     'bearing_sigma_deg','bearing_uncertainty_deg','escrow_timeout_sec','hsmm_min_duration_sec',
                     'hsmm_max_duration_sec','global_group_max_age_sec','dormancy_sec','revision_horizon_sec','original_embedding_window_sec'):
            if getattr(self,name)<=0:raise ValueError(name+' must be positive')
        if not .5<=self.max_window_sec<=3 or not .5<=self.original_embedding_window_sec<=self.max_window_sec:
            raise ValueError('supported contiguous ReDim window range is .5..3 seconds')
        if not 0<=self.quarantine_hold_sec<=30 or not 0<=self.innovation_drift_deg<=180:raise ValueError('invalid quarantine/innovation range')
        if self.hsmm_max_duration_sec<self.hsmm_min_duration_sec:raise ValueError('HSMM duration bounds reversed')
        if self.graph_max_nodes>self.max_revision_records:raise ValueError('graph nodes exceed revision history bound')
        if self.direction_match_deg>180 or self.direction_change_deg>180:raise ValueError('folded native bearing is linear [0,180]')
        if self.mode=='original_common' and (self.cues_enabled or self.sensor_quarantine_enabled or self.update_escrow_enabled):
            raise ValueError('original common control has no cue/escrow extensions')
        if self.mode=='voice' and self.cues_enabled:raise ValueError('voice parent cannot enable spatial cues')

    def validate(self):
        self.__post_init__()
        return self

    def field_usage(self):
        """Declare conditional fields; unused defaults are metadata, not executed knobs."""
        common={'mode','cues_enabled','max_tracks','max_window_sec','commit_evidence_sec','commit_disjoint_count',
                'cosine_threshold','ambiguity_margin','prototype_update_threshold','voice_learning_rate',
                'max_revision_records','sensor_quarantine_enabled','update_escrow_enabled'}
        mode='voice' if self.mode in SPATIAL_ONLY and not self.cues_enabled else self.mode
        if mode in ('original_common','one_person','all_unknown'):
            common={'mode','max_tracks','max_window_sec','commit_evidence_sec','commit_disjoint_count'}
            if mode=='original_common':common|={'cosine_threshold','original_embedding_window_sec'}
        if self.cues_enabled:
            common|={'direction_max_age_sec','direction_match_deg','minimum_spatial_reliability',
                     'spatial_weight','conflict_cosine_floor','direction_continuity_gap_sec'}
            if mode in ('decay','adaptive','conflict_reject','dual_memory') or self.sensor_quarantine_enabled:common.add('position_decay_sec')
            if mode=='sustained':common|={'direction_change_deg','direction_persistence_sec'}
            if mode=='innovation':common|={'innovation_drift_deg','innovation_threshold_deg','innovation_decay'}
            if mode=='folded':common|={'bearing_sigma_deg','bearing_uncertainty_deg'}
            if self.sensor_quarantine_enabled or mode=='conflict_reject':
                common|={'contradiction_count','recovery_count','quarantine_hold_sec','reliable_voice_cosine'}
            if self.update_escrow_enabled:common|={'escrow_agreement_cosine','escrow_timeout_sec'}
        if mode=='bayes':common|={'temporal_temperature','continuity_prior','posterior_min_confidence','hypothesis_count','hypothesis_horizon'}
        if mode=='hsmm':common|={'hsmm_min_duration_sec','hsmm_max_duration_sec','hsmm_duration_bins','hsmm_switch_penalty'}
        if mode=='global_assignment':common|={'global_max_groups','global_group_cosine','global_group_max_age_sec','global_beam_width',
                                            'global_consistency_weight','global_continuity_weight'}
        if mode=='dual_memory':
            common|={'slow_voice_learning_rate','dormancy_sec','reentry_cosine'};common.discard('voice_learning_rate')
            if self.cues_enabled:common.add('location_learning_rate')
        if mode=='multiprototype':common|={'max_prototypes','prototype_novelty_cosine'}
        if mode in ('quarantine','delay_graph'):common|={'revision_enabled','revision_horizon_sec'}
        if mode=='quarantine':common.add('rollback_margin')
        if mode=='delay_graph':common|={'revision_confidence','revision_margin','graph_max_nodes','graph_switch_cost'}
        inactive={f.name:getattr(self,f.name) for f in fields(self) if f.name not in common}
        changed=[f.name for f in fields(self) if f.name in inactive and getattr(self,f.name)!=f.default]
        return {'effective_mode':mode,'active_fields':sorted(common),'inactive_fields':inactive,'nondefault_inactive_fields':changed,
                'conditional_note':'Active means reachable for this mode; counters establish whether a dataset exercised it.'}


def _unit(value):
    v=np.asarray(value,dtype=np.float32).reshape(-1)
    if v.shape!=(192,) or not np.all(np.isfinite(v)):raise ValueError('finite 192-D ReDim vector required')
    n=float(np.linalg.norm(v))
    if n<=0:raise ValueError('nonzero ReDim vector required')
    return (v/n).astype(np.float32,copy=True)


def _union(ranges):
    out=[]
    for a,b in sorted(ranges):
        if b<=a:continue
        if out and a<=out[-1][1]+1e-9:out[-1][1]=max(b,out[-1][1])
        else:out.append([a,b])
    return out


@dataclass
class _Track:
    identifier: int
    prototypes: list[np.ndarray]
    created_at: float
    last_end: float
    ranges: list = field(default_factory=list)
    frozen_unique_sec: float = 0.
    disjoint_end: float = -math.inf
    disjoint_count: int = 0
    observation_count: int = 0
    committed: bool = False
    location: float | None = None
    location_at: float = -math.inf
    dormant: bool = False
    version: int = 0
    escrow: dict | None = None
    rollback: dict | None = None
    retired: bool = False

    @property
    def unique_sec(self):return self.frozen_unique_sec+sum(b-a for a,b in self.ranges)

    def admit(self,start,end,max_window):
        previous=self.unique_sec
        cutoff=end-max_window
        keep=[]
        for a,b in self.ranges:
            if b<=cutoff:self.frozen_unique_sec+=b-a
            elif a<cutoff:self.frozen_unique_sec+=cutoff-a;keep.append([cutoff,b])
            else:keep.append([a,b])
        self.ranges=_union(keep+[[start,end]])
        self.observation_count+=1
        disjoint=start>=self.disjoint_end-1e-9
        if disjoint:self.disjoint_count+=1;self.disjoint_end=end
        self.last_end=end
        return max(0.,self.unique_sec-previous),disjoint


@dataclass
class _Node:
    evidence_id: str
    decision_id: str
    vector: np.ndarray
    start: float
    end: float
    available: float
    first_track: int | None
    latest_track: int | None


class S6BTracker:
    """One deterministic incremental policy instance; no external files or truth."""
    def __init__(self,config: S6BTrackingConfig | None=None):
        self.config=(config or S6BTrackingConfig()).validate()
        self.mode='voice' if self.config.mode in SPATIAL_ONLY and not self.config.cues_enabled else self.config.mode
        self.effective_mode=self.mode
        self.tracks: list[_Track]=[];self.next_track=1;self.count=0
        self.last_end=-math.inf;self.last_available=-math.inf;self.last_selected=None
        self.seen_spans=deque(maxlen=256)
        self.nodes=deque(maxlen=self.config.max_revision_records)
        self.operations=Counter();self.last_cue_stamp=-math.inf;self.last_cue_sequence=None
        self.pending_angle=None;self.pending_since=0.;self.pending_last=-math.inf
        self.innovation=0.;self.innovation_anchor=None;self.innovation_alarm=False
        self.sensor_credit=1.;self.contradictions=0;self.recovery=0;self.quarantine_at=-math.inf;self.last_cue_audit_end=-math.inf
        self.hypotheses=[];self.hsmm_states={};self.global_groups=[];self.last_global_end=-math.inf
        self._legacy=None
        if self.mode=='original_common':
            from .speakers import SpeakerTracker
            class EmptyProfiles:
                def load(self):return {}
            config=SimpleNamespace(clustering_threshold=self.config.cosine_threshold,
                                   embedding_window_sec=self.config.original_embedding_window_sec,
                                   identity_score_threshold=.5128856897354127,identity_margin_threshold=.03,
                                   identity_minimum_evidence_sec=2.)
            self._legacy=SpeakerTracker(config,EmptyProfiles())
        self.legacy=self._legacy

    def _event(self,events,name,available,**values):
        self.operations[name]+=1
        events.append(dict(event=name,available_at_sec=available,**values))

    def _active(self):return [t for t in self.tracks if not t.retired]

    def _voice(self,track,vector):
        return max(float(vector@p) for p in track.prototypes)

    def _threshold(self,track):
        return max(self.config.cosine_threshold,self.config.reentry_cosine) if self.mode=='dual_memory' and track.dormant else self.config.cosine_threshold

    def _spatial(self,observation,start,end,now,events):
        c=self.config
        if not c.cues_enabled:return None,0.,'disabled'
        if observation is None:return None,0.,'missing'
        stamp=getattr(observation,'available_at_sec',None)
        if not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or not getattr(observation,'valid',False):return None,0.,'invalid'
        if stamp>now+1e-9:return None,0.,'future_delivery'
        if now-stamp>c.direction_max_age_sec+1e-9:return None,0.,'stale_delivery'
        observed=getattr(observation,'source_end_sec',None)
        if observed is not None and (not math.isfinite(observed) or observed>stamp+1e-9 or now-observed>c.direction_max_age_sec+1e-9):return None,0.,'invalid_or_stale_source'
        sequence=getattr(observation,'sequence',None)
        if stamp<self.last_cue_stamp-1e-9 or (sequence is not None and self.last_cue_sequence is not None and sequence<self.last_cue_sequence):return None,0.,'reordered'
        if sequence is not None and sequence==self.last_cue_sequence and stamp>self.last_cue_stamp+1e-9:return None,0.,'redelivered_old_sequence'
        angle=getattr(observation,'angle_deg',None);quality=getattr(observation,'reliability',0.);energy=getattr(observation,'energy',None)
        if not isinstance(angle,(int,float)) or not math.isfinite(angle) or not 0<=angle<=180:return None,0.,'invalid_angle'
        if not isinstance(quality,(int,float)) or not math.isfinite(quality) or not 0<=quality<=1:return None,0.,'invalid_reliability'
        if energy is not None and (not math.isfinite(energy) or energy<=0):return None,0.,'invalid_or_nonpositive_energy'
        quality*=max(0.,1-(now-stamp)/c.direction_max_age_sec)
        if quality<c.minimum_spatial_reliability:return None,0.,'low_reliability'
        fresh=stamp>self.last_cue_stamp+1e-9
        self.last_cue_stamp=stamp
        if sequence is not None:self.last_cue_sequence=sequence
        if fresh:
            if self.pending_angle is None or abs(angle-self.pending_angle)>c.direction_match_deg or now-self.pending_last>c.direction_continuity_gap_sec:
                self.pending_angle=angle;self.pending_since=now
            self.pending_last=now
            if self.mode=='innovation':
                if self.innovation_anchor is None:self.innovation_anchor=angle
                residual=abs(angle-self.innovation_anchor)
                self.innovation=max(0.,c.innovation_decay*self.innovation+residual-c.innovation_drift_deg)
                self.innovation_alarm=self.innovation>=c.innovation_threshold_deg
                self._event(events,'innovation_accumulate',now,residual_deg=residual,cusum=self.innovation)
                if self.innovation_alarm:
                    self._event(events,'innovation_change_proposal',now,angle_deg=angle,cusum=self.innovation,forces_new_identity=False)
                    self.innovation_anchor=angle;self.innovation=0.
                elif residual<c.direction_match_deg:self.innovation_anchor=.9*self.innovation_anchor+.1*angle
        return float(angle),float(quality),'qualified'

    def _sensor(self,voice,angle,quality,start,end,now,events):
        c=self.config
        if angle is None or not (c.sensor_quarantine_enabled or self.mode=='conflict_reject'):return quality
        if start<self.last_cue_audit_end-1e-9:return quality*self.sensor_credit
        self.last_cue_audit_end=end
        # During quarantine, retained stale anchors may audit later strong voice
        # agreement, but receive no association credit until probation succeeds.
        located=[t for t in self._active() if t.location is not None and
                 (now-t.location_at<=c.position_decay_sec or self.sensor_credit==0.)]
        if not located:return quality*self.sensor_credit
        angular=min(located,key=lambda t:abs(angle-t.location))
        if self.sensor_credit==0. and now-angular.location_at>c.position_decay_sec:
            self._event(events,'sensor_stale_anchor_audit',now,track_id=angular.identifier,anchor_age_sec=now-angular.location_at,
                        grants_association_credit=False,reason='bounded retained anchor used only for disjoint voice revalidation')
        ranked=sorted(voice.items(),key=lambda x:(-x[1],x[0]))
        best,score=ranked[0] if ranked else (None,-1.)
        clear=score>=c.reliable_voice_cosine and (len(ranked)==1 or score-ranked[1][1]>=c.ambiguity_margin)
        close=abs(angle-angular.location)<=c.direction_match_deg
        contradiction=close and ((clear and best!=angular.identifier) or score<c.conflict_cosine_floor)
        agreement=close and clear and best==angular.identifier
        if contradiction:
            self.contradictions+=1;self.recovery=0
            self._event(events,'sensor_contradiction',now,voice_track_id=best,location_track_id=angular.identifier,independent_audio_end_sec=end)
            if self.contradictions>=c.contradiction_count and self.sensor_credit:
                self.sensor_credit=0.;self.quarantine_at=now
                self._event(events,'sensor_quarantine',now,reason='independent voice/location conflict; no reference geometry used')
            return 0. # Contradictory packets never overwrite the location used by later audits.
        elif agreement:
            self.contradictions=0
            if self.sensor_credit==0 and now-self.quarantine_at>=c.quarantine_hold_sec:
                self.recovery+=1
                if self.recovery>=c.recovery_count:
                    self.sensor_credit=1.;self.recovery=0
                    self._event(events,'sensor_recovery',now,reason='disjoint later audio/observation agreement')
        else:self.recovery=0
        return quality*self.sensor_credit

    def _location_scores(self,voice,angle,quality,now):
        c=self.config;mode=self.effective_mode
        scores=dict(voice);contribution={k:0. for k in voice}
        if angle is None or quality<=0:return scores,contribution
        if mode=='sustained' and now-self.pending_since<c.direction_persistence_sec:return scores,contribution
        if mode=='innovation' and not self.innovation_alarm:return scores,contribution
        for track in self._active():
            if track.location is None:continue
            distance=abs(angle-track.location) # Native folded endpoints 0 and 180 remain distinct.
            match=math.exp(-.5*(distance/c.direction_match_deg)**2)
            weight=c.spatial_weight
            if mode in ('decay','adaptive','conflict_reject','dual_memory'):
                weight*=math.exp(-max(0.,now-track.location_at)/c.position_decay_sec)
            if mode not in ('static','sustained','innovation'):weight*=quality
            if mode=='adaptive' or mode not in SPATIAL_ONLY:
                # Strong voice reduces location authority; no true-identity calibration is implied.
                weight*=max(.10,1.-max(0.,voice[track.identifier]))
            if mode=='sustained' and self.last_selected==track.identifier and distance<c.direction_change_deg:
                weight=0.
            if mode=='folded':
                # Bounded quadrature over observable bearing uncertainty, not invented signed geometry.
                width=(1.-quality)*c.bearing_uncertainty_deg
                hypotheses=np.clip(np.array([angle-width,angle,angle+width]),0.,180.)
                match=float(np.sum(np.array([.25,.5,.25])*np.exp(-.5*((hypotheses-track.location)/c.bearing_sigma_deg)**2)))
            if voice[track.identifier]<c.conflict_cosine_floor:weight=0.
            contribution[track.identifier]=weight*(2.*match-1.)
            scores[track.identifier]+=contribution[track.identifier]
        return scores,contribution

    def _bayes(self,scores,eligible,now,events):
        c=self.config;states=[None]+sorted(eligible)
        prior=self.hypotheses or [(0.,())]
        expanded=[]
        for logp,path in prior:
            previous=path[-1] if path else None
            for identifier in states:
                emission=0. if identifier is None else (scores[identifier]-c.cosine_threshold)/c.temporal_temperature
                transition=1./len(states) if not path else (c.continuity_prior if identifier==previous else (1.-c.continuity_prior)/max(1,len(states)-1))
                expanded.append((logp+math.log(transition)+emission,(path+(identifier,))[-c.hypothesis_horizon:]))
        expanded.sort(key=lambda x:(-x[0],str(x[1])))
        kept=expanded[:c.hypothesis_count];peak=kept[0][0]
        total=sum(math.exp(logp-peak) for logp,_ in kept)
        self.hypotheses=[(logp-peak-math.log(total),path) for logp,path in kept]
        mass={identifier:0. for identifier in states}
        for logp,path in self.hypotheses:mass[path[-1]]+=math.exp(logp)
        winner=max(states,key=lambda k:(mass[k],-(k or 0)))
        self._event(events,'bayes_hypothesis_update',now,hypotheses=len(kept),heuristic_mass={str(k):v for k,v in mass.items()},calibrated=False)
        return winner if mass[winner]>=c.posterior_min_confidence else None

    def _hsmm(self,scores,eligible,start,end,now,events):
        c=self.config;states=[None]+sorted(eligible)
        quantum=c.hsmm_max_duration_sec/c.hsmm_duration_bins
        novel=max(0.,end-max(start,getattr(self,'hsmm_last_end',start)))
        steps=max(1,int(math.ceil(novel/quantum))) if novel>0 else 0
        self.hsmm_last_end=end
        prior=self.hsmm_states or {(None,0):0.}
        following={}
        for (previous,duration_bin),cost in prior.items():
            for identifier in states:
                same=identifier==previous
                duration=min(c.hsmm_duration_bins,duration_bin+steps) if same else min(c.hsmm_duration_bins,steps)
                emission=0. if identifier is None else scores[identifier]-c.cosine_threshold
                penalty=0. if same else c.hsmm_switch_penalty
                if not same and previous is not None and duration_bin*quantum<c.hsmm_min_duration_sec:
                    penalty+=c.hsmm_switch_penalty*(1.-duration_bin*quantum/c.hsmm_min_duration_sec)
                # At maximum duration switching becomes less costly, never compulsory identity evidence.
                if not same and duration_bin>=c.hsmm_duration_bins:penalty*=.5
                key=(identifier,duration);value=cost+emission-penalty
                if value>following.get(key,-math.inf):following[key]=value
        peak=max(following.values());self.hsmm_states={k:v-peak for k,v in following.items()}
        winner=max(following,key=lambda k:(following[k],-(k[0] or 0),k[1]))
        self._event(events,'hsmm_duration_update',now,state_count=len(following),winner_track_id=winner[0],duration_bin=winner[1],heuristic=True)
        return winner[0]

    def _global(self,vector,scores,eligible,start,end,now,events):
        c=self.config
        self.global_groups=[g for g in self.global_groups if end-g['end']<=c.global_group_max_age_sec]
        similarities=[float(np.dot(g['vector'],vector)) for g in self.global_groups]
        index=int(np.argmax(similarities)) if similarities and max(similarities)>=c.global_group_cosine else None
        independent=start>=self.last_global_end-1e-9
        if index is None and independent:
            if len(self.global_groups)>=c.global_max_groups:self.global_groups.pop(0)
            self.global_groups.append({'vector':vector.copy(),'start':start,'end':end,'count':1});index=len(self.global_groups)-1
        elif index is not None and independent:
            g=self.global_groups[index];g['vector']=_unit(g['vector']*g['count']+vector);g['count']+=1;g['end']=end
        if independent:self.last_global_end=end
        if index is None:return None
        # A serial mono stream supplies no independently observed simultaneous sources.
        # Sequential acoustic groups may share an identity. Pairwise acoustic consistency
        # and continuity softly couple assignments; neither imposes a person count.
        beam=[(0.,())]
        for gi,g in enumerate(self.global_groups):
            options=[(None,0.)]
            for track in self._active():
                similarity=self._voice(track,g['vector'])
                if similarity>=self._threshold(track):
                    value=(scores.get(track.identifier,similarity) if gi==index else similarity)-c.cosine_threshold
                    options.append((track.identifier,value))
            next_beam=[]
            for value,path in beam:
                for identifier,emission in options:
                    pairwise=0.
                    for previous_index,previous_id in enumerate(path):
                        if identifier is None or previous_id is None:continue
                        acoustic=float(np.dot(g['vector'],self.global_groups[previous_index]['vector']))
                        compatibility=2.*max(0.,acoustic)-1.
                        pairwise+=c.global_consistency_weight*(compatibility if identifier==previous_id else -compatibility)/max(1,gi)
                    if path and identifier is not None and path[-1] is not None and identifier!=path[-1]:pairwise-=c.global_continuity_weight
                    next_beam.append((value+emission+pairwise,path+(identifier,)))
            next_beam.sort(key=lambda item:(-item[0],str(item[1])))
            beam=next_beam[:c.global_beam_width]
        self._event(events,'bounded_global_assignment',now,group_count=len(self.global_groups),beam_count=len(beam),assignment=list(beam[0][1]),approximate=True,
                    sequential_identity_reuse_allowed=True,independent_simultaneous_observations_available=False)
        winner=beam[0][1][index]
        return winner if winner in eligible else None

    def _select(self,vector,voice,scores,angle,quality,start,end,now,events):
        c=self.config;mode=self.effective_mode
        if mode=='angle':
            if angle is None or quality<=0:return None,False,'angle_unavailable'
            located=[t for t in self._active() if t.location is not None]
            if not located:return None,True,'first_observable_bearing'
            compatible=[t for t in located if voice[t.identifier]>=c.conflict_cosine_floor]
            if not compatible:
                self._event(events,'angle_voice_conflict_reject',now,reason='bearing cannot override severe voice contradiction')
                return None,True,'new_voice_despite_shared_bearing'
            nearest=min(compatible,key=lambda t:(abs(angle-t.location),-voice[t.identifier],t.identifier))
            if abs(angle-nearest.location)>c.direction_match_deg:return None,True,'new_observable_bearing'
            return nearest.identifier,False,'anonymous_angle_association'
        eligible={t.identifier for t in self._active() if voice[t.identifier]>=self._threshold(t)}
        if not eligible:return None,True,'no_voice_association'
        if mode=='bayes':return self._bayes(scores,eligible,now,events),False,'bounded_hypothesis_association'
        if mode=='hsmm':return self._hsmm(scores,eligible,start,end,now,events),False,'semi_markov_association'
        if mode=='global_assignment':return self._global(vector,scores,eligible,start,end,now,events),False,'group_assignment'
        ranked=sorted(eligible,key=lambda identifier:(-scores[identifier],identifier))
        best=ranked[0]
        if len(ranked)>1 and scores[best]-scores[ranked[1]]<c.ambiguity_margin:return None,False,'ambiguous_voice_association'
        return best,False,'voice_and_arrived_cue' if scores!=voice else 'voice_association'

    def _new_track(self,vector,now,events):
        if len(self.tracks)>=self.config.max_tracks:
            self._event(events,'track_capacity_rejection',now,max_tracks=self.config.max_tracks)
            return None
        t=_Track(self.next_track,[vector.copy()],now,-math.inf)
        self.next_track+=1;self.tracks.append(t)
        self._event(events,'track_create',now,track_id=t.identifier,prototype_version=0)
        return t

    def _revise(self,node,replacement,now,reason,events):
        c=self.config
        if not c.revision_enabled or now-node.available>c.revision_horizon_sec or node.latest_track==replacement:return False
        previous=node.latest_track;node.latest_track=replacement
        replacement_track=next((track for track in self._active() if track.identifier==replacement),None)
        self._event(events,'label_revision',now,revision_of=node.decision_id,evidence_id=node.evidence_id,
                    from_track_id=previous,to_track_id=replacement,replacement_track_id=replacement,
                    replacement_anonymous_label='Unknown' if replacement is None else 'Speaker_'+str(replacement),
                    replacement_state='unknown' if replacement_track is None else ('committed' if replacement_track.committed else 'provisional'),
                    replacement_committed=bool(replacement_track and replacement_track.committed),
                    original_available_at_sec=node.available,reason=reason,first_decision_preserved=True)
        return True

    def _prototype(self,track,vector,start,end,now,node_id,independent,angle,quality,events):
        c=self.config;mode=self.effective_mode
        if not independent:
            self._event(events,'overlapping_prototype_update_suppressed',now,track_id=track.identifier)
            return
        similarity=self._voice(track,vector)
        if mode=='quarantine' and track.rollback is not None:
            old=track.rollback
            old_similarity=max(float(np.dot(p,vector)) for p in old['prototypes'])
            if start>=old['end']-1e-9 and old_similarity-similarity>=c.rollback_margin:
                track.prototypes=[p.copy() for p in old['prototypes']];track.version+=1
                self._event(events,'prototype_rollback',now,track_id=track.identifier,restored_from_version=old['version'],prototype_version=track.version,
                            reason='later disjoint audio favors pre-update prototype')
                for node in self.nodes:
                    if node.decision_id==old['decision_id']:self._revise(node,None,now,'rolled-back prototype update quarantined',events)
                track.rollback=None
                return
            if now-old['available']>c.revision_horizon_sec:track.rollback=None
        if similarity<c.prototype_update_threshold:return
        escrow_active=c.update_escrow_enabled and c.cues_enabled and angle is not None and quality>0
        if escrow_active:
            pending=track.escrow
            if pending is not None:
                if now-pending['available']>c.escrow_timeout_sec:
                    self._event(events,'prototype_escrow_expire',now,track_id=track.identifier,pending_decision_id=pending['decision_id']);track.escrow=None
                elif start>=pending['end']-1e-9:
                    if float(np.dot(pending['vector'],vector))>=c.escrow_agreement_cosine:
                        proposal=_unit(pending['vector']+vector)
                        track.prototypes[0]=_unit((1.-c.voice_learning_rate)*track.prototypes[0]+c.voice_learning_rate*proposal)
                        track.version+=1;track.escrow=None
                        self._event(events,'prototype_escrow_release',now,track_id=track.identifier,pending_decision_id=pending['decision_id'],confirming_decision_id=node_id,prototype_version=track.version)
                        return
                    self._event(events,'prototype_escrow_reject',now,track_id=track.identifier,pending_decision_id=pending['decision_id']);track.escrow=None
            if track.escrow is None:
                track.escrow={'vector':vector.copy(),'end':end,'available':now,'decision_id':node_id}
                self._event(events,'prototype_escrow_hold',now,track_id=track.identifier,decision_id=node_id)
            return
        if mode=='multiprototype':
            if similarity<c.prototype_novelty_cosine and len(track.prototypes)<c.max_prototypes:
                track.prototypes.append(vector.copy());track.version+=1
                self._event(events,'prototype_slot_add',now,track_id=track.identifier,slot=len(track.prototypes)-1,prototype_version=track.version)
                return
            slot=int(np.argmax([float(np.dot(p,vector)) for p in track.prototypes]))
        else:slot=0
        if mode=='quarantine':
            track.rollback={'prototypes':[p.copy() for p in track.prototypes],'end':end,'available':now,'decision_id':node_id,'version':track.version}
            self._event(events,'prototype_rollback_checkpoint',now,track_id=track.identifier,prototype_version=track.version)
        alpha=c.slow_voice_learning_rate if mode=='dual_memory' else c.voice_learning_rate
        track.prototypes[slot]=_unit((1.-alpha)*track.prototypes[slot]+alpha*vector);track.version+=1
        self._event(events,'prototype_update',now,track_id=track.identifier,slot=slot,prototype_version=track.version)

    def _graph(self,now,events):
        c=self.config
        nodes=[node for node in self.nodes if now-node.available<=c.revision_horizon_sec][-c.graph_max_nodes:]
        if len(nodes)<2:return
        candidates=[None]+[track.identifier for track in self._active()]
        byid={t.identifier:t for t in self._active()}
        paths={None:(0.,())}
        for node in nodes:
            following={}
            for identifier in candidates:
                score=0. if identifier is None else self._voice(byid[identifier],node.vector)-c.cosine_threshold
                if identifier is not None and score<0:continue
                choices=[(cost+score-(c.graph_switch_cost if previous!=identifier else 0.),path+(identifier,)) for previous,(cost,path) in paths.items()]
                following[identifier]=max(choices,key=lambda item:(item[0],str(item[1])))
            paths=following
        _,path=max(paths.values(),key=lambda item:(item[0],str(item[1])))
        self._event(events,'delayed_graph_update',now,node_count=len(nodes),state_count=len(paths),best_path=list(path),heuristic=True)
        for node,replacement in zip(nodes,path):
            if replacement is None or replacement==node.latest_track:continue
            scores=sorted([(self._voice(t,node.vector),t.identifier) for t in self._active()],reverse=True)
            score=self._voice(byid[replacement],node.vector)
            alternative=max([s for s,i in scores if i!=replacement],default=-1.)
            if score>=c.revision_confidence and score-alternative>=c.revision_margin:
                self._revise(node,replacement,now,'bounded arrived-evidence graph reconciliation',events)

    def _base_result(self,identifier,decision_id,evidence_id,start,end,now,events,reason,voice=None):
        track=next((t for t in self.tracks if t.identifier==identifier),None)
        scores=sorted((voice or {}).values(),reverse=True)
        label='Unknown' if identifier is None else 'Speaker_'+str(identifier)
        return {'anonymous_label':label,'display_label':label,'cluster_id':identifier,'tracker_id':identifier,
                'decision_id':decision_id,'first_decision_id':decision_id,'evidence_id':evidence_id,
                'state':'unknown' if track is None else ('committed' if track.committed else 'provisional'),
                'committed':bool(track and track.committed),'unique_evidence_sec':0. if track is None else track.unique_sec,
                'evidence_sec':0. if track is None else track.unique_sec,
                'disjoint_evidence_count':0 if track is None else track.disjoint_count,
                'observation_count':0 if track is None else track.observation_count,
                'prototype_version':None if track is None else track.version,
                'top1_score':scores[0] if scores else None,'top2_score':scores[1] if len(scores)>1 else None,
                'margin':scores[0]-scores[1] if len(scores)>1 else None,
                'source_start_sec':start,'source_end_sec':end,'available_at_sec':now,
                'reason':reason,'lineage':events}

    def update(self,embedding,source_start_sec,source_end_sec,available_at_sec,spatial=None,speech=True,overlap=False):
        """Consume a single arrived finite 192-D audio vector. No reference metadata is accepted.

        Source ends and availability must be monotone. Equal ends support a later
        longer window; exact repeated spans are rejected. Wall compute belongs to
        the caller's instrumentation, never silently shifts this common clock.
        """
        c=self.config
        start,end,now=map(float,(source_start_sec,source_end_sec,available_at_sec))
        if not all(math.isfinite(v) for v in (start,end,now)) or start<0 or end<=start or now<end-1e-8:
            raise ValueError('finite nonnegative source span must precede availability')
        if not .5-1e-8<=end-start<=c.max_window_sec+1e-8:raise ValueError('unsupported embedding window duration')
        if end<self.last_end-1e-8 or now<self.last_available-1e-8:raise ValueError('audio/availability clock cannot run backward')
        span=(round(start,9),round(end,9))
        if span in self.seen_spans:raise ValueError('duplicate source embedding span would double-use evidence')
        if type(speech) is not bool or type(overlap) is not bool:raise ValueError('speech/overlap gates must be boolean')
        vector=_unit(embedding)
        # Original control consumes the already-normalized ReDim value exactly as the old app does.
        if self.effective_mode=='original_common':vector=np.asarray(embedding,dtype=np.float32).reshape(-1).copy()
        self.last_end=end;self.last_available=now;self.seen_spans.append(span);self.count+=1
        decision_id='D%08d'%self.count;evidence_id='E%08d'%self.count;events=[]
        for retained in self._active():
            if retained.escrow is not None and now-retained.escrow['available']>c.escrow_timeout_sec:
                self._event(events,'prototype_escrow_expire',now,track_id=retained.identifier,pending_decision_id=retained.escrow['decision_id'])
                retained.escrow=None
            if retained.rollback is not None and now-retained.rollback['available']>c.revision_horizon_sec:
                retained.rollback=None
        if not speech or overlap:
            self._event(events,'audio_gate_reject',now,reason='overlap' if overlap else 'not_speech')
            return self._base_result(None,decision_id,evidence_id,start,end,now,events,'audio_gate_reject')
        if self.effective_mode in ('one_person','all_unknown'):
            track=None
            if self.effective_mode=='one_person':
                track=self.tracks[0] if self.tracks else self._new_track(vector,now,events)
                track.admit(start,end,c.max_window_sec)
                track.committed=track.unique_sec>=c.commit_evidence_sec and track.disjoint_count>=c.commit_disjoint_count
            self._event(events,'diagnostic_control_assignment',now,control=self.effective_mode)
            result=self._base_result(None if track is None else track.identifier,decision_id,evidence_id,start,end,now,events,'diagnostic_control')
            result['diagnostic_control']=True
            return result
        if self.effective_mode=='original_common':
            voice={t.identifier:self._voice(t,vector) for t in self._active()}
            if len(self.tracks)>=c.max_tracks and max(voice.values(),default=-1.)<c.cosine_threshold:
                self._event(events,'track_capacity_rejection',now,max_tracks=c.max_tracks)
                return self._base_result(None,decision_id,evidence_id,start,end,now,events,'original_control_capacity',voice)
            legacy=self.legacy.update(vector,end);identifier=legacy.cluster_id
            track=next((t for t in self.tracks if t.identifier==identifier),None)
            if track is None:track=self._new_track(vector,now,events)
            old=self.legacy.clusters[identifier-1]
            track.prototypes=[old.center.copy()]
            track.admit(start,end,c.max_window_sec)
            track.committed=track.unique_sec>=c.commit_evidence_sec and track.disjoint_count>=c.commit_disjoint_count
            result=self._base_result(identifier,decision_id,evidence_id,start,end,now,events,'original_common_scheduler_control',voice)
            for key in ('anonymous_label','display_label','state','top1_score','top2_score','margin'):
                result[key]=getattr(legacy,key)
            result['legacy_evidence_sec']=legacy.evidence_sec
            result['evidence_sec']=legacy.evidence_sec
            return result
        if self.effective_mode=='dual_memory':
            for track in self._active():
                dormant=end-track.last_end>c.dormancy_sec
                if dormant and not track.dormant:self._event(events,'track_dormant',now,track_id=track.identifier)
                track.dormant=dormant
        angle,quality,cue_reason=self._spatial(spatial,start,end,now,events)
        voice={t.identifier:self._voice(t,vector) for t in self._active()}
        quality=self._sensor(voice,angle,quality,start,end,now,events)
        scores,contribution=self._location_scores(voice,angle,quality,now)
        identifier,create,reason=self._select(vector,voice,scores,angle,quality,start,end,now,events)
        track=next((t for t in self.tracks if t.identifier==identifier),None)
        created=False
        if create:
            track=self._new_track(vector,now,events);identifier=None if track is None else track.identifier;created=track is not None
            # Start temporal models with the actually created branch rather than an impossible empty history.
            if track is not None and self.effective_mode=='bayes':self.hypotheses=[(0.,(identifier,))]
            if track is not None and self.effective_mode=='hsmm':self.hsmm_states={(identifier,1):0.};self.hsmm_last_end=end
            if track is not None and self.effective_mode=='global_assignment':
                self._global(vector,{identifier:1.},{identifier},start,end,now,events)
        if track is not None:
            if track.dormant:self._event(events,'track_reactivate',now,track_id=track.identifier);track.dormant=False
            increment,independent=track.admit(start,end,c.max_window_sec)
            self._event(events,'evidence_admit',now,track_id=identifier,evidence_id=evidence_id,unique_increment_sec=increment,
                        unique_evidence_sec=track.unique_sec,disjoint=independent,disjoint_evidence_count=track.disjoint_count)
            if not created:self._prototype(track,vector,start,end,now,decision_id,independent,angle,quality,events)
            if angle is not None and quality>0:
                alpha=c.location_learning_rate if self.effective_mode=='dual_memory' else 1.
                track.location=angle if track.location is None else (1.-alpha)*track.location+alpha*angle
                track.location_at=now
                self._event(events,'location_update',now,track_id=identifier,bearing_deg=track.location,reliability=quality)
            if not track.committed and track.unique_sec>=c.commit_evidence_sec and track.disjoint_count>=c.commit_disjoint_count and track.escrow is None:
                track.committed=True;self._event(events,'track_commit',now,track_id=identifier,unique_evidence_sec=track.unique_sec,disjoint_evidence_count=track.disjoint_count)
        node=_Node(evidence_id,decision_id,vector.copy(),start,end,now,identifier,identifier);self.nodes.append(node)
        if self.effective_mode=='delay_graph':self._graph(now,events)
        self.last_selected=identifier
        result=self._base_result(identifier,decision_id,evidence_id,start,end,now,events,reason,voice)
        # Disabled-cue modes emit identical operational decisions to their voice parent.
        if c.cues_enabled:
            result['cue']={'reason':cue_reason,'qualified_bearing_deg':angle,'reliability':quality,'sensor_credit':self.sensor_credit,
                           'location_score_contribution':{str(k):v for k,v in contribution.items()}}
        return result

    def snapshot(self):
        """Compact bounded state; does not expose or accept reference identities."""
        return {'mode':self.effective_mode,'decisions':self.count,'track_count':len(self.tracks),'operations':dict(sorted(self.operations.items())),
                'tracks':[{'tracker_id':t.identifier,'unique_evidence_sec':t.unique_sec,'disjoint_evidence_count':t.disjoint_count,
                           'committed':t.committed,'prototype_count':len(t.prototypes),'prototype_version':t.version,
                           'dormant':t.dormant,'location_deg':t.location,'escrow_pending':t.escrow is not None,'rollback_pending':t.rollback is not None,
                           'retained_intervals':len(t.ranges)} for t in self.tracks],
                'state_bounds':{'max_tracks':self.config.max_tracks,'max_prototypes_per_track':self.config.max_prototypes,
                                'retained_nodes':len(self.nodes),'max_revision_records':self.config.max_revision_records,
                                'hypotheses':len(self.hypotheses),'hsmm_states':len(self.hsmm_states),'global_groups':len(self.global_groups)},
                'sensor_credit':self.sensor_credit,'posterior_calibrated':False,
                'first_decisions_immutable':True,'clock':'caller-supplied arrived-audio availability; wall compute measured by caller'}


def decision_to_speaker(decision):
    from .contracts import SpeakerDecision
    return SpeakerDecision(**{key:decision.get(key) for key in ('anonymous_label','display_label','state','top1_score','top2_score','margin','evidence_sec','cluster_id')})
