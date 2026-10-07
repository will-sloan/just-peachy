"""Shared causal identity presentation and diagnostics. See README_IDENTITY_MODES.md.

No embedding, gallery write, new threshold, or calibration fitting occurs here.
The delegate remains the actual pinned resolver for the selected encoder.
"""
from collections import OrderedDict
from copy import deepcopy
from itertools import islice
import math
import threading
import time


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def apply_display_roster(rows, display_ids, strict, mode):
    """Presentation filter only; never alter the biometric profile field."""
    selected = set(display_ids)
    for row in rows:
        profile = row.get('profile_id')
        display_profile = row.get('display_profile_id') or profile
        row['selected'] = display_profile in selected
        row['visible'] = not strict or row['selected']
        if mode == 'enrolled_names' and not profile:
            row['label'] = 'Unknown'


def annotate_caption_policy(resolver, payload, mode):
    """Use each actual resolver, then separate legacy forced display from identity."""
    row = resolver.annotate_caption(payload)
    if mode != 'selected_closed':
        return row
    row = deepcopy(row)
    for part in [row, *row.get('segments', [])]:
        if part.get('prototype_assignment') not in ('forced', 'assumed_unlinked'):
            continue
        person = part.get('known_profile_id')
        gallery = getattr(resolver, 'gallery', None)
        names = dict(zip(gallery.ids, gallery.names)) if gallery is not None else {}
        if person not in names:
            continue
        # Retained C088 closed policy historically used confirmed internally
        # even for a forced roster winner. Its published biometric profile must
        # not survive that explicit forced/unlinked assignment annotation.
        part['closed_display_assignment'] = dict(profile_id=person, name=names[person],
            assignment='closed_assumed', basis='actual_voice_roster_winner_not_verification',
            evidence_ids=list(part.get('prototype_assignment_evidence_ids') or []),
            acoustic_confidence=None, voice_identity_verified=False, verified=False,
            adaptation_eligible=False, scope='Closed-group display assumption; original voice policy result is unverified')
        part.update(naming_state='closed_assumption', voice_identity_verified=False)
    return row


def decision_diagnostic_line(decision, encoder):
    """Small GUI explanation; complete numeric/pin evidence stays in session logs."""
    detail = decision.get('identity') or {}
    scores = detail.get('scores') or []
    top = scores[0].get('cosine') if scores else None
    cosine = f'{top:.3f}' if finite(top) else 'unavailable'
    duration = detail.get('unique_clean_sec', detail.get('eligible_clean_duration_sec'))
    seconds = f'{duration:.2f}s' if finite(duration) else 'unavailable'
    gate = detail.get('calibration_status', 'retained C088')
    query = 'yes' if detail.get('query_executed') is True else 'no'
    return (f'Identity {encoder}: {detail.get("reason", "unavailable")}; gate={gate}; '
        f'profiles={detail.get("loaded_profiles", "?")}; unique={seconds}; query={query}; cosine={cosine}')[:192]


def evidence_status(event):
    start, end = event.get('source_start_sec'), event.get('source_end_sec')
    clean = event.get('clean_intervals') or []
    extent = finite(start) and finite(end) and 0 <= start < end
    clean_valid = bool(extent and clean and all(isinstance(p, (list, tuple)) and
        len(p) == 2 and finite(p[0]) and finite(p[1]) and start <= p[0] < p[1] <= end
        for p in clean))
    return dict(source_window_sec=[start, end] if extent else None,
        evidence_duration_sec=end-start if extent else None,
        eligible_clean_duration_sec=sum(b-a for a,b in clean) if clean_valid else 0.,
        clean_support_valid=clean_valid, speech=event.get('speech'), overlap=event.get('overlap'),
        evidence_event_id=event.get('event_id'), evidence_kind=event.get('evidence_kind'),
        eligibility_scope='actual selected voice window; independent of caption fragment length')


