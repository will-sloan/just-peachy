"""Isolated exact-class regression checks, invoked by the guarded probe only."""
import ast
import math
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest

from common import bind, freeze
from source_delivery import CHUNK, FORMAT, MAX_FRAMES, RECORD, SourceDelivery, summarize

CONTEXT = {}


def classes(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
    if {n.name for n in nodes} != set(names):
        raise ValueError('Exact source class extraction failed')
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return [namespace[name] for name in names]


class Fixture:
    """RAM-only values, deterministic time and synchronous fake thread/soundfile.

    Production FileSource/MemoryJournal/AbsolutePacer class bodies are unchanged.
    No source file is opened as audio and no model/application modules are imported.
    """
    def __init__(self, frames=650, *, observer=True, stop_after=None, fail_archive=None):
        import numpy as np
        self.now = 100.; self.frames = frames; self.callbacks = []; self.archived = []; self.read_blocks = []
        self.archive_cost = .003; self.read_cost = .001; self.stop_after = stop_after
        self.values = np.full(frames, .25, dtype=np.float32)
        time_api = SimpleNamespace(perf_counter=lambda: self.now)
        fixture = self

        class Event:
            def __init__(self): self.flag = False
            def is_set(self): return self.flag
            def set(self): self.flag = True
            def wait(self, seconds): fixture.now += seconds + .002; return self.flag

        class Thread:
            def __init__(self, target, **kw): self.target = target; self.alive = False
            def start(self):
                self.alive = True
                try: self.target()
                finally: self.alive = False
            def is_alive(self): return self.alive
            def join(self, seconds):
                if self.alive: raise ValueError('Synchronous fixture is unexpectedly alive')

        class SoundFile:
            def __init__(self, path): self.cursor = 0
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def seek(self, start): self.cursor = start
            def read(self, count, dtype):
                if count != CHUNK or dtype != 'float32': raise ValueError('FileSource changed its read contract')
                fixture.now += fixture.read_cost
                block = fixture.values[self.cursor:self.cursor + count]; self.cursor += len(block)
                if len(block): fixture.read_blocks.append(block)
                return block

        root = CONTEXT['prototype']
        Pacer, = classes(root/'vendor/edge_speech_pipeline/research_s7.py', ['AbsolutePacer'], dict(math=math, time=time_api))
        Gap, Journal = classes(root/'app/buffers.py', ['AudioGap', 'MemoryJournal'],
                               dict(Path=Path, threading=threading, time=time_api, np=np))
        Source, = classes(root/'app/pipeline.py', ['FileSource'], dict(Path=Path, time=time_api, AbsolutePacer=Pacer,
            threading=SimpleNamespace(Event=Event, Thread=Thread, current_thread=threading.current_thread),
            sf=SimpleNamespace(SoundFile=SoundFile, info=lambda path: SimpleNamespace(samplerate=16000, channels=1, subtype='PCM_16', frames=frames))))
        self.types = (Source, Journal)

        def archive(start, block):
            self.archived.append((start, block))
            self.now += self.archive_cost
            if self.stop_after is not None and len(self.archived) >= self.stop_after:
                self.source.stop_event.set()
            if fail_archive is not None: raise fail_archive

        self.journal = Journal(observer=archive)
        self.path = CONTEXT['output']/'NO_AUDIO_FILE_RAM_FIXTURE.wav'
        self.source = Source(self.journal, self.path, lambda *a: self.callbacks.append(a))
        self.job = dict(job_id='ram_fixture', audio_path=str(self.path), audio_sha256='0'*64,
                        frames=frames, sample_rate_hz=16000, gain=1, reset_between_scenes=True, tap='O0')
        self.observe = self.attach() if observer else None

    def attach(self):
        return SourceDelivery(self.source, self.job, _types=self.types, _clock=lambda: self.now)

    def start_event(self):
        self.source.callback('source_started', dict(source_epoch_monotonic_sec=self.now, mode='file',
            path=str(self.path), start_sample=0, gain=1., pacing='absolute'))
        self.source.thread = SimpleNamespace(is_alive=lambda: False)


class DeliveryTests(unittest.TestCase):
    def setUp(self): CONTEXT['checkpoint']()
    def tearDown(self): CONTEXT['checkpoint']()

    def test_exact_source_pacer_and_journal_are_unchanged(self):
        import numpy as np
        plain = Fixture(observer=False); measured = Fixture()
        plain.source.start(); measured.source.start()
        report, raw = measured.observe.close()
        self.assertEqual(report['status'], 'OBSERVED_FULL_SOURCE_DELIVERY_REQUIRES_REVIEW')
        self.assertEqual(plain.callbacks, measured.callbacks)
        self.assertEqual(plain.source.sent, measured.source.sent)
        self.assertEqual(plain.now, measured.now)
        np.testing.assert_array_equal(plain.journal.read(0, 650), measured.journal.read(0, 650))
        self.assertEqual(report['summary']['records'], 3)
        self.assertEqual([r[1] for r in RECORD.iter_unpack(raw)], [320, 320, 10])
        self.assertAlmostEqual(report['summary']['append_entry_lateness_ms']['minimum'], 2.)
        self.assertAlmostEqual(report['summary']['append_return_lateness_ms']['maximum'], 8.375)
        self.assertTrue(report['test_seams_used'])
        self.assertFalse(report['timing_or_continuity_accepted'])
        self.assertNotIn('append', vars(measured.journal))
        target = CONTEXT['output']/'SYNTHETIC_DELIVERY.bin'; target.write_bytes(raw)
        freeze(CONTEXT['output']/'SYNTHETIC_DELIVERY.json', dict(observation=report, trace=bind(target),
            scope='RAM fixture with isolated exact class bodies; no actual application or audio file'))

    def test_same_arrays_and_archive_hook_preserved(self):
        f = Fixture(); archive = f.journal.observer; f.source.start(); f.observe.close()
        self.assertIs(f.journal.observer, archive)
        self.assertEqual(len(f.archived), 3)
        # np.asarray(...).reshape(-1) may return a view; memory and values must match.
        import numpy as np
        for (_, archived), read in zip(f.archived, f.read_blocks):
            self.assertTrue(np.shares_memory(archived, read)); np.testing.assert_array_equal(archived, read)

    def test_partial_stop_is_explicit(self):
        f = Fixture(stop_after=1); f.source.start(); report, raw = f.observe.close()
        self.assertEqual(report['status'], 'OBSERVED_PARTIAL_SOURCE_DELIVERY_REQUIRES_REVIEW')
        self.assertEqual(report['source_sent'], 320); self.assertTrue(report['source_stop_requested'])
        self.assertEqual(report['summary']['records'], 1)
        self.assertFalse(report['source_stop_requested_by_observer'])

    def test_fresh_observers_do_not_share_session_state(self):
        first = Fixture(stop_after=1); first.source.start(); a, _ = first.observe.close()
        with self.assertRaises(ValueError): first.attach()
        second = Fixture(); second.now = 200.; second.source.start(); b, _ = second.observe.close()
        self.assertEqual(a['source_sent'], 320); self.assertEqual(b['source_sent'], 650)
        self.assertEqual(b['source_origin_perf_counter'], 200.)
        self.assertFalse(b['source_stop_requested'])

    def test_reject_wrong_job_and_nonfresh_source(self):
        changes = [('gain', 2), ('frames', MAX_FRAMES+1), ('audio_path', 'G:/wrong.wav')]
        for key, value in changes:
            f = Fixture(observer=False); f.job[key] = value
            with self.assertRaises(ValueError): f.attach()
        for key, value in [('sent', 1), ('start_sample', 1), ('thread', object())]:
            f = Fixture(observer=False); setattr(f.source, key, value)
            with self.assertRaises(ValueError): f.attach()
        f = Fixture(observer=False); f.journal.finish()
        with self.assertRaises(ValueError): f.attach()
        f = Fixture(observer=False)
        with self.assertRaises(ValueError): SourceDelivery(f.source, f.job, _types=(object, f.types[1]))

    def test_double_install_and_existing_append_refused(self):
        f = Fixture()
        with self.assertRaises(ValueError): f.attach()
        other = Fixture(observer=False); original = other.journal.append; other.journal.append = original
        with self.assertRaises(ValueError): other.attach()
        self.assertIs(other.journal.append, original)

    def test_live_source_cannot_be_detached(self):
        f = Fixture(); f.start_event(); f.source.thread = SimpleNamespace(is_alive=lambda: True)
        with self.assertRaises(ValueError): f.observe.close()
        self.assertIs(f.source.callback, f.observe.callback_hook)
        self.assertIs(f.journal.append, f.observe.append_hook)
        self.assertFalse(f.observe.closed)

    def test_foreign_hooks_are_not_overwritten(self):
        f = Fixture(); f.source.start(); foreign = lambda *a: None
        f.source.callback = foreign; f.journal.append = foreign
        report, _ = f.observe.close()
        self.assertEqual(report['status'], 'FAILED_SOURCE_DELIVERY_OBSERVATION')
        self.assertIs(f.source.callback, foreign); self.assertIs(f.journal.append, foreign)
        self.assertEqual(report['errors']['foreign_hook_at_closure'], 2)

    def test_original_callback_exception_is_same_object(self):
        f = Fixture(observer=False); error = RuntimeError('fixture original callback failure')
        def fail(*a): raise error
        f.source.callback = fail; f.observe = f.attach()
        with self.assertRaises(RuntimeError) as captured: f.start_event()
        self.assertIs(captured.exception, error)
        report, _ = f.observe.close()
        self.assertEqual(report['errors']['original_callback_raised'], 1)
        self.assertEqual(report['status'], 'FAILED_SOURCE_DELIVERY_OBSERVATION')

    def test_append_exception_after_commit_preserved(self):
        error = RuntimeError('fixture archive failure'); f = Fixture(fail_archive=error); f.start_event()
        with self.assertRaises(RuntimeError) as captured: f.journal.append(f.values[:320])
        self.assertIs(captured.exception, error); f.journal.finish('fixture failure')
        report, raw = f.observe.close(); row, = RECORD.iter_unpack(raw)
        self.assertEqual(row[2], 320); self.assertEqual(row[-1], 1)
        self.assertEqual(report['summary']['failed_appends'], 1)
        self.assertEqual(report['source_sent'], 0); self.assertEqual(report['journal_committed'], 320)
        self.assertEqual(report['status'], 'FAILED_SOURCE_DELIVERY_OBSERVATION')

    def test_source_fatal_and_duplicate_start_never_pass(self):
        for payload in ({}, dict(source_epoch_monotonic_sec=float('nan'))):
            f = Fixture(); f.source.callback('source_started', payload)
            self.assertIs(f.callbacks[0][1], payload)
            f.source.start(); report, _ = f.observe.close()
            self.assertEqual(report['status'], 'FAILED_SOURCE_DELIVERY_OBSERVATION')
            self.assertEqual(f.source.sent, 650)
        f = Fixture(fail_archive=RuntimeError('fixture failure')); f.source.start(); report, _ = f.observe.close()
        self.assertTrue(report['source_fatal_seen']); self.assertEqual(f.callbacks[-1][0], 'fatal')

    def test_invalid_observer_clock_does_not_drop_block(self):
        f = Fixture(); f.start_event(); f.observe.clock = lambda: float('nan')
        f.journal.append(f.values[:320]); f.source.sent = 320; f.journal.finish()
        report, raw = f.observe.close()
        self.assertEqual(f.journal.committed_samples, 320); self.assertEqual(len(f.archived), 1)
        self.assertEqual(report['status'], 'FAILED_SOURCE_DELIVERY_OBSERVATION'); self.assertEqual(len(raw), 0)

    def test_trace_tamper_and_missing_records_rejected(self):
        f = Fixture(); f.source.start(); report, raw = f.observe.close()
        kw = dict(origin=100., frames=650, sent=650, committed=650)
        for value in (raw[:-1], raw[:RECORD.size], raw+raw, raw[RECORD.size:]):
            with self.assertRaises(ValueError): summarize(value, **kw)
        row = list(RECORD.unpack(raw[:RECORD.size])); row[0] = 1
        with self.assertRaises(ValueError): summarize(RECORD.pack(*row)+raw[RECORD.size:], **kw)
        row[0] = 0; row[4] = float('inf')
        with self.assertRaises(ValueError): summarize(RECORD.pack(*row)+raw[RECORD.size:], **kw)

    def test_signed_delay_and_nearest_rank_are_not_clamped(self):
        raw = RECORD.pack(0,320,320,100.010,100.011,0)+RECORD.pack(320,320,640,100.070,100.075,0)
        result = summarize(raw, origin=100., frames=640, sent=640, committed=640)
        self.assertAlmostEqual(result['append_entry_lateness_ms']['p50'], -10.)
        self.assertAlmostEqual(result['append_entry_lateness_ms']['p95'], 30.)
        self.assertEqual(result['early_entry_count'], 1); self.assertEqual(result['entry_over_20ms'], 1)
        self.assertAlmostEqual(result['append_call_total_ms'], 6.)

    def test_one_hour_binary_budget_and_empty_partial(self):
        raw = b''.join(RECORD.pack(start,320,start+320,100.+(start+320)/16000.,100.+(start+320)/16000.,0)
                       for start in range(0, MAX_FRAMES, 320))
        result = summarize(raw, origin=100., frames=MAX_FRAMES, sent=MAX_FRAMES, committed=MAX_FRAMES)
        self.assertTrue(result['complete_source']); self.assertEqual(result['records'], 180000)
        self.assertEqual(len(raw), 5220000); self.assertLess(len(raw)+2*1024**2, 8*1024**2)
        empty = summarize(b'', origin=100., frames=650, sent=0, committed=0)
        self.assertIsNone(empty['append_entry_lateness_ms']['p95']); self.assertFalse(empty['complete_source'])
        freeze(CONTEXT['output']/'TRACE_BUDGET.json', dict(records=result['records'], binary_bytes=len(raw),
            metadata_reserve_bytes=2*1024**2, total_allowance_bytes=8*1024**2, format=FORMAT,
            scope='One-hour record sizing fixture only; no one-hour source run'))

    def test_bound_exhaustion_preserves_forwarding_and_failure(self):
        f = Fixture(observer=False); f.job['frames'] = 320; f.observe = f.attach(); f.source.start()
        report, raw = f.observe.close()
        self.assertEqual(f.source.sent, 650); self.assertLessEqual(len(raw), RECORD.size)
        self.assertEqual(report['status'], 'FAILED_SOURCE_DELIVERY_OBSERVATION')
        self.assertEqual(report['append_attempts'], 3)

    def test_wrong_producer_invalidates_without_dropping(self):
        f = Fixture(); f.start_event()
        worker = threading.Thread(target=lambda: f.journal.append(f.values[:320])); worker.start(); worker.join(5)
        self.assertFalse(worker.is_alive()); f.source.sent = 320; f.journal.finish()
        report, raw = f.observe.close()
        self.assertEqual(f.journal.committed_samples, 320); self.assertEqual(len(raw), 0)
        self.assertEqual(report['status'], 'FAILED_SOURCE_DELIVERY_OBSERVATION')

    def test_never_started_and_second_close_refused(self):
        f = Fixture(); report, _ = f.observe.close()
        self.assertEqual(report['status'], 'FAILED_SOURCE_DELIVERY_OBSERVATION')
        self.assertIn('missing_source_start_or_thread', report['errors'])
        with self.assertRaises(ValueError): f.observe.close()
