"""Mocked coordinator/lifetime/reader wiring; no actual process or model launch."""
from contextlib import ExitStack, contextmanager, nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load
from test_restart_child import payload as fixture_payload
import test_paced_application_runner_v3 as prior
import restart_application_runner as subject

OUTPUT = None


@contextmanager
def collection(folder, failure=None, mutate_child=None, mutate_pair=None):
    events=[]; state=subject.LOCAL/'supervision'; parent,child_code,exe,script=subject.qualified_manifests()
    payload=fixture_payload(); owner=dict(pid=987654321,create_time=1.); seen={}
    def fail(name):
        if failure==name:raise ValueError('fixture '+name)
    class Slot:
        def __init__(self,*args):pass
        def acquire(self):events.append('acquire');fail('acquire');return dict(synthetic=True)
        def register_application(self,*args,**kwargs):events.append('register');fail('register')
        def check(self):events.append('guard');fail('guard')
        def release(self):events.append('release');fail('release');return dict(status='FIXTURE_RELEASED')
    class Child:
        def __init__(self,output,**kwargs):
            fail('constructor');seen['arguments']=kwargs;self.output=output;output.mkdir(parents=True)
            self.closed=False;self.argv=['fixed-synthetic-child'];self.desktop_name='codex-n1-n4-'+'d'*32
        def spawn_suspended(self):events.append('spawn');fail('spawn');return owner
        def resume(self,register):
            register(owner,executable_binding=exe,argv_sha256=fingerprint(self.argv));events.append('resume');fail('resume')
            freeze(folder/'application/RESULT.json',dict(synthetic=True))
            permit=load(self.output/'PERMIT.json');seen['permit']=permit
            r=dict(status=subject.CHILD_SUCCESS,owner=owner,input=permit['input'],error=None,
                restart_control=subject.control(payload),cell_result=bind(folder/'application/RESULT.json'),
                actual_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False)
            if mutate_child:mutate_child(r)
            freeze(self.output/'CHILD_RESULT.json',r)
        def close(self,**kwargs):
            events.append('close');seen.setdefault('close_grace',[]).append(kwargs['grace_seconds']);self.closed=True
            self.receipt=dict(status='OWNED_PROCESS_LIFETIME_CLOSED',job_empty_verified=failure!='descendants',
                observed_members_exited=failure!='descendants',synthetic=True)
            freeze(self.output/'LIFETIME.json',self.receipt);return self.receipt
    def lease(path,permit,digest,sequence):events.append('lease'+str(sequence));fail('lease');seen['lease_code']=permit['code']
    def monitor(child,slot,renew,**kwargs):
        events.append('monitor');seen['maximum_seconds']=kwargs['maximum_seconds'];slot.check();renew(1)
        fail('monitor');return dict(renewals=1,synthetic=True)
    def lifetime(value,**kwargs):events.append('lifetime');seen['lifetime_args']=kwargs;fail('lifetime');return dict(synthetic=True)
    def checkpoint(*args):events.append('post_exit');fail('post_exit')
    def review(app,**kwargs):
        events.append('pair');fail('pair');kwargs['checkpoint']()
        r=dict(status='PASS_COMPLETE_RESTART_PAIR_EVIDENCE_JOINS_ONLY',cell_result=bind(app/'RESULT.json'),
            cell_id=payload['cell_id'],application_owner=owner,control=subject.control(payload),
            actual_restart_qualified=False,N4_accepted=False,integrated_N4_cells=0,synthetic=True)
        if mutate_pair:mutate_pair(r)
        return r
    with ExitStack() as stack:
        for name,value in [('qualified_manifests',lambda:(parent,child_code,exe,script)),('execution_payload',lambda *a:payload),
            ('ExclusiveApplicationSlot',Slot),('PrivateApplicationProcess',Child),('write_lease',lease),
            ('supervise_child',monitor),('validate_lifetime',lifetime),('check_after_exit',checkpoint),('review_pair',review),
            ('supervised_identity',lambda s:(dict(pid=20,create_time=2.),dict(pid=10,create_time=1.),'synthetic'))]:
            stack.enter_context(patch.object(subject,name,value))
        yield SimpleNamespace(folder=folder,parent=parent,child_code=child_code,script=script,exe=exe,
            events=events,seen=seen,payload=payload,owner=owner,call=lambda:subject.collect_one({},0,folder,state,parent))


