"""Model-free launch/join/cell wiring fixtures; not application qualification."""
from copy import deepcopy
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load
from application_delivery import SourceLaunchCapture, validate_delivery, review_files
from source_delivery import SourceDelivery
import paced_application_cell_v2 as cell_module
import test_source_delivery as source_tests

CONTEXT = {}


class Fixture:
    def __init__(self):
        self.f = source_tests.Fixture(observer=False)
        self.contract = dict(engine='PrototypeEngine', mode='open_with_names')
        self.c = SimpleNamespace(engine=None, worker=threading.current_thread(), saved_audio_only=True, closed=False,
            state='STOPPED', source_kind='file', file_offset=0, file_path=self.f.path, tap='O0', mode='open_with_names',
            collect_references=False, use_references=False, error=None)
        def status(engine, *a): self.f.callbacks.append(a)
        Engine = type('PrototypeEngine', (), {'_source_status': status})
        self.engine = Engine(); self.engine._source = self.f.source
        self.engine.enhancement_route = 'bypass'; self.engine.enhancement_router = None
        for key in ('_input_journal', '_journal', '_identity_journal'): setattr(self.engine, key, self.f.journal)
        self.f.source.callback = self.engine._source_status
        self.capture = SourceLaunchCapture(self.c, self.f.job, self.contract, CONTEXT['prototype'], _types=self.f.types,
            _observer_factory=lambda s,j: SourceDelivery(s,j,_types=self.f.types,_clock=lambda:self.f.now))

    def ready(self):
        self.capture.install(); self.c.engine = self.engine; self.c.state = 'STARTING'

    def stopped(self):
        self.c.closed = True; self.c.worker = SimpleNamespace(is_alive=lambda:False, join=lambda seconds:None)

    def finish(self, folder):
        self.stopped(); return load(self.capture.finish(folder, engine=self.engine)['path'])


def join_fixture(f, launch, value):
    """Explicit fabricated owner/consumer facts for the pure production validator.

    Fixture flags are normalized only in these copied test values, never in
    captured files. The probe labels the result as a synthetic branch check.
    """
    launch = deepcopy(launch); value = deepcopy(value)
    launch['test_seams_used'] = value['test_seams_used'] = False
    job = f.f.job; session = str(CONTEXT['output']/'SYNTHETIC_SESSION')
    payload = dict(path=job['audio_path'], session_id=Path(session).name, mode='file', pacing='absolute',
                   start_sample=0, gain=1., source_epoch_monotonic_sec=100.)
    clock = dict(publication_session=payload['session_id'], source_epoch_monotonic_sec=100.,
        source_started=dict(event_payload=payload, source_epoch_monotonic_sec=100.), errors=0,
        event_counts=dict(source_started=1), event_count=3, last_publication_sequence=3, missing_publication_sequences=0)
    observed = dict(job=deepcopy(job), engine_class='PrototypeEngine', session=session, controller_clock=clock,
        source_clock_owner_join=dict(same_engine=True, consumer_retained=True),
        publication_census=dict(consumed=3, published=3, coalesced_obsolete_ui_partials=0),
        source=dict(actual_FileSource=True, path=job['audio_path'], start_sample=0, sent=650,
            journal=dict(committed_samples=650), thread=dict(present=True, started=True, alive=False)))
    return [value, Path(launch['trace']['path']).read_bytes(), launch, observed, deepcopy(clock), job, f.contract]


