"""RAM-only release commands and explicit synthetic closure joins; see README."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from common import bind, fingerprint, freeze, load
import application_delivery as full
import restart_source_capture as subject
import restart_session_closure as closure
import test_application_delivery as prior
import test_application_closure_v2 as historical

CONTEXT = {}


class Fixture(prior.Fixture):
    def __init__(self, intent='mid_file_stop'):
        super().__init__(); self.intent=intent; self.commands=0
        self.c.models=object(); self.c.epoch=1; self.c.commands=SimpleNamespace(unfinished_tasks=0)
        self.c.consumer=SimpleNamespace(is_alive=lambda:False)
        self.capture=subject.RestartSourceCapture(self.c,self.f.job,self.contract,CONTEXT['prototype'],intent=intent,
            _types=self.f.types,_observer_factory=lambda s,j:prior.SourceDelivery(s,j,_types=self.f.types,_clock=lambda:self.f.now))
        self.c.stop=self.stop

    def start(self):
        if self.intent=='mid_file_stop':self.f.stop_after=1
        self.ready();self.f.source.start()
        self.c.state='RUNNING' if self.intent=='mid_file_stop' else 'STOPPED'
        self.engine.state='RUNNING' if self.intent=='mid_file_stop' else 'COMPLETED'
        # Source execution is synchronous RAM-only. These explicit fake owner
        # states exercise command admission, not a live application producer.
        self.f.source.thread.is_alive=lambda:self.intent=='mid_file_stop'
        self.c.consumer.is_alive=lambda:self.intent=='mid_file_stop'
        self.f.source.stop_event.flag=False

    def stop(self):
        self.commands+=1;self.f.source.thread.is_alive=lambda:False
        self.c.consumer.is_alive=lambda:False;self.f.source.stop_event.set()
        self.c.file_offset=self.f.source.sent;self.c.engine=None;self.c.consumer=None
        self.c.source_kind=None;self.c.state='STOPPED';self.engine.state='COMPLETED'

    def finish(self, folder):return load(self.capture.finish(folder,engine=self.engine)['path'])


class RestartSessionTests(unittest.TestCase):
    def setUp(self):
        CONTEXT['checkpoint']();self.folder=CONTEXT['output']/self._testMethodName;self.folder.mkdir();self.fixtures=[]

    def tearDown(self):
        for f in self.fixtures:f.capture.restore_start()
        CONTEXT['checkpoint']()

    def fixture(self,intent='mid_file_stop'):
        f=Fixture(intent);self.fixtures.append(f);return f

    def collected(self,intent='mid_file_stop',suffix='delivery'):
        f=self.fixture(intent);f.start();f.capture.request_stop();capture=f.finish(self.folder/suffix)
        return f,capture,load(capture['observation']['path']),Path(capture['trace']['path']).read_bytes()

    def args(self,intent='mid_file_stop'):
        f,c,v,raw=self.collected(intent)
        # Copies only: synthetic branches never modify saved fixture flags.
        c=deepcopy(c);v=deepcopy(v);c['test_seams_used']=v['test_seams_used']=False
        return [v,raw,c,f.f.job,f.contract]

    def test_mid_file_stop_keeps_controller_and_full_input(self):
        f,c,v,raw=self.collected()
        self.assertEqual(c['status'],'COLLECTED_RELEASED_SESSION_DELIVERY_REQUIRES_REVIEW')
        self.assertEqual(f.commands,1);self.assertEqual(v['source_sent'],320)
        self.assertEqual(v['expected_frames'],650);self.assertFalse(v['summary']['complete_source'])
        self.assertFalse(f.c.closed);self.assertTrue(f.c.worker.is_alive())
        self.assertTrue(all(c['owner_join'].values()));self.assertIs(f.c.models,f.capture.models)

    def test_completed_release_keeps_controller_available(self):
        f,c,v,raw=self.collected('completed_release')
        self.assertEqual(c['status'],'COLLECTED_RELEASED_SESSION_DELIVERY_REQUIRES_REVIEW')
        self.assertEqual(v['source_sent'],650);self.assertTrue(v['summary']['complete_source'])
        self.assertEqual(f.commands,1);self.assertFalse(f.c.closed)

    def test_whole_file_delivery_validator_rejects_new_schema(self):
        a=self.args()
        with self.assertRaises(ValueError):full.validate_delivery(a[0],a[1],a[2],{}, {},a[3],a[4])

    def test_mid_file_request_rejects_eof(self):
        f=self.fixture();f.f.stop_after=None;f.start();f.f.source.sent=f.f.job['frames']
        with self.assertRaises(ValueError):f.capture.request_stop()
        self.assertEqual(f.commands,0)

    def test_mid_file_request_rejects_zero_prefix(self):
        f=self.fixture();f.start();f.f.source.sent=0
        with self.assertRaises(ValueError):f.capture.request_stop()
        self.assertEqual(f.commands,0)

    def test_second_stop_cannot_enqueue_again(self):
        f=self.fixture();f.start();f.capture.request_stop()
        with self.assertRaises(ValueError):f.capture.request_stop()
        self.assertEqual(f.commands,1)

    def test_second_source_start_rejected(self):
        f=self.fixture();f.start()
        with self.assertRaises(ValueError):f.f.source.start()
        with self.assertRaises(ValueError):f.capture.request_stop()
        self.assertEqual(f.commands,0)

    def test_wrong_owners_pending_commands_and_stopped_source_rejected(self):
        changes=[lambda f:setattr(f.c,'models',object()),lambda f:setattr(f.c,'engine',object()),
            lambda f:setattr(f.c,'closed',True),lambda f:setattr(f.c,'error','synthetic error'),
            lambda f:setattr(f.c.commands,'unfinished_tasks',1),lambda f:setattr(f.c,'file_offset',1),
            lambda f:setattr(f.c,'source_kind','live'),lambda f:setattr(f.c,'state','STOPPED'),
            lambda f:f.f.source.stop_event.set(),lambda f:setattr(f.c.consumer,'is_alive',lambda:False)]
        for change in changes:
            f=self.fixture();f.start();change(f)
            with self.assertRaises(ValueError):f.capture.request_stop()
            self.assertEqual(f.commands,0);f.capture.restore_start()

    def test_stop_exception_preserved_and_not_retried(self):
        f=self.fixture();f.start();error=RuntimeError('fixture stop failure')
        def fail():raise error
        f.c.stop=fail
        with self.assertRaises(RuntimeError) as got:f.capture.request_stop()
        self.assertIs(got.exception,error)
        with self.assertRaises(ValueError):f.capture.request_stop()
        self.assertEqual(f.capture.request['error'],'RuntimeError')
        f.stop();c=f.finish(self.folder/'failed')
        self.assertEqual(c['status'],'FAILED_RELEASED_SESSION_DELIVERY_PRESERVED')

    def test_missing_release_and_closed_controller_preserve_failure(self):
        f=self.fixture();f.start();f.capture.request_stop();f.c.closed=True
        c=f.finish(self.folder/'closed');self.assertEqual(c['status'],'FAILED_RELEASED_SESSION_DELIVERY_PRESERVED')
        self.assertIsNotNone(c['observation']);self.assertTrue(c['controller_closed'])

    def test_foreign_start_hook_preserved(self):
        f=self.fixture();f.start();f.capture.request_stop();foreign=lambda s:None;f.f.types[0].start=foreign
        c=f.finish(self.folder/'foreign')
        self.assertIs(f.f.types[0].start,foreign);self.assertIn('foreign_start_hook_preserved',c['errors'])

    def test_pure_prefix_review_has_explicit_limits(self):
        a=self.args();result=subject.validate_delivery(*a)
        self.assertEqual((result['planned_frames'],result['delivered_frames']),(650,320))
        self.assertFalse(result['same_controller_restart_qualified']);self.assertEqual(result['integrated_N4_cells'],0)
        freeze(CONTEXT['output']/'SYNTHETIC_PREFIX_DELIVERY.json',dict(scope='Copied fixture flags normalized for pure reader only',result=result))

    def test_pure_completed_release_review(self):
        result=subject.validate_delivery(*self.args('completed_release'))
        self.assertEqual(result['delivered_frames'],650);self.assertFalse(result['same_controller_restart_qualified'])

    def test_test_seams_cannot_qualify_production(self):
        f,c,v,raw=self.collected()
        with self.assertRaises(ValueError):subject.validate_delivery(v,raw,c,f.f.job,f.contract)

    def test_request_clock_epoch_and_count_tampering_rejected(self):
        a=self.args()
        for changes in [dict(returned=False),dict(error='failure'),dict(epoch=0),dict(source_sent_before=0),
                        dict(source_sent_before=321),dict(state_before='STOPPED'),dict(source_stop_set_before=True),
                        dict(requested_monotonic_sec=float('nan')),dict(returned_monotonic_sec=1.)]:
            b=deepcopy(a);b[2]['request'].update(changes)
            with self.assertRaises(ValueError):subject.validate_delivery(*b)

    def test_trace_corruption_and_false_census_rejected(self):
        a=self.args()
        for change in [lambda b:b.__setitem__(1,b[1][:-1]),lambda b:b[0].update(journal_committed=321),
                       lambda b:b[0]['summary'].update(complete_source=True),lambda b:b[0].update(append_attempts=0),
                       lambda b:b[0].update(source_origin_perf_counter=1e20)]:
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):subject.validate_delivery(*b)

    def test_false_owners_source_effects_and_changed_job_rejected(self):
        a=self.args()
        for change in [lambda b:b[2].update(schema='n4-application-delivery-capture-v1'),
            lambda b:b[2]['owner_join'].update(controller_open=False),lambda b:b[2].update(intent='completed_release'),
            lambda b:b[0].update(source_pacer_changed=True),lambda b:b[0].update(source_stop_requested=False),
            lambda b:b[3].update(frames=320),lambda b:b[2].update(job_fingerprint='foreign'),
            lambda b:b[2].update(controller_closed=True),lambda b:b[2].update(same_controller_restart_qualified=True),
            lambda b:b[2].update(integrated_N4_cells=1)]:
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):subject.validate_delivery(*b)

    def closure_fixture(self,intent='mid_file_stop',suffix='capture'):
        row=historical.observed_fixture();count=row['job']['frames']
        if intent=='mid_file_stop':row['job']['frames']+=320
        request=dict(intent=intent,epoch=1,state_before='RUNNING' if intent=='mid_file_stop' else 'STOPPED',
            source_sent_before=count,source_stop_set_before=False,requested_monotonic_sec=200.,
            returned_monotonic_sec=200.1,returned=True,error=None)
        capture=dict(schema='n4-released-session-delivery-v1',policy=subject.POLICY,
            status='COLLECTED_RELEASED_SESSION_DELIVERY_REQUIRES_REVIEW',intent=intent,
            job_fingerprint=fingerprint(row['job']),request=request,owner_join={k:True for k in subject.JOIN_KEYS},
            test_seams_used=False,errors=[])
        path=self.folder/(suffix+'.json');freeze(path,capture)
        row.update(schema='n4-released-session-engine-closure-v1',delivered_frames=count,release_capture=bind(path),
            observed_monotonic_sec=201.,session_owner_join=dict(same_engine=True,same_controller=True,retained_consumer_exited=True,capture_finished=True))
        row['controller_clock']['epoch']=1
        return row

    def test_explicit_prefix_engine_closure_preserves_planned_job(self):
        row=self.closure_fixture();before=deepcopy(row);result=closure.validate_engine(row)
        self.assertEqual(row,before);self.assertEqual(result['source_samples'],row['delivered_frames'])
        self.assertEqual(result['planned_frames'],row['delivered_frames']+320)
        self.assertFalse(result['same_controller_restart_qualified'])
        freeze(CONTEXT['output']/'SYNTHETIC_PREFIX_ENGINE.json',dict(scope='Synthetic longer planned input and owner facts joined to historical terminal counts; no new application',observed=row,result=result))

    def test_completed_engine_release_and_archive(self):
        row=self.closure_fixture('completed_release')
        archive=load(CONTEXT['cases'][0]['archive']['path']);result=closure.validate_complete(row,archive)
        self.assertEqual(result['integrated_N4_cells'],0);self.assertFalse(result['same_controller_restart_qualified'])

    def test_prefix_archive_uses_delivered_count(self):
        row=self.closure_fixture();result=closure.validate_complete(row,load(CONTEXT['cases'][0]['archive']['path']))
        self.assertEqual(result['engine']['source_samples'],row['delivered_frames'])

    def test_prefix_engine_rejects_incomplete_workers_counts_and_foreign_epoch(self):
        row=self.closure_fixture()
        for change in [lambda r:r.update(delivered_frames=r['job']['frames']),lambda r:r['source'].update(sent=0),
            lambda r:r['threads']['consumer'].update(alive=True),lambda r:r['workers']['journal'].update(depth=1),
            lambda r:r['journals']['_identity_journal'].update(committed_samples=0),
            lambda r:r.update(asr_cursor_sec=0),lambda r:r['session_owner_join'].update(same_controller=False),
            lambda r:r['controller_clock'].update(epoch=2),lambda r:r.update(observed_monotonic_sec=100.)]:
            copy=deepcopy(row);change(copy)
            with self.assertRaises(ValueError):closure.validate_engine(copy)

    def test_release_capture_binding_is_verified(self):
        row=self.closure_fixture();row['release_capture']['sha256']='0'*64
        with self.assertRaises((ValueError,RuntimeError)):closure.validate_engine(row)
