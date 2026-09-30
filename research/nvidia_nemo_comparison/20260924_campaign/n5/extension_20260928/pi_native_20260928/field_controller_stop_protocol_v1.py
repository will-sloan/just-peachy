"""Changed actual installed controller paths; README_FIELD_CONTROLLER_STOP_V1.md."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from field_sidecar_budget_v1 import GroupWriter
from field_run_outputs_v1 import RunOutputs
from field_controller_stop_v1 import controller_class
import field_archive_budget_v4 as publisher


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def wait_for(predicate,label):
    deadline=time.monotonic()+12
    while not predicate():
        if time.monotonic()>=deadline:raise TimeoutError(label)
        time.sleep(.01)


def run(root,a):
    base=Path(a['installed_release'])
    for p,h in a['archive_binding_files'].items():assert sha(p)==h
    sys.path[:0]=[str(base),str(base/'vendor'),str(base/'native')]
    import app
    assert 'app.sessions' not in sys.modules
    source=root/'code/archive_stop_sessions_v1.py'
    spec=importlib.util.spec_from_file_location('app.sessions',source)
    sessions=importlib.util.module_from_spec(spec);sys.modules['app.sessions']=sessions
    spec.loader.exec_module(sessions);app.sessions=sessions
    import app.controller as cm
    from app import paths
    assert Path(cm.__file__).resolve()==base/'app/controller.py' and paths.ROOT.resolve()==base
    original_archive=sessions.EpochArchive
    limits=json.loads((base/'config/artifact_limits.json').read_text())
    policy=dict(archive_budget=publisher.validate(publisher.DEFAULT),artifact_limits=limits,
        quota_mib=512,free_floor_mib=5120,record_bytes=65536,resource_interval_sec=3600)
    receipts=root/'binding_receipts';receipts.mkdir()
    writer=GroupWriter(receipts,a['case_receipt_limits']);cases=[]
    installed=json.loads((base/'RELEASE_MANIFEST.json').read_text())
    manifest={r['path']:r for r in installed['files']}
    def loaded():
        checked=[]
        for name,module in tuple(sys.modules.items()):
            if name.split('.')[0] not in ('app','edge_speech_pipeline','release_tools','field_artifact_limits_v1'):continue
            origin=getattr(module,'__file__',None)
            if not origin:continue
            path=Path(origin).resolve()
            if name=='app.sessions':assert path==source;continue
            rel=path.relative_to(base).as_posix();assert sha(path)==manifest[rel]['sha256']
            checked.append(name)
        return checked
    initial_loaded=loaded()
    original_atomic=cm.atomic_json
    for name in ('prepare-failure','worker-failure'):
        case=root/name;case.mkdir();data=case/'data';data.mkdir()
        writer.json(name+'-DATA_SCHEMA.json',{'schema_version':1})
        # ApplicationLock requires the schema in its actual data root, not a fixture.
        GroupWriter(data,a['case_receipt_limits']).json('DATA_SCHEMA.json',{'schema_version':1})
        outputs=RunOutputs(case/'outputs')
        C=controller_class(cm,sessions,outputs,policy,a['archive_binding_files'][str(base/'app/controller.py')])
        created_engines=[]
        create_engine=C._create_epoch_engine
        def observed_engine(self,*args,**kwargs):
            value=create_engine(self,*args,**kwargs);created_engines.append(value);return value
        C._create_epoch_engine=observed_engine
        original_write=publisher._write_block;calls=[];controller=None;archive=None
        def write_block(stream,raw):
            calls.append(dict(path=str(stream.name),bytes=len(raw)))
            if name=='prepare-failure' and Path(stream.name).name=='.conversation.json.pending':
                return original_write(stream,raw[:3])
            if name=='worker-failure' and Path(stream.name).name=='.epoch.json.pending':
                epoch_calls=sum(Path(r['path']).name=='.epoch.json.pending' for r in calls)
                if epoch_calls==2:return original_write(stream,raw[:3])
            return original_write(stream,raw)
        def bounded_close(path,value):
            assert Path(path).resolve()==data/'last_application.json'
            return writer.json(name+'-last_application.json',value)
        cm.atomic_json=bounded_close
        try:
            controller=C(data,Path.home()/'JustPeachy/install/models',saved_audio_only=True)
            assert controller.owner._ownership.owned and controller.worker.is_alive()
            publisher._write_block=write_block
            if name=='prepare-failure':
                # Real queued file Start reaches archive preparation before opening this path.
                controller.start_file(case/'not-opened.wav')
                wait_for(lambda:controller.commands.unfinished_tasks==0 and controller._archive_stop_processed,'prepare failure Stop')
                assert controller._archive_failure and controller.engine is None and controller.consumer is None
                assert controller._archive_cleanup_error is None
                pending=list(data.rglob('.conversation.json.pending'))
                assert len(pending)==1 and pending[0].read_bytes()==b'{\n '
                assert not list(data.rglob('epoch.json'))
                assert len(calls)==1 and len(created_engines)==1
                assert created_engines[0]._source is None and created_engines[0]._journal is None and not created_engines[0]._threads
                assert outputs.failures['entry']['stop_requested'] and outputs.failures['entry']['raw_retained']
            else:
                # Actual store and archive worker call the actual controller callback.
                identifier=controller.session_store.new(audio=False,title='Controller archive failure; no audio')
                controller.conversation_id=identifier
                archive=controller.session_store.begin(identifier,dict(conversation_id=identifier,synthetic_no_capture=True))
                controller.archive=archive
                wait_for(lambda:controller._archive_stop_processed and not archive.thread.is_alive(),'archive worker Stop')
                # If the callback preceded assignment, explicit queued Stop finishes attachment.
                controller.stop();wait_for(lambda:controller.commands.unfinished_tasks==0,'Stop queue')
                assert controller.archive is None and not controller.session_store.active
                assert archive.closed and not archive.thread.is_alive()
                assert (archive.path/'.epoch.json.pending').read_bytes()==b'{\n '
                assert json.loads((outputs.root/'closure/archive.json').read_text())['worker_joined']
                assert controller._archive_cleanup_error is None
            failure=controller.error
            assert failure==controller._archive_failure and controller.state=='ERROR'
            controller.stop();wait_for(lambda:controller.commands.unfinished_tasks==0,'explicit Stop')
            assert controller.error==failure and controller.state=='ERROR'
            controller.start_file(case/'not-opened-again.wav')
            wait_for(lambda:controller.commands.unfinished_tasks==0,'rejected restart')
            assert controller.error==failure and controller.engine is None
            assert controller.models.asr_loads==controller.models.speaker_loads==0
            assert not list(data.rglob('*.wav')) and not list(data.rglob('*.f32le'))
            before=len(calls)
            controller.close();wait_for(lambda:controller.closed,'Close')
            controller.worker.join(5)
            assert not controller.worker.is_alive() and controller.commands.unfinished_tasks==0
            assert not (data/'runtime.lock').exists() and len(calls)==before
            assert controller.error==failure and controller.state=='CLOSED'
            row=dict(case=name,error=failure,state_after_close=controller.state,
                stop_observations=controller._archive_stop_observations,automatic_stop_processed=True,
                command_worker_joined=True,application_lock_released=True,publisher_calls=calls,
                no_publisher_retry_on_close=True,archive_worker_joined=archive is None or not archive.thread.is_alive(),
                engine_released=controller.engine is None,models_loaded=0,source_started=False,
                controller_origin=str(cm.__file__),sessions_origin=str(sessions.__file__),actual_engine_constructors=len(created_engines))
            cases.append(row);writer.json(name+'-CASE.json',row)
        finally:
            publisher._write_block=original_write;sessions.EpochArchive=original_archive
            if archive is not None and archive.thread.is_alive():archive.stop_event.set();archive.thread.join(10)
            if controller is not None and not controller.closed:
                controller.close();wait_for(lambda:controller.closed,'failure cleanup');controller.worker.join(5)
            cm.atomic_json=original_atomic
    final_loaded=loaded()
    assert not any(t.name in ('proto-controller','proto-session-archive','proto-file-source') for t in threading.enumerate())
    result=dict(status='PASS_INSTALLED_CONTROLLER_ARCHIVE_FAILURE_STOP_ONLY',cases=cases,
        actual_controller=True,actual_command_workers_joined=True,actual_source=False,models=False,capture=False,GUI=False,
        source_samples=0,full_live_composition=False,loaded_before=initial_loaded,loaded_after=final_loaded)
    writer.json('CONTROLLER_CLOSURE.json',result)
    return result
