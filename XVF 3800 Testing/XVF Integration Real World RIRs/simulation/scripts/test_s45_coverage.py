"""Offline metadata-contract tests; no models, audio or hardware. README_S45_COVERAGE.md."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import s45_coverage as c


def fixture():
    geometry = {'room_table': 'Test room', 'recorder_position': 'Table', 'orientation': 'FLAT', 'obstructed': False,
                'speaker_angle_deg_effective': -20, 'source_distance_m_effective': 1.0}
    source = {'source_id': 'probe1', 'identity': 'CMU_test', 'dataset': 'CMU ARCTIC', 'split': 'development',
              'usage': 'probe', 'samples': 16000, 'transcript': 'A whole test.', 'preparation_gain': 0.5,
              'role_frozen_before_QC': True, 'prompt_group': 'TEXT_a', 'quality_disposition': 'PASS',
              'source_binding': {'sha256': 'raw'}, 'decoded_16k_binding': {'sha256': 'decoded'}}
    segment = {'kind': 'utterance', 'source_id': 'probe1', 'speaker_key': 'CMU_test', 'participant_id': 'A',
               'source_start_sample': 48000, 'source_stop_sample': 64000, 'convolution_stop_sample': 64100,
               'rir_id': 'R1', 'source_split': 'development', 'whole_clip': True, 'source_crop_samples': [0, 16000],
               'preparation_gain_scalar': 0.5, 'transcript': 'A whole test.'}
    scene = {'case_id': 'SCENE1', 'family_id': 'F01', 'split': 'development', 'reserve_stratum': 'development',
             'source_partition': 'development', 'task_scoring_allowed': True, 'duration_s': 20,
             'receiver_configuration': {k: geometry[k] for k in c.GROUP_KEYS}, 'segments': [segment],
             'snr_reference_segments': [], 'cast': {'A': 'CMU_test'}, 'canonical_audio': {'sha256': 'canonical'},
             'overlap_scoring_limited': False, 'all_speaker_reference_complete': True,
             'common_family_headroom_scalar': 1, 'canonical_peak_fs': 0.1, 'all_speaker_references': []}
    rirs = {'records': [{'run_id': 'R1', 'can_proceed_to_hil_proof': True, 'capture_audit_pass': True,
                         'original_acquisition_status': 'REVIEW', 'geometry': geometry, 'output': {'sha256': 'rir'}}]}
    manifest = {'validation': {'status': 'PASS'}, 'scenes': [scene], 'selected_sources': {'probe1': copy.deepcopy(source)},
                'selected_noise': {}, 'selected_rirs': {'R1': {'file': {'sha256': 'rir'}, 'geometry': copy.deepcopy(geometry)}}}
    return manifest, {'probe1': source}, {'prepared_segments': []}, rirs


def inspect(data):
    return c.analyze_bank(*data, expected_scenes=1, expected_development=1)


class CoverageTests(unittest.TestCase):
    def test_numeric_bin_boundaries(self):
        self.assertEqual([c.duration_bin(n) for n in [0.9, 1, 1.9, 2, 2.9, 3, 5, 5.001]],
                         ['under_1s', '1_to_under_2s', '1_to_under_2s', '2_to_under_3s', '2_to_under_3s', '3_to_5s', '3_to_5s', 'over_5s'])

    def test_snr_reference_is_not_actual_played_speech(self):
        data = fixture()
        scene = data[0]['scenes'][0]
        scene['snr_reference_segments'] = scene['segments']
        scene['segments'] = []
        scene['cast'] = {}
        result = inspect(data)
        self.assertEqual(len(result['actual']), 0)
        self.assertEqual(len(result['calibration']), 1)

    def test_enrollment_cannot_be_canonical_or_calibration_probe(self):
        for mode in ('segments', 'snr_reference_segments'):
            data = fixture()
            data[1]['probe1']['usage'] = 'enrollment_reference'
            data[0]['selected_sources']['probe1']['usage'] = 'enrollment_reference'
            if mode == 'snr_reference_segments':
                data[0]['scenes'][0]['snr_reference_segments'] = data[0]['scenes'][0]['segments']
                data[0]['scenes'][0]['segments'] = []
                data[0]['scenes'][0]['cast'] = {}
            with self.assertRaisesRegex(c.CoverageError, 'Enrollment/non-probe'):
                inspect(data)

    def test_rejects_angle_sign_flip_and_over_5m(self):
        data = fixture()
        data[0]['selected_rirs']['R1']['geometry']['speaker_angle_deg_effective'] = 20
        with self.assertRaisesRegex(c.CoverageError, 'angle sign'):
            inspect(data)
        data = fixture()
        data[3]['records'][0]['geometry']['source_distance_m_effective'] = 100
        with self.assertRaisesRegex(c.CoverageError, 'distance outside'):
            inspect(data)

    def test_rejects_nonqualified_acquisition_and_retakes(self):
        for status in ('RETAKE', 'TEST', 'FAIL'):
            data = fixture()
            data[3]['records'][0]['original_acquisition_status'] = status
            with self.assertRaisesRegex(c.CoverageError, 'qualified acquisition'):
                inspect(data)

    def test_rejects_heldout_speaker_in_development(self):
        data = fixture()
        data[1]['probe1']['split'] = 'downstream_reserve'
        data[0]['selected_sources']['probe1']['split'] = 'downstream_reserve'
        with self.assertRaisesRegex(c.CoverageError, 'Speech reserve leakage'):
            inspect(data)

    def test_rejects_identity_misassignment_and_crop(self):
        data = fixture()
        data[0]['scenes'][0]['segments'][0]['speaker_key'] = 'CMU_other'
        data[0]['scenes'][0]['cast'] = {'A': 'CMU_other'}
        with self.assertRaisesRegex(c.CoverageError, 'identity misassignment'):
            inspect(data)
        data = fixture()
        data[0]['scenes'][0]['segments'][0]['source_crop_samples'][0] = 100
        with self.assertRaisesRegex(c.CoverageError, 'cropped'):
            inspect(data)

    def test_no_l2_and_no_parent_split_leakage(self):
        source = fixture()[1]['probe1']
        person = {'identity': 'CMU_test', 'dataset': 'CMU ARCTIC', 'split': 'development'}
        source['dataset'] = 'L2 ARCTIC'
        with self.assertRaisesRegex(c.CoverageError, 'Unapproved'):
            c.validate_sources({'people': [person], 'sources': [source]}, {})
        source['dataset'] = 'CMU ARCTIC'
        other = {**source, 'source_id': 'probe2', 'identity': 'CMU_reserve', 'split': 'downstream_reserve'}
        with self.assertRaisesRegex(c.CoverageError, 'Parent/prompt split leakage'):
            c.validate_sources({'people': [person, {**person, 'identity': 'CMU_reserve', 'split': 'downstream_reserve'}], 'sources': [source, other]}, {})

    def test_f12_requires_documented_speech_free_noise(self):
        data = fixture()
        scene = data[0]['scenes'][0]
        scene['family_id'] = 'F12'
        noise = {'noise_id': 'N1', 'parent_id': 'P1', 'split': 'development', 'prepared_sha256': 'noise',
                 'speech_content': 'unknown', 'strict_nonspeech_eligible': False}
        data[2]['prepared_segments'] = [noise]
        data[0]['selected_noise'] = {'N1': noise}
        scene['segments'].append({'kind': 'real_noise', 'source_id': 'N1', 'parent_id': 'P1', 'rir_id': 'R1',
                                  'source_start_sample': 32000, 'source_stop_sample': 120000, 'convolution_stop_sample': 120100,
                                  'source_split': 'development', 'speech_content': 'unknown', 'strict_nonspeech_eligible': False})
        with self.assertRaisesRegex(c.CoverageError, 'F12 contains'):
            inspect(data)

    def test_capture_requires_bound_integrity_and_frozen_recipe(self):
        scene = fixture()[0]['scenes'][0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            receipt = {'case_id': 'SCENE1', 'status': 'PASS', 'audio_integrity_status': 'PASS', 'telemetry_status': 'PASS',
                       'input_scene_sha256': 'canonical', 'final_recipe_capture': True, 'code_key': 'code'}
            c.save(path / 'result.json', receipt)
            accepted = {'scene_manifest': {'sha256': 'manifest'}, 'accepted_count': 1,
                        'accepted': [{'case_id': 'SCENE1', 'case_result': c.bind(path / 'result.json'), 'input_scene_sha256': 'canonical',
                                      'split': 'development', 'task_scoring_allowed': True}]}
            c.save(path / 'accept.json', accepted)
            result = c.capture_snapshot(path / 'accept.json', [scene], {'sha256': 'manifest'})
            self.assertEqual(result['accepted_count'], 1)
            receipt['telemetry_status'] = 'FAIL'
            c.save(path / 'result.json', receipt)
            with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
                c.capture_snapshot(path / 'accept.json', [scene], {'sha256': 'manifest'})
            accepted['accepted'][0]['case_result'] = c.bind(path / 'result.json')
            c.save(path / 'accept.json', accepted)
            with self.assertRaisesRegex(c.CoverageError, 'integrity/telemetry'):
                c.capture_snapshot(path / 'accept.json', [scene], {'sha256': 'manifest'})

    def test_missing_capture_is_pending_not_completed_or_error(self):
        with tempfile.TemporaryDirectory() as folder:
            result = c.capture_snapshot(Path(folder) / 'absent.json', fixture()[0]['scenes'], {'sha256': 'manifest'})
            self.assertEqual((result['status'], result['accepted_count'], result['pending_count']), ('NOT_YET_REPORTED', 0, 1))


if __name__ == '__main__':
    unittest.main()
