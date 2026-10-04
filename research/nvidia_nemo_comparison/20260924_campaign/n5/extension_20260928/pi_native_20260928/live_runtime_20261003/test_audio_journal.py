"""Direct-run checks; registers CPU14 ownership before project imports.

Run exactly as documented in README_AUDIO_JOURNAL.md. Do not use discovery.
"""
import os
import sys


def _register_owner():
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        process = kernel.GetCurrentProcess()
        if not kernel.SetProcessAffinityMask(process, 1 << 14):
            raise ctypes.WinError(ctypes.get_last_error())
        times = [ctypes.c_ulonglong() for _ in range(4)]
        kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
        if not kernel.GetProcessTimes(process, *(ctypes.byref(value) for value in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        creation_identity = dict(creation_filetime=times[0].value)
    else:
        os.sched_setaffinity(0, {14})
        creation_identity = dict(start_ticks=int(open('/proc/self/stat').read().rsplit(')', 1)[1].split()[19]))
    import json
    import uuid
    from datetime import datetime, timezone
    from pathlib import Path
    if len(sys.argv) != 3 or sys.argv[1] != '--output-root':
        raise SystemExit('Usage: python test_audio_journal.py --output-root PRIVATE_AUDIT_PREPARATION')
    root = Path(sys.argv[2]).absolute() / ('audio-journal-tests-' + uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(),
        purpose='BOUNDED_DISK_JOURNAL_TESTS', cpu=14, affinity_mask=1 << 14,
        registered_utc=datetime.now(timezone.utc).isoformat(), root=str(root), **creation_identity)
    with (root / 'REGISTERED_OWNER.json').open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    sys.dont_write_bytecode = True
    sys.argv = [sys.argv[0]]
    print('REGISTERED_OWNER:', root, flush=True)
    return root


if __name__ != '__main__':
    raise RuntimeError('Run this file directly so CPU14 ownership precedes project imports')

AUDIT_ROOT = _register_owner()

import json
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from audio_journal import AudioGap, DiskAudioJournal


class FileSpool:
    """Small filesystem fixture implementing the actual spool interface."""
    def __init__(self, root, duration=600, io_bytes=65536):
        self.root = root
        root.mkdir()
        self.data_path = root / 'processed.f32le'
        self.data_path.touch()
        self.spec = dict(duration_seconds=duration, sample_rate=16000)
        self.store = SimpleNamespace(policy=SimpleNamespace(max_append_bytes=io_bytes))
        self.processed_samples = 0
        self.partial_write = False
        self.observations = []
        self.faults = []

    def append_processed(self, start, data):
        if start != self.processed_samples:
            raise ValueError('Noncontiguous test source')
        with self.data_path.open('ab') as stream:
            if self.partial_write:
                stream.write(data[:len(data)//2])
                stream.flush()
                os.fsync(stream.fileno())
                raise OSError('Injected partial write')
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.processed_samples += len(data) // 4

    def read_processed(self, start, count):
        if start + count > self.processed_samples:
            raise ValueError('Read exceeds committed prefix')
        with self.data_path.open('rb') as stream:
            stream.seek(start * 4)
            return stream.read(count * 4)

    def fault_receipt(self, receipt):
        self.faults.append(receipt)
        with (self.root / 'FAULTS.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(receipt, sort_keys=True) + '\n')
            stream.flush()
            os.fsync(stream.fileno())


class AudioJournalTests(unittest.TestCase):
    def create(self, **kwargs):
        spool = FileSpool(AUDIT_ROOT / self._testMethodName, **kwargs)
        journal = DiskAudioJournal(spool, policy=spool.spec,
            fault_receipt=spool.fault_receipt,
            observer=lambda start, samples: spool.observations.append((start, len(samples))))
        return spool, journal

    def test_old_reads_after_nominal_ram_horizon(self):
        spool, journal = self.create()
        for index in range(20):
            journal.append(np.full(8000, index, dtype=np.float32))
        np.testing.assert_array_equal(journal.read(0, 8000), np.zeros(8000, dtype=np.float32))
        np.testing.assert_array_equal(journal.read(152000, 8000), np.full(8000, 19, dtype=np.float32))
        self.assertEqual(spool.observations, [(i * 8000, 8000) for i in range(20)])
        self.assertEqual(journal.snapshot()['audio_ram_cache_bytes'], 0)
        journal.finish()

    def test_partial_write_does_not_publish_cursor_or_observer(self):
        spool, journal = self.create()
        journal.append(np.arange(100, dtype=np.float32))
        spool.partial_write = True
        with self.assertRaisesRegex(OSError, 'partial write'):
            journal.append(np.ones(100, dtype=np.float32))
        self.assertEqual(journal.committed_samples, 100)
        self.assertEqual(spool.processed_samples, 100)
        self.assertEqual(spool.observations, [(0, 100)])
        self.assertTrue(journal.finished)
        self.assertEqual(spool.faults[0]['accepted_samples'], 0)
        np.testing.assert_array_equal(journal.read(0, 200), np.arange(100, dtype=np.float32))
        self.assertEqual(len(journal.read(100, 100)), 0)

    def test_concurrent_reader_receives_complete_prefix_then_eof(self):
        spool, journal = self.create()
        ready = threading.Event()
        result = []
        errors = []
        def consume():
            cursor = 0
            ready.set()
            try:
                while True:
                    block = journal.read(cursor, 63, wait_sec=0.1)
                    if len(block):
                        result.extend(block.tolist())
                        cursor += len(block)
                    elif journal.finished and cursor == journal.committed_samples:
                        break
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=consume)
        thread.start()
        self.assertTrue(ready.wait(1))
        for index in range(10):
            journal.append(np.arange(index * 100, (index + 1) * 100, dtype=np.float32))
        journal.finish()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(result, list(range(1000)))

    def test_stream_beyond_300_seconds_with_small_working_blocks(self):
        spool, journal = self.create(duration=301, io_bytes=65536)
        block = np.arange(8000, dtype=np.float32) / 8000
        for _ in range(602):
            journal.append(block)
        journal.finish()
        self.assertEqual(journal.committed_samples, 301 * 16000)
        self.assertEqual(journal.duration_sec, 301)
        self.assertEqual(spool.data_path.stat().st_size, 301 * 16000 * 4)
        np.testing.assert_array_equal(journal.read(0, 8000), block)
        np.testing.assert_array_equal(journal.read(601 * 8000, 8000), block)
        self.assertEqual(journal.snapshot()['audio_ram_cache_bytes'], 0)
        self.assertLessEqual(journal.max_read_samples * 4, 65536)

    def test_observer_fault_reports_already_accepted_samples_once(self):
        spool, journal = self.create()
        stops = []
        def fail(start, samples):
            spool.observations.append((start, len(samples)))
            raise ValueError('Injected observer failure')
        journal.observer = fail
        journal.request_stop = stops.append
        journal.append(np.zeros(100, dtype=np.float32))
        self.assertEqual(journal.committed_samples, 100)
        self.assertEqual(spool.observations, [(0, 100)])
        self.assertEqual(spool.faults[0]['accepted_samples'], 100)
        self.assertTrue(journal.finished)
        self.assertEqual(stops, ['AUDIO_JOURNAL_OBSERVER'])

    def test_nonfinite_input_and_policy_limit_fail_before_disk_acceptance(self):
        spool, journal = self.create(duration=1)
        with self.assertRaisesRegex(AudioGap, 'Nonfinite'):
            journal.append(np.array([np.nan], dtype=np.float32))
        self.assertEqual(journal.committed_samples, 0)
        self.assertEqual(spool.data_path.stat().st_size, 0)
        self.assertEqual(len(spool.faults), 1)

    def test_read_is_bounded_and_finish_wakes_waiter(self):
        spool, journal = self.create()
        done = threading.Event()
        result = []
        def wait():
            result.append(journal.read(0, 1, wait_sec=1))
            done.set()
        thread = threading.Thread(target=wait)
        thread.start()
        journal.finish()
        self.assertTrue(done.wait(0.5))
        thread.join(1)
        self.assertEqual(len(result[0]), 0)
        with self.assertRaises(ValueError):
            journal.read(0, 1, wait_sec=2)


result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AudioJournalTests))
summary = dict(schema='just-peachy.audio-journal-checks.v1', tests_run=result.testsRun,
    failures=len(result.failures), errors=len(result.errors), successful=result.wasSuccessful(),
    synthetic_duration_seconds=301, native_executed=False, model_executed=False)
with (AUDIT_ROOT / 'RESULT.json').open('x', encoding='utf-8') as stream:
    json.dump(summary, stream, sort_keys=True, indent=2)
with (AUDIT_ROOT / 'EXIT.json').open('x', encoding='utf-8') as stream:
    json.dump(dict(pid=os.getpid(), exit_code=0 if result.wasSuccessful() else 1,
        threads_joined=threading.active_count() == 1), stream, sort_keys=True)
sys.exit(0 if result.wasSuccessful() else 1)
