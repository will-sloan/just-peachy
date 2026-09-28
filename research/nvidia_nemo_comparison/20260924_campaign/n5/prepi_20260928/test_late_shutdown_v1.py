"""Real Controller, injected delayed worker, no model/device. See README.md."""
import os
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import psutil
p = psutil.Process()
p.cpu_affinity([14])
if os.name == 'nt': p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get('PREPI_TEST_RELEASE', Path(__file__).resolve().parents[1]))
sys.path[:0] = [str(ROOT), str(ROOT/'vendor')]
from app.controller import Controller


class LateShutdownTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='prepi-shutdown-')
        self.root = Path(self.tmp.name)
        self.c = Controller(self.root/'data', self.root/'nonexistent-models', saved_audio_only=True)
        self.release = threading.Event()
        self.lane = threading.Thread(target=self.release.wait, name='injected-late-speaker', daemon=True)
        self.lane.start()
        done = threading.Thread(target=lambda:None)
        done.start(); done.join()
        def wait(timeout):
            raise RuntimeError('Preserved 60-second inference drain failure')
        self.engine = SimpleNamespace(stop=lambda:None, wait_for_completion=wait,
            _finalization_thread=done, _journal=None, _threads=[self.lane], text_writers=[],
            _source=SimpleNamespace(thread=None,sent=0,live=None), events=queue.Queue(), session_dir=None,
            _s6d_writer=None,_s6d_punctuation=None,_scheduler=None,_s7_trace=None,
            _state='FAILED', config=SimpleNamespace(input_gain=1.))
        self.c.engine = self.engine

    def tearDown(self):
        self.release.set(); self.lane.join(2)
        if not self.c.closed:
            self.c.close(); self.c.commands.join(); self.c.worker.join(3)
        self.tmp.cleanup()

    def test_close_waits_for_late_lane_without_accepting_failed_session(self):
        timer = threading.Timer(.15, self.release.set)
        timer.start()
        try:
            self.c._do_close()
            self.c.commands.join(); self.c.worker.join(2)
            self.assertTrue(self.c.closed)
            self.assertFalse(self.lane.is_alive())
            self.assertEqual(self.engine._state, 'FAILED')
            receipt=json.loads((self.root/'data/last_application.json').read_text())
            self.assertIn('inference drain failure', receipt['metrics']['last_terminal_failures'][0])
            self.assertFalse(receipt['metrics']['last_worker_cleanup']['inference_success_implied'])
        finally: timer.join()

    def test_stuck_lane_retains_owner_and_names_blocker(self):
        from app.session_shutdown_v1 import join_owned_workers
        with patch('app.session_shutdown_v1.join_owned_workers',
                   side_effect=lambda threads:join_owned_workers(threads, .02)):
            with self.assertRaisesRegex(RuntimeError, 'injected-late-speaker'):
                self.c._do_close()
        self.assertIs(self.c.engine, self.engine)
        self.assertFalse(self.c.closed)
        self.assertTrue((self.root/'data/runtime.lock').exists())
        self.assertIn('inference drain failure', self.c.metrics['last_terminal_failures'][0])
        self.release.set(); self.lane.join(2)
        self.c._do_close(); self.c.commands.join(); self.c.worker.join(2)
        self.assertTrue(self.c.closed)

    def test_multiple_workers_share_one_cleanup_budget(self):
        from app.session_shutdown_v1 import join_owned_workers
        other=threading.Thread(target=self.release.wait,name='second-stuck-lane',daemon=True)
        other.start()
        try:
            began=time.monotonic()
            receipt=join_owned_workers([self.lane,other,threading.current_thread(),self.lane], .08)
            self.assertLess(time.monotonic()-began,.4)
            self.assertEqual(receipt['live_after'],['injected-late-speaker','second-stuck-lane'])
            self.assertFalse(receipt['owned_threads_joined'])
        finally:self.release.set();other.join(2)

    def test_invalid_timeout_is_rejected(self):
        from app.session_shutdown_v1 import join_owned_workers
        for value in (-1,6,float('nan'),float('inf')):
            with self.assertRaises(ValueError):join_owned_workers([],value)


if __name__ == '__main__': unittest.main(verbosity=2)
