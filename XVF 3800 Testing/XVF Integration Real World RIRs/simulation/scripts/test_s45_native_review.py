"""Small model-free fixtures. README_S45_NATIVE_REVIEW.md."""
import copy
import json
import unittest
import tempfile
from pathlib import Path

import numpy as np

from s45_native_review import Evidence, join_primary_bindings, json_stream, qualified_alignment, verify_audio, verify_event_metrics, verify_gate, verify_metric_identity, verify_turns


def native_fixture():
    telemetry = {'elapsed_wall_sec': 1., 'audio_frames_dropped': 0, 'portaudio_input_overflows': 0, 'raw_capture_reserve_failures': 0}
    events = [{'event_type': x, 'payload': {}} for x in ('session_created', 'session_started', 'source_started')]
    events.append({'event_type': 'session_completed', 'payload': {'telemetry': telemetry}})
    summary = {'state': 'COMPLETED', 'telemetry': telemetry, 'scientific_policy': {}}
    metrics = {'state': 'COMPLETED', 'telemetry': telemetry, 'scientific_policy': {}, 'failure_events': [],
               'event_counts': {e['event_type']: 1 for e in events}, 'final_transcripts': [],
               'speaker': {'emitted_final_labels': [], 'decision_label_counts': {}, 'decision_label_switches': 0,
                           'embedding_calls_successful': 0, 'embedding_calls_rejected': None, 'reconciled_labels': None,
                           'naming_accuracy': None, 'reconciliation_status': 'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE'}}
    return events, summary, metrics, events + [telemetry]


