"""S5 aggregation semantic fixtures. README_S5.md."""
import unittest
from s5_results import level_pool, return_tags, strict_summary, strata, failed_empty_sensitivity

class ResultTests(unittest.TestCase):
    def test_levels_pool_energy_not_db_or_unweighted_rms(self):
        def level(n, rms):
            return {'samples': n, 'rms_fs': rms, 'peak_fs': rms, 'rail_samples': 0,
                    'rail_runs': 0, 'longest_rail_run_samples': 0}
        r = level_pool([level(1, 1), level(99, 0)])
        self.assertEqual(r['pooled_rms_fs'], .1)
        self.assertEqual(r['zero_rms_scenes'], 1)

    def test_folded_spatial_family_is_not_speech_overlap(self):
        row = {'family_id': 'F05', 'scheduled_overlap': False, 'scheduled_speaker_order': ['a', 'b', 'a']}
        group = {'speaker_key': 'a', 'strata': ['returning_person', 'close_or_overlap_family']}
        tags = return_tags(row, group)
        self.assertIn('folded_spatial_contrast_family', tags)
        self.assertIn('return_after_other_speaker', tags)
        self.assertNotIn('scheduled_overlapping_speech', tags)
        self.assertNotIn('close_or_overlap_family', tags)

    def test_adjacent_repeat_separate_from_return_after_other(self):
        row = {'family_id': 'F01', 'scheduled_overlap': False, 'scheduled_speaker_order': ['a', 'a']}
        tags = return_tags(row, {'speaker_key': 'a', 'strata': ['returning_person']})
        self.assertIn('repeat_without_intervening_speaker', tags)
        self.assertNotIn('return_after_other_speaker', tags)

    def test_strict_empty_has_undefined_wer_and_correct_minute_rate(self):
        rows = [{'O0': {'text': {'empty_reference_insertions': 2}, 'decoded_duration_s': 30}},
                {'O0': {'text': {'empty_reference_insertions': 0}, 'decoded_duration_s': 90}}]
        r = strict_summary(rows, 'O0')
        self.assertIsNone(r['wer'])
        self.assertEqual(r['words_per_decoded_minute'], 1)
        self.assertEqual(r['affected_control_fraction'], .5)

    def test_native_sir_field_is_preserved(self):
        scene = {'segments': [], 'receiver_configuration': {'room_table': 'room', 'orientation': 'FLAT', 'obstructed': False},
                 'family_id': 'F09', 'family': 'Background speaker', 'relative_source_level_db': 0,
                 'common_family_headroom_scalar': 1, 'all_speaker_reference_complete': True,
                 'speech_interference_policy': {'requested_sir_db': -6}}
        self.assertEqual(strata(scene)['requested_speech_sir_db'], '-6')

    def test_failed_output_sensitivity_is_full_deletion_not_zero(self):
        native = {'text': {'word_counts': {'errors': 0, 'substitutions': 0, 'deletions': 0, 'insertions': 0,
                                          'reference_words': 2, 'hypothesis_words': 2}}}
        scene = {'duration_s': 1, 'segments': [{'kind': 'utterance', 'source_start_sample': 0, 'transcript': 'one two'}]}
        r = failed_empty_sensitivity([{'case_id': 'a', 'O0': native, 'O1': None}], {'a': scene},
                                     {('a', 'O0'): 'COMPLETE', ('a', 'O1'): 'FAILED'})
        self.assertEqual(r['paired']['O1']['deletions'], 2)
        self.assertEqual(r['paired']['O1']['wer'], 1)
        self.assertEqual(r['status'], 'HYPOTHETICAL_FAILED_OUTPUT_AS_EMPTY')

if __name__ == '__main__':
    unittest.main()
