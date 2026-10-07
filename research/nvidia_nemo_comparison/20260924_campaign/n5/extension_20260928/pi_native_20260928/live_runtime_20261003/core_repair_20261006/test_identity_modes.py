"""Deterministic integration contracts; no native/model work. See README_IDENTITY_MODES.md."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from identity_modes import IdentityModeAdapter, RetainedClosedModeAdapter, annotate_caption_policy, apply_display_roster, gallery_status, install_revision_bridge
from d1_spatial_policy import SourceClockSpatialPolicy, revise_spatial_caption_spans

NAMESPACE = dict(model_sha256='a'*64, preprocessing='fixture-mono-16k', dimension=192, normalization='L2')


def event(serial=1, start=0., end=1., available=None, **extra):
    return dict(event_id=f'voice:{serial}', source_start_sec=start, source_end_sec=end,
        available_at_sec=end if available is None else available, speech=True, overlap=False,
        evidence_kind='short' if end-start < 1.5 else 'mature', clean_intervals=[[start,end]],
        vector=[1.]+[0.]*191, **extra)


class Target:
    def __init__(self, ids=('p1',), *, closed=True):
        self.closed, self.minimum_unique_sec = closed, 1.5
        self.gallery = SimpleNamespace(ids=list(ids), names=[p.upper() for p in ids], gallery_id='fixture',
            namespace=deepcopy(NAMESPACE), calibration=dict(status='UNCALIBRATED_PERSONAL_DOMAIN'),
            receipt=dict(templates=[dict(references=[{}]) for _ in ids]), query_count=0)
        self.next = None
        self.calls = 0
        self.states = {}

    def resolve(self, decision, evidence):
        self.calls += 1
        chosen = self.next
        state = 'closed_assumption' if chosen and self.closed else 'confirmed' if chosen else 'unknown'
        detail = dict(query_executed=evidence['speech'] and not evidence['overlap'],
            known_profile_id=chosen, known_name=chosen.upper() if chosen else None,
            naming_state=state, verified=state == 'confirmed', scores=[], reason='fixture_decision')
        if detail['query_executed']:
            self.gallery.query_count += 1
        return dict(decision, identity=detail, known_profile_id=detail['known_profile_id'],
            known_name=detail['known_name'], naming_state=state,
            display_label=detail['known_name'] or 'Unknown', identity_compute_sec=0.)

    def sync_tracks(self, active_ids, now):
        self.active_ids = active_ids

    def snapshot(self):
        return dict(calls=self.calls)


class IdentityContracts(unittest.TestCase):
    def test_caption_before_voice_has_assumed_name_without_query_or_biometric(self):
        target = Target()
        adapter = IdentityModeAdapter(target, NAMESPACE)
        caption = dict(text='hello', source_start_sec=0., source_end_sec=.3, known_profile_id=None,
            naming_state='unresolved', segments=[dict(known_profile_id=None, naming_state='unresolved')])
        result = adapter.annotate_caption(caption)
        for part in [result, *result['segments']]:
            self.assertEqual(part['closed_display_assignment']['profile_id'], 'p1')
            self.assertFalse(part['closed_display_assignment']['voice_identity_verified'])
            self.assertIsNone(part['known_profile_id'])
        self.assertEqual(target.calls, 0)
        self.assertNotIn('closed_display_assignment', caption)

    def test_recent_source_winner_and_future_exclusion(self):
        target = Target(('p1','p2'))
        adapter = IdentityModeAdapter(target, NAMESPACE)
        target.next = 'p2'
        adapter.resolve(dict(tracker_id='track2'), event(1))
        recent = adapter.annotate_caption(dict(source_start_sec=1.2, source_end_sec=1.5))
        self.assertEqual(recent['closed_display_assignment']['profile_id'], 'p2')
        self.assertEqual(recent['closed_display_assignment']['basis'], 'recent_voice_winner')
        future = adapter.annotate_caption(dict(source_start_sec=0., source_end_sec=.5))
        self.assertEqual(future['closed_display_assignment']['profile_id'], 'p1')
        expired = adapter.annotate_caption(dict(source_start_sec=4., source_end_sec=4.5))
        self.assertEqual(expired['closed_display_assignment']['profile_id'], 'p1')

    def test_assumption_and_rejection_revisions_do_not_fabricate_confirmed(self):
        target = Target()
        adapter = IdentityModeAdapter(target, NAMESPACE)
        target.next = 'p1'
        assumed = adapter.resolve(dict(tracker_id='t1'), event())
        self.assertEqual(assumed['name_revision']['replacement_naming_state'], 'closed_assumption')
        self.assertFalse(assumed['identity']['voice_identity_verified'])
        target.next = None
        rejected = adapter.resolve(dict(tracker_id='t1'), event(2, 1., 2.))
        self.assertIsNone(rejected['name_revision']['replacement_known_profile_id'])
        self.assertEqual(rejected['name_revision']['replacement_label'], 'Unknown')
        self.assertEqual(rejected['identity']['eligible_clean_duration_sec'], 1.)
        self.assertEqual(rejected['identity']['gallery_query_count'], 2)

    def test_empty_gallery_and_invalidated_caption_have_no_roster_fabrication(self):
        adapter = IdentityModeAdapter(Target(()), NAMESPACE)
        self.assertNotIn('closed_display_assignment', adapter.annotate_caption(dict(source_start_sec=0.,source_end_sec=1.)))
        other = IdentityModeAdapter(Target(), NAMESPACE)
        self.assertNotIn('closed_display_assignment', other.annotate_caption(dict(naming_state='invalidated')))

    def test_display_roster_preserves_biometric_field_and_constant_unknown(self):
        rows = [dict(profile_id=None,display_profile_id='p1',label='P1 · assumed'),
            dict(profile_id='p2',display_profile_id='p2',label='P2')]
        apply_display_roster(rows, ['p1'], True, 'selected_closed')
        self.assertTrue(rows[0]['visible'])
        self.assertIsNone(rows[0]['profile_id'])
        self.assertFalse(rows[1]['visible'])
        apply_display_roster(rows, ['p1'], False, 'enrolled_names')
        self.assertEqual(rows[0]['label'], 'Unknown')
        self.assertTrue(rows[1]['visible'])

    def test_calibration_reason_is_separate_from_query_and_model_namespace(self):
        target = Target()
        status = gallery_status(target.gallery, NAMESPACE)
        self.assertEqual(status['status'], 'UNCALIBRATED_PERSONAL_DOMAIN')
        self.assertFalse(status['calibrated'])
        self.assertIsNone(status['score_threshold'])
        self.assertEqual(status['compatible_references'], 1)
        changed = dict(NAMESPACE, model_sha256='b'*64)
        self.assertEqual(gallery_status(target.gallery, changed)['status'], 'NAMESPACE_MISMATCH')
        self.assertEqual(gallery_status(Target(()).gallery, NAMESPACE)['status'], 'EMPTY_COMPATIBLE_GALLERY')

    def test_legacy_forced_confirmed_roster_result_cannot_publish_biometric_profile(self):
        resolver = SimpleNamespace(gallery=Target().gallery, annotate_caption=lambda row:deepcopy(row))
        row = dict(known_profile_id='p1', known_name='P1', naming_state='confirmed',
            prototype_assignment='forced', prototype_assignment_evidence_ids=['voice:1'])
        result = annotate_caption_policy(resolver,row,'selected_closed')
        self.assertEqual(result['naming_state'],'closed_assumption')
        self.assertFalse(result['voice_identity_verified'])
        self.assertEqual(result['closed_display_assignment']['profile_id'],'p1')
        self.assertEqual(row['naming_state'],'confirmed')

    def test_legacy_forced_decision_is_display_only_before_spatial_consumer(self):
        original = dict(identity=dict(assignment='forced',naming_state='confirmed'),naming_state='confirmed',
            name_revision=dict(replacement_naming_state='confirmed'))
        target = SimpleNamespace(resolve=lambda decision,evidence:deepcopy(original))
        result = RetainedClosedModeAdapter(target).resolve({},event())
        self.assertEqual(result['identity']['naming_state'],'closed_assumption')
        self.assertFalse(result['identity']['voice_identity_verified'])
        self.assertEqual(result['name_revision']['replacement_naming_state'],'closed_assumption')
        self.assertEqual(original['naming_state'],'confirmed')


class Scheduler:
    def __init__(self):
        self.evidence_expiry, self.revision_horizon, self.max_revisions_per_utterance = 2., 2., 10
        self._utterances = {'u':dict(tracker_id='t', source_start_sec=0., source_end_sec=1.,
            latest_label='P1', latest_known_profile_id='p1', latest_known_name='P1', latest_naming_state='confirmed',
            first_display_time=0., first_final_time=None, revision_count=0)}

    def _revise(self, evidence, decision):
        return []  # The pinned path skips a same-label metadata change.

    def _record(self, kind, evidence, payload):
        return dict(kind=kind, **payload)


class RevisionContracts(unittest.TestCase):
    def test_same_label_assumption_clears_verified_metadata_in_active_source(self):
        scheduler = Scheduler()
        install_revision_bridge(SimpleNamespace(n2_diarization='D0',_scheduler=SimpleNamespace(scheduler=scheduler)))
        decision = dict(name_revision=dict(track_id='t',replacement_label='P1',replacement_known_name='P1',
            replacement_known_profile_id='p1',replacement_naming_state='closed_assumption'))
        revised = scheduler._revise(event(),decision)
        self.assertEqual(len(revised),1)
        self.assertEqual(revised[0]['latest_naming_state'],'closed_assumption')
        self.assertFalse(revised[0]['changes_words'])
        self.assertEqual(scheduler._revise(event(),decision),[])

    def test_expired_disjoint_and_overlap_cannot_clear_unrelated_history(self):
        for evidence in (event(available=5.),event(start=2.,end=3.),dict(event(),overlap=True)):
            scheduler = Scheduler()
            install_revision_bridge(SimpleNamespace(n2_diarization='D0',_scheduler=SimpleNamespace(scheduler=scheduler)))
            decision = dict(name_revision=dict(track_id='t',replacement_label='Unknown',replacement_known_name=None,
                replacement_known_profile_id=None,replacement_naming_state='unknown'))
            self.assertEqual(scheduler._revise(evidence,decision),[])
            self.assertEqual(scheduler._utterances['u']['latest_naming_state'],'confirmed')


class Tracker:
    def __init__(self):
        self.inputs = []

    def update(self, vector, start, end, now, **kwargs):
        self.inputs.append((start,end,now,kwargs))
        return dict(tracker_id=7, anonymous_label='Speaker_7', state='committed', committed=True)

    def scheduling_state(self, now):
        return [dict(track_id=7)]

    def snapshot(self):
        return dict(calls=len(self.inputs))


class Provider:
    def __init__(self, stamp=.9):
        self.stamp, self.inputs, self.in_context = stamp, [], False

    @contextmanager
    def _query(self, end):
        self.in_context = True
        try:
            yield True
        finally:
            self.in_context = False

    def evidence_for_window(self, start, end, available):
        if not self.in_context:
            raise AssertionError('Recorded source pose context missing')
        self.inputs.append((start,end,available))
        return SimpleNamespace(available_at_sec=self.stamp)


class SpatialContracts(unittest.TestCase):
    def test_delayed_model_uses_source_cue_and_reports_unmodified_delay(self):
        tracker, provider = Tracker(), Provider()
        policy = SourceClockSpatialPolicy(tracker, provider)
        result = policy.associate(dict(tracker_id='native:slot0'),event(available=31.))
        self.assertEqual(provider.inputs,[(0.,1.,1.)])
        self.assertEqual(tracker.inputs[0][:3],(0.,1.,1.))
        self.assertEqual(result['spatial_association']['model_delay_from_source_sec'],30.)
        self.assertEqual(result['native_tracker_id'],'native:slot0')
        self.assertFalse(result['spatial_association']['current_position_claim'])
        self.assertFalse(provider.in_context)

    def test_future_cue_cannot_enter_shared_tracker(self):
        tracker = Tracker()
        policy = SourceClockSpatialPolicy(tracker, Provider(2.))
        with self.assertRaisesRegex(ValueError,'after the source window'):
            policy.associate(dict(tracker_id='native'),event())
        self.assertEqual(tracker.inputs,[])

    def test_audio_gates_and_clean_support_reach_original_tracker(self):
        tracker = Tracker()
        policy = SourceClockSpatialPolicy(tracker, Provider())
        policy.associate(dict(tracker_id='native'),dict(event(),speech=False,overlap=True))
        kwargs = tracker.inputs[0][3]
        self.assertFalse(kwargs['speech'])
        self.assertTrue(kwargs['overlap'])
        self.assertEqual(kwargs['clean_intervals'],[[0.,1.]])

    def test_source_linked_shared_track_reaches_caption_and_mixed_activity_stays_unknown(self):
        target = Target(closed=False)
        adapter = IdentityModeAdapter(target,NAMESPACE,spatial_policy=SourceClockSpatialPolicy(Tracker(),Provider()))
        adapter.resolve(dict(tracker_id='session:nemotron-slot-0'),event())
        emitted = []
        row = dict(utterance_id='u',text_revision_id='text:1',source_start_sec=0.,source_end_sec=1.,
            word_spans=[dict(id='w1',source_start_sec=0.,source_end_sec=.4)])
        engine = SimpleNamespace(_s6d_presentation=SimpleNamespace(snapshot_rows=lambda:[row]),
            _n2_lock=__import__('threading').RLock(),_n2_timeline=SimpleNamespace(end=1.,reserve_sec=120.,
                associate=lambda a,b:dict(slot=0,reason='singleton')),
            _n2_associations={},_n2_span_signatures={},_n2_revision=0,_session_dir=Path('session'),
            n2_name_map=adapter,_s7_observed_clock=SimpleNamespace(relative=lambda:31.),
            _emit=lambda kind,end,payload:emitted.append(payload))
        revise_spatial_caption_spans(engine)
        self.assertEqual(emitted[0]['replacement_tracker_id'],7)
        self.assertEqual(emitted[0]['native_tracker_id'],'session:nemotron-slot-0')
        self.assertEqual(emitted[0]['evidence_ids'],['voice:1'])
        revise_spatial_caption_spans(engine)
        self.assertEqual(len(emitted),1)
        engine._n2_associations.clear()
        engine._n2_timeline.associate=lambda a,b:dict(slot=None,reason='mixed')
        revise_spatial_caption_spans(engine)
        self.assertIsNone(emitted[-1]['replacement_tracker_id'])
        self.assertIsNone(emitted[-1]['latest_known_profile_id'])


if __name__ == '__main__':
    unittest.main()
