"""Offline source-contract tests. Run with README_S45_SOURCES.md commands."""
import unittest
import numpy as np
import s45_sources as s

class SourceTests(unittest.TestCase):
    def test_only_user_authorized_corpora(self):
        self.assertEqual(s.ALLOWED_DATASETS,{'CMU ARCTIC','HiFiTTS','Common Voice'})
    def test_metadata_prompt_split_and_role_stable(self):
        self.assertEqual(s.planned_text_split('Hello!'),s.planned_text_split('hello'))
        self.assertEqual(s.planned_text_usage('Hello!'),s.planned_text_usage('hello'))
    def test_short_complete_text_excludes_abbreviation_and_fragment(self):
        self.assertTrue(s.whole_short_candidate('“Yes!”'))
        self.assertFalse(s.whole_short_candidate('Dr.'))
        self.assertFalse(s.whole_short_candidate('and then'))
    def test_short_actual_audio_activity_is_permitted(self):
        x=.08*np.sin(2*np.pi*300*np.arange(8000)/16000)
        q=s.active_stats(x)
        self.assertEqual(s.qc_reasons(q,.5)[0],[])
    def test_faint_source_requires_rejection_before_gain(self):
        q={'active_rms':1e-5,'peak':.001}
        with self.assertRaises(ValueError):s.gain_for(q)
    def test_peak_cap_is_shared_scalar_without_clipping(self):
        q={'active_rms':.04,'peak':.9}
        self.assertAlmostEqual(s.gain_for(q),.5/.9)
        self.assertLessEqual(q['peak']*s.gain_for(q),.5)
    def test_selection_never_borrows_enrollment_for_probe(self):
        row={'source_id':'x','usage':'enrollment_reference','metadata_duration_sec':1.2,'transcript':'Yes.','prompt_group':'x'}
        self.assertEqual(s.choose_rows([row],'probe'),[])
    def test_repeated_within_person_prompt_not_extra_clip(self):
        rows=[{'source_id':str(i),'usage':'probe','metadata_duration_sec':3.0,'transcript':'Hello there.','prompt_group':'same'} for i in range(4)]
        self.assertEqual(len(s.choose_rows(rows,'probe')),1)
    def test_clipping_is_hard_rejection_but_pause_contrast_review(self):
        q=s.active_stats(.1*np.sin(2*np.pi*200*np.arange(16000)/16000))
        self.assertFalse(s.qc_reasons(q,1.0)[0])
        q.update(max_run_abs_ge_0_999=8,samples_abs_ge_0_999=8)
        self.assertIn('source_rail_or_overrange',s.qc_reasons(q,1.0)[0])

if __name__=='__main__':unittest.main()
