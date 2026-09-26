"""Synthetic cross-reader and fixed-file tests; no application or model execution."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load
from restart_application_cell import POLICY
from test_restart_child import payload as child_payload
import restart_pair_evidence as subject

OUTPUT = None


def session_values(job, contract, folder, index):
    """Only test metadata; the three separately qualified leaf readers are mocked."""
    intent = ('mid_file_stop', 'completed_release')[index]
    sent = 32320 if index == 0 else job['frames']; origin = 100.+20*index; epoch = index+1
    native_path = folder/'data/sessions'/str(epoch); native_path.mkdir(parents=True)
    for name in ('session_finalization_v3.json', 's6d_consumer_closure.json', 'events.jsonl'):
        freeze(native_path/name, dict(synthetic=True))
    terminal = [bind(native_path/name) for name in ('session_finalization_v3.json', 's6d_consumer_closure.json')]
    event = dict(publication_sequence=2, publication_monotonic_sec=origin+.1, publication_source_cursor_sec=0)
    clock = dict(epoch=epoch, source_epoch_monotonic_sec=origin, source_started=dict(event_payload=event),
        last_publication_sequence=6, event_count=5, missing_publication_sequences=1)
    capture = dict(intent=intent, request=dict(epoch=epoch, source_sent_before=sent))
    delivery = dict(status='PASS_RELEASED_SESSION_DELIVERY_ONLY', intent=intent, planned_frames=job['frames'],
        delivered_frames=sent, source_origin_perf_counter=origin,
        summary=dict(successful_samples=sent, last_append_return_after_origin_seconds=sent/16000))
    closure = dict(status='PASS_RELEASED_SESSION_ENGINE_AND_OPEN_CONTROLLER_ARCHIVE',
        engine=dict(source_samples=sent), controller_still_open=True, same_controller_restart_qualified=False)
    native = dict(schema='n4-released-native-envelope-v1', status='PASS_COMPLETE_RELEASED_NATIVE_EVENT_ENVELOPE_ONLY',
        job_fingerprint=fingerprint(job), planned_audio_frames=job['frames'], delivered_audio_frames=sent, intent=intent,
        complete_envelope=True, terminal=terminal, journal=[bind(native_path/'events.jsonl')],
        expected_events=6, retained_events=6, source_start=dict(sequence=2, source_epoch_monotonic_sec=origin,
        publication_monotonic_sec=origin+.1), completion_publication_monotonic_sec=origin+4.1,
        delivered_length_independently_joined=False, same_controller_restart_qualified=False, N4_accepted=False, integrated_N4_cells=0)
    observed = dict(job=job, engine_class=contract['engine'], session=str(native_path), controller_clock=clock,
        delivered_frames=sent, source=dict(sent=sent), observed_monotonic_sec=origin+5,
        publication_census=dict(published=6, consumed=5, coalesced_obsolete_ui_partials=1),
        persisted=dict(finalization=terminal[0], consumer=terminal[1]))
    row = dict(status='COLLECTED_RESTART_SESSION_REQUIRES_REVIEW', index=index, intent=intent, job=job,
        controller_epoch=epoch, native_session=str(native_path), actual_restart_qualified=False, integrated_N4_cells=0,
        delivery_join=delivery, closure=closure, completed_monotonic_sec=origin+6)
    return [row, capture, observed, clock, delivery, closure, native]


def pair_value(rows, owner, receipts):
    return dict(schema='n4-same-controller-restart-observation-v1', same_controller=True, same_ui=True,
        same_tk_root=True, same_command_worker=True, same_model_store=True,
        distinct_engines_sources_journals_consumers_clocks_viewports=True, source_jobs_unchanged=True,
        second_origin_after_first_release=True, controller_still_open=True, initial_epoch=0, process_owner=owner,
        session_receipts=receipts, actual_restart_qualified=False, integrated_N4_cells=0,
        consecutive_epochs=[1, 2], source_start_samples=[0, 0],
        native_sessions=[r['native_session'] for r in rows], planned_stop_after_samples=32000)


@contextmanager
def wired(folder):
    payload=child_payload();payload['job']['frames']=64000
    app=folder/'application';app.mkdir(parents=True);owner=dict(pid=987654321, create_time=1.)
    prototype=folder/'synthetic_source';files={}
    for name in ('app/pipeline.py', 'app/buffers.py'):
        path=prototype/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_text('# synthetic source, never imported\n')
        b=bind(path);files[name]={k:b[k] for k in ('sha256', 'bytes')}
    freeze(folder/'SOURCE.json', dict(prototype=str(prototype), files=files));payload['source_receipt']=bind(folder/'SOURCE.json')
    source_files=[bind(prototype/name) for name in files]
    rows=[];args=[];receipts=[]
    for index, n in enumerate(('01', '02')):
        values=session_values(payload['job'], payload['contract'], app, index)
        row,capture,observed,clock,delivery,closure,native=values;session=app/'sessions'/n
        freeze(session/'delivery/OBSERVATION.json', dict(synthetic=True, index=index))
        (session/'delivery/TRACE.bin').write_bytes(b'synthetic trace')
        capture.update(observation=bind(session/'delivery/OBSERVATION.json'), trace=bind(session/'delivery/TRACE.bin'), source_files=source_files)
        freeze(session/'delivery/CAPTURE.json', capture);row['delivery_capture']=bind(session/'delivery/CAPTURE.json')
        observed['release_capture']=row['delivery_capture'];freeze(session/'ENGINE_CLOSURE.json', observed)
        freeze(app/'data'/f'epoch-{n}.json', dict(synthetic=True));archive=dict(epoch=bind(app/'data'/f'epoch-{n}.json'))
        freeze(session/'ARCHIVE_INTEGRITY.json', archive);freeze(session/'SOURCE_CLOCK.json', clock)
        row.update(engine_closure=bind(session/'ENGINE_CLOSURE.json'),archive=bind(session/'ARCHIVE_INTEGRITY.json'),source_clock=bind(session/'SOURCE_CLOCK.json'))
        scope=dict(schema='n4-restart-viewport-session-scope-v1',native_session=observed['session'],publication_session=str(index+1),
            controller_epoch=index+1,prior_native_sessions=[r['native_session'] for r in rows],prior_caption_history_retained=True,
            all_rows_have_current_source_clock=False,source_to_widget_latency_qualified=False,
            instruction='Match caption keys/publication sessions before interpreting each row; old history is not new-session output')
        freeze(session/'VIEWPORT_SCOPE.json',scope);freeze(session/'CONTROLLER_SNAPSHOT.json',dict(synthetic=True))
        vp=app/'viewport' if index==0 else session/'viewport';freeze(vp/'SUMMARY.json',dict(synthetic=True))
        freeze(vp/'RESULT.json',dict(status='RECORDED_RENDER_AND_TIMER_OBSERVATIONS',failure=None,timer_cancelled=True,
            source_to_widget_latency_qualified=False,integrated_N4_cells=0,ledger=bind(vp/'SUMMARY.json')))
        row.update(viewport_scope=bind(session/'VIEWPORT_SCOPE.json'),controller_snapshot=bind(session/'CONTROLLER_SNAPSHOT.json'),viewport=bind(vp/'RESULT.json'))
        freeze(session/'RESULT.json',row);receipts.append(bind(session/'RESULT.json'));rows.append(row);args.append(values)
    freeze(app/'PAIR_OBSERVATION.json',pair_value(rows,owner,receipts))
    freeze(app/'PREPARED.json',dict(status='PREPARED_NO_SOURCE_OR_MODELS_STARTED',no_auto_start=True,job=payload['job'],
        contract=payload['contract'],runtimes=payload['runtimes'],gallery_preparation=payload['gallery_preparation'],logical_client=[480,800],active_height_px=184))
    freeze(app/'RESTART_PREPARED.json',dict(status='PREPARED_RESTART_PAIR_NO_SOURCE_STARTED',policy=POLICY,job=payload['job'],
        contract=payload['contract'],resources_owner=owner,initial_epoch=0,actual_restart_qualified=False,integrated_N4_cells=0,
        inherited_preparation=bind(app/'PREPARED.json')))
    freeze(app/'resources/RESULT.json',dict(status='OBSERVED_HOST_RESOURCES',error=None,owner=owner,observer_thread_exited=True))
    freeze(app/'RESULT.json',dict(schema='n4-restart-application-cell-v1',status='COLLECTED_RESTART_PAIR_CLOSED_REQUIRES_REVIEW',
        policy=POLICY,source_start_requested=True,completed_sessions=2,errors=[],callback_errors=[],controller_closed=True,
        controller_worker_exited=True,failure_delivery_capture=None,actual_restart_qualified=False,source_to_widget_latency_qualified=False,
        complete_N4_acceptance=False,integrated_N4_cells=0,sessions=receipts,pair_observation=bind(app/'PAIR_OBSERVATION.json'),
        resources=bind(app/'resources/RESULT.json')))
    def delivery(value, raw, capture, job, contract):
        assert raw==b'synthetic trace' and job==payload['job'] and contract==payload['contract']
        return deepcopy(args[value['index']][4])
    def complete(observed, archive):
        index=observed['controller_clock']['epoch']-1
        assert archive['epoch']==bind(app/'data'/f'epoch-{index+1:02d}.json')
        return deepcopy(args[index][5])
    def native(path, *, job, delivered_frames, intent, checkpoint):
        index=int(path.name)-1
        assert job==payload['job'] and delivered_frames==args[index][4]['delivered_frames'] and intent==args[index][0]['intent']
        return deepcopy(args[index][6])
    with ExitStack() as stack:
        mocks=[stack.enter_context(patch.object(subject,name,side_effect=value)) for name,value in
            [('validate_delivery',delivery),('validate_complete',complete),('inspect',native)]]
        yield app,payload,owner,args,mocks


class PairEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.folder=OUTPUT/self._testMethodName;self.folder.mkdir()
        self.payload=child_payload();self.payload['job']['frames']=64000
    def values(self,index=0):return session_values(self.payload['job'],self.payload['contract'],self.folder/str(index),index)
    def join(self,a,index=0):return subject.join_session(*a,job=self.payload['job'],contract=self.payload['contract'],index=index,epoch=index+1)
    def test_valid_partial_and_full_joins_preserve_originals(self):
        for index in (0,1):
            a=self.values(index);before=deepcopy(a);r=self.join(a,index)
            self.assertEqual(a,before);self.assertEqual(r['delivered_frames'],(32320,64000)[index])
    def test_mismatched_full_job_engine_or_intent_rejected(self):
        a=self.values()
        for change in (lambda a:a[0].update(job={}),lambda a:a[2].update(engine_class='foreign'),lambda a:a[0].update(intent='completed_release')):
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):self.join(b)
    def test_cross_epoch_and_source_clock_rejected(self):
        a=self.values()
        for change in (lambda a:a[1]['request'].update(epoch=2),lambda a:a[0].update(controller_epoch=True),
                       lambda a:a.__setitem__(3,dict(a[3],epoch=2)),lambda a:a[0].update(native_session='foreign')):
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):self.join(b)
    def test_independent_delivery_or_closure_disagreement_rejected(self):
        a=self.values()
        for field in ('delivery_join','closure'):
            b=deepcopy(a);b[0][field]={}
            with self.assertRaises(ValueError):self.join(b)
    def test_native_delivery_and_engine_counts_must_agree(self):
        a=self.values()
        for change in (lambda a:a[6].update(delivered_audio_frames=32000),lambda a:a[2]['source'].update(sent=64000),
                       lambda a:a[4]['summary'].update(successful_samples=0),lambda a:a[6].update(planned_audio_frames=32320)):
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):self.join(b)
    def test_terminal_substitution_and_incomplete_journal_rejected(self):
        a=self.values()
        for change in (lambda a:a[6].update(terminal=[]),lambda a:a[6].update(complete_envelope=False),
                       lambda a:a[6].update(delivered_length_independently_joined=True)):
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):self.join(b)
    def test_origin_publication_and_event_census_rejected(self):
        a=self.values()
        for change in (lambda a:a[6]['source_start'].update(source_epoch_monotonic_sec=99),
            lambda a:a[6]['source_start'].update(sequence=3),lambda a:a[6].update(expected_events=7),
            lambda a:a[2]['publication_census'].update(consumed=6)):
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):self.join(b)
    def test_append_native_and_release_order_rejected(self):
        a=self.values()
        for change in (lambda a:a[0].update(completed_monotonic_sec=100.),
            lambda a:a[4]['summary'].update(last_append_return_after_origin_seconds=10.),
            lambda a:a[6].update(completion_publication_monotonic_sec=110.),lambda a:a[0].update(completed_monotonic_sec=float('nan'))):
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):self.join(b)
    def test_false_session_acceptance_rejected(self):
        a=self.values()
        for change in (lambda a:a[0].update(actual_restart_qualified=True),lambda a:a[0].update(integrated_N4_cells=True),
            lambda a:a[5].update(controller_still_open=False)):
            b=deepcopy(a);change(b)
            with self.assertRaises(ValueError):self.join(b)
    def pair_args(self):
        sessions=[self.join(self.values(i),i) for i in (0,1)];owner=dict(pid=1,create_time=1.);receipts=[dict(synthetic=1),dict(synthetic=2)]
        p=pair_value(sessions,owner,receipts)
        return p,sessions,dict(owner=owner,initial_epoch=0,planned_control=subject.control(self.payload),session_bindings=receipts)
    def test_pair_join_keeps_review_limits(self):
        p,s,k=self.pair_args();before=deepcopy([p,s,k]);r=subject.join_pair(p,s,**k)
        self.assertEqual([p,s,k],before);self.assertFalse(r['actual_restart_qualified']);self.assertFalse(r['independent_object_identity_instrumentation'])
    def test_pair_wrong_owner_objects_or_bindings_rejected(self):
        p,s,k=self.pair_args()
        for change in (dict(same_model_store=False),dict(same_ui=False),dict(process_owner={}),dict(session_receipts=[]),dict(actual_restart_qualified=True)):
            b=deepcopy(p);b.update(change)
            with self.assertRaises(ValueError):subject.join_pair(b,s,**k)
    def test_pair_epoch_offset_threshold_and_session_reuse_rejected(self):
        p,s,k=self.pair_args()
        for change in (dict(initial_epoch=True),dict(consecutive_epochs=[1,3]),dict(source_start_samples=[0,320]),
                       dict(planned_stop_after_samples=640),dict(native_sessions=['x','x'])):
            b=deepcopy(p);b.update(change)
            with self.assertRaises(ValueError):subject.join_pair(b,s,**k)
    def test_pair_rejects_early_stop_or_overlapping_sessions(self):
        p,s,k=self.pair_args()
        for index,change in ((0,dict(delivered_frames=31680)),(1,dict(source_origin_monotonic_sec=s[0]['completed_monotonic_sec']))):
            b=deepcopy(s);b[index].update(change)
            with self.assertRaises(ValueError):subject.join_pair(p,b,**k)
    def test_fixed_file_reader_dispatches_and_rechecks_all_bindings(self):
        with wired(self.folder/'case') as (app,payload,owner,args,mocks):
            result=subject.review_pair(app,payload=payload,application_owner=owner)
            self.assertEqual([m.call_count for m in mocks],[2,2,2]);self.assertEqual(len(result['sessions']),2)
            self.assertGreater(len(result['evidence']),30);self.assertFalse(result['process_transport_reviewed'])
            self.assertFalse(result['viewport_rows_reviewed']);self.assertFalse(result['N4_accepted'])
            freeze(self.folder/'SYNTHETIC_PAIR_REVIEW.json',result)
    def test_fixed_reader_rejects_alive_process_before_any_leaf_review(self):
        with wired(self.folder/'case') as (app,payload,owner,args,mocks),patch.object(subject,'exact_process',return_value=object()):
            with self.assertRaises(ValueError):subject.review_pair(app,payload=payload,application_owner=owner)
            self.assertEqual(sum(m.call_count for m in mocks),0)
    def test_fixed_reader_rejects_changed_file_and_duplicate_json(self):
        with wired(self.folder/'case') as (app,payload,owner,args,mocks):
            (app/'sessions/01/delivery/TRACE.bin').write_bytes(b'changed')
            with self.assertRaises(ValueError):subject.review_pair(app,payload=payload,application_owner=owner)
            (app/'RESULT.json').write_text('{"status":1,"status":2}')
            with self.assertRaisesRegex(ValueError,'Duplicate'):subject.review_pair(app,payload=payload,application_owner=owner)
    def test_leaf_failure_is_never_promoted_to_success(self):
        with wired(self.folder/'case') as (app,payload,owner,args,mocks):
            mocks[1].side_effect=ValueError('incomplete archive')
            with self.assertRaisesRegex(ValueError,'incomplete archive'):subject.review_pair(app,payload=payload,application_owner=owner)
            self.assertEqual(mocks[2].call_count,0)
    def test_parent_manifest_preserves_child_boundary(self):
        import restart_application_child as child
        parent=subject.code_bindings();runtime=child.code_bindings()
        self.assertEqual(len(runtime),122);self.assertGreater(len(parent),128)
        self.assertTrue(all(b in parent for b in runtime))
        self.assertNotIn(bind(subject.__file__),runtime)