class RestartRunnerTests(unittest.TestCase):
    def setUp(self):self.folder=OUTPUT/self._testMethodName;self.folder.mkdir()
    # The shared supervisor loop is imported unchanged from the qualified V3 runner.
    test_renew_only_after_checks=prior.RunnerTests.test_renew_only_after_checks
    test_guard_failure_cannot_renew=prior.RunnerTests.test_guard_failure_cannot_renew
    test_lifetime_timeout=prior.RunnerTests.test_lifetime_timeout
    test_only_exact_root_exit_race_is_normal=prior.RunnerTests.test_only_exact_root_exit_race_is_normal

    def test_fixed_split_child_and_normal_cleanup_order(self):
        with collection(self.folder/'cell') as f:
            b=f.call();r=load(b['path']);args=f.seen['arguments'];permit=f.seen['permit']
            self.assertEqual(args['script_binding'],f.script);self.assertEqual(args['executable_binding'],f.exe)
            self.assertEqual(args['cpu'],4);self.assertEqual(args['arguments'][0],'--permit');self.assertNotIn('child',args['arguments'])
            self.assertEqual(permit['code'],f.child_code);self.assertEqual(len(permit['code']),122);self.assertGreater(len(f.parent),128)
            self.assertEqual(f.events,['acquire','spawn','register','lease0','resume','monitor','guard','lease1',
                'close','lifetime','post_exit','pair','post_exit','post_exit','release'])
            self.assertEqual(f.seen['close_grace'],[0]);self.assertEqual(f.seen['maximum_seconds'],1200)
            self.assertEqual(f.seen['lifetime_args']['script'],f.script);self.assertEqual(f.seen['lifetime_args']['cpu'],4)
            self.assertEqual(r['status'],subject.COLLECTED);self.assertEqual(r['child_code_sha256'],fingerprint(f.child_code))
            self.assertFalse(r['actual_restart_qualified']);self.assertFalse(r['independent_complete_transport_reviewed'])
            self.assertIsNone(load(f.folder/'PARENT_CLOSURE.json')['cleanup_error'])
    def test_failed_acquire_never_spawns(self):
        with collection(self.folder/'cell',failure='acquire') as f:
            with self.assertRaisesRegex(ValueError,'acquire'):f.call()
            self.assertEqual(f.events,['acquire'])
    def test_constructor_failure_releases_slot(self):
        with collection(self.folder/'cell',failure='constructor') as f:
            with self.assertRaisesRegex(ValueError,'constructor'):f.call()
            self.assertEqual(f.events,['acquire','release']);self.assertFalse((f.folder/'COLLECTED.json').exists())
    def test_spawn_register_and_resume_failure_close_before_release(self):
        for failure in ('spawn','register','resume'):
            with collection(self.folder/failure,failure=failure) as f:
                with self.assertRaisesRegex(ValueError,failure):f.call()
                self.assertEqual(f.events[-2:],['close','release']);self.assertEqual(f.seen['close_grace'],[150])
                self.assertFalse((f.folder/'COLLECTED.json').exists());self.assertNotIn('pair',f.events)
    def test_first_lease_failure_cannot_resume(self):
        with collection(self.folder/'cell',failure='lease') as f:
            with self.assertRaisesRegex(ValueError,'lease'):f.call()
            self.assertNotIn('resume',f.events);self.assertEqual(f.events[-2:],['close','release'])
    def test_guard_failure_prevents_renewal_and_closes(self):
        with collection(self.folder/'cell',failure='guard') as f:
            with self.assertRaisesRegex(ValueError,'guard'):f.call()
            self.assertNotIn('lease1',f.events);self.assertEqual(f.events[-2:],['close','release'])
    def test_lifetime_failure_never_reviews_pair(self):
        with collection(self.folder/'cell',failure='lifetime') as f:
            with self.assertRaisesRegex(ValueError,'lifetime'):f.call()
            self.assertNotIn('pair',f.events);self.assertEqual(f.events[-1],'release');self.assertFalse((f.folder/'COLLECTED.json').exists())
    def test_unverified_descendants_retain_slot(self):
        with collection(self.folder/'cell',failure='descendants') as f:
            with self.assertRaisesRegex(ValueError,'Retain slot'):f.call()
            self.assertNotIn('release',f.events);self.assertIsNone(load(f.folder/'PARENT_CLOSURE.json')['slot_release'])
    def test_post_exit_resource_failure_preserved(self):
        with collection(self.folder/'cell',failure='post_exit') as f:
            with self.assertRaisesRegex(ValueError,'post_exit'):f.call()
            self.assertNotIn('pair',f.events);self.assertEqual(f.events[-1],'release')
    def test_wrong_child_owner_input_control_error_and_status_rejected(self):
        changes=[dict(owner={}),dict(input={}),dict(restart_control={}),dict(error='run failed'),dict(status='READY_FOR_REVIEW')]
        for i,change in enumerate(changes):
            with collection(self.folder/str(i),mutate_child=lambda r:r.update(change)) as f:
                with self.assertRaises(ValueError):f.call()
                self.assertNotIn('pair',f.events);self.assertFalse((f.folder/'COLLECTED.json').exists())
    def test_false_child_acceptance_and_foreign_cell_result_rejected(self):
        for i,change in enumerate((dict(actual_restart_qualified=True),dict(N4_accepted=True),dict(integrated_N4_cells=True),dict(cell_result={}))):
            with collection(self.folder/str(i),mutate_child=lambda r:r.update(change)) as f:
                with self.assertRaises(ValueError):f.call()
                self.assertNotIn('pair',f.events)
    def test_pair_reader_failure_preserves_failed_attempt(self):
        with collection(self.folder/'cell',failure='pair') as f:
            with self.assertRaisesRegex(ValueError,'pair'):f.call()
            self.assertIn('fixture pair',load(f.folder/'PARENT_CLOSURE.json')['error']);self.assertEqual(f.events[-1],'release')
    def test_pair_reader_foreign_result_or_acceptance_rejected(self):
        for i,change in enumerate((dict(cell_id='foreign'),dict(application_owner={}),dict(cell_result={}),
                                  dict(control={}),dict(actual_restart_qualified=True),dict(N4_accepted=True))):
            with collection(self.folder/str(i),mutate_pair=lambda r:r.update(change)) as f:
                with self.assertRaises(ValueError):f.call()
                self.assertFalse((f.folder/'COLLECTED.json').exists());self.assertEqual(f.events[-1],'release')
    def test_changed_parent_manifest_rejected_before_slot(self):
        with collection(self.folder/'cell') as f:
            with self.assertRaisesRegex(ValueError,'manifest'):
                subject.collect_one({},0,f.folder,subject.LOCAL/'supervision',[])
            self.assertEqual(f.events,[])
    def test_release_failure_is_preserved_even_after_collection(self):
        with collection(self.folder/'cell',failure='release') as f:
            with self.assertRaisesRegex(ValueError,'release'):f.call()
            self.assertTrue((f.folder/'COLLECTED.json').exists())
            self.assertIn('fixture release',load(f.folder/'PARENT_CLOSURE.json')['cleanup_error'])
    def test_post_exit_gate_rechecks_owner_supervision_and_policy(self):
        owner=dict(pid=1,create_time=1.);supervision=({}, {}, 'run');seen=[]
        with ExitStack() as stack:
            for name,value in [('exact_process',lambda o:None),('supervised_identity',lambda s:supervision),
                ('load',lambda p:{}),('bounded_output_bytes',lambda p:123),('validate_policy',lambda *a:seen.append(a))]:
                stack.enter_context(patch.object(subject,name,value))
            stack.enter_context(patch.object(subject.time,'monotonic',return_value=100.))
            subject.check_after_exit(self.folder,subject.LOCAL/'supervision',99.,owner,supervision)
            self.assertEqual(seen[0][-2:],(123,subject.MAX_CELL_BYTES))
            with patch.object(subject,'exact_process',return_value=object()),self.assertRaises(ValueError):
                subject.check_after_exit(self.folder,subject.LOCAL/'supervision',99.,owner,supervision)
            with self.assertRaisesRegex(ValueError,'deadline'):
                subject.check_after_exit(self.folder,subject.LOCAL/'supervision',-2000.,owner,supervision)
    def test_real_manifests_keep_fixed_child_and_interpreter(self):
        parent,child,exe,script=subject.qualified_manifests()
        self.assertGreater(len(parent),128);self.assertEqual(len(child),122);self.assertTrue(all(b in parent for b in child))
        self.assertEqual(script,bind(subject.HERE/'restart_application_child.py'))
        self.assertNotIn(bind(subject.__file__),child);self.assertIs(subject.supervise_child,prior.runner.supervise_child)

    def run_fixture(self, failure=False):
        output=self.folder/'run';code=[];child=[];exe={};script={};qualification={}
        plan=dict(required=2,required_sessions=4,rows=[dict(cell_id='pair1'),dict(cell_id='pair2')])
        freeze(self.folder/'PLAN.json',plan);pb=bind(self.folder/'PLAN.json')
        admission=dict(schema=subject.RUN_SCHEMA,status=subject.PREPARED,owner=dict(pid=987654321,create_time=1.),
            code=code,child_code=child,executable=exe,child_script=script,qualification=qualification,output=str(output),
            state=str(subject.LOCAL/'supervision'),plan=pb,required=2,required_sessions=4)
        freeze(output/'ADMISSION.json',admission);seen=[]
        def collect(plan,index,folder,state,code):
            seen.append(index)
            if failure and index==1:raise ValueError('fixture second pair')
            freeze(folder/'COLLECTED.json',dict(synthetic=True));return bind(folder/'COLLECTED.json')
        with ExitStack() as stack:
            for name,value in [('qualified_runner',lambda:(code,child,exe,script,qualification)),('exact_process',lambda o:None),
                ('supervised_identity',lambda s:({}, {}, 'fixture')),('admit_plan',lambda p:(pb,plan)),('collect_one',collect)]:
                stack.enter_context(patch.object(subject,name,value))
            if failure:
                with self.assertRaisesRegex(ValueError,'failed'):subject.run(output/'ADMISSION.json')
                terminal=bind(output/'RESULT.json')
                with self.assertRaisesRegex(ValueError,'existing terminal attempt'):subject.run(output/'ADMISSION.json')
                self.assertEqual(bind(output/'RESULT.json'),terminal)
            else:subject.run(output/'ADMISSION.json')
        return output,load(output/'RESULT.json'),seen
    def test_run_collects_exact_pair_population_without_acceptance(self):
        output,r,seen=self.run_fixture();self.assertEqual(seen,[0,1]);self.assertEqual(r['completed'],2)
        self.assertEqual(r['required_sessions'],4);self.assertEqual(len(r['collected']),2);self.assertFalse(r['N4_accepted'])
        self.assertEqual(r['status'],'COLLECTED_SELECTED_RESTART_PAIRS_REQUIRES_REVIEW')
    def test_run_preserves_partial_failure_and_never_reuses_terminal_attempt(self):
        output,r,seen=self.run_fixture(True);self.assertEqual(r['status'],'FAILED_RESTART_RUN_PRESERVED')
        self.assertEqual(r['completed'],1);self.assertIn('fixture second pair',r['error']);self.assertEqual(seen,[0,1])
    def test_prepare_binds_both_manifests_and_only_writes_worker_configuration(self):
        parent,child,exe,script=subject.qualified_manifests();output=self.folder/'prepared'
        plan=dict(required=2,required_sessions=4,synthetic=True);freeze(self.folder/'PLAN.json',plan);pb=bind(self.folder/'PLAN.json')
        with ExitStack() as stack:
            for name,value in [('qualified_runner',lambda:(parent,child,exe,script,dict(synthetic=True))),
                ('admit_plan',lambda p:(pb,plan)),('shared_allowance',lambda p:dict(synthetic=True)),
                ('writer_lock',lambda p:nullcontext())]:stack.enter_context(patch.object(subject,name,value))
            spawn=stack.enter_context(patch.object(subject,'PrivateApplicationProcess'))
            subject.prepare(self.folder/'PLAN.json',output);spawn.assert_not_called()
        r=load(output/'ADMISSION.json');worker=load(output/'worker.json')
        self.assertEqual(r['code'],parent);self.assertEqual(r['child_code'],child);self.assertFalse(r['actual_application_started'])
        self.assertEqual(worker['argv'][2],str(Path(subject.__file__).resolve()));self.assertEqual(worker['argv'][3],'run')
