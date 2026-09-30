"""Native live-controller saved-source fixture; never opens hardware. See README_B01_ISOLATED_FIXTURE_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time
import threading
import weakref
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
    from native_artifact_envelope_v1 import record_envelope
    record_envelope(root,owner)
    result=dict(status='FAILED_PRESERVED',owner=owner,native_CM5=True,stage_accepted=False,
                GUI_tested=False,microphone_opened=False,saved_audio_accuracy_scoring=False,
                scope='Real Controller.start_live/LivePipelineSource/CaptureTimeline with saved-source fixture and actual B01 models; no device or acoustic evidence')
    result['ort_disable_telemetry']=os.environ['ORT_DISABLE_TELEMETRY']
    result['allocator_arena_limit']=os.environ.get('MALLOC_ARENA_MAX')
    if result['allocator_arena_limit']!='1': raise RuntimeError('Expected process-local arena limit 1')
    result['allocator_thresholds']={key:os.environ.get(key) for key in ('MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')}
    if set(result['allocator_thresholds'].values())!={'131072'}:raise RuntimeError('Expected bounded process-local allocator thresholds')
    result['startup_stack_rlimit_bytes']=list(resource.getrlimit(resource.RLIMIT_STACK))
    assert result['startup_stack_rlimit_bytes']==[1048576,1048576]
    import ctypes
    libc=ctypes.CDLL(None)
    libc.pthread_getattr_default_np.argtypes=[ctypes.c_void_p]
    libc.pthread_attr_getstacksize.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t)]
    libc.pthread_attr_destroy.argtypes=[ctypes.c_void_p]
    attr=(ctypes.c_ulong*32)();stack=ctypes.c_size_t()
    assert libc.pthread_getattr_default_np(attr)==0
    assert libc.pthread_attr_getstacksize(attr,ctypes.byref(stack))==0
    assert libc.pthread_attr_destroy(attr)==0
    result['native_default_thread_stack_bytes']=stack.value
    assert stack.value==1048576
    result['memory_samples']=[]
    (root/'MEMORY.jsonl').open('x').close()
    def memory(stage):
        row=dict(stage=stage,monotonic=time.monotonic(),values=[x for x in Path('/proc/self/status').read_text().splitlines() if x.startswith(('VmRSS:','VmSize:','VmPeak:','Threads:'))])
        result['memory_samples'].append(row)
        with (root/'MEMORY.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
    result['prior_python_stack_bytes']=threading.stack_size(1024*1024)
    result['requested_python_stack_bytes']=1024*1024
    result['stack_set_without_resetting_getter']=True
    controller=None;tkroot=None
    began=time.perf_counter()
    try:
        source=Path(admission['prototype']);sys.path[:0]=[str(source),str(source/'vendor')]
        import tkinter
        result['tkinter_imported']=True
        memory('before_application_import')
        from app import live_audio as L
        assert L.XVFLiveSource.__name__=='DetailedSource'
        result['callback_detail_bound_before_saved_substitution']=True
        from unittest.mock import patch
        import types
        def forbidden(*args,**kwargs):raise AssertionError('Hardware access forbidden in saved isolated fixture')
        denied=types.ModuleType('sounddevice');denied.__getattr__=lambda name:forbidden(name)
        patches=[patch.dict(sys.modules,{'sounddevice':denied}),patch.object(L,'HostControl',side_effect=forbidden),patch.object(L,'DeviceLease',side_effect=forbidden),patch.object(L,'inventory',side_effect=forbidden)]
        result['real_sounddevice_imported']=False
        for item in patches:item.start()
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
        from app.controller import Controller as OriginalController
        from app import pipeline
        from isolated_pipeline_source_v2 import IsolatedLiveConfig,bind_pipeline
        original_source=bind_pipeline(pipeline)
        class Controller(OriginalController):
            def _live_config(self):
                directory=root/('source-epoch-'+str(self.epoch));directory.mkdir()
                cfg=dict(source_module='isolated_saved_source_v1',source_factory='create',capture=False,
                         prototype=str(source),fixture_root=str(root),case_directory=str(directory),backpressure_seconds=1)
                with (directory/'CONFIG.json').open('x') as f:json.dump(cfg,f,indent=2)
                return IsolatedLiveConfig(directory/'CONFIG.json',source)
        from app.backends import backend_catalog
        memory('after_application_import')
        assert not any(k=='scipy' or k.startswith('scipy.') for k in sys.modules)
        controller=Controller(root/'data',Path.home()/'JustPeachy/install/models',saved_audio_only=False)
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        controller.session_action('new',audio=True,consent=True,title='Private B01 saved-input artifact trial');controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        selected=next(x['id'] for x in backend_catalog() if x['key']=='nemotron_hybrid')
        result['backend_manifest_id']=selected
        controller.select_backend(selected);controller.commands.join()
        if controller.error: raise RuntimeError(controller.error)
        assert controller.models.document['streaming_profile']=='native_v3_delayed'
        result['configured_diarizer_profile']=controller.models.document['streaming_profile']
        controller.switch(mode='open_with_names',recipe='balanced',tap='O0');controller.commands.join()
        if controller.error: raise RuntimeError(controller.error)
        from app.ui import PrototypeUI
        tkroot=tkinter.Tk(screenName=':0');tkroot.withdraw()
        tkroot.tk.eval('rename wm jp_original_wm; proc wm {args} {if {[lindex $args 0] eq "deiconify" || ([lindex $args 0] eq "state" && [llength $args] > 2 && [lindex $args 2] ne "withdrawn")} {error "visible windows forbidden"}; return [uplevel 1 [linsert $args 0 jp_original_wm]]}')
        callbacks=[]
        tkroot.report_callback_exception=lambda kind,value,trace:callbacks.append(kind.__name__+': '+str(value))
        ui=PrototypeUI(tkroot,controller,allow_auto_start=False)
        result['withdrawn_Tk_constructed']=True
        def gui_pump():
            tkroot.update()
            assert tkroot.state()=='withdrawn' and not tkroot.winfo_ismapped()
            assert not callbacks and not ui._notice.startswith('Display update:'),str(callbacks)+ui._notice
        snapshots=[]
        result['sessions']=[]
        def record(label):
            gui_pump()
            memory(label)
            snapshot=controller.snapshot()
            snapshots.append(dict(label=label,elapsed=time.perf_counter()-began,state=snapshot['state'],rows=len(snapshot['rows'])))
            if time.perf_counter()-began>140:raise TimeoutError('Stop/restart diagnostic exceeded 140 seconds')
            return snapshot
        memory('before_early_start')
        controller.start_live(consent=True);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        first_engine=controller.engine
        first_session=str(first_engine.session_dir)
        first_epoch=controller.epoch
        while first_engine._source.sent < 128000:
            if controller.state!='RUNNING':raise RuntimeError('Session ended before scheduled early Stop')
            record('early_running');time.sleep(.25)
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
        result['early_conversion']=first_engine._source.stop_receipt['terminal']['source_close']['conversion']
        assert 0<first_samples<715127
        result['sessions'].append(dict(kind='early_stop',session_dir=first_session,epoch=first_epoch,source_samples=first_samples,samples_at_stop_request=samples_at_stop_request,stop_requested_monotonic=stop_requested,stop_completed_monotonic=time.monotonic()))
        with (root/'EARLY_STOP.json').open('x') as f:json.dump(result['sessions'][0],f,indent=2)
        first_engine_ref=weakref.ref(first_engine)
        del first_engine, stopped
        result['harness_retains_early_engine']=False
        result['early_engine_alive_after_release']=first_engine_ref() is not None
        # start_file deliberately resets the source offset; reuse this controller/model cache.
        controller.start_live(consent=True);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        second_engine=controller.engine
        second_session=str(second_engine.session_dir)
        assert second_session!=first_session and controller.epoch>first_epoch
        assert controller.file_offset==0
        result['sessions'].append(dict(kind='full_restart',session_dir=second_session,epoch=controller.epoch))
        while controller.state in ('RUNNING','STARTING','STOPPING'):
            record('restart_running')
            until=time.monotonic()+1
            while time.monotonic()<until:
                gui_pump();time.sleep(.05)
        settle=time.monotonic()+1.35
        while time.monotonic()<settle:
            gui_pump();time.sleep(.05)
        memory('terminal')
        final=controller.snapshot()
        result['sessions'][1]['source_samples']=second_engine._source.sent
        result['full_conversion']=second_engine._source.stop_receipt['terminal']['source_close']['conversion']
        result['live_source_timeline']=second_engine._source.timing.snapshot()
        result['live_source_integrity']=second_engine._source.integrity
        result['live_source_stop_receipt']=second_engine._source.stop_receipt
        assert result['live_source_timeline']['model_samples_accepted']==715127
        assert result['live_source_timeline']['native_frames_accepted']==2145381
        assert result['live_source_integrity']['ok']
        assert result['live_source_stop_receipt']['child_exit']==0 and not result['live_source_stop_receipt']['forced_close']
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
        if final['error']:raise RuntimeError(final['error'])
        assert second_engine._source.sent==715127
        result['early_engine_alive_at_restart_end']=first_engine_ref() is not None
        result['diarizer_manifest']=controller.models.diarizer.manifest() if controller.models.diarizer else None
        result['redim_encoder_loaded']=controller.models.speakers is not None and getattr(controller.models.speakers,'_redim',None) is not None
        assert result['redim_encoder_loaded'] is True, 'Retained E0 must load once'
        assert controller.models.speaker_loads == 1
        assert not any(k=='scipy' or k.startswith('scipy.') for k in sys.modules)
        result['embedding_policy']='UNCHANGED_NAMING_OR_RESEARCH'
        result['empty_new_gallery']=True
        result['no_scipy_loaded']=True
        result['model_load_counts']={key:getattr(controller.models,key,None) for key in ('asr_loads','speaker_loads','punctuation_loads')}
        with (root/'FINAL_SNAPSHOT.json').open('x') as f: json.dump(final,f,indent=2)
        with (root/'PROGRESS.json').open('x') as f: json.dump(snapshots,f,indent=2)
        if final['error']: raise RuntimeError(final['error'])
        if not final['rows']: raise RuntimeError('No caption rows collected')
        ui.poll();ui._flush_rows();ui._render_rows(final['rows'],force=True);gui_pump()
        result['widget_rows']=[]
        for row in final['rows']:
            rid=str(row['id']);label,caption,_=ui._row_cache[rid]
            actual=ui.caption_text.get(*ui._marks[rid])
            assert actual==(label+'\n' if label else '')+caption+'\n\n'
            result['widget_rows'].append(dict(id=rid,label=label,caption=caption,actual_text=actual))
        result['GUI_tested']='withdrawn widgets with actual inference; no physical display qualification'
        result['root_withdrawn']=tkroot.state()=='withdrawn' and not tkroot.winfo_ismapped()
        result['callback_errors']=callbacks
        result['final_state']=final['state'];result['row_count']=len(final['rows'])
        # Actual controller Save/Open boundaries with the new compact archive reader.
        identifier=controller.conversation_id
        reopened=controller.session_store.rows(identifier)
        assert reopened  # Raw utterances contain nested display segments.
        with (root/'REOPENED_ROWS.json').open('x') as stream:json.dump(reopened,stream,indent=2)
        controller.session_action('save');controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        assert controller.session_store.metadata(identifier)['pinned']
        controller.session_action('open',identifier=identifier);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        gui_pump();opened=controller.snapshot()
        assert len(opened['rows'])==len(final['rows'])==40
        fields=['id','caption_key','utterance_id','raw_asr_text','provisional_display_text','final_punctuated_display_text','label','final','profile_id','track_id','span_ids','source_start_sec','source_end_sec','timing_kind','word_spans','speaker_revision','first_shown_label','identity_version']
        for old,new in zip(final['rows'],opened['rows'],strict=True):
            assert {k:old.get(k) for k in fields}=={k:new.get(k) for k in fields},old['id']
        result['reopen_compared_fields']=fields
        ui.poll();ui._flush_rows();ui._render_rows(opened['rows'],force=True);gui_pump()
        with (root/'OPENED_SNAPSHOT.json').open('x') as stream:json.dump(opened,stream,indent=2)
        epochs=controller.session_store.metadata(identifier)['epochs'];assert len(epochs)==2
        archive_results=[]
        for epoch in epochs:
            folder=controller.session_store.epoch(identifier,epoch)
            meta=json.loads((folder/'epoch.json').read_text())
            assert meta['state']=='CLOSED' and meta['closed'] and not meta['archive_error']
            assert meta['event_format']=='compact-patch-v1' and meta['audio_enabled']
            assert meta['recorded_samples']==meta['source_samples']
            assert meta['artifact_metrics']['events']['status']=='COMPLETE'
            assert meta['artifact_metrics']['audio']['status']=='COMPLETE'
            archive_results.append(dict(path=str(folder),epoch=epoch,samples=meta['recorded_samples'],float_sha256=sha(folder/'model_input.f32le'),wav_sha256=sha(folder/'model_input.wav'),artifacts=meta['artifact_metrics']))
        result['archives']=archive_results
        result['controller_save_open']=True
        result['raw_reopened_utterances']=len(reopened);result['reopened_row_count']=len(opened['rows'])
        result['status']='B01_ISOLATED_FIXTURE_COLLECTED_REFERENCES_PENDING' 
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
        if tkroot is not None:
            tkroot.destroy();result['Tk_destroyed']=True
        for item in reversed(locals().get('patches',[])):item.stop()
        if 'original_source' in locals():pipeline.LivePipelineSource=original_source
        result['actual_device_tested']=False
        result['elapsed_seconds']=time.perf_counter()-began
        result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        result['ended_utc']=datetime.now(timezone.utc).isoformat()
        with (root/'RESULT.json').open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k in ('status','error','closure_error','elapsed_seconds','peak_rss_bytes')}),flush=True)
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__': raise SystemExit(main())
