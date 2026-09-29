"""Native shared-controller B05 passage/memory/drain probe. See README_B05_STOP_RESTART_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time
import threading
from datetime import datetime, timezone
from dataclasses import replace

for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['ORT_DISABLE_TELEMETRY']='1'
os.environ['NEMO_SPEECH_MEMSTATS']='1'


def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    root=Path(__file__).resolve().parent
    admission=json.loads((root/'ADMISSION.json').read_text())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot!=admission['boot_id'] or sorted(os.sched_getaffinity(0))!=[2,3] or os.getuid()==0:
        raise RuntimeError('Unexpected owner target/CPU')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(admission['expires_utc']):
        raise RuntimeError('Expired admission')
    if shutil.disk_usage(root).free<5*1024**3: raise RuntimeError('Disk floor')
    available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    if available<850*1024**2: raise RuntimeError('Available RAM floor')
    cgroup=next(x.split(':',2)[2] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    quota,period=(Path('/sys/fs/cgroup')/cgroup.lstrip('/')/'cpu.max').read_text().split()
    if quota=='max' or int(quota)/int(period)>2: raise RuntimeError('CPU quota absent')
    resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    for row in admission['files']:
        if sha(Path(row['path']))!=row['sha256']: raise RuntimeError('Changed admitted input: '+row['path'])
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=boot,admission_sha256=sha(root/'ADMISSION.json'))
    with (root/'OWNER.json').open('x') as f: json.dump(owner,f)
    result=dict(status='FAILED_PRESERVED',owner=owner,native_CM5=True,stage_accepted=False,
                GUI_tested=False,microphone_opened=False,saved_audio_accuracy_scoring=False,
                scope='Anonymous D1 slots without external voice identity, shared controller B05, early Stop at 8 seconds then original full 44.6954375-second restart in the same process; existing app remains active')
    result['ort_disable_telemetry']=os.environ['ORT_DISABLE_TELEMETRY']
    result['allocator_arena_limit']=os.environ.get('MALLOC_ARENA_MAX')
    if result['allocator_arena_limit']!='1': raise RuntimeError('Expected process-local arena limit 1')
    result['allocator_thresholds']={key:os.environ.get(key) for key in ('MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')}
    if set(result['allocator_thresholds'].values())!={'131072'}:raise RuntimeError('Expected bounded process-local allocator thresholds')
    result['memory_samples']=[]
    (root/'MEMORY.jsonl').open('x').close()
    def memory(stage):
        row=dict(stage=stage,monotonic=time.monotonic(),values=[x for x in Path('/proc/self/status').read_text().splitlines() if x.startswith(('VmRSS:','VmSize:','VmPeak:','Threads:'))])
        result['memory_samples'].append(row)
        with (root/'MEMORY.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
    result['prior_python_stack_bytes']=threading.stack_size(1024*1024)
    result['requested_python_stack_bytes']=1024*1024
    result['stack_set_without_resetting_getter']=True
    controller=None
    began=time.perf_counter()
    try:
        source=Path(admission['prototype']);sys.path[:0]=[str(source),str(source/'vendor')]
        import tkinter
        result['tkinter_imported']=True
        memory('before_application_import')
        from app.controller import Controller
        from app.backends import backend_catalog
        memory('after_application_import')
        controller=Controller(root/'data',Path.home()/'JustPeachy/install/models',saved_audio_only=True)
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        selected=next(x['id'] for x in backend_catalog() if x['key']=='nemotron_hybrid')
        result['backend_manifest_id']=selected
        controller.select_backend(selected);controller.commands.join()
        if controller.error: raise RuntimeError(controller.error)
        assert controller.models.document['streaming_profile']=='native_v3_delayed'
        result['configured_diarizer_profile']=controller.models.document['streaming_profile']
        controller.switch(mode='anonymous_conversation',recipe='balanced',tap='O0');controller.commands.join()
        if controller.error: raise RuntimeError(controller.error)
        snapshots=[]
        result['sessions']=[]
        def record(label):
            memory(label)
            snapshot=controller.snapshot()
            snapshots.append(dict(label=label,elapsed=time.perf_counter()-began,state=snapshot['state'],rows=len(snapshot['rows']),metrics=snapshot['metrics']))
            if time.perf_counter()-began>140:raise TimeoutError('Stop/restart diagnostic exceeded 140 seconds')
            return snapshot
        memory('before_early_start')
        controller.start_file(root/'source.wav');controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        first_engine=controller.engine
        first_session=str(first_engine.session_dir)
        first_epoch=controller.epoch
        while first_engine._source.sent < 128000:
            if controller.state!='RUNNING':raise RuntimeError('Session ended before scheduled early Stop')
            record('early_running');time.sleep(.1)
        stop_requested=time.monotonic()
        samples_at_stop_request=first_engine._source.sent
        controller.stop();controller.commands.join()
        stopped=record('after_early_stop')
        with (root/'STOP_SNAPSHOT.json').open('x') as f:json.dump(stopped,f,indent=2)
        if controller.error:raise RuntimeError(controller.error)
        assert controller.engine is None and controller.consumer is None
        assert stopped['state']=='STOPPED'
        assert stopped['metrics']['last_worker_cleanup']['owned_threads_joined']
        first_samples=first_engine._source.sent
        assert 0<first_samples<715127
        result['sessions'].append(dict(kind='early_stop',session_dir=first_session,epoch=first_epoch,source_samples=first_samples,samples_at_stop_request=samples_at_stop_request,stop_requested_monotonic=stop_requested,stop_completed_monotonic=time.monotonic()))
        with (root/'EARLY_STOP.json').open('x') as f:json.dump(result['sessions'][0],f,indent=2)
        # start_file deliberately resets the source offset; reuse this controller/model cache.
        controller.start_file(root/'source.wav');controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        second_engine=controller.engine
        second_session=str(second_engine.session_dir)
        assert second_session!=first_session and controller.epoch>first_epoch
        assert controller.file_offset==0
        result['sessions'].append(dict(kind='full_restart',session_dir=second_session,epoch=controller.epoch))
        while controller.state in ('RUNNING','STARTING','STOPPING'):
            record('restart_running');time.sleep(.5)
        memory('terminal')
        final=controller.snapshot()
        result['sessions'][1]['source_samples']=second_engine._source.sent
        assert second_engine._source.sent==715127
        result['diarizer_manifest']=controller.models.diarizer.manifest() if controller.models.diarizer else None
        result['redim_encoder_loaded']=controller.models.speakers is not None and getattr(controller.models.speakers,'_redim',None) is not None
        assert result['redim_encoder_loaded'] is False, 'Anonymous control must not load E0'
        assert controller.models.speaker_loads == 0
        result['embedding_policy']='BYPASSED_ANONYMOUS_NATIVE_SLOTS'
        result['model_load_counts']={key:getattr(controller.models,key,None) for key in ('asr_loads','speaker_loads','punctuation_loads')}
        with (root/'FINAL_SNAPSHOT.json').open('x') as f: json.dump(final,f,indent=2)
        with (root/'PROGRESS.json').open('x') as f: json.dump(snapshots,f,indent=2)
        if final['error']: raise RuntimeError(final['error'])
        if not final['rows']: raise RuntimeError('No caption rows collected')
        result['final_state']=final['state'];result['row_count']=len(final['rows'])
        result['status']='B05_STOP_RESTART_COLLECTED_REQUIRES_REVIEW'
    except Exception as exc:
        memory('exception')
        result['error']=type(exc).__name__+': '+str(exc)
    finally:
        if controller is not None:
            try:
                controller.close();controller.commands.join();controller.worker.join(10)
                result['controller_closed']=controller.closed
                if not controller.closed: raise RuntimeError('Controller failed to close')
            except Exception as exc:
                result['status']='FAILED_PRESERVED';result['closure_error']=type(exc).__name__+': '+str(exc)
        result['elapsed_seconds']=time.perf_counter()-began
        result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        result['ended_utc']=datetime.now(timezone.utc).isoformat()
        with (root/'RESULT.json').open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__': raise SystemExit(main())
