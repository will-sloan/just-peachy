"""Focused regression for scoring denominators, gate evidence and limited lineage."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile as sf

from s4_h2_analysis import score_text, rail_metrics, gate_evidence, journal_audio, speaker_turn_evidence, normalize
from s4_h2_run import alignment_for, fixed_gain_copy, recover_completed_job, stable_hash, verified_restoration


def event(kind, time, payload):
    return {'event_type': kind, 'source_time_sec': time, 'payload': payload}


class S4AnalysisTest(unittest.TestCase):
    def test_existing_edit_counts_and_denominators(self):
        result = score_text('a b c', 'a x c d', duration_s=10)
        self.assertEqual(result['word_counts']['substitutions'], 1)
        self.assertEqual(result['word_counts']['insertions'], 1)
        self.assertEqual(result['word_counts']['reference_words'], 3)
        self.assertEqual(result['wer'], 2/3)

    def test_empty_reference_has_no_defined_wer(self):
        result = score_text('', 'two invented words', duration_s=30)
        self.assertIsNone(result['wer'])
        self.assertIsNone(result['cer'])
        self.assertEqual(result['empty_reference_insertions'], 3)
        self.assertEqual(result['empty_reference_words_per_minute'], 6)

    def test_overlap_does_not_get_arbitrary_concatenation_score(self):
        result = score_text('a b', 'b a', duration_s=5, overlap=True)
        self.assertEqual(result['status'], 'LIMITED')
        self.assertIsNone(result['wer'])

    def test_normalization_is_explicit_and_shared(self):
        self.assertEqual(normalize("  IT'S  $12. "), 'its 12')
        result = score_text("It's fine.", 'ITS FINE', duration_s=1)
        self.assertEqual(result['cer'], 0)
        self.assertEqual(result['character_counts']['reference_characters'], 7)

    def test_rail_runs_onset_and_steady_are_distinct(self):
        full = 2**23
        x = np.array([0, -full, -full, 0, full-2, full-2, full-2, 0])
        result = rail_metrics(x, rate=4, support_intervals=[(0, 2)], onset_window_s=0.5)
        self.assertEqual(result['rail_samples'], 5)
        self.assertEqual(result['maximum_contiguous_rail_run_samples'], 3)
        self.assertEqual(result['onset_rail_samples'], 1)
        self.assertEqual(result['steady_support_rail_samples'], 4)
        json.dumps(result, allow_nan=False)

    def test_gate_reconstructs_pcm16_and_overlapping_reasons(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'mono.wav'
            sf.write(path, np.r_[np.full(12000, .0001), np.full(12000, .01)], 16000, subtype='FLOAT')
            events = [event('segmentation', .75, {'speech': True, 'overlap': False}),
                      event('speaker_decision', 1, {}), event('speaker_decision', 1.25, {}),
                      event('speaker_decision', 1.5, {})]
            result = gate_evidence(path, events)
            self.assertEqual(result['counts']['single_speech_hops_below_rms'], 1)
            self.assertEqual(result['counts']['eligible_hops_reconstructed'], 3)
            self.assertEqual(result['counts']['eligible_without_decision'], 0)

    def test_never_average_multichannel_h2_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'six.wav'
            sf.write(path, np.zeros((100, 6)), 16000, subtype='PCM_24')
            with self.assertRaises(ValueError):
                journal_audio(path)

    def test_returning_labels_use_source_window_not_final_transcript_time(self):
        turns = [{'participant_id': 'A', 'start_s': 0, 'end_s': 1},
                 {'participant_id': 'B', 'start_s': 2, 'end_s': 3},
                 {'participant_id': 'A', 'start_s': 4, 'end_s': 5}]
        events = [event('speaker_decision', t, {'anonymous_label': label}) for t, label in
                  [(0.5, 'Speaker_1'), (.75, 'Speaker_1'), (2.5, 'Speaker_2'), (4.5, 'Speaker_3')]]
        result = speaker_turn_evidence(events, turns)
        self.assertFalse(result['returning_participants'][0]['consistent'])
        self.assertEqual(result['turns'][1]['dominant_label'], 'Speaker_2')

    def test_missing_return_evidence_is_unknown_not_failure(self):
        turns = [{'participant_id': 'A', 'start_s': 0, 'end_s': 1}, {'participant_id': 'A', 'start_s': 2, 'end_s': 3}]
        result = speaker_turn_evidence([], turns)
        self.assertIsNone(result['returning_participants'][0]['consistent'])

    def test_cross_speaker_overlap_window_is_not_identity_scored(self):
        turns = [{'participant_id': 'A', 'start_s': 0, 'end_s': 2}, {'participant_id': 'B', 'start_s': 1, 'end_s': 3}]
        events = [event('speaker_decision', 1.75, {'anonymous_label': 'Speaker_1'})]
        result = speaker_turn_evidence(events, turns)
        self.assertEqual(sum(t['decision_count'] for t in result['turns']), 0)

    def test_fixed_adapter_gain_preserves_source_and_refuses_rewrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'raw.wav', Path(temporary) / 'adapter.wav'
            sf.write(source, np.array([-.1, 0, .1], dtype=np.float32), 16000, subtype='FLOAT')
            before = source.read_bytes()
            result = fixed_gain_copy(source, output, 2)
            self.assertEqual(result['gain_scalar'], 2)
            np.testing.assert_array_equal(sf.read(output, dtype='float32')[0], np.array([-.2, 0, .2], np.float32))
            self.assertEqual(source.read_bytes(), before)
            with self.assertRaises(RuntimeError):
                fixed_gain_copy(source, output, 3)

    def test_fixed_adapter_gain_does_not_silently_clip(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary) / 'raw.wav', Path(temporary) / 'adapter.wav'
            sf.write(source, np.array([.6], dtype=np.float32), 16000, subtype='FLOAT')
            with self.assertRaises(ValueError):
                fixed_gain_copy(source, output, 2)
            self.assertFalse(output.exists())

    def test_resume_adopts_completed_model_without_repeating(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            session = root / 'edge_speech_sessions' / 'one'
            session.mkdir(parents=True)
            (session / 'session_summary.json').write_text(json.dumps({'state': 'COMPLETED'}))
            self.assertEqual(recover_completed_job({'job_key': 'same', 'status': 'MODEL_COMPLETED'}, 'same', root), session)
            with self.assertRaises(RuntimeError):
                recover_completed_job({'job_key': 'old'}, 'new', root)

    def test_resume_does_not_rerun_incomplete_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(RuntimeError):
                recover_completed_job({'job_key': 'same', 'status': 'STARTED'}, 'same', temporary)

    def test_missing_alignment_is_not_filled_with_fitted_shift(self):
        capture = {'payload': {'capture_minus_source_offset_samples': 1600}}
        self.assertIsNone(alignment_for({}, 'S4_01', 'O0', capture))
        mapping = {'S4_01': {'O0': {'processed_output_minus_recaptured_input_s': .06, 'evidence': 'measured correlation'}}}
        self.assertAlmostEqual(alignment_for(mapping, 'S4_01', 'O0', capture)['alignment_offset_s'], .21)
        with self.assertRaises(ValueError):
            alignment_for({'S4_01': {'O0': {'processed_output_minus_recaptured_input_s': .06}}}, 'S4_01', 'O0', capture)

    def test_identity_hash_is_order_independent(self):
        self.assertEqual(stable_hash({'gain': 2, 'raw': 'abc'}), stable_hash({'raw': 'abc', 'gain': 2}))

    def test_bound_exact_recovery_preserves_failed_history(self):
        from s4_h2_analysis import binding
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            initial = {'identity': {'I2S_INPUT_PACKED': [0], 'USB_BIT_DEPTH': [16, 16]}, 'settings': {'gain': [84.72903]}, 'observe_only': {}, 'usb_bits': [16, 16]}
            original = {'status': 'FAIL', 'error': 'Getter roundtrip differed'}
            path = folder / 'restoration.json'
            path.write_text(json.dumps(original))
            (folder / 'initial_state.json').write_text(json.dumps(initial))
            recovery = {'status': 'PASS', 'original_failure': original, 'original_failure_binding': binding(path),
                        'exact_recorded_configuration_match': True, 'hardware_lease_released': True,
                        'audio_handles_closed': True, 'telemetry_process_closed': True, 'packed_input_disabled': True,
                        'readback': {k: initial[k] for k in ('settings', 'identity', 'observe_only')}}
            recovery_path = folder / 'restoration_recovery.json'
            recovery_path.write_text(json.dumps(recovery))
            self.assertTrue(verified_restoration(path)['recovery_used'])
            self.assertEqual(json.loads(path.read_text()), original)
            recovery['readback']['settings'] = {'gain': [84.72902]}
            recovery_path.write_text(json.dumps(recovery))
            with self.assertRaises(AssertionError):
                verified_restoration(path)
            recovery['readback']['settings'] = initial['settings']
            recovery['original_failure_binding']['sha256'] = '0' * 64
            recovery_path.write_text(json.dumps(recovery))
            with self.assertRaises(ValueError):
                verified_restoration(path)

    def test_unrecovered_failure_and_unclosed_handle_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'restoration.json'
            path.write_text(json.dumps({'status': 'FAIL'}))
            with self.assertRaises(FileNotFoundError):
                verified_restoration(path)
            path.write_text(json.dumps({'status': 'PASS', 'exact_recorded_configuration_match': True,
                                       'hardware_lease_released': True, 'audio_handles_closed': False}))
            with self.assertRaises(AssertionError):
                verified_restoration(path)


if __name__ == '__main__':
    unittest.main()
