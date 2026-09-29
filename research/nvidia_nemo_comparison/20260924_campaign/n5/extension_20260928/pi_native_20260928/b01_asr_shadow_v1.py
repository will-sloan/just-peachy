"""Native shared-controller B05 passage/memory/drain probe. See README_ASR_SHADOW_V1.md."""
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
    result=dict(status='FAILED_PRESERVED',owner=owner,native_CM5=True,stage_accepted=False,
                GUI_tested=False,microphone_opened=False,saved_audio_accuracy_scoring=False,
                scope='B01 online ASR/energy cue observation with post-session causal shadow policy replay; all converted source audio feeds unchanged D1; no applied gating or speedup claim')
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
        # Inject only a diagnostic saved producer; never instantiate capture or a device.
        from asr_shadow_v1 import Shadow
        from app.n2_pipeline import N2Engine
        original_emit=N2Engine._emit;active_shadow=[None]
        def observed_emit(engine,event_type,source_sec,payload):
            answer=original_emit(engine,event_type,source_sec,payload)
            if event_type=='s6d_text_ready' and active_shadow[0] is not None:active_shadow[0].cue(payload)
            return answer
        N2Engine._emit=observed_emit
        from app import pipeline as pipeline_module
        from app.live_audio import StreamingDecimator
        import numpy as np
        class Constructed48kSource(pipeline_module.FileSource):
            def _run(self):
                converter=StreamingDecimator();digest=hashlib.sha256();input_digest=hashlib.sha256()
                calls=0;work=0.;native=0
                try:
                    with pipeline_module.sf.SoundFile(self.path) as handle:
                        handle.seek(self.start_sample)
                        assert self.start_sample==0
                        origin=time.perf_counter();self.shadow=Shadow(origin);active_shadow[0]=self.shadow;pacer=pipeline_module.AbsolutePacer(origin,16000,self.stop_event)
                        self.callback('source_started',{'source_epoch_monotonic_sec':origin,'mode':'constructed_saved_48k','path':str(self.path),'start_sample':0,'gain':1.,'pacing':'absolute','filter_delay_seconds':.001,'constructed_zero_order_hold':True,'not_capture':True})
                        while not self.stop_event.is_set():
                            raw=handle.read(320,dtype='float32')
                            if not len(raw):break
                            if pacer.wait_for_end(self.sent+len(raw)) is None:break
                            expanded=np.repeat(raw,3);before=expanded.tobytes();start=time.perf_counter()
                            output=converter.convert(expanded);work+=time.perf_counter()-start
                            assert expanded.tobytes()==before and len(output)==len(raw) and np.isfinite(output).all()
                            self.shadow.audio(self.sent,output);self.journal.append(output);self.sent+=len(output);native+=len(expanded);calls+=1
                            digest.update(output.tobytes());input_digest.update(before)
                            assert converter.native_count==native==3*self.sent
                    self.journal.finish()
                except Exception as exc:
                    self.journal.finish(str(exc));self.callback('fatal',{'reason':str(exc)})
                finally:
                    self.conversion=dict(native_samples=native,model_samples=self.sent,calls=calls,work_seconds=work,output_float32_sha256=digest.hexdigest(),input_float32_sha256=input_digest.hexdigest(),filter_delay_seconds=converter.delay_seconds,constructed_only=True,no_appended_tail=True)
        pipeline_module.FileSource=Constructed48kSource
        from app.controller import Controller
        from app.backends import backend_catalog
        memory('after_application_import')
        assert not any(k=='scipy' or k.startswith('scipy.') for k in sys.modules)
        controller=Controller(root/'data',Path.home()/'JustPeachy/install/models',saved_audio_only=True)
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
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
        controller.start_file(root/'source.wav');controller.commands.join()
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
        result['early_conversion']=first_engine._source.conversion
        with (root/'SHADOW_EARLY.json').open('x') as f:json.dump(first_engine._source.shadow.report(first_samples),f,indent=2)
        assert 0<first_samples<715127
        result['sessions'].append(dict(kind='early_stop',session_dir=first_session,epoch=first_epoch,source_samples=first_samples,samples_at_stop_request=samples_at_stop_request,stop_requested_monotonic=stop_requested,stop_completed_monotonic=time.monotonic()))
        with (root/'EARLY_STOP.json').open('x') as f:json.dump(result['sessions'][0],f,indent=2)
        first_engine_ref=weakref.ref(first_engine)
        del first_engine, stopped
        result['harness_retains_early_engine']=False
        result['early_engine_alive_after_release']=first_engine_ref() is not None
        # start_file deliberately resets the source offset; reuse this controller/model cache.
        controller.start_file(root/'source.wav');controller.commands.join()
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
        result['full_conversion']=second_engine._source.conversion
        with (root/'SHADOW_FULL.json').open('x') as f:json.dump(second_engine._source.shadow.report(second_engine._source.sent),f,indent=2)
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
        result['status']='B01_ASR_SHADOW_COLLECTED_REQUIRES_REVIEW'
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
        result['elapsed_seconds']=time.perf_counter()-began
        result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        result['ended_utc']=datetime.now(timezone.utc).isoformat()
        with (root/'RESULT.json').open('x') as f: json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__': raise SystemExit(main())
