"""Authority-bound quiet B01 with compact archives. See README_B01_ISOLATED_QUIET_V1.md."""
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
    from b01_isolated_quiet_envelope_v1 import record_envelope
    record_envelope(root,owner)
    authority=json.loads((root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json').read_text())
    assert sha(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')==admission['authority_sha256']
    assert authority['scheduled_quiet_capture_authorized'] and authority['quiet_audio_retention_authorized']
    assert admission['mode']=='autonomous_quiet' and admission['capture'] and admission['audio_saved']
    assert not admission.get('physically_ready_attested',False)
    assert 'ALSA_CONFIG_PATH' not in os.environ
    os.environ['ALSA_CONFIG_PATH']=str(root/'alsa_hw_only_v1.conf')
    assert sha(root/'alsa_hw_only_v1.conf')=='d81bc353dcab14d172e78b26c6116bfc8462b96e45e44b1a93ac3f217898564d'
    with (root/'ALSA_ENVIRONMENT.json').open('x') as stream:json.dump(dict(path=os.environ['ALSA_CONFIG_PATH'],process_local=True,sha256=sha(root/'alsa_hw_only_v1.conf')),stream)
    assert admission['capture_seconds']==30
    result=dict(status='FAILED_PRESERVED',owner=owner,native_CM5=True,stage_accepted=False,
                GUI_tested=False,microphone_opened=False,real_capture_intended=True,private_audio_journal=True,saved_audio_accuracy_scoring=False,
                scope='Autonomous quiet/background30s B01 with private bounded compact/PCM diagnostics; no labelled silence or speech-quality claim')
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
        result['callback_detail_bound']=True
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
        import signal
        def stop_requested(signum,frame):raise RuntimeError('Bounded service stop requested')
        signal.signal(signal.SIGTERM,stop_requested)
        from app.controller import Controller as OriginalController
        from app import pipeline
        from isolated_pipeline_source_v2 import IsolatedLiveConfig,bind_pipeline,IsolatedPipelineSource
        original_source=bind_pipeline(pipeline)
        class TracedSource(IsolatedPipelineSource):
            def _accept(self,block,ipc):
                super()._accept(block,ipc)
                from dataclasses import fields
                item=dict(samples=len(block.audio),metadata={f.name:getattr(block,f.name) for f in fields(block) if f.name!='audio'},ipc=ipc,
                          audio_sha256=hashlib.sha256(block.audio.astype('<f4',copy=False).tobytes()).hexdigest())
                line=json.dumps(item,separators=(',',':'),allow_nan=False)+'\n'
                trace=self.facade.config_path.parent/'TRACE.jsonl'
                if trace.exists() and trace.stat().st_size+len(line.encode())>4*1024**2:raise RuntimeError('Source trace quota')
                with trace.open('a') as f:f.write(line)
                if self.sent>admission['maximum_accepted_samples']:raise RuntimeError('Accepted sample ceiling exceeded; preserve prefix and fail')
        pipeline.LivePipelineSource=TracedSource
        class Controller(OriginalController):
            def _live_config(self):
                directory=root/('source-epoch-'+str(self.epoch));directory.mkdir()
                cfg=dict(source_module='source_quiet_factory_v1',source_factory='create',capture=True,quiet_only=True,
                         prototype=str(source),case_directory=str(directory),backpressure_seconds=1,
                         authority=str(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json'),alsa_config=str(root/'alsa_hw_only_v1.conf'),
                         live_config=str(root/'LIVE_CONFIG_BACKUP.json'))
                with (directory/'CONFIG.json').open('x') as f:json.dump(cfg,f,indent=2)
                return IsolatedLiveConfig(directory/'CONFIG.json',source)
        from app.backends import backend_catalog
        memory('after_application_import')
        assert not any(k=='scipy' or k.startswith('scipy.') for k in sys.modules)
        controller=Controller(root/'data',Path.home()/'JustPeachy/install/models',saved_audio_only=False)
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        controller.session_action('new',audio=True,consent=True,title='Private autonomous quiet stream trial');controller.commands.join()
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
        memory('before_live_start')
        controller.start_live(consent=True);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        engine=controller.engine
        result['microphone_opened']=True
        result['sessions']=[dict(kind='autonomous_quiet',session_dir=str(engine.session_dir),epoch=controller.epoch)]
        capture_begin=time.monotonic();stop_requested_at=None
        while controller.state in ('RUNNING','STARTING','STOPPING'):
            record('live_running')
            if stop_requested_at is None and engine._source.sent>=admission['stop_at_samples']:
                stop_requested_at=dict(samples=engine._source.sent,monotonic=time.monotonic())
                result['stop_requested_at']=stop_requested_at
                controller.stop();controller.commands.join()
                result['stop_return_monotonic']=time.monotonic()
            if stop_requested_at is None and time.monotonic()-capture_begin>40:
                raise TimeoutError('Accepted capture did not reach 30s within 40s')
            time.sleep(.025)
        settle=time.monotonic()+1.35
        while time.monotonic()<settle:
            gui_pump();time.sleep(.05)
        final=controller.snapshot()
        if final['error']:raise RuntimeError(final['error'])
        result['sessions'][0]['source_samples']=engine._source.sent
        result['source_timeline']=engine._source.timing.snapshot()
        result['source_integrity']=engine._source.integrity
        result['source_stop_receipt']=engine._source.stop_receipt
        result['source_metadata']=engine._source.start_metadata
        n=engine._source.sent
        assert admission['stop_at_samples']<=n<=admission['maximum_accepted_samples']
        assert result['source_timeline']['model_samples_accepted']==n
        assert result['source_timeline']['native_frames_accepted']==n*3
        assert result['source_integrity']['ok']
        terminal=result['source_stop_receipt']['terminal'];close=terminal['source_close']
        assert terminal['fault'] is None and terminal['sent_samples']==n
        assert close['stream_closed'] and close['lease_released'] and not close['errors']
        assert all(v in ('RESTORED','ALREADY_RESTORED') for v in close['route_restoration'].values())
        assert result['source_stop_receipt']['child_exit']==0 and not result['source_stop_receipt']['forced_close']
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
        memory('terminal')
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
        result['speech_text_observed']=bool(final['rows'])  # Quiet input must not be scored as ASR failure.
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
        with (root/'REOPENED_ROWS.json').open('x') as stream:json.dump(reopened,stream,indent=2)
        controller.session_action('save');controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        assert controller.session_store.metadata(identifier)['pinned']
        controller.session_action('open',identifier=identifier);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        gui_pump();opened=controller.snapshot()
        assert len(opened['rows'])==len(final['rows'])
        fields=['id','caption_key','utterance_id','raw_asr_text','provisional_display_text','final_punctuated_display_text','label','final','profile_id','track_id','span_ids','source_start_sec','source_end_sec','timing_kind','word_spans','speaker_revision','first_shown_label','identity_version']
        for old,new in zip(final['rows'],opened['rows'],strict=True):
            assert {k:old.get(k) for k in fields}=={k:new.get(k) for k in fields},old['id']
        result['reopen_compared_fields']=fields
        ui.poll();ui._flush_rows();ui._render_rows(opened['rows'],force=True);gui_pump()
        with (root/'OPENED_SNAPSHOT.json').open('x') as stream:json.dump(opened,stream,indent=2)
        epochs=controller.session_store.metadata(identifier)['epochs'];assert len(epochs)==1
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
        result['status']='B01_ISOLATED_QUIET_COLLECTED_REQUIRES_INDEPENDENT_REVIEW'
    except Exception as exc:
        memory('exception')
        result['error']=type(exc).__name__+': '+str(exc)
    finally:
        if controller is not None:
            try:
                controller.close();controller.commands.join();controller.worker.join(10)
                result['controller_closed']=controller.closed
                result['controller_worker_alive']=controller.worker.is_alive()
                if controller.worker.is_alive():raise RuntimeError('Controller worker still alive')
                e=locals().get('engine') or getattr(controller,'engine',None)
                if e is not None:
                    src=e._source
                    result['terminal_source_samples']=getattr(src,'sent',None)
                    result['terminal_source_timeline']=src.timing.snapshot()
                    result['terminal_source_integrity']=src.integrity
                    result['terminal_source_stop_receipt']=src.stop_receipt
                    result['terminal_source_metadata']=src.start_metadata
                    if result.get('sessions'):result['sessions'][0]['source_samples']=getattr(src,'sent',None)
                if not controller.closed: raise RuntimeError('Controller failed to close')
            except Exception as exc:
                result['status']='FAILED_PRESERVED';result['closure_error']=type(exc).__name__+': '+str(exc)
        if tkroot is not None:
            tkroot.destroy();result['Tk_destroyed']=True
        if 'original_source' in locals():pipeline.LivePipelineSource=original_source
        result['new_capture_numerical_reference_pending']=True
        result['actual_device_tested']=True
        result['elapsed_seconds']=time.perf_counter()-began
        result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        result['ended_utc']=datetime.now(timezone.utc).isoformat()
        with (root/'RESULT.json').open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps({k:result.get(k) for k in ['status','error','controller_closed','elapsed_seconds','peak_rss_bytes']}),flush=True)
    return int(result['status']!='B01_ISOLATED_QUIET_COLLECTED_REQUIRES_INDEPENDENT_REVIEW')


if __name__=='__main__': raise SystemExit(main())
