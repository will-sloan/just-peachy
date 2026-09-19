"""Model-free supervisor checkpoint/drain fixtures. See README_S6D_APPLICATION.md."""
from pathlib import Path
import queue
import tempfile
import threading
import unittest
import json
import s6d_application_native as native


class FakeEngine:
    def __init__(self):
        self.state='IDLE';self.events=queue.Queue();self._threads=[]
        self._finalization_thread=None;self.session_dir=None
        self.start_calls=self.stop_calls=0;self.leak=False

    def telemetry(self):
        row={'depth':0,'accepted':2,'completed':1 if self.leak else 2,'error':None,'closed':True,'thread_alive':False}
        return {'state':self.state,'asr_cursor_sec':.5,'source_duration_sec':.5,
            's6d':{'event_consumer':{'depth':self.events.qsize()},'journal':row,'punctuation':row,'policy':row}}

    def start_file(self,path,realtime):
        self.start_calls+=1;self.state='COMPLETED'
        self._finalization_thread=threading.Thread(target=lambda:None)
        self._finalization_thread.start();self._finalization_thread.join()

    def wait_for_completion(self,timeout):
        if self._finalization_thread:self._finalization_thread.join(timeout)

    def stop(self):
        self.stop_calls+=1

    def record_s6d_consumer_closure(self,consumer):
        if not self.events.empty():raise RuntimeError('not drained')


class NativeChecks(unittest.TestCase):
    def run_fixture(self,engine,checkpoint=None,expect_failure=False):
        with tempfile.TemporaryDirectory(prefix='s6d-native-fixture-') as temp:
            output=Path(temp);manifest=output/'fixture_manifest.json';manifest.write_text('{}')
            job={'job_id':'fixture','settings':{},'audio':{'path':'model-free-unused.wav'},'audio_duration_sec':.5}
            args=(engine,job,{'limits':{'cell_timeout_sec':1.}},manifest,output,checkpoint)
            if expect_failure:
                with self.assertRaises(RuntimeError):native.execute_cell(*args)
            else:native.execute_cell(*args)
            return json.loads((output/'RESULT.json').read_text())

    def test_checked_stop_before_start_records_failed_and_no_start(self):
        engine=FakeEngine()
        def stop(**context):
            self.assertIs(context['engine'],engine)
            self.assertEqual(set(context),{'engine','telemetry','job','output'})
            engine.stop();raise RuntimeError('fixture run-bound STOP_REQUEST')
        row=self.run_fixture(engine,stop,True)
        self.assertEqual(engine.start_calls,0)
        self.assertGreaterEqual(engine.stop_calls,1)
        self.assertEqual(row['status'],'FAILED')
        self.assertFalse(row['native_tested'])
        self.assertTrue(row['resource_observer_closed'])

    def test_after_start_stop_cannot_report_complete(self):
        engine=FakeEngine();calls=[]
        def stop(**context):
            calls.append(engine.state)
            if engine.start_calls:
                engine.stop();raise RuntimeError('fixture checked stop after start')
        row=self.run_fixture(engine,stop,True)
        self.assertEqual(calls,['IDLE','COMPLETED'])
        self.assertEqual(row['status'],'FAILED')

    def test_complete_requires_worker_counts_and_all_callback_boundaries(self):
        engine=FakeEngine();calls=[]
        row=self.run_fixture(engine,lambda **context:calls.append(context['engine'].state))
        self.assertEqual(calls,['IDLE','COMPLETED','COMPLETED'])
        self.assertEqual(row['status'],'COMPLETE');self.assertEqual(row['completion_errors'],[])
        engine=FakeEngine();engine.leak=True
        row=self.run_fixture(engine,expect_failure=True)
        self.assertEqual(row['status'],'FAILED')
        self.assertEqual(len(row['completion_errors']),3)


if __name__=='__main__':unittest.main(verbosity=2)