def gallery_status(gallery, namespace, *, policy='n2'):
    """Metadata only; scores and vector payloads never enter this receipt."""
    receipt = getattr(gallery, 'receipt', {}) if gallery is not None else {}
    gate = getattr(gallery, 'calibration', {}) if gallery is not None else {}
    actual = getattr(gallery, 'namespace', None) if gallery is not None else None
    ids = list(getattr(gallery, 'ids', [])) if gallery is not None else []
    compatible = sum(len(t.get('references') or []) for t in receipt.get('templates', []))
    calibrated = bool(gallery is not None and gate.get('status') == 'CALIBRATED'
        and actual == namespace and gate.get('namespace') == namespace)
    if policy == 'retained_c088':
        status = 'RETAINED_C088_POLICY'
        reason = 'Original ReDimNet C088 resolver and original thresholds; no N2 calibration claim'
    elif gallery is None:
        status, reason = 'NO_GALLERY', 'This Mode has no personal lookup'
    elif not ids:
        status, reason = 'EMPTY_COMPATIBLE_GALLERY', 'No compatible enrolled profiles in the active encoder gallery'
    elif actual != namespace:
        status, reason = 'NAMESPACE_MISMATCH', 'Active gallery namespace differs from model/preprocessing namespace'
    elif not calibrated:
        status = gate.get('status') or 'UNCALIBRATED_PERSONAL_DOMAIN'
        reason = 'No independently calibrated C gate for this exact encoder, query domain and roster; biometric names remain Unknown'
    else:
        status, reason = 'CALIBRATED', 'Existing exact encoder/domain/roster C gate'
    return dict(schema='just-peachy.identity-readiness.v1', policy=policy,
        status=status, reason=reason, model_namespace=deepcopy(namespace),
        gallery_namespace=deepcopy(actual), gallery_id=getattr(gallery, 'gallery_id', None),
        loaded_profiles=len(ids), compatible_references=compatible,
        gallery_query_count=getattr(gallery, 'query_count', 0),
        gate_sha256=gate.get('gate_sha256') if calibrated else None,
        calibrated=calibrated, score_threshold=gate.get('score_threshold') if calibrated else None,
        margin_threshold=gate.get('margin_threshold') if calibrated else None,
        query_domain=receipt.get('expected_query_domain'),
        calibration_scope='Verification only; closed roster display assumptions do not require or imply calibration')


