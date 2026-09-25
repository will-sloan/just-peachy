"""Model-free qualification, including actual Controller consumption. See README_PACED_ADAPTERS_V3.md."""
from copy import deepcopy
from pathlib import Path
import queue
import threading
import time
from types import SimpleNamespace
import unittest

from common import bind, load, verify
from paced_adapters_v3 import ConsumerSourceClock, PacedResearchPeople

HERE = Path(__file__).resolve().parent
CONTEXT = {}


class PacedAdapterTests(unittest.TestCase):
    def job(self):
        return dict(job_id='fixture', audio_path=str(HERE/'fixture-not-opened.wav'), audio_sha256='0'*64,
            frames=16000, sample_rate_hz=16000, gain=1, reset_between_scenes=True, tap='O0')

    def controller(self):
        calls = []
        c = SimpleNamespace(engine=None, consumer=None, epoch=1, source_kind='file', saved_audio_only=True,
            collect_references=False, use_references=False, settings={},
            _adaptation_event=lambda e, v: calls.append((e, v)))
        return c, calls

    def event(self, job, **updates):
        from edge_speech_pipeline.contracts import PipelineEvent
        payload = dict(source_epoch_monotonic_sec=time.perf_counter()-.25, mode='file', path=job['audio_path'],
            start_sample=0, gain=1., pacing='absolute', publication_sequence=1,
            publication_monotonic_sec=time.perf_counter(), publication_source_cursor_sec=0., session_id='fixture-session')
        payload.update(updates)
        payload.update(consumer_monotonic_sec=time.perf_counter(), consumer_queue_age_sec=0.)
        return PipelineEvent('source_started', 0., payload)

    def test_clock_preserves_payload_origin_order_and_delegate(self):
        c, calls = self.controller(); j = self.job(); observer = ConsumerSourceClock(j).install(c)
        engine = c.engine = object(); event = self.event(j); original = deepcopy(event.payload)
        c._adaptation_event(engine, event)
        result = observer.snapshot()
        self.assertEqual(event.payload, original)
        self.assertIs(calls[0][1], event)
        self.assertEqual(result['source_epoch_monotonic_sec'], original['source_epoch_monotonic_sec'])
        self.assertGreater(result['source_started']['consumer_receipt_delay_sec'], .2)
        self.assertFalse(result['source_to_widget_latency_qualified'])
        observer.detach(); self.assertIs(c._adaptation_event, observer.original)

    def test_invalid_source_metadata_never_becomes_a_clock(self):
        for bad in (dict(source_epoch_monotonic_sec=float('nan')), dict(source_epoch_monotonic_sec=True),
                    dict(source_epoch_monotonic_sec=time.perf_counter()+100), dict(pacing='modeled'),
                    dict(path=str(HERE/'foreign.wav')), dict(start_sample=1), dict(gain=2.), dict(extra=True)):
            with self.subTest(bad=bad):
                c, calls = self.controller(); observer = ConsumerSourceClock(self.job()).install(c); c.engine = object()
                c._adaptation_event(c.engine, self.event(self.job(), **bad))
                self.assertFalse(observer.snapshot()['source_event_clock_available'])
                self.assertEqual(len(calls), 1); observer.detach()

    def test_duplicate_epoch_change_and_bounded_errors(self):
        c, calls = self.controller(); o = ConsumerSourceClock(self.job()).install(c); c.engine = object()
        e = self.event(self.job()); c._adaptation_event(c.engine, e)
        e.payload['publication_sequence']=2; c._adaptation_event(c.engine, e)
        self.assertFalse(o.snapshot()['source_event_clock_available'])
        c.epoch += 1
        for _ in range(100): c._adaptation_event(c.engine, e)
        result = o.snapshot(); self.assertEqual(len(result['violations']), 32)
        self.assertTrue(result['violations_truncated']); self.assertEqual(len(calls), 102); o.detach()

    def test_delegate_exception_and_hook_ownership_preserved(self):
        c, _ = self.controller()
        def fail(*args): raise RuntimeError('original hook error')
        c._adaptation_event = fail; o = ConsumerSourceClock(self.job()).install(c); c.engine = object()
        with self.assertRaisesRegex(RuntimeError, 'original hook error'):
            c._adaptation_event(c.engine, self.event(self.job()))
        wrapped = c._adaptation_event; c._adaptation_event = lambda *a: None
        with self.assertRaisesRegex(ValueError, 'ownership'): o.detach()
        c._adaptation_event = wrapped; o.detach(); self.assertIs(c._adaptation_event, fail)

    def test_active_or_duplicate_observer_rejected(self):
        c, _ = self.controller(); c.engine = object()
        with self.assertRaises(ValueError): ConsumerSourceClock(self.job()).install(c)
        c.engine = None; o = ConsumerSourceClock(self.job()).install(c)
        with self.assertRaises(ValueError): ConsumerSourceClock(self.job()).install(c)
        c.consumer = SimpleNamespace(is_alive=lambda: True)
        with self.assertRaises(ValueError): o.detach()
        c.consumer = None; o.detach()

    def test_actual_inbox_coalescence_is_accounted_without_retiming_source(self):
        from edge_speech_pipeline.research_s6d import EventInbox
        from edge_speech_pipeline.contracts import PipelineEvent
        c, calls = self.controller(); o = ConsumerSourceClock(self.job()).install(c)
        engine = c.engine = SimpleNamespace(events=EventInbox(16), _s6d_event_serial=3, session_dir=Path('fixture-session'))
        source = self.event(self.job()); engine.events.put(source)
        for seq in (2,3):
            payload = deepcopy(source.payload); payload.update(publication_sequence=seq, utterance_id='u', text=str(seq))
            engine.events.put(PipelineEvent('transcript_partial', 0., payload))
        while not engine.events.empty(): c._adaptation_event(engine, engine.events.get(block=False))
        result = o.reconcile_inbox()
        self.assertEqual(result['published'], 3); self.assertEqual(result['consumed'], 2)
        self.assertEqual(result['coalesced_obsolete_ui_partials'], 1)
        self.assertEqual(o.snapshot()['source_epoch_monotonic_sec'], source.payload['source_epoch_monotonic_sec'])
        self.assertEqual(len(calls), 2); o.detach()

    def test_unaccounted_publication_gap_is_rejected_at_closure(self):
        from edge_speech_pipeline.research_s6d import EventInbox
        c, _ = self.controller(); o = ConsumerSourceClock(self.job()).install(c)
        engine = c.engine = SimpleNamespace(events=EventInbox(16), _s6d_event_serial=2, session_dir=Path('fixture-session'))
        event = self.event(self.job()); event.payload['publication_sequence'] = 2; engine.events.put(event)
        c._adaptation_event(engine, engine.events.get(block=False))
        with self.assertRaisesRegex(ValueError, 'counts disagree'): o.reconcile_inbox()
        self.assertFalse(o.snapshot()['source_event_clock_available']); o.detach()

    def test_all_saved_catalog_galleries_preserve_scores_and_routes(self):
        import numpy as np
        from mode_galleries import backend_contract, CONDITIONS, load_prepared_gallery
        from paced_adapters_v3 import CountedBaselineGallery
        checked = []
        for row in CONTEXT['catalog']['backends']:
            if not row['implemented']: continue
            for mode in CONDITIONS:
                contract = backend_contract(CONTEXT['catalog'], row['key'], mode)
                for tap in ('O0', 'O1'):
                    store = PacedResearchPeople(CONTEXT['preparation'], contract, CONTEXT['output']/'unused-roster', tap)
                    raw, condition = load_prepared_gallery(CONTEXT['preparation'], contract)
                    self.assertEqual(store.condition, condition)
                    self.assertFalse(store.root.exists())
                    if raw is None:
                        self.assertEqual(store.list(), [])
                        with self.assertRaises(ValueError): store.gallery(store.expected_route())
                    else:
                        selected = list(raw.ids) if mode in ('selected_focus', 'selected_closed') else None
                        g = store.gallery(store.expected_route(), selected)
                        if isinstance(g, CountedBaselineGallery): self.assertIs(g.matrix, g._gallery.matrix)
                        before = g.matrix.tobytes()
                        vectors = [raw.matrix[0].copy(), -raw.matrix[-1].copy()]
                        for vector in vectors: self.assertEqual(g.score(vector), raw.score(vector))
                        zero = np.zeros(raw.matrix.shape[1], dtype=np.float32)
                        if contract['uses_n2']:
                            with self.assertRaises(ValueError): g.score(zero)
                            with self.assertRaises(ValueError): raw.score(zero)
                        else:
                            self.assertEqual(g.score(zero), raw.score(zero))
                        self.assertEqual(g.query_count, 3); self.assertEqual(g.matrix.tobytes(), before)
                        self.assertIsNone(g.adaptation)
                        changed = store.expected_route(); changed['tap'] = 'O1' if tap == 'O0' else 'O0'
                        with self.assertRaises(ValueError): store.gallery(changed, selected)
                        with self.assertRaises(ValueError): store.gallery(store.expected_route(), selected, alternate_advisory=True)
                        with self.assertRaises(ValueError): store.gallery(store.expected_route(), ['foreign'])
                        if selected:
                            with self.assertRaises(ValueError): store.gallery(store.expected_route(), selected+[selected[0]])
                        copied = store.list(); copied[0]['name'] = 'changed copy'; self.assertNotEqual(copied, store.list())
                    checked.append(dict(backend=row['key'], mode=mode, tap=tap, profiles=condition['available_size']))
        self.assertEqual(len(checked), 160); CONTEXT['gallery_checks'] = checked

    def test_actual_controller_consumes_source_event_for_all_three_engine_classes(self):
        import shutil
        from app.controller import Controller
        from app.backends import backend_catalog
        from app.pipeline import PrototypeEngine, effective_profile
        from app.n2_pipeline import N2Engine
        from app.n3_pipeline import N3IdentityEngine
        from controller_projection import drain_commands
        from mode_galleries import backend_contract
        checked = []
        for kind, cls in [('PrototypeEngine', PrototypeEngine), ('N2Engine', N2Engine), ('N3IdentityEngine', N3IdentityEngine)]:
            row = next(r for r in CONTEXT['catalog']['backends'] if r['implemented'] and
                backend_contract(CONTEXT['catalog'], r['key'], 'open_with_names')['engine'] == kind)
            contract = backend_contract(CONTEXT['catalog'], row['key'], 'open_with_names')
            root = CONTEXT['output']/kind; root.mkdir()
            for b in CONTEXT['runtimes']:
                verify(b); shutil.copyfile(b['path'], root/Path(b['path']).name)
            c = Controller(root, root/'NO_MODEL_PAYLOAD', saved_audio_only=True); o = None
            try:
                entry = next(r for r in backend_catalog() if r['key'] == row['key'])
                c.select_backend(entry['id']); drain_commands(c)
                c.store = PacedResearchPeople(CONTEXT['preparation'], contract, root/'unused-roster', 'O0')
                c.switch(mode='open_with_names', recipe='balanced', tap='O0', selected_ids=[], strict=False); drain_commands(c)
                self.assertEqual(c.route(), c.store.expected_route())
                gallery = c.store.gallery(c.route()); c._adaptation_start(gallery)
                self.assertFalse(c.collect_references); self.assertFalse(c.use_references)
                gallery.score(gallery.matrix[0].copy())
                o = ConsumerSourceClock(self.job()).install(c)
                kwargs = dict(diarization=contract['diarization']) if contract['uses_n2'] else {}
                engine = cls(c.config, c.models, effective_profile('balanced', 'open_with_names', 'O0'), gallery, 'open_with_names', **kwargs)
                engine._session_dir = root/'fixture-session'; engine._session_dir.mkdir(); engine._state = 'COMPLETED'
                engine._finalization_thread = threading.Thread(target=lambda: None)
                engine._finalization_thread.start(); engine._finalization_thread.join()
                c.engine = engine; c.source_kind = 'file'; c.state = 'RUNNING'
                from edge_speech_pipeline.research_s6d import EventInbox
                engine.events = EventInbox(4096)
                e = self.event(self.job())
                source_payload = {k:v for k,v in e.payload.items() if not k.startswith(('publication_', 'consumer_')) and k!='session_id'}
                engine._emit('source_started', 0., source_payload)
                c.consumer = threading.Thread(target=c._consume, args=(engine, c.epoch)); c.consumer.start(); c.consumer.join(10.)
                self.assertFalse(c.consumer.is_alive()); self.assertFalse(c.error)
                self.assertEqual(c.metrics['gallery_queries'], 1)
                self.assertEqual(c.metrics['events_consumed'], 1)
                self.assertEqual(c.metrics['completed_sessions'], 1)
                self.assertTrue(o.snapshot()['source_event_clock_available'])
                inbox_census = o.reconcile_inbox()
                self.assertEqual(o.snapshot()['source_epoch_monotonic_sec'], e.payload['source_epoch_monotonic_sec'])
                closure = bind(engine.session_dir/'s6d_consumer_closure.json')
                self.assertTrue(load(closure['path'])['full_event_consumer_drained'])
                checked.append(dict(engine=kind, closure=closure, clock=o.snapshot(), inbox_census=inbox_census, gallery_queries=1,
                    source_event_is_fixture=True, actual_source_execution=False, models_loaded=0))
            finally:
                if o is not None and o.installed: o.detach()
                c.close(); drain_commands(c); c.worker.join(10.)
                self.assertFalse(c.worker.is_alive()); self.assertTrue(c.closed)
                self.assertFalse(any(getattr(c.models, k, 0) for k in ('asr_loads', 'speaker_loads', 'streams')))
        CONTEXT['consumer_checks'] = checked
