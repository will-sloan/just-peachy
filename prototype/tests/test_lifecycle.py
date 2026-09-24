"""No-microphone, no-native-model failure/ownership regression tests."""
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.controller import Controller
from app.pipeline import ResidentModels


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='PROTO1 lifecycle synthetic tests ')
        self.root=Path(self.temp.name)
        self.controller=None
        self.endpoint_patch=patch.object(Controller,'_observe_output',return_value=None)
        self.endpoint_patch.start()

    def tearDown(self):
        if self.controller and not self.controller.closed:
            self.controller.close();self.controller.commands.join();self.controller.worker.join(3)
        self.endpoint_patch.stop()
        self.temp.cleanup()

    def make(self):
        self.controller=Controller(self.root/'data',self.root/'nonexistent-models')
        return self.controller

    def close(self):
        self.controller.close();self.controller.commands.join();self.controller.worker.join(3)
        self.assertTrue(self.controller.closed,self.controller.error)
        self.assertFalse((self.root/'data'/'runtime.lock').exists())

    def completed_engine(self, *, terminal_error=None, live=None):
        finished=threading.Thread(target=lambda:None);finished.start();finished.join()
        def wait(timeout):
            if terminal_error:raise RuntimeError(terminal_error)
        return SimpleNamespace(stop=lambda:None,wait_for_completion=wait,
            _finalization_thread=finished,_journal=None,_threads=[],text_writers=[],
            _source=SimpleNamespace(thread=None,sent=0,live=live),events=queue.Queue(),session_dir=None,
            _s6d_writer=None,_s6d_punctuation=None,_scheduler=None,_s7_trace=None,
            config=SimpleNamespace(input_gain=1.),telemetry=lambda:{'state':'MOCK_COMPLETED'})

    def test_bad_settings_does_not_leave_application_lock(self):
        data=self.root/'data';data.mkdir();(data/'settings.json').write_text('{',encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):Controller(data,self.root/'models')
        self.assertFalse((data/'runtime.lock').exists())

    def test_new_epoch_clears_old_gui_error_but_preserves_terminal_evidence(self):
        controller=self.make()
        controller.error='Previous timing failure'
        controller.metrics['last_terminal_failures']=['Previous timing failure']
        controller.source_kind='file';controller.file_path=Path('unused.fixture.wav')
        engine=self.completed_engine();engine.start_prepared_file=lambda *args:None
        with patch('app.controller.PrototypeEngine',return_value=engine),patch.object(controller,'_consume'):
            controller._start_session();controller.consumer.join(2)
        self.assertIsNone(controller.error)
        self.assertEqual(controller.metrics['last_terminal_failures'],['Previous timing failure'])
        self.close()

    def test_incomplete_failed_source_close_is_retried_before_owner_release(self):
        controller=self.make();state={'finished':False};calls=[]
        live=SimpleNamespace(status=lambda:dict(started=True,finished=state['finished']),
            stream=SimpleNamespace(active=True))
        engine=self.completed_engine(live=live)
        def stop_source():
            calls.append('stop');state['finished']=True;live.stream.active=False
        engine._source.stop=stop_source;controller.engine=engine
        controller._do_stop()
        self.assertEqual(calls,['stop']);self.assertIsNone(controller.engine)
        self.close()

    def test_finished_worker_terminal_error_can_close_and_preserves_failure(self):
        controller=self.make();controller.engine=self.completed_engine(terminal_error='Injected finalization failure')
        self.close()
        self.assertIn('Injected finalization failure',controller.metrics['last_terminal_failures'][0])
        receipt=json.loads((self.root/'data'/'last_application.json').read_text(encoding='utf-8'))
        self.assertFalse(receipt['microphone_open'])
        self.assertIn('Injected finalization failure',receipt['metrics']['last_terminal_failures'][0])

    def test_native_model_constructor_failure_closes_started_journals(self):
        controller=self.make();path=self.root/'synthetic silence.wav'
        with wave.open(str(path),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0'*3200)
        before={t.ident for t in threading.enumerate()}
        with patch.object(ResidentModels,'acquire',side_effect=RuntimeError('Injected model construction failure')):
            controller.start_file(path);controller.commands.join()
        self.assertEqual(controller.state,'ERROR')
        self.assertIn('Injected model construction failure',controller.error)
        self.assertIsNone(controller.engine)
        self.assertFalse([t.name for t in threading.enumerate() if t.ident not in before and t.name.startswith(('edge-','proto-journal'))])
        self.close()

    def test_bad_wav_does_not_open_journal_workers(self):
        controller=self.make();before={t.ident for t in threading.enumerate()}
        controller.start_file(self.root/'does not exist.wav');controller.commands.join()
        self.assertEqual(controller.state,'ERROR')
        self.assertIsNone(controller.engine)
        self.assertFalse([t.name for t in threading.enumerate() if t.ident not in before and t.name.startswith(('edge-','proto-journal'))])
        self.close()

    def test_live_worker_prevents_owner_release(self):
        controller=self.make();release=threading.Event();worker=threading.Thread(target=release.wait,daemon=True);worker.start()
        engine=self.completed_engine();engine._threads=[worker];controller.engine=engine
        try:
            with self.assertRaisesRegex(RuntimeError,'live workers'):controller._do_close()
            self.assertFalse(controller.closed)
            self.assertTrue((self.root/'data'/'runtime.lock').exists())
        finally:release.set();worker.join(2)
        self.close()

    def test_historical_started_flag_allows_finished_live_session_close(self):
        controller=self.make()
        live=SimpleNamespace(status=lambda:dict(started=True,finished=True),stream=SimpleNamespace(active=False))
        controller.engine=self.completed_engine(live=live)
        self.close()

    def test_live_bounded_journal_worker_also_retains_owner(self):
        controller=self.make();release=threading.Event();worker=threading.Thread(target=release.wait,daemon=True);worker.start()
        engine=self.completed_engine();engine._s6d_writer=SimpleNamespace(thread=worker);controller.engine=engine
        try:
            with self.assertRaisesRegex(RuntimeError,'live workers'):controller._do_close()
            self.assertTrue((self.root/'data'/'runtime.lock').exists())
        finally:release.set();worker.join(2)
        self.close()

    def test_active_capture_prevents_owner_release(self):
        controller=self.make();stream=SimpleNamespace(active=True)
        live=SimpleNamespace(status=lambda:dict(started=True,finished=True),stream=stream)
        controller.engine=self.completed_engine(live=live)
        try:
            with self.assertRaisesRegex(RuntimeError,'stream remains active'):controller._do_close()
            self.assertFalse(controller.closed)
            self.assertTrue((self.root/'data'/'runtime.lock').exists())
        finally:stream.active=False
        self.close()


if __name__=='__main__':unittest.main(verbosity=2)
