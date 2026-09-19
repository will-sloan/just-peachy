"""Opt-in causal anonymous tracking policies. See README_RESEARCH_TRACKING.md.

No reference text, identity, room, source schedule or future samples are inputs.
Every timestamp is on one caller-declared availability axis, in seconds.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from collections import deque
import math
import numpy as np

MODES = ('voice_time', 'angle_diagnostic', 'sustained_angle',
         'decaying_memory', 'reliability_adaptive')


@dataclass(frozen=True)
class TrackingConfig:
    mode: str = 'voice_time'
    cosine_threshold: float = .35
    ambiguity_margin: float = .03
    commit_evidence_sec: float = 1.0
    prototype_update_threshold: float = .45
    max_tracks: int = 16
    direction_match_deg: float = 25.0
    direction_change_deg: float = 35.0
    direction_persistence_sec: float = .75
    direction_max_age_sec: float = .25
    position_decay_sec: float = 12.0
    spatial_weight: float = .12
    conflict_cosine_floor: float = .20
    reconciliation_enabled: bool = True
    revision_horizon_sec: float = 2.0
    reconciliation_cosine: float = .65

    def __post_init__(self):
        if self.mode not in MODES: raise ValueError('unsupported tracker mode')
        if not isinstance(self.max_tracks, int) or not 1 <= self.max_tracks <= 64:
            raise ValueError('max_tracks must be an integer in [1,64]')
        if not isinstance(self.reconciliation_enabled, bool): raise ValueError('reconciliation_enabled must be bool')
        for name in ('cosine_threshold', 'prototype_update_threshold', 'conflict_cosine_floor', 'reconciliation_cosine'):
            if not math.isfinite(getattr(self, name)) or not -1 <= getattr(self, name) <= 1:
                raise ValueError(name + ' must be finite cosine in [-1,1]')
        for name in ('ambiguity_margin', 'commit_evidence_sec', 'direction_persistence_sec',
                     'spatial_weight'):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(name + ' must be finite and nonnegative')
        for name in ('direction_max_age_sec', 'position_decay_sec', 'revision_horizon_sec'):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(name + ' must be positive')
        for name in ('direction_match_deg', 'direction_change_deg'):
            if not math.isfinite(getattr(self, name)) or not 0 < getattr(self, name) <= 180:
                raise ValueError(name + ' must lie in (0,180]')


@dataclass(frozen=True)
class SpatialObservation:
    angle_deg: float | None
    available_at_sec: float
    energy: float | None = None
    reliability: float = 1.0
    valid: bool = True
    sequence: int | None = None
    source_start_sec: float | None = None
    source_end_sec: float | None = None


@dataclass
class _Track:
    identifier: int
    center: np.ndarray
    first_sec: float
    last_sec: float
    unique_evidence_sec: float
    prototype_weight_sec: float
    angle_deg: float | None = None
    angle_update_sec: float | None = None
    committed: bool = False
    parent_identifier: int | None = None


class ResearchTracker:
    """Bounded online tracker; linear native 0..180 degrees, never circular.

    Direction only offers bounded association support. It never establishes a
    named identity, forces a speaker count, or resets the ASR stream. Prototype
    updates require unambiguous voice evidence. Overlapping windows contribute
    only newly covered seconds, not their summed durations.
    """
    def __init__(self, config: TrackingConfig | None = None):
        self.config = config or TrackingConfig()
        self.tracks: list[_Track] = []
        self.last_end = -math.inf
        self.last_available = -math.inf
        self.last_spatial_sequence: int | None = None
        self.last_spatial_stamp = -math.inf
        self.pending_angle: float | None = None
        self.pending_since = 0.0
        self.pending_last = -math.inf
        self.update_count = 0
        self.rejected_count = 0
        self.next_identifier = 1
        self.last_assigned = None
        self.recent_first_decisions = deque(maxlen=64)
        self.merge_count = 0
        self.split_count = 0
        self.revision_count = 0

    def _spatial(self, observation, now):
        if self.config.mode == 'voice_time' or observation is None:
            return None, 0.0, 'disabled_or_missing'
        age = now - observation.available_at_sec
        if not observation.valid or not math.isfinite(observation.available_at_sec):
            return None, 0.0, 'invalid'
        if age < -1e-9: return None, 0.0, 'not_arrived'
        if age > self.config.direction_max_age_sec + 1e-9: return None, 0.0, 'stale'
        observed_end = getattr(observation, 'source_end_sec', None)
        if observed_end is not None:
            if not math.isfinite(observed_end) or observed_end > observation.available_at_sec + 1e-9:
                return None, 0.0, 'invalid_observation_time'
            if now-observed_end > self.config.direction_max_age_sec + 1e-9:
                return None, 0.0, 'stale_source_observation'
        if observation.available_at_sec < self.last_spatial_stamp - 1e-9:
            return None, 0.0, 'reordered'
        if (observation.sequence is not None and self.last_spatial_sequence is not None
                and observation.sequence < self.last_spatial_sequence):
            return None, 0.0, 'reordered_sequence'
        angle = observation.angle_deg
        if angle is None or not math.isfinite(angle) or not 0 <= angle <= 180:
            return None, 0.0, 'missing_or_invalid_angle'
        if observation.energy is not None and (not math.isfinite(observation.energy) or observation.energy <= 0):
            return None, 0.0, 'nonpositive_or_invalid_energy'
        self.last_spatial_stamp = observation.available_at_sec
        if observation.sequence is not None: self.last_spatial_sequence = observation.sequence
        quality = float(np.clip(observation.reliability, 0., 1.)) if math.isfinite(observation.reliability) else 0.
        # Energy is an availability/positive-support check, not calibrated VAD.
        quality *= max(0., 1. - age / self.config.direction_max_age_sec)
        # Receipt freshness and feature cadence are distinct. A fresh packet at
        # each 0.5-s evidence update can establish sampled persistence; this
        # does not claim continuous DSP observation between those updates.
        continuity_gap = max(self.config.direction_max_age_sec, self.config.direction_persistence_sec) + .11
        if (self.pending_angle is None or abs(angle - self.pending_angle) > self.config.direction_match_deg
                or now - self.pending_last > continuity_gap):
            self.pending_angle, self.pending_since = angle, now
        self.pending_last = now
        return angle, quality, 'qualified'

    def update(self, embedding, source_start_sec, source_end_sec, available_at_sec,
               spatial: SpatialObservation | None = None, speech=True, overlap=False):
        values = (source_start_sec, source_end_sec, available_at_sec)
        if not all(math.isfinite(x) for x in values): raise ValueError('finite times required')
        if not 0 <= source_start_sec < source_end_sec <= available_at_sec + 1e-9:
            raise ValueError('input end must precede availability')
        if source_end_sec <= self.last_end or available_at_sec < self.last_available:
            raise ValueError('features must arrive once in monotonic span/availability order')
        self.last_end, self.last_available = source_end_sec, available_at_sec
        self.update_count += 1
        previous_identifier = self.last_assigned
        v = np.asarray(embedding, np.float32).reshape(-1)
        norm = float(np.linalg.norm(v))
        if v.size != 192 or not np.all(np.isfinite(v)) or norm <= 0:
            raise ValueError('finite nonzero ReDimNet2 192-vector required')
        v = v / norm
        angle, quality, spatial_status = self._spatial(spatial, available_at_sec)
        if angle is None:
            self.pending_angle = None
            self.pending_last = -math.inf
        base = dict(source_start_sec=source_start_sec, source_end_sec=source_end_sec,
                    available_at_sec=available_at_sec, mode=self.config.mode,
                    spatial_status=spatial_status, spatial_reliability=quality,
                    direction_deg=angle, lineage=[], revision_of=None,
                    first_decision_rewritten=False)
        if not speech or overlap:
            return self._unknown(base, 'speech_or_overlap_gate', None, None)
        voice = [float(v @ track.center) for track in self.tracks]
        scores = list(voice)
        eligible = [s >= self.config.cosine_threshold for s in voice]
        if self.config.mode == 'angle_diagnostic':
            if angle is None: return self._unknown(base, 'angle_unavailable', None, None)
            scores = [1. - abs(angle - t.angle_deg) / 180. if t.angle_deg is not None else -1.
                      for t in self.tracks]
            eligible = [t.angle_deg is not None and abs(angle-t.angle_deg) <= self.config.direction_match_deg
                        for t in self.tracks]
        elif angle is not None and self.config.mode != 'voice_time':
            sustained = available_at_sec - self.pending_since >= self.config.direction_persistence_sec
            for i, track in enumerate(self.tracks):
                if track.angle_deg is None or track.angle_update_sec is None: continue
                distance = abs(angle - track.angle_deg)
                spatial_score = max(-1., 1. - distance / self.config.direction_match_deg)
                decay = math.exp(-max(0., available_at_sec-track.angle_update_sec) / self.config.position_decay_sec)
                weight = self.config.spatial_weight
                if distance >= self.config.direction_change_deg:
                    base['lineage'].append(dict(event='direction_change_proposal', track_id=track.identifier,
                                                sustained=sustained, available_at_sec=available_at_sec, reset_asr=False))
                if self.config.mode == 'sustained_angle':
                    weight *= float(sustained)
                elif self.config.mode == 'decaying_memory': weight *= decay
                else: weight *= decay * quality
                scores[i] += weight * spatial_score
                # Even a perfect direction cannot accept a severe voice conflict.
                eligible[i] = voice[i] >= self.config.conflict_cosine_floor and scores[i] >= self.config.cosine_threshold
        ranked = sorted((i for i, ok in enumerate(eligible) if ok), key=lambda i: scores[i], reverse=True)
        top1 = scores[ranked[0]] if ranked else max(scores, default=None)
        top2 = scores[ranked[1]] if len(ranked)>1 else None
        if len(ranked)>1 and top1-top2 < self.config.ambiguity_margin:
            return self._unknown(base, 'ambiguous_association', top1, top2)
        created = not ranked
        if created:
            if len(self.tracks) >= self.config.max_tracks:
                return self._unknown(base, 'track_capacity', top1, top2)
            track = _Track(self.next_identifier, v.copy(), source_start_sec, source_end_sec,
                           source_end_sec-source_start_sec, source_end_sec-source_start_sec,
                           angle, available_at_sec if angle is not None else None)
            self.next_identifier += 1
            parents=[t for t in self.tracks if t.identifier==previous_identifier and t.committed]
            proposed={p['track_id'] for p in base['lineage'] if p['event']=='direction_change_proposal'}
            if parents and parents[0].identifier in proposed and self.config.reconciliation_enabled:
                track.parent_identifier=parents[0].identifier
                base['lineage'].append(dict(event='split_provisional_branch', from_track_id=parents[0].identifier,
                                            to_track_id=track.identifier, available_at_sec=available_at_sec,
                                            boundary_support_start_sec=source_start_sec,
                                            reason='qualified direction change plus voice association conflict; not confirmed new person'))
                self.split_count += 1
            self.tracks.append(track)
            base['lineage'].append(dict(event='create', track_id=track.identifier, available_at_sec=available_at_sec))
            new_seconds = source_end_sec-source_start_sec
        else:
            i = ranked[0]; track = self.tracks[i]
            new_seconds = max(0., source_end_sec-max(source_start_sec, track.last_sec))
            track.unique_evidence_sec += new_seconds
            track.last_sec = source_end_sec
            if voice[i] >= self.config.prototype_update_threshold and new_seconds>0:
                combined = track.center*track.prototype_weight_sec + v*new_seconds
                track.center = combined/max(float(np.linalg.norm(combined)), 1e-8)
                track.prototype_weight_sec += new_seconds
                base['lineage'].append(dict(event='prototype_update', track_id=track.identifier,
                                            new_unique_seconds=new_seconds, available_at_sec=available_at_sec))
            if angle is not None and (self.config.mode=='angle_diagnostic' or voice[i]>=self.config.prototype_update_threshold):
                track.angle_deg = angle if track.angle_deg is None else .8*track.angle_deg+.2*angle
                track.angle_update_sec = available_at_sec
            # A just-created, direction-proposed branch may be reconciled only
            # by fresh overlapping acoustic evidence confidently matching its
            # established parent. Old first decisions remain immutable. The
            # provisional branch's uncertain vectors/evidence are NOT pooled.
            prior=next((t for t in self.tracks if t.identifier==previous_identifier),None)
            if (self.config.reconciliation_enabled and prior is not None and prior is not track
                    and not prior.committed and prior.parent_identifier==track.identifier
                    and voice[i]>=self.config.reconciliation_cosine
                    and source_start_sec < prior.last_sec
                    and available_at_sec-prior.last_sec<=self.config.revision_horizon_sec):
                revised=[d for d in self.recent_first_decisions if d['track_id']==prior.identifier
                         and available_at_sec-d['available_at_sec']<=self.config.revision_horizon_sec]
                base['lineage'].append(dict(event='merge_provisional_branch',from_track_id=prior.identifier,
                                            to_track_id=track.identifier,available_at_sec=available_at_sec,
                                            uncertain_branch_evidence_discarded_sec=prior.unique_evidence_sec,
                                            first_decisions_preserved=True))
                for old in revised:
                    base['lineage'].append(dict(event='label_revision',revision_of=old['first_decision_id'],
                                                from_track_id=prior.identifier,to_track_id=track.identifier,
                                                original_available_at_sec=old['available_at_sec'],available_at_sec=available_at_sec,
                                                first_decision_preserved=True))
                self.tracks.remove(prior);self.merge_count+=1;self.revision_count+=len(revised)
        if not track.committed and track.unique_evidence_sec >= self.config.commit_evidence_sec:
            track.committed=True
            base['lineage'].append(dict(event='commit', track_id=track.identifier, available_at_sec=available_at_sec))
        label = ('Spatial_' if self.config.mode=='angle_diagnostic' else 'Speaker_')+str(track.identifier)
        return self._finish(dict(base, anonymous_label=label, display_label=label,
                    state='anonymous_committed' if track.committed else 'anonymous_provisional',
                    top1_score=top1, top2_score=top2, margin=top1-top2 if top1 is not None and top2 is not None else None,
                    evidence_sec=track.unique_evidence_sec, cluster_id=track.identifier,
                    provisional_track_id=track.identifier, committed_track_id=track.identifier if track.committed else None,
                    unique_added_evidence_sec=new_seconds, reason='create' if created else 'associate'))

    def _unknown(self, base, reason, top1, top2):
        self.rejected_count += 1
        return self._finish(dict(base, anonymous_label='Unknown', display_label='Unknown', state='unknown',
                    top1_score=top1, top2_score=top2, margin=top1-top2 if top1 is not None and top2 is not None else None,
                    evidence_sec=0., cluster_id=None, provisional_track_id=None, committed_track_id=None,
                    unique_added_evidence_sec=0., reason=reason))

    def _finish(self, result):
        result['first_decision_id']=f'd{self.update_count:06d}'
        self.last_assigned=result['cluster_id']
        self.recent_first_decisions.append(dict(first_decision_id=result['first_decision_id'],
                                                track_id=result['cluster_id'],available_at_sec=result['available_at_sec']))
        while (self.recent_first_decisions and result['available_at_sec']-self.recent_first_decisions[0]['available_at_sec']
               > self.config.revision_horizon_sec): self.recent_first_decisions.popleft()
        return result

    def snapshot(self):
        return dict(config=asdict(self.config), track_count=len(self.tracks), updates=self.update_count,
                    rejected=self.rejected_count, prototype_float32_bytes=len(self.tracks)*192*4,
                    splits=self.split_count,merges=self.merge_count,revisions=self.revision_count,
                    bounded_revision_records=len(self.recent_first_decisions),
                    tracks=[dict(track_id=t.identifier, unique_evidence_sec=t.unique_evidence_sec,
                                 committed=t.committed, angle_deg=t.angle_deg) for t in self.tracks])


def decision_to_speaker(decision):
    """Project a research event to the existing GUI decision contract."""
    from .contracts import SpeakerDecision
    keys=('anonymous_label','display_label','state','top1_score','top2_score','margin','evidence_sec','cluster_id')
    return SpeakerDecision(**{key:decision[key] for key in keys})
