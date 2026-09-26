"""Mocked child wiring; no process, desktop, application, audio or model launch."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from common import bind,freeze,load
from test_paced_child_admission import fixture_input
import restart_application_child as subject

OUTPUT=None


def payload():
    value=fixture_input();value['job'].update(job_id='N2_S45_03_03_O0',frames=715127,tap='O0')
    value['contract'].update(variant='A0',diarization='D0',encoder='E0',backend_key='baseline',engine='PrototypeEngine')
    contract=value['contract'];composition='_'.join(contract[k] for k in ('variant','diarization','encoder'))
    value['cell_id']='restart_0_'+value['job']['job_id']+'_'+composition
    return value


@contextmanager
def wired(folder, *, failure=None, data=None, result_mutation=None):
    value=deepcopy(data or payload());events=[]; transport=folder/'transport';transport.mkdir(parents=True)
    app=folder/'application';freeze(transport/'INPUT.json',value);input_binding=bind(transport/'INPUT.json')
    control_seen=[]; original_path=list(sys.path)
    class Gate:
        def __init__(self,*args,**kwargs):
            events.append('gate');self.payload=value;self.transport=transport;self.output=app;self.permit={'input':input_binding};self.count=0
            if failure=='constructor':raise ValueError('Rejected constructor')
        def check(self,*args):
            events.append('check');self.count+=1
            if failure=='initial_gate' and self.count==1:raise ValueError('Rejected initial gate')
            if failure=='callback' and self.count==4:raise ValueError('Revoked callback lease')
        def prime(self):
            events.append('prime')
            if failure=='prime':raise ValueError('Rejected source priming')
            return dict(source=str(folder/'NO_RELEASE_IMPORTED'))
    class Cell:
        def __init__(self,output,job,contract):
            events.append('construct');self.output=output;self.job=deepcopy(job);self.contract=deepcopy(contract)
        def prepare(self,**kwargs):
            events.append('prepare')
            if failure=='prepare':raise ValueError('Preparation failed')
        def run_pair(self,*,admission_check,stop_after_samples):
            events.append('run_pair');control_seen.append(stop_after_samples)
            admission_check(self.job,self.contract)
            if failure=='run':raise ValueError('Pair failed')
        def close(self):
            events.append('close')
            if failure=='close':raise ValueError('Cleanup failed')
            for name in ('01','02'):freeze(app/'sessions'/name/'RESULT.json',dict(synthetic=True,index=name))
            freeze(app/'PAIR_OBSERVATION.json',dict(synthetic=True))
            result=dict(schema='n4-restart-application-cell-v1',status=subject.SUCCESS,source_start_requested=True,
                completed_sessions=2,errors=[],callback_errors=[],controller_closed=True,controller_worker_exited=True,
                failure_delivery_capture=None,actual_restart_qualified=False,source_to_widget_latency_qualified=False,
                complete_N4_acceptance=False,integrated_N4_cells=0,pair_observation=bind(app/'PAIR_OBSERVATION.json'),
                sessions=[bind(app/'sessions'/name/'RESULT.json') for name in ('01','02')])
            if result_mutation:result_mutation(result)
            freeze(app/'RESULT.json',result)
            if failure=='returned_mismatch':result=dict(result,extra=True)
            return result
    try:
        with patch.object(subject,'ChildAdmission',Gate),patch.object(subject,'actual_desktop',return_value='MOCK_PRIVATE_DESKTOP'),\
             patch.dict(sys.modules,{'restart_application_cell':SimpleNamespace(RestartApplicationCell=Cell)}):
            yield SimpleNamespace(call=lambda:subject.child_main(transport/'PERMIT.json','SYNTHETIC'),
                events=events,transport=transport,app=app,control_seen=control_seen,payload=value)
    finally:sys.path[:]=original_path


class RestartChildTests(unittest.TestCase):
    def setUp(self):self.folder=OUTPUT/self._testMethodName

    def test_exact_pair_branch_control_and_cleanup_order(self):
        with wired(self.folder) as f:
            f.call();r=load(f.transport/'CHILD_RESULT.json')
            self.assertEqual(f.events,['gate','check','prime','check','construct','prepare','check','run_pair','check','check','close'])
            self.assertEqual(f.control_seen,[357440]);self.assertEqual(r['status'],subject.CHILD_SUCCESS)
            self.assertEqual(r['restart_control'],subject.control(f.payload));self.assertEqual(r['cell_result'],bind(f.app/'RESULT.json'))
            self.assertFalse(r['actual_restart_qualified']);self.assertEqual(r['integrated_N4_cells'],0)

    def test_initial_gate_rejection_starts_no_cell(self):
        with wired(self.folder,failure='initial_gate') as f:
            with self.assertRaises(ValueError):f.call()
            self.assertEqual(f.events,['gate','check']);self.assertIsNone(load(f.transport/'CHILD_RESULT.json')['cell_result'])

    def test_source_priming_failure_starts_no_cell(self):
        with wired(self.folder,failure='prime') as f:
            with self.assertRaises(ValueError):f.call()
            self.assertNotIn('construct',f.events);self.assertIn('Rejected source priming',load(f.transport/'CHILD_RESULT.json')['error'])

    def test_prepare_failure_still_closes_constructed_cell(self):
        with wired(self.folder,failure='prepare') as f:
            with self.assertRaises(ValueError):f.call()
            self.assertEqual(f.events[-1],'close');self.assertNotIn('run_pair',f.events)

    def test_pair_failure_cannot_be_overridden_by_successful_close(self):
        with wired(self.folder,failure='run') as f:
            with self.assertRaises(ValueError):f.call()
            self.assertEqual(f.events[-1],'close');self.assertEqual(load(f.transport/'CHILD_RESULT.json')['status'],'FAILED_RESTART_APPLICATION_CHILD_PRESERVED')

    def test_pair_callback_uses_the_same_live_gate(self):
        with wired(self.folder,failure='callback') as f:
            with self.assertRaises(ValueError):f.call()
            self.assertEqual(f.events[-1],'close');self.assertIn('Revoked callback lease',load(f.transport/'CHILD_RESULT.json')['error'])

    def test_close_exception_preserves_failure(self):
        with wired(self.folder,failure='close') as f:
            with self.assertRaises(ValueError):f.call()
            result=load(f.transport/'CHILD_RESULT.json');self.assertIn('Cleanup failed',result['error']);self.assertIsNone(result['cell_result'])

    def test_constructor_rejection_writes_no_child_result(self):
        with wired(self.folder,failure='constructor') as f:
            with self.assertRaisesRegex(ValueError,'constructor'):f.call()
            self.assertFalse((f.transport/'CHILD_RESULT.json').exists());self.assertNotIn('construct',f.events)

    def test_false_acceptance_and_unclosed_results_fail(self):
        mutations={'status':'CELL_CLOSED_REQUIRES_REVIEW','completed_sessions':1,'controller_closed':False,
            'controller_worker_exited':False,'errors':['failure'],'actual_restart_qualified':True,'source_to_widget_latency_qualified':True,
            'complete_N4_acceptance':True,'integrated_N4_cells':1,'failure_delivery_capture':{'bad':True},'callback_errors':['bad']}
        for field,value in mutations.items():
            with self.subTest(field=field),wired(self.folder/field,result_mutation=lambda r,k=field,v=value:r.update({k:v})) as f:
                with self.assertRaises(ValueError):f.call()
                self.assertEqual(load(f.transport/'CHILD_RESULT.json')['status'],'FAILED_RESTART_APPLICATION_CHILD_PRESERVED')

    def test_foreign_pair_or_session_receipts_fail(self):
        for key in ('pair_observation','sessions'):
            with self.subTest(key=key),wired(self.folder/key,result_mutation=lambda r,k=key:r.update({k:[]})) as f:
                with self.assertRaises(ValueError):f.call()

    def test_returned_and_persisted_closure_must_match(self):
        with wired(self.folder,failure='returned_mismatch') as f:
            with self.assertRaises(ValueError):f.call()
            self.assertIn('persisted result',load(f.transport/'CHILD_RESULT.json')['error'])

    def test_controls_reject_other_jobs_modes_and_extra_payload(self):
        for mutation in ('cell_id','job_id','frames','mode','truth'):
            value=payload()
            if mutation=='cell_id':value['cell_id']='panel_0_other'
            if mutation=='job_id':value['job']['job_id']='N2_S45_08_07_O0'
            if mutation=='frames':value['job']['frames']=1
            if mutation=='mode':value['contract']['mode']='closed_roster'
            if mutation=='truth':value['evaluator_truth']={'actor':'forbidden'}
            with self.subTest(mutation=mutation),wired(self.folder/mutation,data=value) as f:
                with self.assertRaises(ValueError):f.call()
                self.assertNotIn('prime',f.events);self.assertNotIn('construct',f.events)

    def test_control_does_not_change_full_job_or_payload(self):
        value=payload();before=deepcopy(value);control=subject.control(value)
        self.assertEqual(value,before);self.assertEqual(control['sessions'],2);self.assertEqual(value['job']['frames'],715127)

    def test_full_prior_dependencies_preserved_within_unchanged_limit(self):
        entries=subject.code_bindings();q=load(subject.HERE/'RESTART_PLAN_CHECK_V1.json')
        actual={b['path']:b for b in entries};self.assertEqual(len(entries),122);self.assertEqual(len(q['code']),117)
        self.assertLessEqual(len(entries),128)
        for b in q['code']:self.assertEqual(actual[b['path']],b)
        for n in subject.OWN:self.assertEqual(actual[str((subject.HERE/n).resolve())],bind(subject.HERE/n))

    def test_changed_qualification_cannot_build_manifest(self):
        with patch.object(subject,'load',return_value={'status':'FAILED'}),self.assertRaises(ValueError):subject.code_bindings()
