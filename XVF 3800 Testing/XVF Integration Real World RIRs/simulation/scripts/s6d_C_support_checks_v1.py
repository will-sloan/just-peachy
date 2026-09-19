"""Tiny metadata-only projection checks; see README_S6D_C_SUPPORT_PREPARE_V1.md."""
import argparse
from copy import deepcopy
from pathlib import Path
import unittest
import s6d_C_support_prepare_v1 as S

class Checks(unittest.TestCase):
    def setUp(self):
        self.case={'proposed_case_lag_envelope_samples':[861,1501]}
        self.fragment=dict(input_span_samples=[16000,75688],proposed_capture_interior_samples=[33501,92549],possible_source_identities=['person_A'],source_ids=['C_A'],unique_source_identity=True)
    def run_fragment(self):return S.project_fragment(self.case,self.fragment,{'C_A':'person_A','C_B':'person_B'},{'person_A':'opaque_original_A'})
    def test_exact_pre_eroded_not_double_shifted(self):
        x,reason=self.run_fragment();self.assertEqual((x['start_min'],x['stop_max']),(33501,92549));self.assertEqual(x['profile_id'],'opaque_original_A');self.assertFalse(x['unique_auto_to_focus_target_proven'])
    def test_unknown_gallery_identity_is_retained_null(self):
        x,_=S.project_fragment(self.case,self.fragment,{'C_A':'person_A'},{});self.assertIsNone(x['profile_id'])
    def test_second_guard_or_lag_rejected(self):
        self.fragment['proposed_capture_interior_samples'][0]+=16000
        with self.assertRaises(ValueError):self.run_fragment()
    def test_identity_mismatch_rejected(self):
        self.fragment['possible_source_identities']=['person_B']
        with self.assertRaises(ValueError):self.run_fragment()
    def test_multi_identity_excluded(self):
        self.fragment.update(source_ids=['C_A','C_B'],possible_source_identities=['person_A','person_B'],unique_source_identity=False)
        self.assertEqual(self.run_fragment(),(None,'multiple_source_or_identity_support'))
    def test_short_fragment_excluded_without_grid_claim(self):
        self.fragment.update(input_span_samples=[16000,17000],proposed_capture_interior_samples=[33501,33861]);self.assertEqual(self.run_fragment(),(None,'less_than_one_1p5s_mature_window'))
    def test_unknown_or_boolean_source_clock_rejected(self):
        self.fragment['input_span_samples'][0]=True
        with self.assertRaises(ValueError):self.run_fragment()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();S.need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G output required');a.output.mkdir(parents=True)
    with (a.output/'TESTS.log').open('w',encoding='utf-8') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    S.save(a.output/'RECEIPT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),source=S.bind(S.__file__),checks=S.bind(__file__),actual_models=0));raise SystemExit(0 if r.wasSuccessful() else 1)
