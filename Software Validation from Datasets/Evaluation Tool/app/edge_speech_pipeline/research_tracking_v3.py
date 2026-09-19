"""S6C opt-in joint anonymous tracking. See README_RESEARCH_TRACKING_V3.md.

Only delivered embeddings and sensor observations enter this module. All joint
scores and tempered hypotheses are engineering scores, not calibrated person
probabilities. Names, reference boundaries and roster/person metadata are absent.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import asdict, dataclass, field, fields
import math
import sys
import numpy as np

from .research_tracking_v2 import S6BTrackingConfig, S6BTracker, _Track, _Node, _unit, _union

MODES = ('old_voice_gate', 'normalized_joint', 'reliability_joint',
         'hypothesis_joint', 'semimarkov_joint', 'bounded_global_joint',
         'quarantine_joint', 'shadow_gallery_joint')


@dataclass(frozen=True)
class S6CTrackingConfig(S6BTrackingConfig):
    mode: str = 'normalized_joint'
    lifecycle_policy: str = 'retire_archive'
    max_tracks: int = 64
    archive_capacity: int = 128
    retirement_sec: float = 30.
    provisional_retirement_sec: float = 10.
    pressure_retirement_sec: float = 5.
    archive_reentry_cosine: float = .70
    archive_reentry_margin: float = .05
    voice_score_scale: float = .15
    joint_spatial_weight: float = .60
    new_hypothesis_bias: float = 0.
    unresolved_hypothesis_bias: float = -.20
    joint_margin: float = .10
    conflict_new_bonus: float = .60
    strong_voice_spatial_scale: float = .10
    mature_only_prototype_updates: bool = True
    minimum_clean_fraction: float = .50
    clean_shadow_count: int = 2
    clean_shadow_cosine: float = .70
    structural_split_enabled: bool = False
    structural_merge_enabled: bool = False
    structural_merge_cosine: float = .90
    structural_merge_disjoint_count: int = 3

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError('unknown S6C tracker mode')
        # Reuse established numeric/boolean validation; keep the old class and
        # old source unchanged. Its mode-specific inactive map does not apply.
        base = {f.name: getattr(self, f.name) for f in fields(S6BTrackingConfig)}
        base['mode'] = 'adaptive' if self.cues_enabled else 'voice'
        S6BTrackingConfig(**base)
        if self.lifecycle_policy not in ('none', 'retire', 'retire_archive'):
            raise ValueError('unknown lifecycle policy')
        for name in ('mature_only_prototype_updates', 'structural_split_enabled', 'structural_merge_enabled'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(name + ' must be boolean')
        for name, lo, hi in (('archive_capacity', 0, 256), ('clean_shadow_count', 2, 8),
                             ('structural_merge_disjoint_count', 2, 16)):
            value = getattr(self, name)
            if type(value) is not int or not lo <= value <= hi:
                raise ValueError(name + ' outside bounded integer range')
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, (float, int)) and not isinstance(value, bool) and not math.isfinite(value):
                raise ValueError(f.name + ' must be finite')
        for name in ('retirement_sec', 'provisional_retirement_sec', 'pressure_retirement_sec', 'voice_score_scale'):
            if getattr(self, name) <= 0:
                raise ValueError(name + ' must be positive')
        if self.retirement_sec < self.dormancy_sec or self.pressure_retirement_sec < self.dormancy_sec:
            raise ValueError('retirement must follow dormancy')
        for name in ('archive_reentry_cosine', 'clean_shadow_cosine', 'structural_merge_cosine'):
            if not self.prototype_update_threshold <= getattr(self, name) <= 1:
                raise ValueError(name + ' must be a conservative voice cosine')
        for name in ('archive_reentry_margin', 'joint_margin', 'minimum_clean_fraction', 'strong_voice_spatial_scale'):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(name + ' must be in [0,1]')
        if not 0 <= self.joint_spatial_weight <= 3 or not 0 <= self.conflict_new_bonus <= 3:
            raise ValueError('bounded joint score weights required')
        if not -3 <= self.new_hypothesis_bias <= 3 or not -3 <= self.unresolved_hypothesis_bias <= 3:
            raise ValueError('bounded hypothesis biases required')
        if self.structural_split_enabled and self.mode != 'quarantine_joint':
            raise ValueError('structural split requires quarantine_joint')

    @classmethod
    def from_mapping(cls, value):
        if not isinstance(value, dict):
            raise ValueError('tracker settings must be an object')
        unknown = set(value) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError('unknown tracker settings: ' + ','.join(sorted(unknown)))
        result = cls(**value)
        inactive = result.field_usage()['nondefault_inactive_fields']
        if inactive:
            raise ValueError('nondefault inactive tracker settings: ' + ','.join(inactive))
        return result

    def validated(self):
        self.__post_init__()
        return self

    def validate(self):
        return self.validated()

    def to_dict(self):
        return asdict(self)

    def field_usage(self):
        active = {'mode','cues_enabled','cosine_threshold','ambiguity_margin','prototype_update_threshold',
                  'commit_evidence_sec','commit_disjoint_count','max_tracks','max_window_sec','voice_learning_rate',
                  'max_prototypes','prototype_novelty_cosine','max_revision_records','lifecycle_policy','dormancy_sec',
                  'mature_only_prototype_updates','minimum_clean_fraction','revision_enabled','revision_horizon_sec',
                  'structural_merge_enabled'}
        if self.lifecycle_policy != 'none':
            active |= {'retirement_sec','provisional_retirement_sec','pressure_retirement_sec'}
        if self.lifecycle_policy == 'retire_archive':
            active |= {'archive_capacity','archive_reentry_cosine','archive_reentry_margin'}
        if self.mode != 'old_voice_gate':
            active |= {'voice_score_scale','new_hypothesis_bias','unresolved_hypothesis_bias','joint_margin',
                       'conflict_cosine_floor','reliable_voice_cosine'}
            if self.mode in ('hypothesis_joint','semimarkov_joint','bounded_global_joint'):
                active.discard('joint_margin')
        if self.cues_enabled:
            active |= {'direction_max_age_sec','direction_match_deg','direction_change_deg','direction_persistence_sec',
                       'direction_continuity_gap_sec','minimum_spatial_reliability','position_decay_sec',
                       'location_learning_rate','sensor_quarantine_enabled'}
            active |= {'spatial_weight'} if self.mode == 'old_voice_gate' else {
                'joint_spatial_weight','conflict_new_bonus','strong_voice_spatial_scale'}
            if self.sensor_quarantine_enabled:
                active |= {'contradiction_count','recovery_count','quarantine_hold_sec','reliable_voice_cosine','conflict_cosine_floor'}
        if self.mode in ('hypothesis_joint','semimarkov_joint','bounded_global_joint'):
            active |= {'temporal_temperature','continuity_prior','posterior_min_confidence','hypothesis_count','hypothesis_horizon'}
        if self.mode == 'semimarkov_joint':
            active |= {'hsmm_min_duration_sec','hsmm_max_duration_sec','hsmm_switch_penalty'}
        if self.mode == 'bounded_global_joint':
            active |= {'graph_max_nodes','graph_switch_cost','revision_confidence','revision_margin','global_consistency_weight'}
        if self.mode == 'quarantine_joint':
            active |= {'rollback_margin','escrow_agreement_cosine','escrow_timeout_sec','structural_split_enabled'}
        if self.mode == 'shadow_gallery_joint':
            active |= {'clean_shadow_count','clean_shadow_cosine'}
        if self.structural_merge_enabled:
            active |= {'structural_merge_cosine','structural_merge_disjoint_count'}
        inactive = {f.name: getattr(self,f.name) for f in fields(self) if f.name not in active}
        changed = [f.name for f in fields(self) if f.name in inactive and getattr(self,f.name) != f.default]
        return {'effective_mode': self.mode, 'active_fields': sorted(active), 'inactive_fields': inactive,
                'nondefault_inactive_fields': changed,
                'conditional_note': 'Code reachability only; observed counters establish dataset activation.'}


@dataclass
class _CTrack(_Track):
    mature_count: int = 0
    mature_disjoint_end: float = -math.inf
    clean_shadow: list = field(default_factory=list)
    shadow_end: float = -math.inf
    archive_at: float | None = None


class S6CTracker(S6BTracker):
    """Finite online state, monotonic external track IDs, joint new/known/unknown.

    Shared v2 primitives are limited to finite vector normalization, interval
    union, cue admission/sensor quarantine and append-only decision formatting.
    The old voice eligibility restriction is an explicit control in this class.
    """
    def __init__(self, config=None):
        config = (config or S6CTrackingConfig()).validated()
        super().__init__(S6BTrackingConfig())
        self.config = config
        self.mode = self.effective_mode = config.mode
        self.tracks = []
        self.archive = OrderedDict()
        self.nodes = deque(maxlen=config.max_revision_records)
        self.beam = []
        self.last_selected_start = None
        self.retired_total = 0
        self.peak_live = 0
        self.peak_archive = 0
        self.blocked_evidence_sec = 0.
        self.blocked_end = -math.inf
        self.total_comparisons = 0
        self.max_comparisons = 0
        self.seen_ids = deque(maxlen=512)

    def _retire(self, track, now, events, reason, archive=True):
        self.tracks.remove(track)
        track.retired = True
        track.dormant = True
        track.archive_at = now
        track.escrow = track.rollback = None
        track.clean_shadow.clear()
        # Preserve overlap-relevant recent intervals even in an archive. A
        # permitted short retirement TTL cannot turn reused samples into new
        # duration on reentry; _admit compacts them against the new source end.
        self.retired_total += 1
        self._event(events, 'track_retire', now, track_id=track.identifier, reason=reason)
        if archive and self.config.lifecycle_policy == 'retire_archive' and self.config.archive_capacity:
            self.archive[track.identifier] = track
            while len(self.archive) > self.config.archive_capacity:
                identifier, _ = self.archive.popitem(last=False)
                self._event(events, 'archive_evict', now, track_id=identifier, external_id_recycled=False)
            self.peak_archive = max(self.peak_archive, len(self.archive))

    def _lifecycle(self, end, now, events):
        c = self.config
        for track in list(self.tracks):
            idle = end-track.last_end
            if idle > c.dormancy_sec and not track.dormant:
                track.dormant = True
                self._event(events, 'track_dormant', now, track_id=track.identifier, source_idle_sec=idle)
            ttl = c.retirement_sec if track.committed else c.provisional_retirement_sec
            if c.lifecycle_policy != 'none' and idle >= ttl:
                self._retire(track, now, events, 'source_inactivity')
            elif track.rollback is not None and now-track.rollback['available'] > c.revision_horizon_sec:
                track.rollback = None
            if track.escrow is not None and now-track.escrow['available'] > c.escrow_timeout_sec:
                self._event(events, 'prototype_escrow_expire', now, track_id=track.identifier)
                track.escrow = None

    def _capacity(self, end, now, events):
        c = self.config
        if len(self.tracks) < c.max_tracks:
            return True
        if c.lifecycle_policy != 'none':
            eligible = [t for t in self.tracks if t.dormant and end-t.last_end >= c.pressure_retirement_sec]
            if eligible:
                victim = min(eligible, key=lambda t:(t.committed,t.last_end,t.identifier))
                self._retire(victim, now, events, 'capacity_pressure')
                return True
        self._event(events, 'track_capacity_rejection', now, max_tracks=c.max_tracks,
                    active_count=sum(not t.dormant for t in self.tracks), dormant_count=sum(t.dormant for t in self.tracks))
        return False

    def _create(self, vector, end, now, events):
        if not self._capacity(end, now, events):
            return None
        track = _CTrack(self.next_track, [vector.copy()], now, end)
        self.next_track += 1
        self.tracks.append(track)
        self.peak_live = max(self.peak_live,len(self.tracks))
        self._event(events, 'track_create', now, track_id=track.identifier, external_id_recycled=False)
        return track

    def _archive_candidate(self, vector, voice, end, now, events):
        if not self.archive:
            return None
        ranks = sorted(((self._voice(t,vector),t.identifier) for t in self.archive.values()), reverse=True)
        self.total_comparisons += sum(len(t.prototypes) for t in self.archive.values())
        score, identifier = ranks[0]
        alternative = max([x[0] for x in ranks[1:]]+list(voice.values()), default=-1.)
        c = self.config
        self._event(events, 'archive_search', now, count=len(ranks), top1_score=score,
                    margin=score-alternative, candidate_track_id=identifier)
        if score < c.archive_reentry_cosine or score-alternative < c.archive_reentry_margin:
            return None
        track = self.archive.pop(identifier)
        track.retired = track.dormant = False
        # Old unique seconds are retained once, but old support cannot overlap a
        # current window. Freeze only at retirement; current source is monotone.
        self.tracks.append(track)
        self._event(events, 'archive_reactivate', now, track_id=identifier, score=score,
                    lifetime_external_id_preserved=True)
        return track

    def _clean(self, intervals, start, end):
        if intervals is None:
            return [[start,end]], 'full_span_gate_only_not_phonetic_truth'
        if not isinstance(intervals,(list,tuple)):
            raise ValueError('clean intervals must be explicit interval pairs')
        clean = []
        for pair in intervals:
            if not isinstance(pair,(list,tuple)) or len(pair) != 2:
                raise ValueError('invalid clean interval')
            a,b = map(float,pair)
            if not all(math.isfinite(v) for v in (a,b)) or a < start-1e-8 or b > end+1e-8 or b <= a:
                raise ValueError('clean support must be within actual waveform support')
            clean.append([max(start,a),min(end,b)])
        return _union(clean), 'arrived_segmentation_estimate'

    def _admit(self, track, intervals, start, end, kind, now, events):
        previous = track.unique_sec
        cutoff = end-self.config.max_window_sec
        keep = []
        for a,b in track.ranges:
            if b <= cutoff:
                track.frozen_unique_sec += b-a
            elif a < cutoff:
                track.frozen_unique_sec += cutoff-a
                keep.append([cutoff,b])
            else:
                keep.append([a,b])
        track.ranges = _union(keep+intervals)
        independent = bool(intervals) and start >= track.disjoint_end-1e-9
        if independent:
            track.disjoint_count += 1
            track.disjoint_end = end
        mature_independent = bool(intervals) and kind == 'mature' and start >= track.mature_disjoint_end-1e-9
        if mature_independent:
            track.mature_count += 1
            track.mature_disjoint_end = end
        track.last_end = end
        track.observation_count += 1
        increment = max(0.,track.unique_sec-previous)
        self._event(events,'evidence_admit',now,track_id=track.identifier,unique_increment_sec=increment,
                    unique_evidence_sec=track.unique_sec,disjoint=independent,
                    disjoint_evidence_count=track.disjoint_count,evidence_kind=kind,
                    mature_disjoint=mature_independent,mature_disjoint_count=track.mature_count)
        return mature_independent if kind == 'mature' else independent

    def _joint_scores(self, voice, angle, quality, start, end, now, events):
        c = self.config
        best_voice = max(voice.values(),default=-1.)
        scores = {}
        details = {}
        conflict_bonus = 0.
        for track in self.tracks:
            cosine = voice[track.identifier]
            if cosine < c.conflict_cosine_floor:
                self._event(events,'severe_voice_exclusion',now,track_id=track.identifier,cosine=cosine)
                continue
            audio_score = (cosine-c.cosine_threshold)/c.voice_score_scale
            cue_score = 0.
            distance = None
            reliability = 0.
            if angle is not None and quality > 0 and track.location is not None:
                distance = abs(angle-track.location)
                reliability = quality*math.exp(-max(0.,now-track.location_at)/c.position_decay_sec)
                strong_scale = c.strong_voice_spatial_scale if cosine >= c.reliable_voice_cosine else 1.
                if c.mode != 'normalized_joint':
                    strong_scale *= min(1.,max(.1,(c.reliable_voice_cosine-cosine)/max(.01,c.reliable_voice_cosine-c.conflict_cosine_floor)))
                persistence = min(1.,max(0.,now-self.pending_since)/c.direction_persistence_sec)
                match = 2.*math.exp(-.5*(distance/c.direction_match_deg)**2)-1.
                cue_score = c.joint_spatial_weight*reliability*strong_scale*match
                if distance >= c.direction_change_deg and cosine < c.reliable_voice_cosine:
                    conflict_bonus = max(conflict_bonus,c.conflict_new_bonus*reliability*persistence)
            score = audio_score+cue_score
            scores[track.identifier] = score
            details[str(track.identifier)] = dict(cosine=cosine,voice_score=audio_score,cue_score=cue_score,
                combined_score=score,bearing_distance_deg=distance,effective_reliability=reliability,
                borderline=cosine<c.cosine_threshold)
        scores['NEW'] = c.new_hypothesis_bias + conflict_bonus
        scores['UNRESOLVED'] = c.unresolved_hypothesis_bias
        self._event(events,'joint_hypothesis_scores',now,existing=details,new_score=scores['NEW'],
                    unresolved_score=scores['UNRESOLVED'],best_voice_cosine=best_voice,
                    score_scale='voice cosine centered at association threshold / voice_score_scale; additive bounded cue score',
                    calibrated_probability=False)
        return scores, details

    def _choose(self, scores, end, now, events):
        c = self.config
        def rank(rows):
            return sorted(rows, key=lambda item:(-item[1],str(item[0])))
        ranked = rank(scores.items())
        if c.mode in ('hypothesis_joint','semimarkov_joint','bounded_global_joint'):
            # Finite beam over arrived observations. NEW is a transient branch
            # rebound to the real created ID after acceptance; never a person ID.
            prior = self.beam or [(0.,())]
            next_beam=[]
            for cost,path in prior:
                last=path[-1] if path else None
                for candidate,score in scores.items():
                    continuity = math.log(c.continuity_prior if last == candidate else 1.-c.continuity_prior)
                    penalty=0.
                    if c.mode == 'semimarkov_joint' and self.last_selected_start is not None:
                        dwell=end-self.last_selected_start
                        if candidate != self.last_selected and dwell < c.hsmm_min_duration_sec:
                            penalty=c.hsmm_switch_penalty*(1.-dwell/c.hsmm_min_duration_sec)
                        if candidate == self.last_selected and dwell > c.hsmm_max_duration_sec:
                            penalty=c.hsmm_switch_penalty*min(1.,(dwell-c.hsmm_max_duration_sec)/c.hsmm_max_duration_sec)
                    next_beam.append((cost+score/c.temporal_temperature+continuity-penalty,
                                      (path+(candidate,))[-c.hypothesis_horizon:]))
            next_beam.sort(key=lambda x:(-x[0],str(x[1])))
            top=next_beam[:c.hypothesis_count]
            norm=top[0][0]
            self.beam=[(a-norm,b) for a,b in top]
            marginal={k:0. for k in scores}
            for cost,path in self.beam:
                marginal[path[-1]] += math.exp(max(-700.,cost))
            total=sum(marginal.values())
            ranked=rank((key,value/total) for key,value in marginal.items())
            self._event(events,'bounded_temporal_hypotheses',now,mode=c.mode,beam_size=len(self.beam),
                        posterior={str(k):v for k,v in ranked},calibrated_probability=False)
            if ranked[0][1] < c.posterior_min_confidence:
                return 'UNRESOLVED','temporal_hypothesis_uncertain'
        elif len(ranked)>1 and ranked[0][1]-ranked[1][1] < c.joint_margin:
            return 'UNRESOLVED','joint_hypothesis_ambiguous'
        return ranked[0][0],'joint_competing_hypotheses'

    def _update_prototype(self, track, vector, start, end, now, kind, independent, decision_id, events):
        c = self.config
        if not independent or (c.mature_only_prototype_updates and kind != 'mature'):
            self._event(events,'prototype_update_suppressed',now,track_id=track.identifier,
                        reason='non_disjoint' if not independent else 'short_provisional_only')
            return
        similarity=self._voice(track,vector)
        if c.mode == 'shadow_gallery_joint':
            if start >= track.shadow_end-1e-9:
                if track.clean_shadow and float(np.dot(track.clean_shadow[0],vector)) < c.clean_shadow_cosine:
                    track.clean_shadow.clear()
                    self._event(events,'clean_shadow_restart',now,track_id=track.identifier)
                track.clean_shadow.append(vector.copy())
                track.clean_shadow=track.clean_shadow[-c.clean_shadow_count:]
                track.shadow_end=end
                if len(track.clean_shadow) >= c.clean_shadow_count:
                    track.prototypes[0]=_unit(np.sum(track.clean_shadow,axis=0))
                    track.version+=1
                    self._event(events,'clean_shadow_promote',now,track_id=track.identifier,
                                evidence_count=len(track.clean_shadow),prototype_version=track.version)
                    return
            self._event(events,'clean_shadow_pending',now,track_id=track.identifier,
                        evidence_count=len(track.clean_shadow),live_prototype_unchanged=True)
            return
        if c.mode == 'quarantine_joint':
            if track.rollback is not None:
                old=track.rollback
                previous=max(float(np.dot(p,vector)) for p in old['prototypes'])
                if start >= old['end']-1e-9 and previous-similarity >= c.rollback_margin:
                    track.prototypes=[p.copy() for p in old['prototypes']]
                    track.version+=1
                    track.rollback=None
                    self._event(events,'prototype_rollback',now,track_id=track.identifier,prototype_version=track.version)
                    if c.structural_split_enabled:
                        child=self._create(old['vector'],end,now,events)
                        if child is not None:
                            child.last_end=old['end']
                            self._event(events,'structural_track_split',now,parent_track_id=track.identifier,
                                        child_track_id=child.identifier,reason='disjoint later voice supports pre-update prototype')
                            for node in self.nodes:
                                if node.decision_id == old['decision_id']:
                                    self._revise(node,child.identifier,now,'bounded structural split',events)
                    return
            pending=track.escrow
            if pending is not None and start >= pending['end']-1e-9:
                if float(np.dot(pending['vector'],vector)) >= c.escrow_agreement_cosine:
                    track.rollback=dict(prototypes=[p.copy() for p in track.prototypes],vector=pending['vector'].copy(),
                                        end=end,available=now,decision_id=pending['decision_id'])
                    proposal=_unit(pending['vector']+vector)
                    track.prototypes[0]=_unit((1.-c.voice_learning_rate)*track.prototypes[0]+c.voice_learning_rate*proposal)
                    track.version+=1
                    track.escrow=None
                    self._event(events,'prototype_escrow_release',now,track_id=track.identifier,prototype_version=track.version)
                    return
                self._event(events,'prototype_escrow_reject',now,track_id=track.identifier)
                track.escrow=None
            if similarity >= c.prototype_update_threshold:
                track.escrow=dict(vector=vector.copy(),end=end,available=now,decision_id=decision_id)
                self._event(events,'prototype_escrow_hold',now,track_id=track.identifier)
            return
        if similarity < c.prototype_update_threshold:
            self._event(events,'prototype_voice_guard_reject',now,track_id=track.identifier,cosine=similarity)
            return
        if similarity < c.prototype_novelty_cosine and len(track.prototypes)<c.max_prototypes:
            track.prototypes.append(vector.copy())
            track.version+=1
            self._event(events,'prototype_slot_add',now,track_id=track.identifier,slot=len(track.prototypes)-1)
        else:
            slot=int(np.argmax([float(np.dot(p,vector)) for p in track.prototypes]))
            track.prototypes[slot]=_unit((1.-c.voice_learning_rate)*track.prototypes[slot]+c.voice_learning_rate*vector)
            track.version+=1
            self._event(events,'prototype_update',now,track_id=track.identifier,slot=slot,prototype_version=track.version)

    def _reconcile(self, now, events):
        c=self.config
        nodes=[n for n in self.nodes if now-n.available<=c.revision_horizon_sec][-c.graph_max_nodes:]
        if not c.revision_enabled or len(nodes)<2 or not self.tracks:
            return
        paths=[(0.,())]
        for node in nodes:
            voice={t.identifier:self._voice(t,node.vector) for t in self.tracks}
            possible={k:(v-c.cosine_threshold)/c.voice_score_scale for k,v in voice.items() if v>=c.conflict_cosine_floor}
            possible[None]=c.unresolved_hypothesis_bias
            expanded=[]
            for cost,path in paths:
                for identifier,score in possible.items():
                    penalty=c.graph_switch_cost if path and identifier!=path[-1] else 0.
                    consistency=0.
                    if len(path)>0 and identifier is not None and identifier==path[-1]:
                        cosine=float(np.dot(nodes[len(path)-1].vector,node.vector))
                        consistency=c.global_consistency_weight*(2.*max(0.,cosine)-1.)
                    expanded.append((cost+score-penalty+consistency,path+(identifier,)))
            expanded.sort(key=lambda x:(-x[0],str(x[1])))
            paths=expanded[:c.hypothesis_count]
        self._event(events,'bounded_global_reconciliation',now,node_count=len(nodes),beam_size=len(paths),best_path=list(paths[0][1]))
        for node,replacement in zip(nodes,paths[0][1]):
            if replacement is None or replacement == node.latest_track:
                continue
            voices=sorted(((self._voice(t,node.vector),t.identifier) for t in self.tracks),reverse=True)
            chosen=next(v for v,i in voices if i==replacement)
            other=max((v for v,i in voices if i!=replacement),default=-1.)
            if chosen>=c.revision_confidence and chosen-other>=c.revision_margin:
                self._revise(node,replacement,now,'bounded arrived-voice global reconciliation',events)

    def _merge(self, track, now, events):
        c=self.config
        if not c.structural_merge_enabled or track.mature_count<c.structural_merge_disjoint_count:
            return track
        candidates=[]
        for other in self.tracks:
            if other is track or other.mature_count<c.structural_merge_disjoint_count or not other.dormant:
                continue
            # Require a silent-source gap. Similar bearing is never a merge vote.
            similarity=max(float(np.dot(a,b)) for a in track.prototypes for b in other.prototypes)
            if similarity>=c.structural_merge_cosine:
                candidates.append((similarity,other))
        if not candidates:
            return track
        _,other=max(candidates,key=lambda x:(x[0],-x[1].identifier))
        survivor,removed=sorted((track,other),key=lambda t:t.identifier)
        # Do not add historical clean durations: compressed past supports may
        # overlap. Retain the conservative larger amount and explicit lineage.
        retained_end=max(track.last_end,other.last_end)
        cutoff=retained_end-c.max_window_sec
        recent=_union([[max(cutoff,a),b] for a,b in track.ranges+other.ranges if b>cutoff])
        recent_sec=sum(b-a for a,b in recent)
        conservative_total=max(track.unique_sec,other.unique_sec,recent_sec)
        survivor.frozen_unique_sec=max(0.,conservative_total-recent_sec)
        survivor.ranges=recent
        survivor.disjoint_count=max(track.disjoint_count,other.disjoint_count)
        survivor.mature_count=max(track.mature_count,other.mature_count)
        survivor.disjoint_end=max(track.disjoint_end,other.disjoint_end)
        survivor.mature_disjoint_end=max(track.mature_disjoint_end,other.mature_disjoint_end)
        survivor.prototypes=(survivor.prototypes+removed.prototypes)[:c.max_prototypes]
        survivor.last_end=max(track.last_end,other.last_end)
        survivor.dormant=False
        self._retire(removed,now,events,'structural_merge',archive=False)
        self._event(events,'structural_track_merge',now,from_track_id=removed.identifier,to_track_id=survivor.identifier,
                    external_id_recycled=False,evidence_duration_policy='conservative maximum, no compressed-support addition')
        for node in self.nodes:
            if node.latest_track==removed.identifier:
                self._revise(node,survivor.identifier,now,'bounded structural merge',events)
        return survivor

    def update(self,embedding,source_start_sec,source_end_sec,available_at_sec,spatial=None,speech=True,
               overlap=False,evidence_kind='mature',clean_intervals=None,observation_id=None):
        c=self.config
        start,end,now=map(float,(source_start_sec,source_end_sec,available_at_sec))
        if not all(math.isfinite(x) for x in (start,end,now)) or start<0 or end<=start or now<end-1e-8:
            raise ValueError('finite arrived embedding support required')
        if not .5-1e-8<=end-start<=c.max_window_sec+1e-8:
            raise ValueError('unsupported contiguous embedding window')
        if end<self.last_end-1e-8 or now<self.last_available-1e-8:
            raise ValueError('source/availability cannot run backward')
        span=(round(start,9),round(end,9))
        if span in self.seen_spans or observation_id is not None and observation_id in self.seen_ids:
            raise ValueError('duplicate embedding support or observation identity')
        if evidence_kind not in ('short','mature') or type(speech) is not bool or type(overlap) is not bool:
            raise ValueError('invalid evidence role/audio gate')
        vector=_unit(embedding)
        clean,clean_scope=self._clean(clean_intervals,start,end)
        self.seen_spans.append(span)
        if observation_id is not None:
            self.seen_ids.append(observation_id)
        self.last_end=end
        self.last_available=now
        self.count+=1
        decision_id='D%08d'%self.count
        evidence_id=str(observation_id) if observation_id is not None else 'E%08d'%self.count
        events=[]
        self._lifecycle(end,now,events)
        clean_sec=sum(b-a for a,b in clean)
        if not speech or overlap or clean_sec/(end-start)<c.minimum_clean_fraction:
            self._event(events,'audio_gate_reject',now,reason='overlap' if overlap else ('not_speech' if not speech else 'insufficient_clean_support'))
            result=self._base_result(None,decision_id,evidence_id,start,end,now,events,'audio_gate_reject')
            result.update(evidence_kind=evidence_kind,clean_intervals=clean,clean_support_scope=clean_scope)
            return result
        angle,quality,cue_reason=self._spatial(spatial,start,end,now,events)
        voice={t.identifier:self._voice(t,vector) for t in self.tracks}
        comparisons=sum(len(t.prototypes) for t in self.tracks)
        self.total_comparisons+=comparisons
        self.max_comparisons=max(self.max_comparisons,comparisons)
        quality=self._sensor(voice,angle,quality,start,end,now,events)
        self._event(events,'cue_authority_admission',now,reason=cue_reason,angle_deg=angle,reliability=quality)
        scores={}
        details={}
        if c.mode=='old_voice_gate':
            eligible={k:v for k,v in voice.items() if v>=c.cosine_threshold}
            for t in self.tracks:
                if t.identifier in eligible and angle is not None and quality>0 and t.location is not None:
                    eligible[t.identifier]+=c.spatial_weight*quality*math.exp(-.5*((angle-t.location)/c.direction_match_deg)**2)
            ranked=sorted(eligible,key=lambda i:(-eligible[i],i))
            if not ranked:
                choice='NEW'
            elif len(ranked)>1 and eligible[ranked[0]]-eligible[ranked[1]]<c.ambiguity_margin:
                choice='UNRESOLVED'
            else:
                choice=ranked[0]
            reason='explicit_old_voice_eligibility_gate'
            self._event(events,'old_voice_gate_selection',now,eligible_ids=ranked,choice=choice)
        else:
            scores,details=self._joint_scores(voice,angle,quality,start,end,now,events)
            choice,reason=self._choose(scores,end,now,events)
        track=next((t for t in self.tracks if t.identifier==choice),None)
        created=False
        if choice=='NEW':
            if self._capacity(end,now,events):
                track=self._archive_candidate(vector,voice,end,now,events)
                if track is None:
                    track=self._create(vector,end,now,events)
                    created=track is not None
            if track is None:
                increment=sum(max(0.,b-max(a,self.blocked_end)) for a,b in clean)
                self.blocked_evidence_sec+=increment
                self.blocked_end=max(self.blocked_end,end)
        identifier=None if track is None else track.identifier
        if self.beam and choice=='NEW':
            replacement=identifier if identifier is not None else 'UNRESOLVED'
            self.beam=[(cost,path[:-1]+(replacement,) if path and path[-1]=='NEW' else path) for cost,path in self.beam]
        if track is not None:
            if track.dormant:
                track.dormant=False
                self._event(events,'track_reactivate',now,track_id=identifier)
            independent=self._admit(track,clean,start,end,evidence_kind,now,events)
            if not created:
                self._update_prototype(track,vector,start,end,now,evidence_kind,independent,decision_id,events)
            if angle is not None and quality>0:
                if track.location is not None and abs(angle-track.location)>=c.direction_change_deg and voice.get(identifier,1.)>=c.reliable_voice_cosine:
                    self._event(events,'strong_voice_relocation',now,track_id=identifier,old_bearing_deg=track.location,new_bearing_deg=angle)
                track.location=angle if track.location is None else (1.-c.location_learning_rate)*track.location+c.location_learning_rate*angle
                track.location_at=now
                self._event(events,'location_update',now,track_id=identifier,bearing_deg=track.location,reliability=quality)
            if not track.committed and track.unique_sec>=c.commit_evidence_sec and track.disjoint_count>=c.commit_disjoint_count and track.escrow is None:
                track.committed=True
                self._event(events,'track_commit',now,track_id=identifier,unique_evidence_sec=track.unique_sec,disjoint_count=track.disjoint_count)
            track=self._merge(track,now,events)
            identifier=track.identifier
        if identifier!=self.last_selected:
            self.last_selected_start=start
        self.last_selected=identifier
        self.nodes.append(_Node(evidence_id,decision_id,vector.copy(),start,end,now,identifier,identifier))
        if c.mode=='bounded_global_joint':
            self._reconcile(now,events)
        result=self._base_result(identifier,decision_id,evidence_id,start,end,now,events,reason,voice)
        result.update(evidence_kind=evidence_kind,clean_intervals=clean,clean_support_scope=clean_scope,
                      joint_choice=choice,joint_scores={str(k):v for k,v in scores.items()},
                      cue={'reason':cue_reason,'qualified_bearing_deg':angle,'reliability':quality,
                           'sensor_credit':self.sensor_credit,'candidate_contributions':details},
                      lifecycle_counts=self._counts())
        return result

    def _counts(self):
        return dict(active=sum(not t.dormant for t in self.tracks),dormant=sum(t.dormant for t in self.tracks),
                    provisional=sum(not t.committed for t in self.tracks),live=len(self.tracks),archive=len(self.archive),
                    cumulative_retirements=self.retired_total,lifetime_external_ids=self.next_track-1,
                    prototypes=sum(len(t.prototypes) for t in self.tracks)+sum(len(t.prototypes) for t in self.archive.values()))

    def scheduling_state(self, now):
        """Bounded online state, published only by the owning causal scheduler.

        A consumer must use a released snapshot stamped no later than its source
        dispatch. Calling this on a future mutable tracker is not cache-safe.
        """
        now=float(now)
        if not math.isfinite(now) or now < self.last_available-1e-8:
            raise ValueError('scheduling state must not request a past view of mutable state')
        return [dict(track_id=t.identifier,state='dormant' if t.dormant else ('committed' if t.committed else 'provisional'),
                     unique_clean_sec=t.unique_sec,disjoint_count=t.disjoint_count,mature_disjoint_count=t.mature_count,
                     last_evidence_sec=t.last_end,snapshot_available_at_sec=now) for t in self.tracks]

    def snapshot(self):
        base=super().snapshot()
        retained=list(self.tracks)+list(self.archive.values())
        arrays=sum(p.nbytes for t in retained for p in t.prototypes)
        arrays+=sum(p.nbytes for t in retained for p in t.clean_shadow)
        arrays+=sum(n.vector.nbytes for n in self.nodes)
        arrays+=sum((t.escrow['vector'].nbytes if t.escrow else 0)+
                    (sum(p.nbytes for p in t.rollback['prototypes'])+t.rollback['vector'].nbytes if t.rollback else 0) for t in retained)
        overhead=sum(sys.getsizeof(t)+sys.getsizeof(t.__dict__)+sys.getsizeof(t.ranges)+sys.getsizeof(t.prototypes) for t in retained)
        base.update(schema='edge-s6c-tracker-state.v1',counts=self._counts(),peak_live=self.peak_live,peak_archive=self.peak_archive,
                    archive=[dict(tracker_id=t.identifier,committed=t.committed,last_source_end_sec=t.last_end,
                                  prototype_count=len(t.prototypes),unique_evidence_sec=t.unique_sec) for t in self.archive.values()],
                    blocked_unique_evidence_sec=self.blocked_evidence_sec,prototype_comparisons=self.total_comparisons,
                    max_live_prototype_comparisons_per_observation=self.max_comparisons,
                    state_bytes=dict(array_payload=arrays,shallow_object_estimate=overhead,
                                     scope='not recursive Python heap/RSS; native endurance independently measures process memory'),
                    state_bounds=dict(max_live_tracks=self.config.max_tracks,max_archive_tracks=self.config.archive_capacity,
                                      max_prototypes_per_track=self.config.max_prototypes,max_revision_records=self.config.max_revision_records,
                                      max_hypotheses=self.config.hypothesis_count,max_hypothesis_horizon=self.config.hypothesis_horizon,
                                      max_seen_spans=256,max_seen_observation_ids=512,lifetime_ids_monotonic_not_recycled=True),
                    profile=self.config.to_dict(),effective_fields=self.config.field_usage())
        return base
