"""Tiny adversarial fixtures. See README_S6D_NATIVE_EVIDENCE_V1.md."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import unittest
import wave
import s6d_native_evidence_v1 as E


def good():
    digest = 'a' * 64
    job = dict(expected_frames=16000, audio_duration_sec=1., audio_pcm_sha256=digest, settings={})
    worker = dict(depth=0, thread_alive=False, closed=True, error=None, accepted=2, completed=2)
    queues = dict(event_consumer=dict(depth=0), journal=worker, punctuation=worker, policy=worker)
    t = dict(state='COMPLETED', source_duration_sec=1., asr_cursor_sec=1., speaker_cursor_sec=1.,
             paired_audio_samples=16000, identity_audio_samples=16000, audio_frames_dropped=0,
             portaudio_input_overflows=0, raw_capture_reserve_failures=0, live_lanes_at_finalization=[],
             bundle_retained_due_live_lanes=False, scheduler=dict(closed=True, pending_events=0,
             watermarks=dict(asr='closed', speaker='closed')), s6d=queues)
    result = dict(status='COMPLETE', failure=None, native_tested=True, job=job, telemetry=t,
                  resource_observer_closed=True, event_consumer_drained=True, observer_errors=[], completion_errors=[])
    final = dict(state='COMPLETED', finalization_error=None, live_lanes_at_finalization=[],
                 resident_bundle_lease_retained=False, event_and_transcript_handles_closed=True,
                 source_samples=16000, identity_samples=16000)
    proofs = dict(source=dict(frames=16000, sha256=digest), asr=dict(bytes=32000, sha256=digest),
                  identity=dict(bytes=32000, sha256=digest))
    closure = dict(state='COMPLETED', full_event_consumer_drained=True, queues=queues)
    return deepcopy((result, job, final, proofs, closure))


def dispatch():
    def e(kind, **payload): return dict(event_type=kind, payload=payload)
    return [e('source_started', expected_samples=16000, pipeline_sample_rate=16000),
            e('research_asr_dispatch', source_start_sec=0., source_end_sec=.9),
            e('research_asr_tail_dispatch', source_start_sec=.9, source_end_sec=1., samples=1600),
            e('research_asr_drain', source_end_sec=1., synthetic_right_padding_sec=.66, padding_is_observed_audio=False),
            e('research_scheduler_watermark', lane='asr', lane_closed=True),
            e('research_scheduler_watermark', lane='speaker', lane_closed=True), e('session_completed')]


class Checks(unittest.TestCase):
    def test_complete_valid(self): self.assertEqual(E.validate_completion(*good()), [])
    def test_stopped_prefix_rejected(self):
        args = good()
        args[0]['telemetry'].update(source_duration_sec=.5, asr_cursor_sec=.5, speaker_cursor_sec=.5,
                                    paired_audio_samples=8000, identity_audio_samples=8000)
        args[2].update(source_samples=8000, identity_samples=8000)
        self.assertTrue(E.validate_completion(*args))
    def test_journal_corruption_and_missing_tail(self):
        for name, field, value in [('asr', 'bytes', 31998), ('identity', 'sha256', 'b'*64)]:
            args = good(); args[3][name][field] = value
            self.assertTrue(E.validate_completion(*args))
    def test_nan_cursor_rejected(self):
        args = good(); args[0]['telemetry']['speaker_cursor_sec'] = float('nan')
        self.assertTrue(E.validate_completion(*args))
    def test_worker_closed_but_unfinished_rejected(self):
        args = good(); args[0]['telemetry']['s6d']['journal']['completed'] = 1
        self.assertTrue(E.validate_completion(*args))
    def test_observer_late_failure_rejected(self):
        args = good(); args[0]['observer_errors'] = ['late write failure']
        self.assertTrue(E.validate_completion(*args))
    def test_missing_closure_and_unclosed_scheduler(self):
        args = good(); self.assertTrue(E.validate_completion(*args[:-1], None))
        args[0]['telemetry']['scheduler']['watermarks']['speaker'] = 'open'
        self.assertTrue(E.validate_completion(*args))
    def test_production_expected_count_required(self):
        args = good(); del args[1]['expected_frames']
        self.assertTrue(E.validate_completion(*args))
    def test_full_dispatch_excludes_padding(self): self.assertEqual(E.validate_dispatch(dispatch(), 16000)['frames'], 16000)
    def test_dispatch_gap_and_duplicate(self):
        for start in (.8, .95):
            rows = dispatch(); rows[2]['payload']['source_start_sec'] = start
            with self.assertRaises(ValueError): E.validate_dispatch(rows, 16000)
    def test_missing_final_tail_and_watermark(self):
        for index in (2, 5):
            rows = dispatch(); rows.pop(index)
            with self.assertRaises(ValueError): E.validate_dispatch(rows, 16000)
    def test_padding_cannot_replace_observed_tail(self):
        rows = dispatch(); rows[3]['payload']['padding_is_observed_audio'] = True
        with self.assertRaises(ValueError): E.validate_dispatch(rows, 16000)
    def test_frame_rejects_bool_nan_fraction(self):
        for value in (True, float('nan'), .1234567):
            with self.assertRaises(ValueError): E.frame(value)
    def test_shift_keeps_repeated_occurrences_and_incomplete(self):
        turn = dict(segment_index=0, source_id='repeated', metadata_identity='person',
                    file_support=[[1, 4]], active_ranges=[[2, 3]], sole=[[2, 3]])
        pieces = [dict(case_id='a', start_sample=0, samples=10, gap_before_samples=0,
                       mapped_turns=[turn], all_reference_complete=True),
                  dict(case_id='a', start_sample=12, samples=10, gap_before_samples=2,
                       mapped_turns=[turn], all_reference_complete=False)]
        rows = E.shift_reference_pieces(pieces, 22)
        self.assertEqual(rows[1]['file_support'], [[13, 16]])
        self.assertNotEqual(rows[0]['occurrence_id'], rows[1]['occurrence_id'])
        self.assertFalse(rows[1]['all_reference_complete'])
        self.assertEqual(turn['file_support'], [[1, 4]])
    def test_shift_rejects_gap_and_foreign_support(self):
        p = dict(case_id='a', start_sample=1, samples=10, gap_before_samples=0, mapped_turns=[], all_reference_complete=True)
        with self.assertRaises(ValueError): E.shift_reference_pieces([p], 11)
        p.update(start_sample=0, mapped_turns=[dict(segment_index=0, file_support=[[0, 11]])])
        with self.assertRaises(ValueError): E.shift_reference_pieces([p], 10)
    def test_never_correct_denominator_preserved(self):
        rows = [dict(occurrence_id='a', status='OBSERVED', wait_sec=.2),
                dict(occurrence_id='b', status='RIGHT_CENSORED', wait_sec=None, censor_sec=5),
                dict(occurrence_id='c', status='INCOMPLETE_REFERENCE', wait_sec=None)]
        self.assertEqual(E.opportunity_census(rows), dict(total=3, observed=1, right_censored=1, unavailable=1))
        rows[1]['wait_sec'] = 0
        with self.assertRaises(ValueError): E.opportunity_census(rows)
    def test_actual_tiny_wav_body(self):
        path = ROOT/'source.wav'
        with wave.open(str(path), 'wb') as f:
            f.setparams((1,2,16000,0,'NONE','not compressed')); f.writeframes(struct.pack('<hhh', -32768, 0, 32767))
        proof = E.pcm_proof(path)
        self.assertEqual(proof['frames'], 3)
        self.assertEqual(proof['sha256'], hashlib.sha256(struct.pack('<hhh', -32768,0,32767)).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    ROOT = args.output.resolve(); ROOT.mkdir(parents=True, exist_ok=False)
    with (ROOT/'TESTS.log').open('x', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    receipt = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun,
                   failures=len(result.failures), errors=len(result.errors), helper=E.binding(E.__file__),
                   checks=E.binding(__file__), log=E.binding(ROOT/'TESTS.log'), models=0, devices=0)
    (ROOT/'FIXTURE_RECEIPT.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt)); raise SystemExit(not result.wasSuccessful())
