"""D1 evidence review corruption fixtures. See README_REVIEW_D1.md."""
from copy import deepcopy
import json
import unittest

import test_d1_lane_components as fixtures
from review_d1_components import scan_events


class TestD1EvidenceReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TestD1ActualLoop.setUpClass()
        fixture = fixtures.TestD1ActualLoop()
        capture = fixture.setup_capture()
        cls.summary = capture.run_capture(fixture.encoder)
        cls.rows = [json.loads(line) for line in fixture.log.getvalue().splitlines()]
        cls.wave, cls.namespace = fixture.wave, fixture.encoder.namespace
        from app.n2_pipeline import ActivityTimeline
        cls.timeline = ActivityTimeline

    def scan(self, rows=None, summary=None):
        return scan_events(self.rows if rows is None else rows, self.wave,
            self.summary if summary is None else summary, self.namespace, self.timeline)

    def changed(self, kind):
        rows = deepcopy(self.rows)
        return rows, next(e for e in rows if e['event_type'] == kind)

    def test_actual_application_fixture_passes_all_frames_and_queries(self):
        result = self.scan()
        self.assertEqual(result['native_frames'], 251)
        self.assertEqual(result['embeddings'], 3)
        self.assertEqual(result['short_runs'], 1)

    def test_missing_frames_or_final_drain_cannot_pass(self):
        for kind in ('n2_diarization_frames', 'component_d1_dispatch'):
            rows = deepcopy(self.rows)
            pos = next(i for i in range(len(rows)-1, -1, -1) if rows[i]['event_type'] == kind)
            del rows[pos]
            with self.assertRaises(ValueError): self.scan(rows)

    def test_query_waveform_hash_and_vector_corruption(self):
        rows, event = self.changed('component_d1_embedding_call')
        event['payload']['waveform_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'waveform support'): self.scan(rows)
        rows, event = self.changed('research_embedding')
        event['payload']['normalized_embedding'][0] = .5
        with self.assertRaisesRegex(ValueError, 'semantics'): self.scan(rows)
        rows, event = self.changed('research_embedding')
        event['payload']['model_namespace'] = {'model': 'wrong-encoder'}
        with self.assertRaisesRegex(ValueError, 'namespace'): self.scan(rows)

    def test_short_turn_denominator_cannot_disappear(self):
        rows = [e for e in self.rows if not (e['event_type'] == 'n2_exclusive_run_coverage'
            and e['payload']['unavailable_reason'] == 'BELOW_EMBEDDING_MINIMUM')]
        with self.assertRaises(ValueError): self.scan(rows)

    def test_future_query_and_bad_probability_rejected(self):
        rows, event = self.changed('research_embedding')
        event['payload']['source_end_sec'] = 500
        with self.assertRaises(ValueError): self.scan(rows)
        rows, event = self.changed('n2_diarization_frames')
        event['payload']['probabilities'][0][0] = 1.1
        with self.assertRaisesRegex(ValueError, 'probabilities'): self.scan(rows)

    def test_modeled_clock_may_not_be_relabelled_or_changed(self):
        rows, event = self.changed('component_d1_dispatch')
        event['payload']['modeled_available_at_sec'] += 1
        with self.assertRaises(ValueError): self.scan(rows)
        rows, event = self.changed('n2_diarization_frames')
        event['component_clock'] = 'observed_S7'
        with self.assertRaisesRegex(ValueError, 'falsely observed'): self.scan(rows)

    def test_summary_and_known_identity_forgery_rejected(self):
        summary = deepcopy(self.summary)
        summary['native_frames'] += 1
        with self.assertRaisesRegex(ValueError, 'Summary'): self.scan(summary=summary)
        rows, event = self.changed('speaker_decision')
        event['payload']['known_profile_id'] = 'unadmitted'
        with self.assertRaisesRegex(ValueError, 'known identity'): self.scan(rows)


if __name__ == '__main__': unittest.main()