class IdentityModeAdapter:
    """Add explicit revisions and honest closed display fallback to pinned N2 naming."""
    def __init__(self, target, namespace, *, spatial_policy=None):
        self.target, self.namespace = target, deepcopy(namespace)
        self.spatial_policy = spatial_policy
        self.assignments = OrderedDict()
        self.lock = threading.RLock()
        self.last_diagnostic = None

    def __getattr__(self, name):
        return getattr(self.target, name)

    def sync_tracks(self, active_ids, now):
        # D1 spatial owns its shared track population on its source clock.
        with self.lock:
            if self.spatial_policy is None:
                return self.target.sync_tracks(active_ids, now)

    def resolve(self, decision, event):
        with self.lock:
            return self._resolve(decision, event)

    def _resolve(self, decision, event):
        began = time.perf_counter()
        if self.spatial_policy is not None:
            decision = self.spatial_policy.associate(decision, event)
            active = {r['track_id'] for r in self.spatial_policy.tracker.scheduling_state(
                event['source_end_sec'])}
            self.target.sync_tracks(active, event['source_end_sec'])
        result = self.target.resolve(decision, event)
        detail = result['identity']
        readiness = gallery_status(self.gallery, self.namespace)
        detail.update(evidence_status(event), model_namespace=deepcopy(self.namespace),
            gallery_namespace=readiness['gallery_namespace'], loaded_profiles=readiness['loaded_profiles'],
            compatible_references=readiness['compatible_references'],
            calibration_status=detail.get('calibration_status', readiness['status']),
            calibration_reason=readiness['reason'], gate_sha256=readiness['gate_sha256'],
            score_threshold=readiness['score_threshold'], margin_threshold=readiness['margin_threshold'],
            minimum_unique_sec=self.target.minimum_unique_sec,
            gallery_query_count=getattr(self.gallery, 'query_count', 0),
            score_meaning='raw cosine, not probability; current query and unique-duration weighted query',
            voice_identity_verified=detail.get('verified') is True,
            personal_reference_update=False, adaptation_eligible=False)
        if self.spatial_policy is not None:
            detail['spatial_association'] = deepcopy(decision['spatial_association'])
        track = result.get('tracker_id', result.get('track_id'))
        # The shared caption scheduler needs an explicit rejection revision too.
        # This does not promote a closed assumption to confirmed identity.
        if track is not None:
            result['name_revision'] = dict(track_id=track,
                replacement_label=result['display_label'],
                replacement_known_name=result.get('known_name'),
                replacement_known_profile_id=result.get('known_profile_id'),
                replacement_naming_state=result.get('naming_state', 'unknown'),
                reason=detail.get('reason'), evidence_id=event.get('event_id'),
                available_at_sec=event.get('available_at_sec'))
        with self.lock:
            self.last_diagnostic = deepcopy(detail)
            eid = event.get('event_id')
            if eid:
                self.assignments[eid] = dict(profile_id=result.get('known_profile_id'),
                    naming_state=result.get('naming_state'), track_id=track,
                    native_track_id=decision.get('native_tracker_id'),
                    name=result.get('known_name'), display_label=result.get('display_label'),
                    source_start_sec=event.get('source_start_sec'), source_end_sec=event.get('source_end_sec'),
                    available_at_sec=event.get('available_at_sec'),
                    assignment='accepted' if detail.get('verified') is True else
                        'forced' if result.get('naming_state') == 'closed_assumption' else 'unavailable')
                while len(self.assignments) > 4096:
                    self.assignments.popitem(last=False)
        result['identity_compute_sec'] = time.perf_counter()-began
        return result

    def _choice(self, part, row):
        if not self.closed or self.gallery is None or not self.gallery.ids:
            return None
        names = dict(zip(self.gallery.ids, self.gallery.names))
        chosen = part.get('known_profile_id')
        evidence_ids = []
        basis = 'historical_name_voice_unavailable'
        if chosen not in names:
            chosen, basis = self.gallery.ids[0], 'roster_default_no_voice_match'
            start = part.get('source_start_sec', row.get('source_start_sec'))
            end = part.get('source_end_sec', row.get('source_end_sec'))
            if finite(start) and finite(end) and 0 <= start < end:
                eligible = []
                for eid, item in islice(reversed(self.assignments.items()), 64):
                    a, b = item['source_start_sec'], item['source_end_sec']
                    if item['profile_id'] not in names or item['assignment'] not in ('accepted', 'forced'):
                        continue
                    if not finite(a) or not finite(b) or b > end:
                        continue
                    overlapping, recent = max(start, a) < min(end, b), 0 <= start-b <= 2.
                    if overlapping or recent:
                        same = part.get('track_id') is not None and part['track_id'] == item['track_id']
                        eligible.append(((same, overlapping, b), eid, item))
                if eligible:
                    _, eid, item = max(eligible, key=lambda item:item[0])
                    chosen, evidence_ids = item['profile_id'], [eid]
                    basis = 'same_utterance_voice_winner' if item['source_end_sec'] > start else 'recent_voice_winner'
        return dict(profile_id=chosen, name=names[chosen], assignment='closed_assumed', basis=basis,
            evidence_ids=evidence_ids, acoustic_confidence=None, voice_identity_verified=False,
            verified=False, adaptation_eligible=False,
            scope='Closed-group display assumption; no word alignment, biometric verification or enrollment evidence')

    def annotate_caption(self, payload):
        row = deepcopy(payload)
        with self.lock:
            for part in [row, *row.get('segments', [])]:
                part['prototype_closed_group'] = self.closed
                part.pop('closed_display_assignment', None)
                if part.get('naming_state') == 'invalidated':
                    continue
                if self.closed and (part.get('naming_state') != 'confirmed' or
                        not part.get('known_profile_id') or part.get('voice_available') is False):
                    choice = self._choice(part, row)
                    if choice is not None:
                        part['closed_display_assignment'] = choice
                if part.get('known_profile_id'):
                    ids = list(part.get('evidence_ids') or [])
                    ids.extend([part.get('identity_input_event_id'), part.get('identity_event_id')])
                    linked = [eid for eid in ids if eid in self.assignments and
                        self.assignments[eid]['profile_id'] == part['known_profile_id']]
                    verified = bool(linked and all(self.assignments[e]['assignment'] == 'accepted' for e in linked))
                    part.update(prototype_assignment='accepted' if verified else
                        'forced' if self.closed and linked else 'assumed_unlinked' if self.closed else 'unavailable',
                        prototype_assignment_evidence_ids=linked,
                        voice_identity_verified=verified,
                        prototype_identity_scope='historical source-linked caption span; no word identity guarantee')
        return row

    def source_assignment(self, native_track, start, end):
        """Exact native source linkage for D1 spatial caption projection."""
        with self.lock:
            for eid, item in reversed(self.assignments.items()):
                if (item['native_track_id'] == native_track and finite(item['source_start_sec']) and
                        finite(item['source_end_sec']) and min(end, item['source_end_sec']) > max(start, item['source_start_sec'])):
                    return dict(deepcopy(item), event_id=eid)
        return None

    def snapshot(self):
        with self.lock:
            result = self.target.snapshot()
            result.update(adapter='core_repair_identity_modes_v1',
                readiness=gallery_status(self.gallery, self.namespace),
                last_decision=deepcopy(self.last_diagnostic), retained_assignments=len(self.assignments))
            if self.spatial_policy is not None:
                result['spatial_policy'] = self.spatial_policy.snapshot()
            return result


