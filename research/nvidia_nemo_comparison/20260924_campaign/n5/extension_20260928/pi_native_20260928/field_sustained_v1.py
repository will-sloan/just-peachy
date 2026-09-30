"""Installed GUI quiet Start/Stop boundary; README_FIELD_SUSTAINED_V1.md."""
import hashlib,json,os,resource,shutil,sys,threading,time
from pathlib import Path
from datetime import datetime,timezone


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)


def main():
    root=Path(__file__).resolve().parent;a=json.loads((root/'ADMISSION.json').read_text())
    installed=Path(a['installed_release']);data=root/'data'
    assert sorted(os.sched_getaffinity(0))==[2,3] and os.getuid()!=0
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    for row in a['files']:assert sha(row['path'])==row['sha256'],row['path']
    assert sha(installed/'RELEASE_MANIFEST.json')==a['release_manifest_sha256']
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    assert owner['boot_id']==a['boot_id'];save(root/'OWNER.json',owner)
    from field_sustained_envelope_v1 import record_envelope
    record_envelope(root,owner);threading.stack_size(1024**2)
    import ctypes
    libc=ctypes.CDLL(None);attr=(ctypes.c_ulong*32)();stack=ctypes.c_size_t()
    libc.pthread_getattr_default_np.argtypes=[ctypes.c_void_p]
    libc.pthread_attr_getstacksize.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t)]
    libc.pthread_attr_destroy.argtypes=[ctypes.c_void_p]
    assert libc.pthread_getattr_default_np(attr)==libc.pthread_attr_getstacksize(attr,ctypes.byref(stack))==libc.pthread_attr_destroy(attr)==0
    assert stack.value==1024**2
    from field_sustained_build_v1 import build,acquire
    installed=build(root,a)
    a=dict(a,release_manifest_sha256=sha(installed/'RELEASE_MANIFEST.json'))
    authority=json.loads((installed/'config/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json').read_text())
    assert authority['scheduled_quiet_capture_authorized'] and authority['quiet_audio_retention_authorized']
    assert sha(installed/'config/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')==a['authority_sha256']
    launch=dict(release_manifest_sha256=a['release_manifest_sha256'],autonomous_quiet_authorized=True,
                expires_unix=time.time()+300,data_root=str(data.resolve()),scope=a['scope'])
    save(root/'GUI_LAUNCH.json',launch)
    os.environ['ALSA_CONFIG_PATH']=str(installed/'config/alsa_hw_only_v1.conf')
    os.environ['ORT_DISABLE_TELEMETRY']='1';os.environ['NEMO_SPEECH_MEMSTATS']='1'
    save(root/'ALSA_ENVIRONMENT.json',dict(path=os.environ['ALSA_CONFIG_PATH'],process_local=True,sha256=sha(os.environ['ALSA_CONFIG_PATH'])))
    sys.path[:0]=[str(installed),str(installed/'vendor'),str(installed/'native')]
    from native import field_entry_v5 as entry
    from app import ui as ui_module
    from field_run_reporting_v1 import model_counters,completed_session
    lease_check,lease_close=acquire(root,a,installed)
    from app import live_audio
    assert live_audio.XVFLiveSource.__name__=='DetailedSource'
    from isolated_pipeline_source_v2 import IsolatedPipelineSource
    original_accept=IsolatedPipelineSource._accept
    def traced_accept(self,block,ipc):
        original_accept(self,block,ipc)
        from dataclasses import fields
        item=dict(samples=len(block.audio),metadata={f.name:getattr(block,f.name) for f in fields(block) if f.name!='audio'},ipc=ipc,
                  audio_sha256=hashlib.sha256(block.audio.astype('<f4',copy=False).tobytes()).hexdigest())
        line=json.dumps(item,separators=(',',':'),allow_nan=False)+'\n';trace=self.facade.config_path.parent/'TRACE.jsonl'
        if trace.exists() and trace.stat().st_size+len(line.encode())>12*1024**2:raise RuntimeError('Source trace quota')
        with trace.open('a') as f:f.write(line)
        if self.sent>a['maximum_accepted_samples']:raise RuntimeError('Accepted sample ceiling; prefix retained, run failed')
    IsolatedPipelineSource._accept=traced_accept
    original_ui=ui_module.PrototypeUI;holder={};errors=[];began=time.monotonic();phase='idle';start_requested=None
    result=dict(status='FAILED_PRESERVED',owner=owner,sessions=[],callback_detail_bound=True,
        startup_stack_rlimit_bytes=list(resource.getrlimit(resource.RLIMIT_STACK)),native_default_thread_stack_bytes=stack.value,
        actions=[],observations=[],callback_errors=errors,root_withdrawn=False,physical_touch=False,
        new_capture_numerical_reference_pending=True,field_release_accepted=False,installed_release=str(installed))
    def action(name):result['actions'].append(dict(name=name,monotonic=time.monotonic()))
    def invoke(key):
        b=holder['ui'].actions[key];assert b.winfo_exists() and str(b.cget('state'))=='normal';b.invoke()
    def photograph(name):
        # No repeated screenshot/readability test; preserve programmatic geometry.
        u=holder['ui'];u.root.update_idletasks()
        assert u.root.winfo_viewable() and (u.root.winfo_width(),u.root.winfo_height())==(480,800)
        result['observations'].append(dict(name=name,width=480,height=800,mapped=True,lease=lease_check()))
    def failed(exc):
        if not errors:errors.append(type(exc).__name__+': '+str(exc))
        holder['ui'].close()
    def complete():
        u=holder['ui'];c=u.controller;e=holder['engine'];s=e._source;n=s.sent
        assert a['stop_at_samples']<=n<=a['maximum_accepted_samples'] and not c.error,c.error
        assert s.integrity['ok'] and s.facade.closed and s.stop_receipt['child_exit']==0 and not s.stop_receipt['forced_close']
        result.update(source_timeline=s.timing.snapshot(),source_integrity=s.integrity,source_stop_receipt=s.stop_receipt,
            source_metadata=s.start_metadata,stop_return_monotonic=time.monotonic(),row_count=len(c.snapshot()['rows']),
            model_load_counts=model_counters(c.models),
            redim_encoder_loaded=c.models.speakers is not None and getattr(c.models.speakers,'_redim',None) is not None,
            no_scipy_loaded=not any(k=='scipy' or k.startswith('scipy.') for k in sys.modules))
        epoch_paths=list((data/'conversations').glob('*/epochs/*/epoch.json'));assert len(epoch_paths)==1
        epoch=json.loads(epoch_paths[0].read_text())
        result['sessions'][0]['session_dir']=completed_session(epoch,data/'sessions',n)
        result['lease_after_drain']=lease_check()
        final=c.snapshot();save(root/'FINAL_SNAPSHOT.json',final)
        c.session_action('save');c.commands.join();assert not c.error,c.error
        identifier=c.conversation_id;assert c.session_store.metadata(identifier)['pinned']
        c.session_action('open',identifier=identifier);c.commands.join();assert not c.error,c.error
        opened=c.snapshot();fields=['id','caption_key','utterance_id','raw_asr_text','provisional_display_text','final_punctuated_display_text','label','final','profile_id','track_id','span_ids','source_start_sec','source_end_sec','timing_kind','word_spans','speaker_revision','first_shown_label','identity_version']
        assert len(final['rows'])==len(opened['rows'])
        for old,new in zip(final['rows'],opened['rows']):assert {k:old.get(k) for k in fields}=={k:new.get(k) for k in fields}
        save(root/'OPENED_SNAPSHOT.json',opened);result['controller_save_open']=True
        result['reopen_compared_fields']=fields
        u.snapshot=opened;u.home();u._render_rows(opened['rows'],force=True)
        action('Stop_drained_and_controller_Save_Open');result['status']='INSTALLED_GUI_QUIET_COLLECTED_REQUIRES_INDEPENDENT_REVIEW'
        u.root.after(600,finish)
    def finish():
        try:photograph('stopped');action('visible_stopped');holder['ui'].close()
        except Exception as exc:failed(exc)
    def step():
        nonlocal phase,start_requested
        try:
            u=holder['ui'];c=u.controller
            if time.monotonic()-began>280:raise TimeoutError('Installed GUI protocol wall bound')
            if c.error:raise RuntimeError(c.error)
            if phase=='idle':
                assert c.engine is None and c.state=='IDLE' and c.models.asr_loads==c.models.speaker_loads==0
                photograph('idle')
                # Prepare a new private audio archive through the unchanged controller API.
                c.session_action('new',audio=True,consent=True,title='Private 120-second sustained quiet trial');c.commands.join()
                assert not c.error;c.settings['microphone_preapproved']=False;u._mic_consented=False
                u.snapshot=c.snapshot();u.home();invoke('start_stop');assert u.page=='consent';action('Start_opened_consent')
                phase='consent';u.root.after(600,step);return
            if phase=='consent':
                photograph('consent');invoke('confirm');action('authorized_quiet_Start_confirmed');start_requested=time.monotonic();phase='running'
            e=c.engine
            if e is not None and 'engine' not in holder:
                holder['engine']=e;result['sessions']=[dict(kind='installed_GUI_quiet',epoch=c.epoch)]
            if phase=='running':
                if time.monotonic()-start_requested>185:raise TimeoutError('Installed startup plus capture progress bound')
                if e is not None and e._source is not None and e._source.sent>=a['stop_at_samples']:
                    assert c.state=='RUNNING','Installed automatic limit won before GUI Stop'
                    u.snapshot=c.snapshot();u._show_status()
                    result['lease_at_stop']=lease_check()
                    result['stop_requested_at']=dict(samples=e._source.sent,monotonic=time.monotonic(),via='actual_GUI_start_stop_button')
                    invoke('start_stop');action('GUI_Stop_invoked');phase='stopping'
                elif e is not None and e._source is not None and e._source.sent>=960000 and not holder.get('running_shot'):
                    photograph('running');holder['running_shot']=True
            elif phase=='stopping':
                if time.monotonic()-result['stop_requested_at']['monotonic']>65:raise TimeoutError('GUI Stop drain bound')
                if c.engine is None and not c.commands.unfinished_tasks:
                    phase='complete';complete();return
            u.root.after(20,step)
        except Exception as exc:failed(exc)
    class ScheduledUI(original_ui):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);holder['ui']=self
            self.root.report_callback_exception=lambda kind,value,tb:failed(value)
            self.root.after(700,step)
    ui_module.PrototypeUI=ScheduledUI;argv=sys.argv[:]
    try:
        sys.argv=[str(installed/'main.py'),'gui','--data-root',str(data),'--launch-admission',str(root/'GUI_LAUNCH.json')]
        code=entry.main();assert code==0
        if errors:raise RuntimeError('; '.join(errors))
        assert phase=='complete' and result['status']=='INSTALLED_GUI_QUIET_COLLECTED_REQUIRES_INDEPENDENT_REVIEW'
    except Exception as exc:result.update(status='FAILED_PRESERVED',error=type(exc).__name__+': '+str(exc))
    finally:
        sys.argv=argv;ui_module.PrototypeUI=original_ui;IsolatedPipelineSource._accept=original_accept
        u=holder.get('ui');c=None if u is None else u.controller;e=holder.get('engine')
        result.update(controller_closed=bool(c and c.closed),controller_worker_alive=bool(c and c.worker.is_alive()),Tk_destroyed=bool(c and c.closed))
        if e is not None:
            s=e._source;result['terminal_source_samples']=getattr(s,'sent',0)
            result['terminal_source_timeline']=s.timing.snapshot() if s.timing else None
            result['terminal_source_integrity']=s.integrity;result['terminal_source_stop_receipt']=s.stop_receipt
            result['terminal_source_metadata']=s.start_metadata
            result['sessions'][0]['source_samples']=getattr(s,'sent',0)
            if 'session_dir' not in result['sessions'][0]:
                epochs=list((data/'conversations').glob('*/epochs/*/epoch.json'))
                if len(epochs)==1:
                    value=json.loads(epochs[0].read_text()).get('native_session_path')
                    if isinstance(value,str) and value!='None' and Path(value).parent==data/'sessions':result['sessions'][0]['session_dir']=value
        try:result['lease_closure']=lease_close()
        except Exception as exc:result.update(status='FAILED_PRESERVED',closure_error=type(exc).__name__+': '+str(exc))
        result.update(elapsed_seconds=time.monotonic()-began,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        save(root/'RESULT.json',result)
    print(json.dumps({k:result.get(k) for k in ('status','error','terminal_source_samples','elapsed_seconds','peak_rss_bytes')}),flush=True)
    return int(result['status']!='INSTALLED_GUI_QUIET_COLLECTED_REQUIRES_INDEPENDENT_REVIEW')


if __name__=='__main__':raise SystemExit(main())
