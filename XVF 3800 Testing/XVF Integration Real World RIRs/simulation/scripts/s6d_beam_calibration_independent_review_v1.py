"""Model-free calibration review probes; see README_S6D_BEAM_CALIBRATION_INDEPENDENT_REVIEW_V1.md."""
import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
FROZEN=R/'application/beam_C_calibration_source_v1/helpers'
sys.dont_write_bytecode=True
sys.path.insert(0,str(FROZEN))
import s6d_beam_calibration_v1 as C
import s6d_beam_native_run_v1 as N

class Checks(unittest.TestCase):
    output=None
    def fixture(self,name,*,spans=None,identity_unknown=True,root_status='FIXTURE_UNRELATED_NOT_ACCEPTED'):
        d=self.output/name;d.mkdir();run=d/'run';run.mkdir()
        def put(name,obj):
            p=d/name;N.save(p,obj);return N.bind(p)
        original=put('original_case.json',dict(fixture=True,status='PASS'))
        base=put('C_partition.json',dict(partition='C',Q_used=False,disjoint_from_E_Q_verified=True,accepted_case_results=[original],C_source_ids=['C1','C2']))
        partition=put('projected_partition.json',dict(original_partition=base))
        admission=put('admission.json',dict(original_case_result=original,calibration_partition=partition,capture_source_id='cap',route_id='route'))
        gallery=put('gallery.json',dict(profiles=[dict(profile_id='A'),dict(profile_id='B')]))
        profile=put('profile.json',dict(embedding=dict(window_sec=1.5,minimum_clean_fraction=.8)))
        settings=put('settings.json',dict(identity_streams=['focus0_asr','focus1_asr'],selected_profile_ids=['A']))
        root=put('root.json',dict(status=root_status,fixture_only=True))
        if spans is None:spans=[dict(source_id='C1',role='C',profile_id='A',start_min=0,start_max=0,stop_min=64000,stop_max=64000)]
        support=put('support.json',dict(schema='s6d-C-captured-support.v1',status='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT',case_result=original,partition=base,gallery=gallery,no_per_beam_alignment=True,rir_origin_added_again=False,root_acceptance=root,spans=spans))
        events=[];candidates=[]
        for i,corr in enumerate([.8,.95]):
            identity=dict(known_profile_id='A',naming_state='confirmed',current_query_name_cosine=.9,margin=.3)
            if i==1 and identity_unknown:identity=dict(known_profile_id=None,naming_state='unresolved')
            event=dict(event_id=f'e{i}',stream_id=f'focus{i}_asr',capture_source_id='cap',route_id='route',source_start_sec=2.,source_end_sec=3.5,available_at_sec=3.6,speech=True,overlap=False,identity=identity,evidence_kind='mature',clean_fraction=.9)
            events.append(dict(event_type='s6d_beam_identity',payload=event))
            candidates.append({k:deepcopy(v) for k,v in event.items() if k not in ('evidence_kind','clean_fraction')}|dict(same_auto_window=True,auto_waveform_correlation=corr,waveform=[corr]))
        events.append(dict(event_type='s6d_C_selector_probe',payload=dict(probe_index=1,selector='auto',selector_now_sec=3.7,collection_only=True,thresholds_applied=False,actual_disabled_result=dict(calibrated=False,status='NO_MATCH'),exclusive_auto_speech=True,auto_support=[2.,3.5],candidates=candidates)))
        ep=run/'consumer_events.jsonl';ep.write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
        proofs={}
        for i in range(2):
            p=run/f'focus{i}.pcm';p.write_bytes(bytes(128000));proofs[f'focus{i}_asr']=N.bind(p)
        job=dict(job_id='Cfixture',mode='calibration_collection',output=str(run),expected_frames=64000,expected_identity_frames=64000,audio_pcm_sha256='0'*64,stream_proofs=proofs,admission=admission,gallery=gallery,profile_binding=profile,beam_settings=settings,capture_profile='P_MAIN6')
        m=dict(schema='s6d-beam-execution.v1',runner_helper=N.bind(N.__file__),jobs=[job],support=dict(evidence=N.bind(SIM/'scripts/s6d_native_evidence_v1.py'),native_loop=N.bind(R/'application/native_pilot_v3/helpers/s6d_application_native.py')))
        mb=put('manifest.json',m)
        result=run/'RESULT.json';N.save(result,dict(job=job,manifest=mb,status='COMPLETE',failure=None))
        ap=run/'FULL_MULTISTREAM_AUDIT.json';N.save(ap,dict(status='PASS_FULL_MULTISTREAM_EVIDENCE',errors=[],manifest=mb,job_id=job['job_id'],physical_case_result=original,source_proofs=proofs,dispatch=dict(frames=64000),journals=proofs,consumer_events=N.bind(ep)))
        completed=dict(status='COMPLETE',manifest=mb,native_job_id=job['job_id'],full_multistream_evidence_validated=True,stop_requested=False,protocol_observer_closed=True,protocol_observer_errors=[],helper=m['runner_helper'],inner_native_loop=m['support']['native_loop'],native_run_one_same_process=True,subprocess_spawned_by_wrapper=False,failure=None,completion_audit=N.bind(ap),result=N.bind(result))
        cb=put('completion.json',completed)
        return mb,job['job_id'],cb,support,d/'FEATURES.json',candidates
    def extract(self,name,**kw):
        args=self.fixture(name,**kw);b=C.extract(*args[:5]);return N.verified(b),args
    def test_empty_support_retains_unlabelled_and_no_thresholds(self):
        value,_=self.extract('empty',spans=[])
        self.assertEqual(value['features'],[])
        self.assertIsNone(C.summarize_thresholds(value['features'])['thresholds'])
    def test_Q_source_rejected(self):
        args=self.fixture('Q',spans=[dict(source_id='C1',role='Q',profile_id='A',start_min=0,start_max=0,stop_min=64000,stop_max=64000)])
        with self.assertRaisesRegex(ValueError,'Non-C source'):C.extract(*args[:5])
    def test_foreign_gallery_support_rejected(self):
        args=self.fixture('foreign',spans=[dict(source_id='C1',role='C',profile_id='foreign',start_min=0,start_max=0,stop_min=64000,stop_max=64000)])
        with self.assertRaisesRegex(ValueError,'Foreign profile'):C.extract(*args[:5])
    def test_possible_overlap_even_outside_guaranteed_interiors_stays_unlabelled(self):
        spans=[dict(source_id='C1',start_min=0,start_max=0,stop_min=50000,stop_max=51000),dict(source_id='C2',start_min=20000,start_max=25000,stop_min=60000,stop_max=61000)]
        self.assertEqual(C.conservative_label(1000,24000,spans),(None,'mixed_or_uncovered_support'))
    def test_only_one_retained_positive_source_disables_fit(self):
        rows=[dict(metric=k,value=v,label=label,source_id=s) for k in C.METRICS for label,s,v in [('positive','P1',.9),('positive','P2',.2),('negative','N1',.3),('negative','N2',.4)]]
        self.assertIsNone(C.summarize_thresholds(rows)['thresholds'])
    def test_observe_unknown_auto_competitor_population_mismatch(self):
        value,args=self.extract('auto_pool')
        features=[r for r in value['features'] if r['metric']=='minimum_auto_correlation']
        self.assertEqual([r['value'] for r in features],[.8])
        self.assertEqual(value['counts']['no_confirmed_identity_retained'],1)
        path=R/'application/beam_native_interface_v3/source/edge_speech_pipeline/research_beams_s6d.py'
        tree=ast.parse(path.read_text(encoding='utf-8'));cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='BeamSelector')
        node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='choose')
        ns={'finite':C.finite,'waveform_similarity':lambda a,b:b[0]}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
        actor=SimpleNamespace(calibration=dict(minimum_auto_correlation=.7,minimum_auto_margin=.05),settings=SimpleNamespace(maximum_evidence_age_sec=.75,identity_streams=['focus0_asr','focus1_asr']),capture_identity=('cap','route'))
        chosen=ns['choose'](actor,args[5],3.7,auto_wave=[1.],auto_support=(2.,3.5),auto_speech=True)
        self.assertEqual(chosen['selected_stream'],'focus1_asr')
        self.assertIsNone(chosen['known_profile_id'])
    def test_observe_unrelated_root_receipt_not_semantically_checked(self):
        value,_=self.extract('root_unaccepted')
        self.assertEqual(value['status'],'EXTRACTED_C_ONLY_NOT_ACCEPTED_THRESHOLDS')
    def test_observe_per_gate_fit_does_not_prove_joint_positive_retention(self):
        rows=[]
        for k in C.METRICS:
            for s in ['P1','P2']:
                for event in ['a','b']:
                    value=.9 if (k=='minimum_selected_score')==(event=='a') else .1
                    rows.append(dict(metric=k,value=value,label='positive',source_id=s,event_id=event))
            for s in ['N1','N2']:rows.append(dict(metric=k,value=.4,label='negative',source_id=s,event_id='negative'))
        fit=C.summarize_thresholds(rows)
        self.assertIsNotNone(fit['thresholds'])
        retained=[]
        for s in ['P1','P2']:
            for e in ['a','b']:
                vals={row['metric']:row['value'] for row in rows if row['source_id']==s and row['event_id']==e}
                if all(vals[k]>=fit['thresholds'][k] for k in C.METRICS):retained.append((s,e))
        self.assertEqual(retained,[])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    N.need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G-only fixture root required')
    a.output.mkdir(parents=True);Checks.output=a.output
    N.need(N.bind(C.__file__)['sha256']=='9165da50cb28e1385c3d6edf19581261171edab68f34c0b5cd67cd37b4ba6e74','Wrong frozen calibration source')
    with (a.output/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    receipt=dict(status='PROBES_REPRODUCED_REVIEW_FINDINGS' if result.wasSuccessful() else 'PROBE_FAILURE',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),source=N.bind(C.__file__),checks=N.bind(__file__),actual_C_scoring=False,models=0,hardware=0,findings=['Auto runtime includes unresolved identity competitors omitted from auto calibration features','Root support acceptance JSON is bound but its status/scope is not checked','Per-gate retained positives need not survive joint gates; proposal is not accepted calibration'],fixture_method='Full extract with tiny synthetic closed-result metadata and128k zero byte journal per stream; exact selector choose AST with precomputed fake scalar correlation; no model/process/device call')
    N.save(a.output/'RECEIPT.json',receipt);print(json.dumps(N.bind(a.output/'RECEIPT.json')));raise SystemExit(not result.wasSuccessful())

