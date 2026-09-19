"""Tiny C calibration tests; see README_S6D_BEAM_CALIBRATION_V1.md."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import unittest
import s6d_beam_calibration_v1 as C
import s6d_beam_native_run_v1 as N

class Checks(unittest.TestCase):
    def span(self,**kw):return dict(source_id='C1',start_min=0,start_max=320,stop_min=40000,stop_max=40320,**kw)
    def rows(self):
        return [dict(metric=k,value=v,label=label,source_id=source) for k in C.METRICS for label,v,sources in [('positive',.9,['P1','P2']),('negative',.4,['N1','N2'])] for source in sources]
    def test_whole_interior_positive(self):self.assertEqual(C.conservative_label(320,40000,[self.span()])[0]['source_id'],'C1')
    def test_boundary_uncertainty_retained_unlabelled(self):self.assertEqual(C.conservative_label(100,25000,[self.span()])[1],'boundary_uncertainty')
    def test_overlap_never_invents_target(self):
        second=dict(source_id='C2',start_min=20000,start_max=20320,stop_min=50000,stop_max=50320)
        self.assertIsNone(C.conservative_label(16000,40000,[self.span(),second])[0])
    def test_no_coverage_retained(self):self.assertIsNone(C.conservative_label(50000,74000,[self.span()])[0])
    def test_finite_complete_threshold_positive(self):
        fit=C.summarize_thresholds(self.rows());self.assertEqual(fit['issues'],[]);self.assertEqual(set(fit['thresholds']),set(C.METRICS));self.assertAlmostEqual(fit['thresholds']['minimum_auto_margin'],.400001)
    def test_missing_negative_keeps_all_selectors_disabled(self):
        fit=C.summarize_thresholds([r for r in self.rows() if r['label']=='positive']);self.assertIsNone(fit['thresholds'])
    def test_correlated_windows_not_distinct_sources(self):
        rows=self.rows()
        for r in rows:r['source_id']='one'
        self.assertIsNone(C.summarize_thresholds(rows*100)['thresholds'])
    def test_no_separation_not_nominal_fallback(self):
        rows=self.rows()
        for r in rows:
            if r['label']=='negative':r['value']=.95
        self.assertIsNone(C.summarize_thresholds(rows)['thresholds'])
    def test_nonfinite_feature_rejects(self):
        rows=self.rows();rows[0]['value']=float('nan')
        with self.assertRaises(ValueError):C.summarize_thresholds(rows)
    def test_large_positive_cosine_margin_is_valid_evidence(self):
        rows=self.rows()
        for r in rows:
            if 'margin' in r['metric'] and r['label']=='positive':r['value']=1.1
        self.assertEqual(C.summarize_thresholds(rows)['issues'],[])
    def join_fixture(self):
        event=dict(event_id='focus0_asr:embedding:00000001',stream_id='focus0_asr',capture_source_id='capture_exact',route_id='route_exact',source_start_sec=2.,source_end_sec=3.5,available_at_sec=3.6,speech=True,overlap=False,identity={'known_profile_id':'opaque_A','naming_state':'confirmed'},evidence_kind='mature',clean_fraction=.9)
        candidate={k:v for k,v in event.items() if k not in ('evidence_kind','clean_fraction')}
        return event,candidate,{('focus0_asr',event['event_id']):event},{'capture_source_id':'capture_exact','route_id':'route_exact'},{'identity_streams':['focus0_asr','focus1_asr']}
    def test_actual_mature_event_probe_join(self):
        event,candidate,seen,admission,settings=self.join_fixture();self.assertEqual(C.require_candidate_join(candidate,seen,admission,settings,1.5,.8),event)
    def test_missing_actual_native_identity_event_rejected(self):
        event,candidate,seen,admission,settings=self.join_fixture()
        with self.assertRaises(ValueError):C.require_candidate_join(candidate,{},admission,settings,1.5,.8)
    def test_changed_probe_identity_rejected(self):
        event,candidate,seen,admission,settings=self.join_fixture();candidate['identity']={'known_profile_id':'opaque_B','naming_state':'confirmed'}
        with self.assertRaises(ValueError):C.require_candidate_join(candidate,seen,admission,settings,1.5,.8)
    def test_foreign_capture_even_with_consistent_probe_rejected(self):
        event,candidate,seen,admission,settings=self.join_fixture();event['capture_source_id']=candidate['capture_source_id']='other_capture'
        with self.assertRaises(ValueError):C.require_candidate_join(candidate,seen,admission,settings,1.5,.8)
    def test_short_or_unclean_native_evidence_cannot_calibrate(self):
        for key,value in (('evidence_kind','short'),('clean_fraction',.79)):
            event,candidate,seen,admission,settings=self.join_fixture();event[key]=value
            with self.assertRaises(ValueError):C.require_candidate_join(candidate,seen,admission,settings,1.5,.8)
    def test_predeclared_pcm_required_before_any_result_read(self):
        m=dict(schema='s6d-beam-execution.v1',runner_helper=N.bind(N.__file__))
        with self.assertRaisesRegex(ValueError,'Full predeclared PCM/frame'):
            C.require_closed_collection({},m,dict(expected_frames=24000,expected_identity_frames=24000),{},{},{})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();N.need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G output required');a.output.mkdir(parents=True)
    with (a.output/'TESTS.log').open('x',encoding='utf-8') as log:r=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    N.save(a.output/'RECEIPT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),source=N.bind(C.__file__),checks=N.bind(__file__),actual_C_scoring=False,models=0,hardware=0));print(json.dumps(N.bind(a.output/'RECEIPT.json')));raise SystemExit(not r.wasSuccessful())
