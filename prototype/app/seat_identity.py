"""Explicit seating assumption / native voice-plus-seat adapter. See README_SEATS.md."""
from copy import deepcopy
from types import SimpleNamespace
import time
import numpy as np

from .identity_policy import PrototypeIdentityResolver
from .live_spatial import DISPLAY_LIMIT
from edge_speech_pipeline.research_tracking_v3 import S6CTracker


class SeatIdentityResolver(PrototypeIdentityResolver):
    def __init__(self, settings, gallery, *, seats, names, provider, tracker_config, direction_only=False, clock=None):
        super().__init__(settings, gallery, clock=clock)
        if seats is None or provider is None:raise ValueError('Assigned seats require an explicit session and spatial provider')
        self.seats, self.names, self.provider = seats, dict(names), provider
        self.direction_only = direction_only; self.tracker_config = tracker_config
        # Reuse the actual retained scorer. Its tracks here are immutable seat
        # hypotheses, never the anonymous voice tracker or personal references.
        self.seat_scorer = S6CTracker(tracker_config)

    def _publish(self, result, event, pid, assignment, reason, now):
        d = result['identity']; name = self.names.get(pid) if pid else None
        state = 'confirmed' if name else 'unresolved'; label = name or result.get('anonymous_label', 'Unknown')
        if not name:pid = None
        d.update(known_profile_id=pid, known_name=name, display_label=label, naming_state=state,
                 name_is_displayed=bool(name), assignment=assignment, forced=assignment=='seat_assumed',
                 name_evidence_available_at_sec=now, reason=reason, personal_reference_update=False)
        result.update(known_profile_id=pid, known_name=name, naming_state=state, display_label=label)
        result['name_revision'] = dict(track_id=result['tracker_id'], replacement_label=label,
            replacement_known_name=name, replacement_known_profile_id=pid, replacement_naming_state=state,
            reason=reason, evidence_id=event['event_id'], available_at_sec=event['available_at_sec'])

    def resolve(self, decision, event):
        began = time.perf_counter(); now = self.clock() if self.clock else event['available_at_sec']
        # The native resolver maintains voice evidence only. No seat data enters
        # its enrollment or voice-memory state; invalid speech never queries it.
        safe = event.get('speech') is True and event.get('overlap') is False
        safe = safe and 0 <= now-event['source_end_sec'] <= 2. and bool(event.get('clean_intervals'))
        result = super().resolve(decision, event if safe else {**event, 'speech':False})
        d = result['identity']; seat = self.seats.snapshot()
        valid = d['valid_fresh_voice']  # Existing native clean speech/overlap/source gates.
        # Cues are admitted on the same upstream-availability clock as the
        # native tracker. Scheduler watermark waiting is a different clock.
        cue, detail = self.provider.seat_evidence(event['source_start_sec'], event['source_end_sec'], event['available_at_sec']) if valid else (None, dict(valid=False, reason='no_fresh_clean_model_speech'))
        if cue is not None:
            detail.update(decision_cue_age_sec=now-cue.available_at_sec,decision_age_limit_sec=DISPLAY_LIMIT,
                          admission_clock='original model evidence availability; same as retained tracker',
                          decision_clock='actual observed policy clock after scheduler release')
            if not 0<=now-cue.available_at_sec<=DISPLAY_LIMIT:
                cue=None;detail.update(valid=False,reason='direction_expired_at_decision')
        candidates = [r for r in seat['rows'] if cue is not None and
                      abs(r['angle_deg']-cue.angle_deg) <= r['tolerance_deg']]
        detail.update(session_id=seat['session_id'], revision=seat['revision'], anchor_valid=seat['valid'],
                      strength=seat['strength'], candidate_ids=[r['person_id'] for r in candidates],
                      ambiguous=len(candidates)>1, released=seat['released'], basis='unavailable',
                      voice_inference_retained=True, voice_identity_used=not self.direction_only)
        if not seat['valid']:detail['reason'] = 're_anchor_required: '+seat['reason']
        pid = None; assignment = 'unavailable'; reason = detail['reason']
        if self.direction_only:
            # No gallery, score or voice-profile comparison in this branch.
            if valid and cue is not None and seat['valid']:
                if len(candidates)==1:
                    pid=candidates[0]['person_id']; assignment='seat_assumed'; reason='closed_seating_direction_assumption'
                    detail['basis']='forced seating assumption'
                else:
                    assignment='ambiguous' if candidates else 'unavailable'
                    reason='overlapping_projected_seats' if candidates else 'outside_assigned_regions'
        else:
            # Keep genuine C088 accepted names, including when directions fail,
            # but expose the voice-only fallback and reject stale name memory.
            scores = self.gallery.score(np.asarray(event['vector'],np.float32)/np.linalg.norm(event['vector'])) if valid and self.gallery else []
            self.comparisons += len(scores)
            detail['current_voice_scores'] = scores
            strong = scores and scores[0]['cosine'] >= self.tracker_config.reliable_voice_cosine and (
                len(scores)==1 or scores[0]['cosine']-scores[1]['cosine'] >= self.settings.margin_threshold)
            voice_id = scores[0]['profile_id'] if strong else None
            if cue is not None and voice_id:
                own = next((r for r in seat['rows'] if r['person_id']==voice_id), None)
                other = [r['person_id'] for r in candidates if r['person_id']!=voice_id]
                if other or (own and abs(own['angle_deg']-cue.angle_deg)>own['tolerance_deg']):
                    self.seats.release([voice_id,*other], 'strong_voice_conflict_or_participant_relocation')
                    detail.update(released=self.seats.snapshot()['released'], trust_released=True)
            known = d.get('known_profile_id') if d.get('naming_state')=='confirmed' else None
            current = next((r['cosine'] for r in scores if r['profile_id']==known), -1.)
            stamp = event['available_at_sec'] if d.get('query_executed') else d.get('name_evidence_available_at_sec', -1e9)
            if valid and known and current >= self.settings.severe_query_cosine and 0<=now-stamp<=2. and (not voice_id or voice_id==known):
                pid=known; assignment='accepted'; reason='voice_accepted_with_seat_agreement' if len(candidates)==1 and candidates[0]['person_id']==known and known not in detail['released'] else 'voice_accepted_spatial_unavailable_or_conflicting'
                detail['basis']='voice'; detail['voice_only_fallback']=reason.endswith('conflicting')
            # A seat prior may resolve an otherwise insufficient NAME MARGIN,
            # never invent a score or waive C088 clean/disjoint/voice thresholds.
            mature = d.get('unique_clean_sec',0)>=self.settings.minimum_unique_sec and d.get('disjoint_count',0)>=self.settings.minimum_disjoint_count
            if pid is None and valid and mature and d.get('query_executed') and seat['valid'] and cue is not None and len(candidates)==1:
                target=candidates[0]['person_id']
                eligible={r['profile_id']:r for r in d.get('scores',[]) if r['cosine']>=self.settings.score_threshold}
                current_score=next((r['cosine'] for r in scores if r['profile_id']==target), -1.)
                if target in eligible and target not in detail['released'] and current_score>=self.settings.score_threshold and d.get('prototype_voice_cosine',-1.)>=self.settings.prototype_update_cosine:
                    scorer=self.seat_scorer
                    scorer.tracks=[SimpleNamespace(identifier=r['profile_id'], location=next((s['angle_deg'] for s in seat['rows'] if s['person_id']==r['profile_id'] and r['profile_id'] not in detail['released']), None),location_at=now) for r in d['scores']]
                    scorer.pending_since=now-self.tracker_config.direction_persistence_sec
                    joint, terms=scorer._joint_scores({r['profile_id']:r['cosine'] for r in d['scores']},cue.angle_deg,cue.reliability,event['source_start_sec'],event['source_end_sec'],now,[])
                    detail.update(joint_scores=joint, joint_terms=terms, score_method='actual retained S6CTracker._joint_scores; extra C088 name floor and duration gates')
                    alternatives=[v for k,v in joint.items() if k!=target]
                    if target in joint and joint[target]-max(alternatives)>=self.tracker_config.joint_margin:
                        pid=target; assignment='spatial_supported'; reason='voice_qualified_seat_prior_resolves_margin';detail['basis']='spatial prior + qualified voice'
            if pid is None:
                assignment='ambiguous' if len(candidates)>1 else 'rejected' if valid else 'unavailable'
                reason='hybrid_unknown: '+('projected_seat_collision' if len(candidates)>1 else detail['reason'] if not cue else 'voice_threshold_margin_or_evidence_rejection')
        self._publish(result,event,pid,assignment,reason,now)
        d['seat']=detail;d['closed_group_assumption']=self.direction_only
        self.assignments[event['event_id']]=dict(assignment=assignment,profile_id=pid,forced=self.direction_only and pid is not None,
            available_at_sec=now,source_start_sec=event['source_start_sec'],source_end_sec=event['source_end_sec'],
            seat_revision=seat['revision'],seat_session_id=seat['session_id'],seat=deepcopy(detail))
        while len(self.assignments)>4096:self.assignments.popitem(last=False)
        elapsed=time.perf_counter()-began;self.total_sec+=max(0,elapsed-result['identity_compute_sec']);result['identity_compute_sec']=elapsed
        return result

    def annotate_caption(self,payload):
        row=super().annotate_caption(payload); current=self.seats.snapshot()
        for part in [row,*row.get('segments',[])]:
            ids=list(part.get('evidence_ids') or [])+[part.get('identity_input_event_id')]
            evidence=[self.assignments[e] for e in ids if e in self.assignments and self.assignments[e]['profile_id']==part.get('known_profile_id')]
            if not part.get('known_profile_id'):continue
            latest=max(evidence,key=lambda r:r['available_at_sec']) if evidence else None
            if latest is None or (latest['assignment']=='seat_assumed' and (not current['valid'] or latest['seat_revision']!=current['revision'])):
                part.update(known_profile_id=None,known_name=None,naming_state='invalidated',prototype_assignment='unavailable')
            else:
                part.update(prototype_assignment=latest['assignment'],prototype_seat=deepcopy(latest['seat']))
        return row