class ReviewTests(unittest.TestCase):
    def test_current_contract_and_dry_parent_joins(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = {k: Path(folder) / (k + '.json') for k in ('scene_manifest', 'sentinel_plan', 'dry_plan', 'output_policy')}
            for path in paths.values(): path.write_text('{}', encoding='utf-8')
            ev = Evidence(); contract = {k: ev.bind(p) for k, p in paths.items()}
            dry = {'identity': {k: contract[k] for k in ('scene_manifest', 'sentinel_plan')}}
            self.assertEqual(join_primary_bindings(ev, contract, paths, dry), contract)

    def test_contract_other_path_rejected_even_with_same_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            active, other = Path(folder) / 'active.json', Path(folder) / 'other.json'
            active.write_text('{}'); other.write_text('{}'); ev = Evidence()
            with self.assertRaises(ValueError): join_primary_bindings(ev, {'scene_manifest': ev.bind(other)}, {'scene_manifest': active})

    def test_replaced_current_plan_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'plan.json'; path.write_text('{}'); bound = Evidence().bind(path)
            path.write_text('{"replacement":true}')
            with self.assertRaises(ValueError): join_primary_bindings(Evidence(), {'sentinel_plan': bound}, {'sentinel_plan': path})

    def test_dry_parent_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = {k: Path(folder) / (k + '.json') for k in ('scene_manifest', 'sentinel_plan')}
            for path in paths.values(): path.write_text('{}')
            ev = Evidence(); contract = {k: ev.bind(p) for k, p in paths.items()}
            dry = {'identity': copy.deepcopy(contract)}; dry['identity']['scene_manifest']['sha256'] = '0' * 64
            with self.assertRaises(ValueError): join_primary_bindings(ev, contract, paths, dry)

    def test_quarantined_metric_identity_and_level(self):
        row = {'case_id': 'S45_01_01', 'stream': 'O1', 'kind': 'outputs', 'status': 'QUARANTINED', 'level_gate': 'QUARANTINED_GROSS_SATURATION'}
        metric = {k: row[k] for k in ('case_id', 'stream', 'kind', 'level_gate')}; metric['fixed_host_gain'] = 1
        verify_metric_identity(row, metric, 1, 'QUARANTINED_GROSS_SATURATION')
        for key, value in [('case_id', 'S45_01_02'), ('stream', 'O0'), ('fixed_host_gain', 2), ('level_gate', 'LEVEL_GATE_NO_RAILS')]:
            changed = {**metric, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError): verify_metric_identity(row, changed, 1, 'QUARANTINED_GROSS_SATURATION')

    def test_alignment_adds_retained_margin_once(self):
        result = qualified_alignment({'payload': {'capture_minus_source_offset_samples': 1600}},
                                     {'processed_output_minus_recaptured_input_s': .02, 'evidence': 'independent audio delay'})
        self.assertAlmostEqual(result['alignment_offset_s'], .17)
        self.assertEqual(result['rir_retained_margin_s'], .05)

    def test_missing_alignment_not_invented(self):
        self.assertIsNone(qualified_alignment({'payload': {}}, None))
        with self.assertRaises(ValueError): qualified_alignment({'payload': {}}, {'processed_output_minus_recaptured_input_s': .1})

    def test_mixed_pretty_json(self):
        self.assertEqual(json_stream('{"event":1}\n' + json.dumps({'elapsed': 2}, indent=2)), [{'event': 1}, {'elapsed': 2}])

    def test_truncated_json_rejected(self):
        with self.assertRaises(ValueError): json_stream('{"a":')

    def test_exact_audio_and_changed_journal(self):
        raw = np.array([[0.], [.25], [-.25]], dtype=np.float32)
        adapter = raw * 2
        pcm = np.array([0, 16384, -16384], dtype='<i2').tobytes()
        np.testing.assert_array_equal(verify_audio(raw, adapter, pcm, 2), adapter[:, 0])
        with self.assertRaises(ValueError): verify_audio(raw, adapter, pcm[:-1] + b'\x01', 2)

    def test_changed_gain_rejected(self):
        raw = np.array([[.25]], dtype=np.float32)
        with self.assertRaises(ValueError): verify_audio(raw, raw, np.array([8192], dtype='<i2').tobytes(), 2)

    def test_native_metadata(self):
        self.assertEqual(verify_event_metrics(*native_fixture())['event_counts']['session_completed'], 1)

    def test_reconstructed_summary_rejected(self):
        items = native_fixture(); items[1]['reconstruction_provenance'] = {}
        with self.assertRaises(ValueError): verify_event_metrics(*items)

    def test_invented_reconciled_labels_rejected(self):
        items = native_fixture(); items[2]['speaker']['reconciled_labels'] = []
        with self.assertRaises(ValueError): verify_event_metrics(*items)

    def test_changed_stdout_event_rejected(self):
        items = list(native_fixture()); items[3] = copy.deepcopy(items[3]); items[3][0]['payload']['changed'] = True
        with self.assertRaises(ValueError): verify_event_metrics(*items)

    def test_gate_counts_and_wrong_counts(self):
        science = {'sample_rate': 16000, 'embedding_hop_sec': .25, 'embedding_window_sec': .5, 'minimum_rms': .002}
        events = [{'event_type': 'segmentation', 'source_time_sec': .25, 'payload': {'speech': True, 'overlap': False}}]
        events += [{'event_type': 'speaker_decision', 'source_time_sec': t} for t in (.5, .75, 1.)]
        counts = {'total_hops': 4, 'eligible_hops_reconstructed': 3, 'emitted_embedding_decisions': 3,
                  'eligible_without_decision': 0, 'decision_despite_ineligible': 0, 'single_speech_hops': 4,
                  'single_speech_hops_below_rms': 0, 'blocked_no_speech': 0, 'blocked_overlap': 0,
                  'blocked_short_window': 1, 'blocked_below_minimum_rms': 0}
        metrics = {'embedding_gate_evidence': {'minimum_rms': .002, 'hop_s': .25, 'embedding_window_s': .5,
                                             'counts': counts, 'embedded_window_unique_speech_seconds': None}}
        self.assertEqual(verify_gate(np.full(16000, .01, dtype=np.float32), events, metrics, science), counts)
        counts['eligible_hops_reconstructed'] = 4
        with self.assertRaises(ValueError): verify_gate(np.full(16000, .01, dtype=np.float32), events, metrics, science)

    def test_missing_first_turn_is_unknown(self):
        segments = [{'source_start_sample': i * 32000, 'source_stop_sample': i * 32000 + 16000,
                     'speaker_key': 'A', 'transcript': 'x'} for i in range(2)]
        events = [{'event_type': 'speaker_decision', 'source_time_sec': 2.75, 'payload': {'anonymous_label': 'X'}}]
        evidence = {'alignment_offset_s': 0, 'turns': [
            {'turn_index': 0, 'participant_id': 'A', 'decision_count': 0, 'labels': {}, 'dominant_label': None, 'label_switches': 0, 'fragment_count': 0, 'missing_evidence': True},
            {'turn_index': 1, 'participant_id': 'A', 'decision_count': 1, 'labels': {'X': 1}, 'dominant_label': 'X', 'label_switches': 0, 'fragment_count': 1, 'missing_evidence': False}],
            'returning_participants': [{'participant_id': 'A', 'turn_indices': [0, 1], 'dominant_labels': [None, 'X'], 'consistent': None}]}
        metrics = {'speaker': {'reference_turn_evidence': evidence}}
        self.assertEqual(verify_turns(events, metrics, segments, 0)['unknown'], 1)
        evidence['returning_participants'][0]['consistent'] = True
        with self.assertRaises(ValueError): verify_turns(events, metrics, segments, 0)


if __name__ == '__main__':
    unittest.main()
