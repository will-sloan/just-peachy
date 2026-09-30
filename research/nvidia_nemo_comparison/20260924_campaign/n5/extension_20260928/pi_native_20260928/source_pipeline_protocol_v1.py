"""Native application-source and shutdown boundaries without model/hardware; README_SOURCE_PIPELINE_V1.md."""
import inspect,json,queue,sys,threading,time
from pathlib import Path
from types import SimpleNamespace


def run(root,a):
    prototype=Path(a['prototype']);sys.path[:0]=[str(prototype),str(prototype/'vendor')]
    from app import pipeline
    from app.controller import Controller
    from app.buffers import MemoryJournal
    from isolated_pipeline_source_v1 import IsolatedPipelineSource,IsolatedLiveConfig,bind_pipeline
    assert Path(inspect.getfile(pipeline.PrototypeEngine.start_xvf)).resolve()==prototype/'app/pipeline.py'
    assert Path(inspect.getfile(Controller._stop_session)).resolve()==prototype/'app/controller.py'
    def forbidden(*args,**kwargs):raise AssertionError('Model use is not admitted')
    pipeline.ResidentModels.acquire=forbidden
    original=bind_pipeline(pipeline)
    cases=[]
    try:
        for name,fixture in [('stop_tail','stop_pending'),('restart','stop_pending'),('empty_stop','empty_stop'),
                             ('callback_fault','callback_fault'),('restore_failure','restore_failure'),
                             ('start_failure','start_failure'),('timing_failure','timing_failure')]:
            d=root/name;d.mkdir();events=[];reached=threading.Event();release=threading.Event()
            cfg=dict(case=fixture,source_module='source_pipeline_fixture_v1',source_factory='create',capture=False,
                     prototype=a['prototype'],source_wav=a['source_wav'],case_directory=str(d),backpressure_seconds=1)
            with (d/'CONFIG.json').open('x') as f:json.dump(cfg,f,indent=2)
            config=IsolatedLiveConfig(d/'CONFIG.json',prototype)
            def observe(start,audio):
                if name in ('stop_tail','restart','restore_failure') and start==320:
                    reached.set()
                    if not release.wait(3):raise RuntimeError('Test consumer was not released')
            journal=MemoryJournal(reserve_sec=2,observer=observe)
            class EngineShell:
                # The model/session watcher is intentionally absent. Only the
                # real application source constructor and controller shutdown
                # methods execute; this is not whole-engine/model qualification.
                _spatial_provider=None;_threads=[];_finalization_thread=None
                enhancement_router=None;_s6d_writer=None;_s6d_punctuation=None;_s7_trace=None
                _scheduler=SimpleNamespace(worker=None);text_writers=[];archive=None;session_dir=None
                mode='caption_only'
                def __init__(self):
                    self._input_journal=self._journal=journal;self.events=queue.Queue();self.begin_calls=0;self.partial_cleanup=[]
                def begin(self):self.begin_calls+=1
                def _source_status(self,kind,payload):events.append(dict(kind=kind,payload=payload))
                def _launch(self,source):
                    self._source=source
                    source.start();self._finalization_thread=source.thread
                    return source
                def stop(self):self._source.stop()
                def wait_for_completion(self,timeout):
                    if not self._source.wait(min(timeout,5)):raise RuntimeError('source not done')
                def _fail(self,reason):self.partial_cleanup.append(reason)
                def _watch_session(self):self.partial_cleanup.append('model-free partial startup finalized')
            engine=EngineShell();startup_error=None
            try:pipeline.PrototypeEngine.start_xvf(engine,config)
            except Exception as exc:startup_error=str(exc)
            source=engine._source
            assert isinstance(source,IsolatedPipelineSource)
            controller=Controller.__new__(Controller)
            controller.engine=engine;controller.consumer=None;controller.state='RUNNING';controller.status=''
            controller.error=None;controller.metrics={};controller.source_kind='live'
            controller.saved_audio_only=True;controller.output_defaults=[]
            stop_errors=[]
            def stop():
                try:controller._stop_session()
                except Exception as exc:stop_errors.append(str(exc))
            if name in ('stop_tail','restart','restore_failure'):
                assert reached.wait(4),'consumer hook not reached'
                stopper=threading.Thread(target=stop,name='test-controller-stop');stopper.start()
                time.sleep(.1)
                held=dict(controller_state=controller.state,engine_retained=controller.engine is engine,
                          journal_samples=journal.committed_samples,source_finished=source.live.status()['finished'])
                assert held==dict(controller_state='STOPPING',engine_retained=True,journal_samples=480,source_finished=False)
                release.set();stopper.join(8);assert not stopper.is_alive()
            else:
                held=None
                if name in ('callback_fault','timing_failure'):assert source.wait(5)
                stop()
            assert not stop_errors and controller.engine is None and controller.consumer is None
            assert source._done.is_set() and (source.thread is None or not source.thread.is_alive())
            assert source.facade.closed and source.facade.transport.proc.poll() is not None
            assert journal.finished
            expected=0 if name in ('empty_stop','start_failure','timing_failure') else (960 if name=='callback_fault' else 15360)
            assert journal.committed_samples==source.sent==expected,(name,journal.committed_samples,source.error)
            failed=name in ('callback_fault','restore_failure','start_failure','timing_failure')
            assert bool(source.error)==failed and bool(journal.fatal_error)==failed and bool(controller.error)==failed
            assert bool(source.integrity['ok'])==(not failed)
            assert engine.begin_calls==1 and (startup_error is not None)==(name=='start_failure')
            content=journal.read(0,max(1,expected),wait_sec=0).astype('<f4',copy=False).tobytes()
            with (d/'JOURNAL.f32').open('xb') as f:f.write(content)
            negative=0
            try:source.start()
            except RuntimeError:negative+=1
            try:IsolatedPipelineSource(journal,object(),lambda *x:None)
            except ValueError:negative+=1
            try:IsolatedPipelineSource(journal,config,lambda *x:None,SimpleNamespace(enabled=True))
            except ValueError:negative+=1
            assert negative==3
            row=dict(case=name,fixture=fixture,expected_journal_samples=expected,journal_samples=source.sent,
                journal_fatal=journal.fatal_error,source_error=source.error,secondary_errors=source.secondary_errors,
                integrity=source.integrity,terminal=source.stop_receipt,startup_error=startup_error,
                timing=source.timing.snapshot() if source.timing else None,recent_ipc=list(source.recent_ipc),
                held_during_stop=held,controller_error=controller.error,controller_metrics=controller.metrics,
                controller_engine_released=controller.engine is None,partial_cleanup=engine.partial_cleanup,
                events=events,negative_calls=negative,child_exit=source.facade.transport.proc.returncode)
            with (d/'CASE_RESULT.json').open('x') as f:json.dump(row,f,indent=2)
            cases.append({k:row[k] for k in ['case','journal_samples','source_error','held_during_stop','child_exit']})
        assert cases[0]['journal_samples']==cases[1]['journal_samples']
        assert (root/'stop_tail/JOURNAL.f32').read_bytes()==(root/'restart/JOURNAL.f32').read_bytes()
        return dict(status='COLLECTED_NATIVE_ISOLATED_PIPELINE_CONTROLLER_BOUNDARY_CASES_ONLY',cases=cases,
            capture=False,models_loaded=False,gui_tested=False,whole_controller_startup_qualified=False,
            binding='actual PrototypeEngine.start_xvf and Controller._stop_session methods; model-free engine shell',
            source_modules=dict(pipeline=str(prototype/'app/pipeline.py'),controller=str(prototype/'app/controller.py')))
    finally:pipeline.LivePipelineSource=original