class RetainedClosedModeAdapter:
    """Retain C088 math; its forced roster result is display-only everywhere."""
    def __init__(self, target):
        self.target = target

    def __getattr__(self, name):
        return getattr(self.target, name)

    def resolve(self, decision, event):
        result = self.target.resolve(decision, event)
        detail = result['identity']
        verified = detail.get('assignment') == 'accepted' and detail.get('naming_state') == 'confirmed'
        detail['voice_identity_verified'] = verified
        if detail.get('assignment') in ('forced', 'assumed_unlinked'):
            detail.update(naming_state='closed_assumption', verified=False)
            result['naming_state'] = 'closed_assumption'
            if isinstance(result.get('name_revision'), dict):
                result['name_revision']['replacement_naming_state'] = 'closed_assumption'
        return result

    def annotate_caption(self, row):
        return self.target.annotate_caption(row)

    def snapshot(self):
        return dict(self.target.snapshot(), closed_assumptions_are_biometric=False,
            adapter='core_repair_retained_closed_display_v1')


def install_revision_bridge(engine, *, retained_closed=False):
    """Preserve bounded D0 scheduler rules while revising same-label metadata."""
    if getattr(engine, 'n2_diarization', None) != 'D0' and not retained_closed:
        return None
    scheduler = engine._scheduler.scheduler
    original = scheduler._revise
    def revise(event, decision):
        records = original(event, decision)
        naming = decision.get('name_revision')
        if not isinstance(naming, dict):
            return records
        now, end = event.get('available_at_sec'), event.get('source_end_sec')
        if not finite(now) or not finite(end) or not 0 <= now-end <= scheduler.evidence_expiry:
            return records
        if event.get('speech') is not True or event.get('overlap') is not False:
            return records
        for key, row in scheduler._utterances.items():
            if row.get('tracker_id') != naming['track_id'] or naming['track_id'] is None:
                continue
            anchor = row.get('first_final_time') if row.get('first_final_time') is not None else row.get(
                'last_text_available_at_sec', row['first_display_time'])
            if not 0 <= now-anchor <= scheduler.revision_horizon or row['revision_count'] >= scheduler.max_revisions_per_utterance:
                continue
            if max(row['source_start_sec'], event['source_start_sec']) >= min(row['source_end_sec'], end):
                continue
            changed = (row.get('latest_known_profile_id'), row.get('latest_known_name'), row.get('latest_naming_state')) != (
                naming['replacement_known_profile_id'], naming['replacement_known_name'], naming['replacement_naming_state'])
            if not changed:
                continue
            old = row['latest_label']
            row.update(latest_label=naming['replacement_label'], latest_label_time=now,
                latest_known_profile_id=naming['replacement_known_profile_id'],
                latest_known_name=naming['replacement_known_name'], latest_naming_state=naming['replacement_naming_state'],
                revision_count=row['revision_count']+1)
            records.append(scheduler._record('transcript_label_revision', event, dict(utterance_id=key,
                previous_label=old, latest_label=row['latest_label'], latest_label_time=now,
                replacement_tracker_id=row['tracker_id'], latest_known_name=row['latest_known_name'],
                latest_known_profile_id=row['latest_known_profile_id'], latest_naming_state=row['latest_naming_state'],
                reason='source-linked identity metadata changed; same-label rejection or assumption remains explicit',
                revision_scope='bounded_post_association_name', evidence_ids=[event['event_id']],
                label_revision_of=key, first_display_is_preserved=True, changes_words=False,
                changes_anonymous_association=False)))
        return records
    scheduler._revise = revise
    return dict(adapter='core_repair_same_label_identity_revision_v1',
        source_overlap_required=True, original_expiry_and_horizon=True, changes_words=False)
