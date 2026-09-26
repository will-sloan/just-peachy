"""Model-free lifecycle wiring and open-Controller archive regressions."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from common import bind, freeze, load
import restart_application_cell as subject
import restart_archive as archive
import test_restart_session as session_tests

CONTEXT={}


@contextmanager
def wired(output):
    """All source/model/GUI/clock/closure facts here are explicitly synthetic."""
    events=[];tick=SimpleNamespace(value=100.);cell=subject.RestartApplicationCell.__new__(subject.RestartApplicationCell)
    fake_time=SimpleNamespace(perf_counter=lambda:tick.value,sleep=lambda n:setattr(tick,'value',tick.value+n))
    out=output;out.mkdir();job=dict(job_id='SYNTHETIC_PAIR',audio_path=str(out/'NO_FILE.wav'),audio_sha256='0'*64,
        frames=3200,sample_rate_hz=16000,gain=1,reset_between_scenes=True,tap='O0')
    worker=SimpleNamespace(alive=True);worker.is_alive=lambda:worker.alive;worker.join=lambda n:None
    c=SimpleNamespace(engine=None,consumer=None,models=object(),worker=worker,commands=SimpleNamespace(unfinished_tasks=0),
        closed=False,saved_audio_only=True,collect_references=False,use_references=False,tap='O0',mode='open_with_names',
        epoch=0,file_offset=0,source_kind=None,state='STOPPED',error=None,rows=[])
    def start(path):
        tick.value+=.001
        events.append('start');c.epoch+=1;c.file_offset=0;c.source_kind='file';c.state='RUNNING'
        session=out/'data/sessions'/str(c.epoch);session.mkdir(parents=True)
        engine=SimpleNamespace(session_dir=session,state='RUNNING',_source=SimpleNamespace(sent=0,start_sample=0,journal=object()))
        engine._source.origin=tick.value
        consumer=SimpleNamespace(alive=True);consumer.is_alive=lambda:consumer.alive
        c.engine=engine;c.consumer=consumer;cell.delivery.engine=engine;cell.delivery.consumer=consumer
        cell.clock.engine=engine;c.rows.append(dict(session=str(session),synthetic=True))
    def stop():
        events.append('stop');c.engine.state='COMPLETED';c.consumer.alive=False
        c.file_offset=c.engine._source.sent;c.engine=c.consumer=None;c.source_kind=None;c.state='STOPPED'
    def close():
        events.append('controller_close')
        if c.engine is not None:stop()
        c.closed=True;worker.alive=False
    def update():
        tick.value+=.1
        if c.engine is not None and c.state=='RUNNING':
            c.engine._source.sent=min(job['frames'],c.engine._source.sent+320)
            if c.engine._source.sent==job['frames']:c.engine.state='COMPLETED';c.consumer.alive=False;c.state='STOPPED'
    c.start_file=start;c.stop=stop;c.close=close;c.snapshot=lambda:dict(rows=deepcopy(c.rows),synthetic=True)
    root=SimpleNamespace(update=update,destroy=lambda:events.append('root_destroy'))
    ui=SimpleNamespace(poll=lambda:events.append('poll'),root=root,controller=c,_closed=False)

    class Clock:
        def __init__(self,job):self.installed=False;self.engine=None
        def install(self,c):self.controller=c;self.installed=True;return self
        def snapshot(self):return dict(synthetic=True,source_epoch_monotonic_sec=self.engine._source.origin if self.engine else None)
        def detach(self):events.append('clock_detach');self.installed=False

    class Viewport:
        def __init__(self,ui,clock,output):self.closed=False;self.output=output
        def check(self):pass
        def close(self):
            events.append('viewport_close');self.closed=True;value=dict(failure=None,synthetic=True)
            freeze(self.output/'RESULT.json',value);return value

    class Capture:
        def __init__(self,c,job,contract,source,*,intent):
            self.controller=c;self.intent=intent;self.finished=False;self.ever_installed=False;self.installed=False
            self.engine=None;self.consumer=None;self.requested=False
        def check(self):pass
        def install(self):events.append('install');self.installed=self.ever_installed=True
        def restore_start(self):self.installed=False
        def request_stop(self):
            events.append('request');self.requested=True;c.stop()
        def finish(self,path,*,engine):
            events.append('extract');self.finished=True
            observation=dict(synthetic=True,source_sent=engine._source.sent,source_origin_perf_counter=engine._source.origin)
            freeze(path/'OBSERVATION.json',observation);(path/'TRACE.bin').write_bytes(b'fixture')
            freeze(path/'CAPTURE.json',dict(synthetic=True,intent=self.intent,observation=bind(path/'OBSERVATION.json'),trace=bind(path/'TRACE.bin')))
            return bind(path/'CAPTURE.json')

    resources=SimpleNamespace(phase='gallery_ready',error=None,owner=dict(pid=1,create_time=1.))
    def mark(phase):resources.phase=phase;events.append(phase)
    def resources_close():
        events.append('resources_close');row=dict(status='OBSERVED_HOST_RESOURCES',error=None,synthetic=True)
        freeze(out/'resources/RESULT.json',row);return row
    resources.mark=mark;resources.close=resources_close
    cell.__dict__.update(output=out,job=job,contract=dict(engine='PrototypeEngine',mode='open_with_names'),
        c=c,ui=ui,root=root,resources=resources,errors=[],started=False,closed=False,run_completed=False,run_error=None,
        result=None,began=100.,source_root=CONTEXT['prototype'],shared=(c,ui,root,worker,c.models),sessions=[],retained=[],
        session_folder=None,viewport_path=None,admission_check=None,next_guard=0.,deadline=None,initial_epoch=0,pair_proof=None,
        clock=Clock(job).install(c),viewport=None,delivery=None,engine=None,consumer=None)
    cell.viewport=Viewport(ui,cell.clock,out/'viewport')
    def delivery_review(v,raw,capture,job,contract):
        events.append('delivery_review')
        return dict(intent=capture['intent'],delivered_frames=v['source_sent'],source_origin_perf_counter=v['source_origin_perf_counter'],synthetic=True)
    def engine_capture(e,consumer,clock,job,release,binding):
        events.append('engine_capture');return dict(synthetic=True,job=job,delivered_frames=e._source.sent,session=str(e.session_dir))
    def complete(observed,archive):events.append('closure_review');return dict(synthetic=True,integrated_N4_cells=0)
    import paced_adapters_v3,paced_viewport
    with ExitStack() as stack:
        for mod,name,value in [(subject,'time',fake_time),(subject,'RestartSourceCapture',Capture),
            (paced_adapters_v3,'ConsumerSourceClock',Clock),(paced_viewport,'PacedViewport',Viewport),
            (subject,'validate_delivery',delivery_review),(subject,'capture_engine',engine_capture),
            (subject,'capture_archive',lambda c,e:dict(synthetic=True,controller_closed=c.closed)),(subject,'validate_complete',complete)]:
            stack.enter_context(patch.object(mod,name,value))
        cell._arm(0)
        yield cell,events,tick


class RestartApplicationTests(unittest.TestCase):
    def setUp(self):
        CONTEXT['checkpoint']();self.folder=CONTEXT['output']/self._testMethodName;self.folder.mkdir()
    def tearDown(self):CONTEXT['checkpoint']()
    def run_pair(self,cell,events):cell.run_pair(admission_check=lambda *a:events.append('admit'),stop_after_samples=640)

    def test_same_controller_pair_starts_twice_and_closes_after_both_reviews(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            original=cell.shared;self.run_pair(cell,events)
            self.assertEqual(original,cell.shared);self.assertFalse(cell.c.closed)
            self.assertEqual([r['controller_epoch'] for r in cell.sessions],[1,2]);self.assertEqual(len(cell.c.rows),2)
            self.assertLess(cell.sessions[0]['delivery_join']['delivered_frames'],3200)
            self.assertEqual(cell.sessions[1]['delivery_join']['delivered_frames'],3200)
            second_start=[i for i,e in enumerate(events) if e=='start'][1]
            self.assertLess(events.index('closure_review'),second_start)
            result=cell.close();self.assertEqual(result['status'],'COLLECTED_RESTART_PAIR_CLOSED_REQUIRES_REVIEW')
            self.assertEqual(events.count('start'),2);self.assertEqual(events.count('stop'),2)
            self.assertLess(max(i for i,e in enumerate(events) if e=='closure_review'),events.index('controller_close'))
            self.assertLess(events.index('controller_close'),events.index('resources_close'))
            self.assertFalse(result['actual_restart_qualified']);self.assertIs(cell.close(),result)
            freeze(CONTEXT['output']/'SYNTHETIC_PAIR_WIRING.json',dict(scope='Actual new lifecycle methods with entirely mocked GUI/source/model/observer/closure/admission; no production plan',events=events,result=bind(cell.output/'RESULT.json')))

    def test_old_single_source_entry_point_disabled(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            with self.assertRaises(ValueError):cell.run_source(admission_check=lambda *a:None)
            self.assertNotIn('start',events);self.assertEqual(cell.close()['status'],'PREPARED_RESTART_PAIR_ONLY_CLOSED')

    def test_threshold_must_leave_positive_prefix_and_eof_margin(self):
        for i,value in enumerate((0,True,321,3199,3200,2880)):
            with wired(self.folder/str(i)) as (cell,events,tick):
                with self.assertRaises(ValueError):cell.run_pair(admission_check=lambda *a:None,stop_after_samples=value)
                self.assertNotIn('start',events);cell.close()

    def test_initial_admission_failure_never_starts(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            def denied(*a):raise ValueError('fixture admission refusal')
            with self.assertRaises(ValueError):cell.run_pair(admission_check=denied,stop_after_samples=640)
            self.assertFalse(cell.started);self.assertNotIn('start',events);cell.close()

    def test_changed_ui_controller_root_or_closed_state_prevents_start(self):
        for i,field in enumerate(('controller','root','_closed')):
            with wired(self.folder/str(i)) as (cell,events,tick):
                original=getattr(cell.ui,field);setattr(cell.ui,field,True if field=='_closed' else object())
                with self.assertRaises(ValueError):self.run_pair(cell,events)
                self.assertNotIn('start',events);setattr(cell.ui,field,original);cell.close()

    def test_expired_pair_deadline_never_starts(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            tick.value=1001.
            with self.assertRaises(ValueError):self.run_pair(cell,events)
            self.assertNotIn('start',events);cell.close()

    def test_changed_shared_owner_prevents_second_start(self):
        for i,attribute in enumerate(('models','worker')):
            with wired(self.folder/str(i)) as (cell,events,tick):
                original=cell._arm
                def arm(index):
                    if index:setattr(cell.c,attribute,object())
                    return original(index)
                with patch.object(cell,'_arm',side_effect=arm):
                    with self.assertRaises(ValueError):self.run_pair(cell,events)
                self.assertEqual(events.count('start'),1)
                cell.c.worker=cell.shared[3];cell.c.models=cell.shared[4];self.assertEqual(cell.close()['status'],'FAILED_RESTART_PAIR_PRESERVED')

    def test_prefix_review_failure_prevents_second_start_and_preserves_capture(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            with patch.object(subject,'validate_complete',side_effect=ValueError('fixture incomplete archive')):
                with self.assertRaises(ValueError):self.run_pair(cell,events)
            self.assertEqual(events.count('start'),1);self.assertTrue((cell.session_folder/'delivery/CAPTURE.json').is_file())
            self.assertEqual(cell.close()['status'],'FAILED_RESTART_PAIR_PRESERVED')

    def test_eof_review_failure_cannot_write_pair_success(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            original=subject.validate_complete
            def review(observed,receipt):
                if observed['delivered_frames']==3200:raise ValueError('fixture final failure')
                return original(observed,receipt)
            with patch.object(subject,'validate_complete',side_effect=review):
                with self.assertRaises(ValueError):self.run_pair(cell,events)
            self.assertEqual(events.count('start'),2);self.assertFalse(cell.run_completed)
            self.assertFalse((cell.output/'PAIR_OBSERVATION.json').exists());cell.close()

    def test_duplicate_pair_cannot_restart_again(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            self.run_pair(cell,events)
            with self.assertRaises(ValueError):self.run_pair(cell,events)
            self.assertEqual(events.count('start'),2);cell.close()

    def test_mid_run_admission_revocation_prevents_restart(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            calls=[]
            def gate(*args):
                calls.append(1)
                if len(calls)>3:raise ValueError('fixture lease revoked')
            with self.assertRaises(ValueError):cell.run_pair(admission_check=gate,stop_after_samples=640)
            self.assertEqual(events.count('start'),1)
            self.assertEqual(cell.close()['status'],'FAILED_RESTART_PAIR_PRESERVED')

    def test_second_origin_must_follow_first_release(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            original=cell.c.start_file
            def start(path):
                original(path)
                if cell.c.epoch==2:cell.c.engine._source.origin=cell.sessions[0]['completed_monotonic_sec']
            cell.c.start_file=start
            with self.assertRaisesRegex(ValueError,'origin'):self.run_pair(cell,events)
            self.assertFalse(cell.run_completed);cell.close()

    def test_failed_gui_cleanup_cannot_return_collected_success(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            self.run_pair(cell,events)
            def failed():raise RuntimeError('fixture Tk cleanup failure')
            cell.root.destroy=failed
            self.assertEqual(cell.close()['status'],'FAILED_RESTART_PAIR_PRESERVED')
            self.assertIn('resources_close',events)

    def test_viewport_scope_retains_and_names_prior_session(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            self.run_pair(cell,events)
            first,second=[load(r['viewport_scope']['path']) for r in cell.sessions]
            self.assertEqual(first['prior_native_sessions'],[])
            self.assertEqual(second['prior_native_sessions'],[first['native_session']])
            self.assertFalse(second['all_rows_have_current_source_clock'])
            self.assertEqual(len(cell.c.rows),2);cell.close()

    def test_pending_first_commands_prevent_arming(self):
        with wired(self.folder/'cell') as (cell,events,tick):
            cell.c.commands.unfinished_tasks=1
            with self.assertRaises(ValueError):cell._arm(0)
            cell.c.commands.unfinished_tasks=0;cell.close()

    def test_reused_source_state_prevents_pair_success(self):
        for i,field in enumerate(('engine','journal','consumer','clock','viewport')):
            with wired(self.folder/str(i)) as (cell,events,tick):
                original=cell.c.start_file
                def start(path):
                    original(path)
                    if cell.c.epoch==2:
                        old=cell.retained[0]
                        if field=='journal':cell.c.engine._source.journal=old['journal']
                        elif field=='engine':cell.c.engine=old['engine'];cell.delivery.engine=old['engine']
                        elif field=='consumer':cell.c.consumer=old['consumer']
                        else:setattr(cell,field,old[field])
                cell.c.start_file=start
                with self.assertRaises(ValueError):self.run_pair(cell,events)
                self.assertFalse(cell.run_completed);cell.close()

    def test_nonzero_restart_offset_or_wrong_epoch_rejected(self):
        for i,field in enumerate(('epoch','file_offset')):
            with wired(self.folder/str(i)) as (cell,events,tick):
                original=cell.c.start_file
                def start(path):
                    original(path)
                    if cell.c.epoch==2:setattr(cell.c,field,5)
                cell.c.start_file=start
                with self.assertRaises(ValueError):self.run_pair(cell,events)
                self.assertFalse(cell.run_completed);cell.close()

    def archive_fixture(self):
        value=load(CONTEXT['cases'][0]['archive']['path'])
        value.update(schema='n4-released-session-archive-v1',controller_closed=False,controller_worker_alive=True,session_released=True)
        return value

    def test_open_controller_archive_keeps_every_drain_check(self):
        value=self.archive_fixture();before=deepcopy(value)
        archive.validate_archive_integrity(value,CONTEXT['cases'][0]['audio']['frames'])
        self.assertEqual(value,before)
        freeze(CONTEXT['output']/'SYNTHETIC_OPEN_ARCHIVE.json',dict(scope='Copied historical archive with synthetic open-Controller ownership; not new runtime evidence',receipt=value))

    def test_old_full_controller_archive_cannot_pass_release_schema(self):
        with self.assertRaises(ValueError):archive.validate_archive_integrity(load(CONTEXT['cases'][0]['archive']['path']),CONTEXT['cases'][0]['audio']['frames'])

    def test_open_archive_rejects_failed_release_or_incomplete_drains(self):
        value=self.archive_fixture();count=CONTEXT['cases'][0]['audio']['frames']
        for change in [lambda r:r.update(controller_closed=True),lambda r:r.update(controller_worker_alive=False),
            lambda r:r.update(session_released=False),lambda r:r.update(worker_alive=True),lambda r:r.update(active_archive_owners=1),
            lambda r:r.update(accepted_items=0),lambda r:r['persisted'].update(source_samples=count-1),
            lambda r:r['persisted'].update(loss='fixture'),lambda r:r['epoch'].update(sha256='0'*64)]:
            row=deepcopy(value);change(row)
            with self.assertRaises((ValueError,RuntimeError)):archive.validate_archive_integrity(row,count)

    def test_open_archive_combines_with_explicit_prefix_engine(self):
        fixture=session_tests.RestartSessionTests();fixture.folder=self.folder
        observed=fixture.closure_fixture();result=archive.validate_complete(observed,self.archive_fixture())
        self.assertTrue(result['controller_still_open']);self.assertFalse(result['same_controller_restart_qualified'])
        self.assertEqual(result['engine']['source_samples'],observed['delivered_frames'])