class ApplicationDeliveryTests(unittest.TestCase):
    def setUp(self):
        CONTEXT['checkpoint'](); self.folder = CONTEXT['output']/self._testMethodName; self.folder.mkdir()
        self.fixtures = []

    def fixture(self):
        f = Fixture(); self.fixtures.append(f); return f

    def tearDown(self):
        for f in self.fixtures:
            f.capture.restore_start()
        CONTEXT['checkpoint']()

    def complete(self):
        f = self.fixture(); f.ready(); f.f.source.start(); launch = f.finish(self.folder/'delivery')
        return f, launch, load(launch['observation']['path'])

    def test_exact_start_owner_and_original_source_forwarding(self):
        f, launch, value = self.complete()
        self.assertEqual(launch['status'], 'COLLECTED_APPLICATION_DELIVERY_REQUIRES_REVIEW')
        self.assertTrue(all(launch['owner_join'].values())); self.assertTrue(launch['test_seams_used'])
        self.assertEqual(value['source_sent'], 650); self.assertEqual(len(f.f.callbacks), 1)
        self.assertIs(f.f.types[0].start, f.capture.original_start)
        self.assertTrue(launch['launch_hook_restored'])

    def test_wrong_controller_source_and_journal_rejected_before_start(self):
        mutations = [lambda f:setattr(f.c,'worker',object()), lambda f:setattr(f.c,'saved_audio_only',False),
            lambda f:setattr(f.c,'state','RUNNING'), lambda f:setattr(f.c,'file_path','G:/foreign.wav'),
            lambda f:setattr(f.c,'collect_references',True), lambda f:setattr(f.c,'tap','O1'),
            lambda f:setattr(f.engine,'_identity_journal',object()), lambda f:setattr(f.engine,'enhancement_route','other'),
            lambda f:setattr(f.f.source,'callback',lambda *a:None)]
        for index, mutate in enumerate(mutations):
            f = self.fixture(); f.ready(); mutate(f)
            with self.assertRaises(ValueError): f.f.source.start()
            self.assertIsNone(f.f.source.thread); self.assertEqual(f.f.source.sent, 0)
            self.assertEqual(f.finish(self.folder/str(index))['status'], 'FAILED_APPLICATION_DELIVERY_PRESERVED')

    def test_second_start_cannot_launch_another_source(self):
        f = self.fixture(); f.ready(); f.f.source.start()
        with self.assertRaises(ValueError): f.f.source.start()
        launch = f.finish(self.folder/'delivery')
        self.assertEqual(launch['launch_attempts'], 2)
        self.assertEqual(launch['status'], 'FAILED_APPLICATION_DELIVERY_PRESERVED')
        self.assertEqual(f.f.source.sent, 650)

    def test_original_start_exception_preserved(self):
        f = self.fixture(); error = RuntimeError('synthetic callback failure')
        def fail(engine, *a): raise error
        type(f.engine)._source_status = fail; f.f.source.callback = f.engine._source_status
        f.ready()
        with self.assertRaises(RuntimeError) as captured: f.f.source.start()
        self.assertIs(captured.exception, error)
        launch = f.finish(self.folder/'delivery')
        self.assertTrue(launch['original_start_raised']); self.assertEqual(launch['status'], 'FAILED_APPLICATION_DELIVERY_PRESERVED')

    def test_foreign_launch_hook_is_preserved(self):
        f = self.fixture(); f.ready(); f.f.source.start(); foreign = lambda source:None
        f.f.types[0].start = foreign; f.capture.restore_start()
        launch = f.finish(self.folder/'delivery')
        self.assertIs(f.f.types[0].start, foreign)
        self.assertIn('foreign_start_hook_preserved', launch['errors'])

    def test_prestart_closure_and_active_controller_install_refusal(self):
        f = self.fixture(); f.stopped(); launch = load(f.capture.finish(self.folder/'prepared',engine=None)['path'])
        self.assertEqual(launch['status'], 'PREPARED_WITHOUT_SOURCE_DELIVERY'); self.assertIsNone(launch['observation'])
        self.assertFalse(launch['installed']); self.assertEqual(launch['launch_attempts'], 0)
        other = self.fixture(); other.c.engine = other.engine
        with self.assertRaises(ValueError): other.capture.install()
        other.c.engine = None; other.capture.install()
        with self.assertRaises(ValueError): other.capture.install()

    def test_partial_capture_is_preserved_and_not_collected(self):
        f = self.fixture(); f.f.stop_after = 1; f.ready(); f.f.source.start()
        launch = f.finish(self.folder/'delivery'); value = load(launch['observation']['path'])
        self.assertEqual(launch['status'], 'FAILED_APPLICATION_DELIVERY_PRESERVED')
        self.assertEqual(value['status'], 'OBSERVED_PARTIAL_SOURCE_DELIVERY_REQUIRES_REVIEW')
        self.assertEqual(value['source_sent'], 320)

    def test_independent_join_has_explicit_scope(self):
        f, launch, value = self.complete(); args = join_fixture(f,launch,value); result = validate_delivery(*args)
        self.assertEqual(result['status'], 'PASS_APPLICATION_DELIVERY_SOURCE_CLOCK_JOIN_ONLY')
        self.assertEqual(result['source_samples'], 650); self.assertEqual(result['summary']['records'], 3)
        self.assertTrue(result['engine_archive_closure_must_pass_separately'])
        self.assertFalse(result['source_to_widget_latency_qualified']); self.assertFalse(result['deadline_or_continuity_accepted'])
        freeze(CONTEXT['output']/'SYNTHETIC_JOIN.json',dict(scope='Pure validator branch with fabricated owner/consumer facts and normalized copied fixture flags; no actual application',result=result))

    def test_real_fixture_flags_cannot_pass_production_join(self):
        f, launch, value = self.complete(); args = join_fixture(f,launch,value)
        args[0] = value
        with self.assertRaises(ValueError): validate_delivery(*args)
        args = join_fixture(f,launch,value); args[2] = launch
        with self.assertRaises(ValueError): validate_delivery(*args)

    def test_join_rejects_wrong_origin_session_counters_and_owner(self):
        f, launch, value = self.complete()
        mutations = [lambda a:a[0].update(source_origin_perf_counter=101.),
            lambda a:a[4].update(event_count=4), lambda a:a[3]['controller_clock'].update(publication_session='foreign'),
            lambda a:a[3].update(engine_class='N2Engine'), lambda a:a[3]['source'].update(sent=649),
            lambda a:a[3]['source']['thread'].update(alive=True), lambda a:a[2]['owner_join'].update(same_source=False),
            lambda a:a[2].update(contract_fingerprint='foreign'), lambda a:a[0].update(source_pacer_changed=True),
            lambda a:a[0]['summary'].update(records=2), lambda a:a[0].update(trace_bytes=1)]
        for change in mutations:
            args = deepcopy(join_fixture(f,launch,value)); change(args)
            with self.assertRaises(ValueError): validate_delivery(*args)

    def test_file_review_rejects_foreign_trace_and_source_bindings(self):
        f, launch, value = self.complete()
        # Production check reaches source binding rejection before parsing synthetic owner facts.
        with self.assertRaisesRegex(ValueError,'caller-bound'):
            review_files(self.folder,f.f.job,f.contract,[])
        altered = deepcopy(launch); altered['trace'] = launch['observation']
        other = self.folder/'foreign'; freeze(other/'delivery/CAPTURE.json',altered)
        freeze(other/'delivery/OBSERVATION.json',value); (other/'delivery/TRACE.bin').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'outside'):
            review_files(other,f.f.job,f.contract,f.capture.source_files)

    def test_positive_file_loader_is_only_a_synthetic_join_fixture(self):
        f, launch, value = self.complete(); args = join_fixture(f,launch,value)
        value, raw, launch, observed, clock, job, contract = args
        app = self.folder/'fabricated-join'; freeze(app/'delivery/OBSERVATION.json',value)
        (app/'delivery/TRACE.bin').write_bytes(raw)
        launch['observation'] = bind(app/'delivery/OBSERVATION.json'); launch['trace'] = bind(app/'delivery/TRACE.bin')
        freeze(app/'delivery/CAPTURE.json',launch); freeze(app/'ENGINE_CLOSURE.json',observed); freeze(app/'SOURCE_CLOCK.json',clock)
        result = review_files(app,job,contract,f.capture.source_files)
        self.assertEqual(result['status'],'PASS_APPLICATION_DELIVERY_SOURCE_CLOCK_JOIN_ONLY')
        self.assertEqual(len(result['evidence']),7); self.assertFalse(result['deadline_or_continuity_accepted'])
        freeze(CONTEXT['output']/'SYNTHETIC_FILE_JOIN.json',dict(scope='Synthetic production-reader branch only; copied test flags normalized, owner/consumer facts fabricated',result=result))

    def test_oversize_capture_rejected_before_hash_or_json_load(self):
        app = self.folder/'oversize'; (app/'delivery').mkdir(parents=True)
        (app/'delivery/CAPTURE.json').write_bytes(b' '*(128*1024+1))
        with patch('application_delivery.bind',side_effect=AssertionError('Must bound before hash')):
            with self.assertRaisesRegex(ValueError,'file bound'):review_files(app,{}, {}, [])

    def wired_cell(self):
        f = self.fixture(); events = []; out = self.folder/'application'; out.mkdir()
        engine = f.engine; engine.session_dir = out/'synthetic-session'; engine.session_dir.mkdir()
        c = f.c; c.commands = SimpleNamespace(unfinished_tasks=0); c.consumer = None
        def start(path):
            events.append('controller_start'); self.assertTrue(f.capture.installed)
            c.engine = engine; c.state = 'STARTING'; f.f.source.start(); c.state = 'STOPPED'
            c.consumer = SimpleNamespace(is_alive=lambda:False)
        def close(): events.append('controller_close'); f.stopped(); c.engine = None
        c.start_file = start; c.close = close; c.snapshot = lambda:{'synthetic':True}
        resources = SimpleNamespace(phase='gallery_ready', error=None)
        def mark(phase): resources.phase = phase; events.append(phase)
        def close_resources():
            self.assertTrue((out/'delivery/CAPTURE.json').is_file()); events.append('resources_close')
            value=dict(status='OBSERVED_HOST_RESOURCES',error=None,synthetic_only=True)
            freeze(out/'resources/RESULT.json',value); return value
        resources.mark = mark; resources.close = close_resources
        cell = cell_module.ApplicationCell.__new__(cell_module.ApplicationCell)
        cell.output = out; cell.job = f.f.job; cell.contract = f.contract; cell.delivery = f.capture
        cell.c = c; cell.root = SimpleNamespace(update=lambda:None,destroy=lambda:events.append('root_destroy'))
        cell.ui = SimpleNamespace(poll=lambda:None); cell.clock = SimpleNamespace(snapshot=lambda:{'synthetic':True},detach=lambda:None)
        cell.viewport = SimpleNamespace(check=lambda:None,close=lambda:{'failure':None})
        cell.engine = cell.consumer = None; cell.resources = resources; cell.errors = []
        cell.started = cell.closed = cell.run_completed = False; cell.run_error = None; cell.result = None; cell.began = 0.
        tick = {'value':0.}
        def now(): tick['value'] += .5; return tick['value']
        fake_time = SimpleNamespace(perf_counter=now,sleep=lambda _:None)
        return f,cell,events,fake_time

    def test_cell_installs_before_start_and_extracts_before_resource_close(self):
        f,cell,events,clock = self.wired_cell()
        with patch.object(cell_module,'time',clock):
            cell.run_source(admission_check=lambda *a:events.append('admit'))
        self.assertFalse(f.capture.installed); self.assertTrue(f.capture.restored)
        with patch('application_closure_v2.capture_engine',return_value={'synthetic':True}),\
             patch('application_closure_v2.capture_archive',return_value={'synthetic':True}),\
             patch('application_closure_v2.validate_complete',return_value={'synthetic':True}),\
             patch.object(cell_module,'review_files',side_effect=lambda *a:events.append('delivery_review') or {'synthetic':True}):
            result = cell.close()
        self.assertEqual(result['status'],'CELL_WITH_SOURCE_DELIVERY_CLOSED_REQUIRES_REVIEW')
        self.assertLess(events.index('admit'),events.index('controller_start'))
        self.assertLess(events.index('controller_close'),events.index('delivery_review'))
        self.assertLess(events.index('delivery_review'),events.index('resources_close'))
        self.assertFalse(result['complete_N4_acceptance']); self.assertIs(cell.close(),result)
        freeze(CONTEXT['output']/'SYNTHETIC_CELL_WIRING.json',dict(scope='Actual new cell methods with mocked Controller/UI/closure/gate; no actual GUI or inference',events=events,result=bind(cell.output/'RESULT.json')))

    def test_cell_cannot_succeed_when_delivery_review_fails(self):
        f,cell,events,clock = self.wired_cell()
        with patch.object(cell_module,'time',clock): cell.run_source(admission_check=lambda *a:None)
        with patch('application_closure_v2.capture_engine',return_value={'synthetic':True}),\
             patch('application_closure_v2.capture_archive',return_value={'synthetic':True}),\
             patch('application_closure_v2.validate_complete',return_value={'synthetic':True}),\
             patch.object(cell_module,'review_files',side_effect=ValueError('synthetic mismatch')):
            result = cell.close()
        self.assertEqual(result['status'],'FAILED_PRESERVED')
        self.assertTrue(any('Source delivery' in e for e in result['errors']))
        self.assertIsNotNone(result['delivery_capture']); self.assertIsNone(result['delivery_join'])
        self.assertIn('resources_close',events)

    def test_admission_failure_does_not_install_or_start(self):
        f,cell,events,clock = self.wired_cell()
        def denied(*args): raise ValueError('synthetic admission refusal')
        with self.assertRaises(ValueError): cell.run_source(admission_check=denied)
        self.assertFalse(cell.started); self.assertFalse(f.capture.ever_installed)
        self.assertIsNone(f.f.source.thread); self.assertNotIn('controller_start',events)
