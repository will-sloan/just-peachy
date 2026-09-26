"""Model-free coordinator/child wiring tests; no production admission."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

import psutil
from common import bind, fingerprint, freeze, load
from metric_process import identity
import continuity_application_runner as runner
from paced_child_admission import validate_lease, write_lease
from test_paced_child_admission import fixture_input, fixture_permit
from test_native_journal_review import NativeJournalTests
import test_application_delivery as delivery_tests

CONTEXT={}


class Clock:
    def __init__(self): self.value = 0.
    def now(self): return self.value
    def sleep(self, seconds): self.value += seconds


class RunnerTests(unittest.TestCase):
    def test_explicit_continuity_admission_and_schema(self):
        import continuity_application_plan as planner
        import paced_panel_plan_v3 as short
        self.assertIs(runner.admit_plan,planner.admit_plan)
        self.assertIs(runner.execution_payload,planner.execution_payload)
        self.assertIsNot(runner.admit_plan,short.admit_plan)
        self.assertEqual(runner.RUN_SCHEMA,'n4-continuity-application-run-v1')
        self.assertEqual(runner.QUALIFICATIONS['CONTINUITY_APPLICATION_PLAN_CHECK_V1.json'],
            'PASS_CONTINUITY_APPLICATION_PLANNER_DEVELOPMENT_ONLY')
        self.assertNotIn('PACED_PANEL_PLAN_CHECK_V3.json',runner.QUALIFICATIONS)

    def test_long_file_retains_finite_supervision_limit(self):
        # The full-file source exceeds the short fixtures. Its unchanged
        # wall-clock cap must remain finite even with slow inference/drain.
        clock=Clock();last=[]
        frames=19308429;maximum=min(3900,frames/16000*25+480)
        self.assertEqual(maximum,3900)
        with self.assertRaisesRegex(ValueError,'lifetime exceeded'):
            runner.supervise_child(SimpleNamespace(root_exited=lambda:False),SimpleNamespace(check=lambda:None),
                lambda value:last.append(value) if value%1000==0 else None,
                maximum_seconds=maximum,now=clock.now,sleep=clock.sleep)
        self.assertEqual(clock.now(),3900);self.assertEqual(last[-1],15000)

    def test_renew_only_after_checks(self):
        clock = Clock(); events = []
        child = SimpleNamespace(root_exited=lambda: clock.value >= .75)
        slot = SimpleNamespace(check=lambda: events.append('check'))
        row = runner.supervise_child(child, slot, lambda n: events.append(n), maximum_seconds=2, now=clock.now, sleep=clock.sleep)
        self.assertEqual(events, ['check',1,'check',2,'check',3]); self.assertEqual(row['renewals'],3)

    def test_guard_failure_cannot_renew(self):
        clock = Clock(); renewed = []
        def fail(): raise ValueError('Competitor detected')
        with self.assertRaisesRegex(ValueError,'Competitor'):
            runner.supervise_child(SimpleNamespace(root_exited=lambda:False),SimpleNamespace(check=fail),renewed.append,
                maximum_seconds=2,now=clock.now,sleep=clock.sleep)
        self.assertEqual(renewed,[])

    def test_lifetime_timeout(self):
        clock = Clock(); renewed = []
        with self.assertRaisesRegex(ValueError,'lifetime exceeded'):
            runner.supervise_child(SimpleNamespace(root_exited=lambda:False),SimpleNamespace(check=lambda:None),renewed.append,
                maximum_seconds=.5,now=clock.now,sleep=clock.sleep)
        self.assertEqual(renewed,[1,2])

    def test_only_exact_root_exit_race_is_normal(self):
        for message, okay in [('Required exact process has exited or PID was reused',True),('Disk floor unavailable',False)]:
            state={'exited':False};clock=Clock()
            def check(): state['exited']=True;raise ValueError(message)
            call=lambda: runner.supervise_child(SimpleNamespace(root_exited=lambda:state['exited']),SimpleNamespace(check=check),
                lambda n:self.fail('No renewal after exit'),maximum_seconds=2,now=clock.now,sleep=clock.sleep)
            if okay:self.assertEqual(call()['renewals'],0)
            else:
                with self.assertRaisesRegex(ValueError,'Disk floor'):call()

    def fake_collection(self, root, *, fail_resume=False, failed_cleanup=False, incomplete_journal=False,
                        failed_delivery=False,old_cell=False,foreign_result=False):
        events=[];payload=fixture_input();folder=root/'cell'
        class Slot:
            def __init__(self,*args):pass
            def acquire(self):events.append('acquire');return {'fixture_only':True}
            def register_application(self,*args,**kwargs):events.append('register')
            def check(self):events.append('check')
            def release(self):events.append('release');return {'status':'FIXTURE_SLOT_RELEASED'}
        class Child:
            def __init__(self,output,**kwargs):
                self.output=output;output.mkdir(parents=True);self.closed=False
                self.argv=['fixture'];self.desktop_name='codex-n1-n4-'+'d'*32
            def spawn_suspended(self):events.append('spawn');return dict(pid=123,create_time=1.)
            def resume(self,register):
                register(dict(pid=123,create_time=1.),executable_binding={},argv_sha256='fixture')
                events.append('resume')
                if fail_resume:raise RuntimeError('Fixture child failed')
                app=folder/'application';freeze(app/'RESULT.json',dict(status='CELL_WITH_SOURCE_DELIVERY_CLOSED_REQUIRES_REVIEW',source_start_requested=True,errors=[]))
                if old_cell:(app/'RESULT.json').write_text(json.dumps(dict(status='CELL_CLOSED_REQUIRES_REVIEW',source_start_requested=True,errors=[])),encoding='utf-8')
                permit=load(self.output/'PERMIT.json')
                target=app/'RESULT.json'
                if foreign_result:
                    target=folder/'FOREIGN.json';target.write_bytes((app/'RESULT.json').read_bytes())
                freeze(self.output/'CHILD_RESULT.json',dict(status='COLLECTED_DELIVERY_APPLICATION_CELL_REQUIRES_REVIEW',
                    owner=dict(pid=123,create_time=1.),input=permit['input'],cell_result=bind(target)))
            def root_exited(self):return True
            def close(self,**kwargs):
                events.append('close');self.closed=True
                self.receipt=dict(status='FAILED_LIFETIME_PRESERVED' if failed_cleanup else 'OWNED_PROCESS_LIFETIME_CLOSED',
                    root_exit_code=0,forced=False,observed_members_exited=not failed_cleanup,job_empty_verified=not failed_cleanup)
                freeze(self.output/'LIFETIME.json',self.receipt);return self.receipt
        stack=ExitStack()
        def envelope(*args):
            events.append('native_envelope')
            if incomplete_journal:raise ValueError('Complete native event history is required; a retained tail cannot qualify')
            freeze(folder/'NATIVE_JOURNAL_ENVELOPE.json',{'fixture_only':True})
            return bind(folder/'NATIVE_JOURNAL_ENVELOPE.json')
        def delivery(*args):
            events.append('delivery_envelope')
            if failed_delivery:raise ValueError('Synthetic delivery mismatch')
            freeze(folder/'SOURCE_DELIVERY_ENVELOPE.json',{'fixture_only':True})
            return bind(folder/'SOURCE_DELIVERY_ENVELOPE.json')
        for name,value in [('execution_payload',lambda *args:payload),('ExclusiveApplicationSlot',Slot),('PrivateApplicationProcess',Child),
            ('supervised_identity',lambda *args:(dict(pid=20,create_time=2.),dict(pid=10,create_time=1.),'fixture')),
            ('check_native_envelope',envelope),
            ('check_delivery_envelope',delivery),
            ('write_lease',lambda *args:events.append('lease'))]:
            stack.enter_context(patch.object(runner,name,value))
        return stack,events,folder

    def test_collection_releases_after_verified_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            stack,events,folder=self.fake_collection(Path(temp))
            with stack:binding=runner.collect_one({},0,folder,Path(temp)/'state',[])
            self.assertEqual(events,['acquire','spawn','register','lease','resume','close','native_envelope','delivery_envelope','release'])
            self.assertEqual(load(binding['path'])['integrated_N4_cells'],0)
            self.assertEqual(load(binding['path'])['native_journal_envelope'],bind(folder/'NATIVE_JOURNAL_ENVELOPE.json'))
            self.assertEqual(load(binding['path'])['source_delivery_envelope'],bind(folder/'SOURCE_DELIVERY_ENVELOPE.json'))
            self.assertEqual(load(binding['path'])['status'],'COLLECTED_SOURCE_DELIVERY_PACED_CELL_REQUIRES_REVIEW')
            self.assertIsNone(load(folder/'PARENT_CLOSURE.json')['cleanup_error'])

    def test_failed_child_still_closes_before_release(self):
        with tempfile.TemporaryDirectory() as temp:
            stack,events,folder=self.fake_collection(Path(temp),fail_resume=True)
            with stack,self.assertRaisesRegex(RuntimeError,'Fixture child failed'):
                runner.collect_one({},0,folder,Path(temp)/'state',[])
            self.assertEqual(events[-2:],['close','release']);self.assertFalse((folder/'COLLECTED.json').exists())
            self.assertIn('Fixture child failed',load(folder/'PARENT_CLOSURE.json')['error'])

    def test_unverified_descendants_do_not_release_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            stack,events,folder=self.fake_collection(Path(temp),failed_cleanup=True)
            with stack,self.assertRaises(ValueError):runner.collect_one({},0,folder,Path(temp)/'state',[])
            self.assertNotIn('release',events)
            self.assertIsNone(load(folder/'PARENT_CLOSURE.json')['slot_release'])

    def test_incomplete_journal_rejects_collection_but_releases_closed_child(self):
        with tempfile.TemporaryDirectory() as temp:
            stack,events,folder=self.fake_collection(Path(temp),incomplete_journal=True)
            with stack,self.assertRaisesRegex(ValueError,'retained tail'):
                runner.collect_one({},0,folder,Path(temp)/'state',[])
            self.assertEqual(events[-3:],['close','native_envelope','release'])
            self.assertFalse((folder/'COLLECTED.json').exists())
            self.assertIn('retained tail',load(folder/'PARENT_CLOSURE.json')['error'])

    def journal_fixture(self, root, *, tail=False, foreign=False, nested=False):
        folder=root/'cell';sessions=folder/'application/data/sessions';sessions.mkdir(parents=True)
        fixture=NativeJournalTests();fixture.folder=root if foreign else sessions
        if nested:fixture.folder=sessions/'nested';fixture.folder.mkdir()
        payload=fixture_input();payload['job']['audio_path']=str(root/'NEVER_OPENED.wav')
        payload['contract']['engine']='PrototypeEngine';fixture.job=payload['job']
        session,events=fixture.fixture();fixture.write(session,events[3:] if tail else events)
        freeze(folder/'application/ENGINE_CLOSURE.json',dict(job=payload['job'],engine_class='PrototypeEngine',session=str(session)))
        return folder,payload

    def test_native_complete_journal_is_bound_without_semantic_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,payload=self.journal_fixture(Path(temp))
            receipt=load(runner.check_native_envelope(folder,payload)['path'])
            self.assertEqual(receipt['cell_id'],payload['cell_id'])
            self.assertEqual(receipt['job_sha256'],fingerprint(payload['job']))
            self.assertEqual(receipt['review']['retained_events'],6)
            self.assertFalse(receipt['review']['native_payload_semantics_reviewed'])
            self.assertFalse(receipt['N4_accepted'])

    def test_native_incomplete_receipt_is_preserved_before_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,payload=self.journal_fixture(Path(temp),tail=True)
            with self.assertRaisesRegex(ValueError,'retained tail'):runner.check_native_envelope(folder,payload)
            receipt=load(folder/'NATIVE_JOURNAL_ENVELOPE.json')
            self.assertEqual(receipt['review']['missing_prefix_events'],3)
            self.assertFalse(receipt['review']['complete_envelope'])

    def test_foreign_and_nested_native_sessions_rejected(self):
        for kind in ('foreign','nested'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                folder,payload=self.journal_fixture(Path(temp),**{kind:True})
                with self.assertRaises(ValueError):runner.check_native_envelope(folder,payload)
                self.assertFalse((folder/'NATIVE_JOURNAL_ENVELOPE.json').exists())

    def test_native_job_or_engine_mismatch_rejected(self):
        for kind in ('job','engine'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                folder,payload=self.journal_fixture(Path(temp))
                if kind=='job':payload['job']['job_id']='different'
                else:payload['contract']['engine']='N2Engine'
                with self.assertRaisesRegex(ValueError,'job/engine'):runner.check_native_envelope(folder,payload)
                self.assertFalse((folder/'NATIVE_JOURNAL_ENVELOPE.json').exists())

    def worker_fixture(self, root, *, prepare_fails=False):
        events=[];transport=root/'transport';transport.mkdir();payload=fixture_input();output=root/'application'
        class Gate:
            def __init__(self,*args,**kwargs):
                self.output=output;self.transport=transport;self.payload=payload;self.permit={'input':{'fixture':True}}
                events.append('gate')
            def prime(self):events.append('prime');return {'source':str(root/'NO_SOURCE_PAYLOAD')}
            def check(self,*args):events.append('check')
        class Cell:
            def __init__(self,*args):events.append('construct')
            def prepare(self,**kwargs):
                events.append('prepare')
                if prepare_fails:raise RuntimeError('Fixture preparation failure')
            def run_source(self,admission_check):admission_check();events.append('run')
            def close(self):
                events.append('close');result={'status':'CELL_WITH_SOURCE_DELIVERY_CLOSED_REQUIRES_REVIEW'};freeze(output/'RESULT.json',result);return result
        stack=ExitStack()
        stack.enter_context(patch.object(runner,'ChildAdmission',Gate));stack.enter_context(patch.object(runner,'actual_desktop',lambda:'fixture'))
        stack.enter_context(patch.object(runner,'code_bindings',lambda:[]));stack.enter_context(patch.object(sys,'path',list(sys.path)))
        stack.enter_context(patch.dict(sys.modules,{'paced_application_cell_v2':SimpleNamespace(ApplicationCell=Cell)}))
        return stack,events,transport

    def test_fixed_worker_orders_prime_prepare_run_close(self):
        with tempfile.TemporaryDirectory() as temp:
            stack,events,transport=self.worker_fixture(Path(temp))
            with stack:runner.child_main(transport/'PERMIT.json','fixture')
            self.assertEqual(events,['gate','prime','check','construct','prepare','check','run','close'])
            self.assertEqual(load(transport/'CHILD_RESULT.json')['status'],'COLLECTED_DELIVERY_APPLICATION_CELL_REQUIRES_REVIEW')

    def test_fixed_worker_closes_after_prepare_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            stack,events,transport=self.worker_fixture(Path(temp),prepare_fails=True)
            with stack,self.assertRaisesRegex(ValueError,'Application child failed'):runner.child_main(transport/'PERMIT.json','fixture')
            self.assertNotIn('run',events);self.assertEqual(events[-1],'close')
            self.assertEqual(load(transport/'CHILD_RESULT.json')['status'],'FAILED_APPLICATION_CELL_PRESERVED')

    def test_real_atomic_lease_writer_with_synthetic_permit(self):
        self.assertEqual(psutil.Process().cpu_affinity(),[14])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'transport').mkdir();permit=fixture_permit()
            permit['coordinator']=identity(psutil.Process());permit['output']=str(root/'application')
            digest=fingerprint(permit);path=root/'transport/LEASE.json'
            first=write_lease(path,permit,digest,0);second=write_lease(path,permit,digest,1)
            self.assertEqual(load(path),second);self.assertEqual(first['sequence'],0)
            self.assertEqual(validate_lease(second,permit,digest,now_monotonic=second['issued_monotonic'],previous_sequence=0),1)
            with self.assertRaisesRegex(ValueError,'advance'):write_lease(path,permit,digest,1)
            self.assertFalse((root/'transport/LEASE.pending').exists())

    def test_missing_production_plan_is_not_admitted(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'PLAN.json';freeze(path,{'fixture':True})
            with patch('paced_panel_plan_v3.reconstruct') as review,self.assertRaises(FileNotFoundError):runner.admit_plan(path)
            review.assert_not_called()

    def test_delivery_failure_preserves_attempt_without_collection_credit(self):
        with tempfile.TemporaryDirectory() as temp:
            stack,events,folder=self.fake_collection(Path(temp),failed_delivery=True)
            with stack,self.assertRaisesRegex(ValueError,'delivery mismatch'):
                runner.collect_one({},0,folder,Path(temp)/'state',[])
            self.assertEqual(events[-3:],['native_envelope','delivery_envelope','release'])
            self.assertFalse((folder/'COLLECTED.json').exists())
            self.assertIn('delivery mismatch',load(folder/'PARENT_CLOSURE.json')['error'])

    def test_old_cell_status_and_foreign_child_result_are_not_collected(self):
        for case in ('old_cell','foreign_result'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                stack,events,folder=self.fake_collection(Path(temp),**{case:True})
                with stack,self.assertRaises(ValueError):runner.collect_one({},0,folder,Path(temp)/'state',[])
                self.assertEqual(events[-1],'release');self.assertNotIn('delivery_envelope',events)
                self.assertFalse((folder/'COLLECTED.json').exists())

    def delivery_fixture(self,folder):
        f=delivery_tests.Fixture()
        try:
            f.ready();f.f.source.start();launch=f.finish(folder/'raw-synthetic')
        finally:f.capture.restore_start()
        value,raw,capture,closure,clock,job,contract=delivery_tests.join_fixture(f,launch,load(launch['observation']['path']))
        app=folder/'application';freeze(app/'delivery/OBSERVATION.json',value);(app/'delivery/TRACE.bin').write_bytes(raw)
        capture['observation']=bind(app/'delivery/OBSERVATION.json');capture['trace']=bind(app/'delivery/TRACE.bin')
        freeze(app/'delivery/CAPTURE.json',capture);freeze(app/'ENGINE_CLOSURE.json',closure);freeze(app/'SOURCE_CLOCK.json',clock)
        # Synthetic receipt and copied fixture flags: exercises the reader only,
        # never production plan admission or an actual application/owner claim.
        files=f.capture.source_files
        receipt=dict(prototype=str(CONTEXT['prototype']),files={
            'app/'+Path(b['path']).name:dict(sha256=b['sha256'],bytes=b['bytes']) for b in files})
        freeze(folder/'SYNTHETIC_SOURCE_RECEIPT.json',receipt)
        payload=dict(cell_id='SYNTHETIC_DELIVERY_CELL',job=job,contract=contract,source_receipt=bind(folder/'SYNTHETIC_SOURCE_RECEIPT.json'))
        joined=runner.review_delivery_files(app,job,contract,files)
        cell=dict(status=runner.APPLICATION_POLICY['success_status'],source_start_requested=True,controller_closed=True,
            controller_worker_exited=True,errors=[],callback_errors=[],application_variant=runner.APPLICATION_POLICY['variant'],
            delivery_policy=runner.APPLICATION_POLICY['delivery'],delivery_capture=bind(app/'delivery/CAPTURE.json'),
            delivery_join=joined,integrated_N4_cells=0,complete_N4_acceptance=False,source_to_widget_latency_qualified=False)
        freeze(app/'RESULT.json',cell);return payload,cell

    def test_parent_reparses_delivery_without_accepting_timing_or_accuracy(self):
        folder=CONTEXT['output']/'synthetic-parent-delivery';payload,cell=self.delivery_fixture(folder)
        binding=runner.check_delivery_envelope(folder,payload);receipt=load(binding['path'])
        self.assertTrue(receipt['independent_parent_read']);self.assertEqual(receipt['review']['source_samples'],650)
        self.assertEqual(receipt['review']['summary']['records'],3);self.assertEqual(receipt['review'],cell['delivery_join'])
        self.assertFalse(receipt['N4_accepted']);self.assertFalse(receipt['review']['deadline_or_continuity_accepted'])
        freeze(CONTEXT['output']/'SYNTHETIC_PARENT_ENVELOPE.json',dict(scope='Synthetic receipt and RAM-source copied flags; no production plan or actual application',envelope=binding))

    def test_parent_rejects_policy_capture_summary_job_or_source_drift(self):
        for index,change in enumerate(('policy','capture','summary','job','source','trace')):
            folder=CONTEXT['output']/('synthetic-drift-'+str(index));payload,cell=self.delivery_fixture(folder)
            if change=='policy':cell['delivery_policy']={}
            if change=='capture':cell['delivery_capture']=payload['source_receipt']
            if change=='summary':cell['delivery_join']['source_samples']=1
            if change=='job':payload['job']=deepcopy(payload['job']);payload['job']['frames']+=1
            if change=='source':
                receipt=load(payload['source_receipt']['path']);receipt['files']['app/pipeline.py']['sha256']='0'*64
                path=folder/'FOREIGN_SOURCE_RECEIPT.json';freeze(path,receipt);payload['source_receipt']=bind(path)
            if change=='trace':
                path=folder/'application/delivery/TRACE.bin';path.write_bytes(path.read_bytes()[:-1])
            (folder/'application/RESULT.json').write_text(json.dumps(cell),encoding='utf-8')
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):
                runner.check_delivery_envelope(folder,payload)
            self.assertFalse((folder/'SOURCE_DELIVERY_ENVELOPE.json').exists())
