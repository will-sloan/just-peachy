"""Single application owner: commands, models, capture, people and caption epochs."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import queue
import re
import shutil
import threading
import time
import uuid
import numpy as np
from .paths import ROOT, ApplicationLock, pipeline_config, read_json, atomic_json
from .pipeline import MODES, RECIPES, ResidentModels, PrototypeEngine, effective_profile
from .people import PersonalStore, PREPROCESSING
from .enrollment_quality import EnrollmentQuality


class Controller:
    def __init__(self,data_root,models_root,*,writer_delay=0):
        self.data_root=Path(data_root).resolve();self.models_root=Path(models_root).resolve()
        self.owner=ApplicationLock(self.data_root)
        try:self._initialize(writer_delay)
        except BaseException:
            self.owner.close()
            raise

    def _initialize(self,writer_delay):
        self.config=pipeline_config(self.data_root,self.models_root)
        self.models=ResidentModels();self.writer_delay=writer_delay
        self.store=PersonalStore(self.data_root/'people',self.config.asset('redimnet2_b2_fp32').sha256)
        self.lock=threading.RLock();self.commands=queue.Queue(32)
        self.engine=None;self.consumer=None;self.epoch=0;self.rows=OrderedDict()
        self.source_kind=None;self.file_path=None;self.file_offset=0;self.live_consent=False
        self.mode='caption_only';self.recipe='fast';self.tap='O0';self.selected_ids=[];self.strict=False
        self.state='IDLE';self.status='Ready. Microphone is off.';self.error=None
        self.closed=False;self.transitions=[];self.metrics={'completed_sessions':0,'events_consumed':0,'retired_rows':0}
        self.settings=read_json(self.data_root/'settings.json') if (self.data_root/'settings.json').exists() else {}
        self.enrollment={'state':'IDLE','can_save':False};self._enroll_audio=[];self._enroll_vector=None
        self._enroll_thread=None;self._enroll_stop=threading.Event();self._enroll_live=None
        self._quality_thread=None;self._quality_queue=None;self._quality=None;self._enroll_integrity=None
        self.output_defaults=[];self._observe_output('application_open')
        self.worker=threading.Thread(target=self._commands,name='proto-controller',daemon=True);self.worker.start()

    def _observe_output(self,stage):
        try:
            from .windows_audio import endpoint_snapshot
            value=endpoint_snapshot()
            self.output_defaults.append({'stage':stage,'value':value})
            self.output_defaults=self.output_defaults[-64:]
        except Exception as exc:self.output_defaults.append({'stage':stage,'error':str(exc)})

    def _enqueue(self,action,*args,**kwargs):
        if self.closed:raise RuntimeError('Application closed')
        try:self.commands.put_nowait((action,args,kwargs))
        except queue.Full:raise RuntimeError('Too many pending actions; wait for the current transition')

    def _commands(self):
        while True:
            item=self.commands.get()
            try:
                if item is None:return
                action,args,kwargs=item
                self.error=None
                getattr(self,'_do_'+action)(*args,**kwargs)
            except Exception as exc:
                self.error=f'{type(exc).__name__}: {exc}';self.status=self.error
                if self.state not in ('RUNNING','ENROLLING'):self.state='ERROR'
            finally:self.commands.task_done()

    def route(self):
        return {'tap':self.tap,'sample_rate':16000,'gain_policy':'O0_host_plus3dB_once' if self.tap=='O0' else 'O1_unity',
                'preprocessing':PREPROCESSING,'waveform_domain':'xvf_ua',
                'source':'verified_live_or_already_gained_file'}

    def _live_config(self):
        from .live_audio import LiveConfig
        path=self.data_root/'live_config.json'
        if not path.exists():raise ValueError('XVF site configuration missing. See docs/LIVE_AUDIO.md')
        value=read_json(path);value.update(tap=self.tap,evidence_dir=str(self.data_root/'device_receipts'))
        return LiveConfig(**value)

    def start_live(self,consent=False):
        if consent is not True:raise ValueError('Visible microphone consent is required')
        self._enqueue('start_live')
    def _do_start_live(self):
        self._stop_session();self._ensure_no_enrollment()
        self.source_kind='live';self.live_consent=True;self._start_session()

    def start_file(self,path):self._enqueue('start_file',str(path))
    def _do_start_file(self,path):
        candidate=Path(path).resolve()
        named_tap={'o0':'O0','o1':'O1','o0_continuous':'O0','o1_continuous':'O1'}.get(candidate.stem.lower())
        if named_tap and named_tap!=self.tap:
            raise ValueError(f'Prepared WAV name declares {named_tap}, but selected tap is {self.tap}. Select the matching tap before loading it.')
        self._stop_session();self._ensure_no_enrollment()
        self.file_path=candidate;self.file_offset=0;self.source_kind='file';self._start_session()

    def _start_session(self):
        self._retention()
        self.state='STARTING';self.status='Loading the selected recipe…';self.epoch+=1
        profile=effective_profile(self.recipe,self.mode,self.tap)
        gallery=self.store.gallery(self.route()) if self.mode in ('enrolled_names','open_with_names','selected_focus') else None
        engine=PrototypeEngine(self.config,self.models,profile,gallery,self.mode,writer_delay=self.writer_delay,
                               ram_horizon_sec=self.settings.get('ram_horizon_sec',120))
        self.engine=engine
        try:
            if self.source_kind=='file':engine.start_prepared_file(self.file_path,self.file_offset)
            else:engine.start_xvf(self._live_config())
        except BaseException:
            self._stop_session()
            raise
        epoch=self.epoch
        self.state='RUNNING';self.status=('Microphone listening' if self.source_kind=='live' else 'File replay (source paced)')+' · '+self.mode
        self.consumer=threading.Thread(target=self._consume,args=(engine,epoch),name='proto-caption-consumer',daemon=True)
        self.consumer.start();self._observe_output('session_start')

    def _consume(self,engine,epoch):
        try:
            while True:
                drained=False
                while True:
                    try:event=engine.events.get(block=False)
                    except queue.Empty:break
                    drained=True;self.metrics['events_consumed']+=1
                    if event.event_type=='s6d_display':
                        row=dict(event.payload)
                        key=row.get('caption_key') or str(row.get('session_id'))+'/'+str(row.get('utterance_id'))
                        if epoch==self.epoch:
                            with self.lock:
                                self.rows[key]=row
                                while len(self.rows)>512:
                                    self.rows.popitem(last=False);self.metrics['retired_rows']+=1
                    elif event.event_type in ('fatal','failure'):
                        # Keep the originating failure; shutdown can emit a
                        # secondary source-closure error after a lane fails.
                        if not self.error:self.error=str(event.payload.get('reason',event.payload))
                done=engine._finalization_thread is not None and not engine._finalization_thread.is_alive()
                if done and engine.events.empty():break
                if not drained:time.sleep(.02)
            engine.record_s6d_consumer_closure('PROTO1 controller; GUI snapshot from fully drained event consumer')
            self.metrics['completed_sessions']+=1
            self.metrics['last_session']=str(engine.session_dir)
            self.metrics['last_state']=engine.state
            self.metrics['last_telemetry']=engine.telemetry()
            self.metrics['model_cache']={'asr_loads':self.models.asr_loads,'speaker_loads':self.models.speaker_loads,'streams':self.models.streams}
            self.metrics['gallery_queries']=engine._research_gallery.query_count if engine._research_gallery else 0
            if epoch==self.epoch:
                if engine.state=='FAILED' or engine._finalization_error:
                    self.state='ERROR';self.error=self.error or str(engine._finalization_error or engine.telemetry());self.status='Session failed. Stop/restart for a fresh audio epoch.'
                elif self.state!='SWITCHING':self.state='STOPPED';self.status='Stopped. Microphone released.'
        except Exception as exc:
            self.error=repr(exc);self.state='ERROR';self.status='Caption consumer failed: '+str(exc)

    def stop(self):self._enqueue('stop')
    def _do_stop(self):
        if self.enrollment.get('state')=='RECORDING':self._do_enrollment_stop()
        self._stop_session();self.source_kind=None;self.state='STOPPED';self.status='Stopped. Microphone released.'

    def _stop_session(self):
        engine=self.engine
        if engine is None:return
        self.state='STOPPING';self.status='Stopping capture and finishing pending words…'
        failures=[]
        try:engine.stop()
        except Exception as exc:failures.append(repr(exc))
        # A failed prelaunch may have opened journals but not installed a watcher.
        if engine._finalization_thread is None and engine._journal is not None:
            try:engine._fail('Partial startup cancelled before capture')
            except Exception as exc:failures.append(repr(exc))
            engine._finalization_thread=threading.Thread(target=engine._watch_session,name='proto-startup-cleanup',daemon=True)
            engine._finalization_thread.start()
        try:engine.wait_for_completion(90)
        except Exception as exc:failures.append(repr(exc))
        if self.consumer and self.consumer is not threading.current_thread():self.consumer.join(15)
        if self.consumer and self.consumer.is_alive():raise RuntimeError('Previous caption consumer still owns the epoch')
        owned_threads=list(engine._threads)
        if engine._finalization_thread:owned_threads.append(engine._finalization_thread)
        source_thread=getattr(engine._source,'thread',None)
        if source_thread:owned_threads.append(source_thread)
        owned_threads.extend(w.thread for w in engine.text_writers)
        for worker in (engine._s6d_writer,engine._s6d_punctuation,
                       getattr(engine._scheduler,'worker',None),engine._s7_trace):
            if worker is not None and getattr(worker,'thread',None):owned_threads.append(worker.thread)
        if any(t.is_alive() for t in owned_threads if t is not threading.current_thread()):
            raise RuntimeError('Previous session still has live workers; its owner cannot be released')
        live=getattr(engine._source,'live',None)
        if live and live.status().get('started') and not live.status().get('finished'):
            raise RuntimeError('Microphone still active; ownership retained')
        if live:
            try:stream_active=bool(live.stream and live.stream.active)
            except Exception:stream_active=False  # Closed PortAudio handles reject queries.
            if stream_active:raise RuntimeError('PortAudio stream remains active; ownership retained')
        if self.consumer is None:
            while not engine.events.empty():engine.events.get(block=False)
            if engine.session_dir:engine.record_s6d_consumer_closure('PROTO1 failed-start cleanup')
        if self.source_kind=='file':self.file_offset+=getattr(engine._source,'sent',0)
        if failures:
            self.error='; '.join(failures);self.metrics['last_terminal_failures']=failures
        self.engine=None;self.consumer=None
        self._observe_output('session_stop')

    def switch(self,mode=None,recipe=None,tap=None,selected_ids=None,strict=None):
        self._enqueue('switch',mode,recipe,tap,selected_ids,strict)
    def _do_switch(self,mode,recipe,tap,selected_ids,strict):
        self._ensure_no_enrollment()
        mode=mode or self.mode;recipe=recipe or self.recipe;tap=tap or self.tap
        if mode not in MODES:raise ValueError('Unknown mode')
        if recipe=='fast' and mode!='caption_only' and recipe==self.recipe:recipe='balanced'
        effective_profile(recipe,mode,tap)
        if self.state=='RUNNING' and self.source_kind=='file' and tap!=self.tap:
            raise ValueError('Stop file replay and load the actual other-tap prepared WAV before changing its audio domain.')
        ids=self.selected_ids if selected_ids is None else list(dict.fromkeys(selected_ids))
        if set(ids)-{p['id'] for p in self.store.list()}:raise ValueError('Selected person no longer exists')
        if strict and (mode!='selected_focus' or not ids):raise ValueError('Experimental strict focus requires selected people')
        running=self.state=='RUNNING'
        old={'mode':self.mode,'recipe':self.recipe,'tap':self.tap,'epoch':self.epoch}
        self._stop_session();self.state='SWITCHING'
        self.mode,self.recipe,self.tap=mode,recipe,tap;self.selected_ids=ids
        self.strict=bool(strict if strict is not None else self.strict) if mode=='selected_focus' else False
        self.transitions.append({'from':old,'to':{'mode':mode,'recipe':recipe,'tap':tap},'monotonic':time.perf_counter()})
        self.transitions=self.transitions[-128:]
        self._observe_output('mode_switch')
        if running:
            if self.source_kind=='file':
                import soundfile as sf
                if self.file_offset>=sf.info(self.file_path).frames:running=False
            if running:self._start_session()
        if not running:self.state='IDLE';self.status='Selection ready. Press Start to listen.'

    def _ensure_no_enrollment(self):
        if self.enrollment.get('state') in ('RECORDING','ANALYZING','READY'):
            raise ValueError('Save or cancel the current enrollment first')
        # A failed cancellation may still own capture/quality workers. The
        # ERROR label alone must never permit overwriting that live owner.
        self._assert_enrollment_quiet()

    def enrollment_start(self,name,target_sec=30,consent=False,person_id=None):
        if consent is not True:raise ValueError('Explicit person/enrollment microphone consent required')
        self._enqueue('enrollment_start',name,int(target_sec),person_id)
    def _do_enrollment_start(self,name,target_sec,person_id):
        from .people import clean_name
        from .live_audio import XVFLiveSource
        name=clean_name(name)
        if target_sec not in (15,30,60):raise ValueError('Choose15,30or60 seconds')
        self._ensure_no_enrollment();self._stop_session();self.source_kind=None
        self.enrollment={'state':'LOADING','name':name,'person_id':person_id,'target_sec':target_sec,
            'elapsed_s':0.,'usable_s':0.,'level':0.,'clipping':0.,'can_save':False,'gaps':0}
        self.models.enrollment_models(self.config)
        self._enroll_audio=[];self._enroll_vector=None;self._enroll_stop.clear()
        self._enroll_live=None;self._enroll_thread=None;self._quality_thread=None
        self._quality=None;self._quality_queue=None;self._enroll_integrity=None
        try:
            self._enroll_live=XVFLiveSource(self._live_config());self._enroll_live.start(consent=True)
            self._enroll_route={**self.route(),'live_capture':deepcopy(self._enroll_live.metadata),
                'source_session_id':str(uuid.uuid4()),'native_rate':self._enroll_live.config.native_rate}
            self._quality=EnrollmentQuality(self.models.speakers,self.config,target_sec)
            self._quality_queue=queue.Queue(20)
            self._quality_thread=threading.Thread(target=self._quality_loop,name='proto-enrollment-quality',daemon=True)
            self._quality_thread.start()
            self.enrollment['state']='RECORDING';self.state='ENROLLING';self.status='Recording enrollment; read the paragraph.'
            self._enroll_thread=threading.Thread(target=self._record_enrollment,name='proto-enrollment',daemon=True);self._enroll_thread.start()
        except Exception as exc:
            # A quality/thread setup failure can occur after opening capture.
            # Wake a waiting quality worker even if no capture worker started.
            self._enroll_stop.set()
            if self._quality_queue is not None:
                try:self._quality_queue.put_nowait(None)
                except queue.Full:pass
            detail='Enrollment startup failed: '+str(exc)
            try:self._do_enrollment_cancel()
            except Exception as cleanup:detail+='; shutdown: '+str(cleanup)
            self.enrollment.update(state='ERROR',can_save=False,gaps=1,error=detail)
            self.state='ERROR';self.status=detail;self.error=detail
            raise RuntimeError(detail) from exc

    def _quality_loop(self):
        while True:
            block=self._quality_queue.get()
            try:
                if block is None:return
                self._quality.process(block)
                q,_=self._quality.result()
                self.enrollment.update(usable_s=q['usable_s'],clipping=q['clipping'],
                    analyzed_s=q['elapsed_s'],model_segment_calls=q['model_segment_calls'],
                    model_embedding_calls=q['model_embedding_calls'])
            except Exception as exc:
                self.enrollment.update(error=repr(exc),gaps=1,can_save=False)
            finally:self._quality_queue.task_done()

    def _record_enrollment(self):
        count=0;pending=[];pending_count=0
        try:
            while not self._enroll_stop.is_set() and count<180*16000:
                block=self._enroll_live.read(.25)
                if block is None:continue
                # Capture drainage performs no inference. Only complete unique10s
                # chunks go to one bounded quality worker; each is analyzed once.
                pending.append(block.audio.copy());count+=len(block.audio);pending_count+=len(block.audio)
                self.enrollment.update(elapsed_s=count/16000,level=float(np.sqrt(np.mean(block.audio.astype(np.float64)**2))))
                if pending_count>=160000:
                    samples=np.concatenate(pending)
                    self._quality_queue.put_nowait(samples[:160000])
                    tail=samples[160000:];pending=[tail] if len(tail) else [];pending_count=len(tail)
        except Exception as exc:
            self.enrollment.update(error=str(exc),gaps=1,can_save=False);self.error=str(exc)
        finally:
            try:
                if pending_count:self._quality_queue.put_nowait(np.concatenate(pending))
                self._quality_queue.put(None,timeout=10)
                from .live_audio import summarize_live_integrity
                self._enroll_live.stop()
                self._enroll_integrity=summarize_live_integrity(self._enroll_live)
                if not self._enroll_integrity['ok']:
                    self.enrollment.update(gaps=1,can_save=False,error='Live capture/restore integrity failed')
            except Exception as exc:self.enrollment.update(gaps=1,error=repr(exc),can_save=False)
            if not self._enroll_stop.is_set():self._enqueue('enrollment_stop')

    def enrollment_stop(self):self._enqueue('enrollment_stop')
    def _do_enrollment_stop(self):
        self._enroll_stop.set()
        if self._enroll_thread:self._enroll_thread.join(30)
        if self._enroll_thread and self._enroll_thread.is_alive():raise RuntimeError('Enrollment capture did not stop')
        if self._quality_thread:self._quality_thread.join(60)
        if self._quality_thread and self._quality_thread.is_alive():raise RuntimeError('Enrollment quality worker did not drain')
        if self._enroll_live:
            from .live_audio import summarize_live_integrity
            self._enroll_live.stop();self._enroll_integrity=summarize_live_integrity(self._enroll_live)
            if not self._enroll_integrity['ok']:
                self.enrollment.update(gaps=1,error='Live capture/restore integrity failed')
        self.enrollment['state']='ANALYZING';self.status='Checking unique usable speech…'
        quality,vector=self._quality.result(gaps=self.enrollment.get('gaps',0))
        quality.update(source_session_id=self._enroll_route['source_session_id'],capture_integrity=self._enroll_integrity)
        self._enroll_vector=vector
        self.enrollment.update(quality,state='READY');self.state='IDLE'
        self.status='Enrollment ready to save.' if quality['can_save'] else 'Not enough clean unique speech. Cancel and record a longer sample.'
        self._observe_output('enrollment_stop')

    def enrollment_save(self):self._enqueue('enrollment_save')
    def _do_enrollment_save(self):
        self._assert_enrollment_quiet()
        if not self._enroll_integrity or not self._enroll_integrity['ok']:
            raise RuntimeError('Enrollment capture integrity must pass before saving')
        row=self.store.save(self.enrollment['name'],self._enroll_vector,self.enrollment,self._enroll_route,person_id=self.enrollment.get('person_id'))
        self._discard_enrollment_buffers()
        self.enrollment.update(state='SAVED',can_save=False,person_id=row['id'])
        self.status='Person saved. Try different fresh speech in Enrolled names mode.'

    def _assert_enrollment_quiet(self):
        for worker,label in ((self._enroll_thread,'capture'),(self._quality_thread,'quality')):
            if worker and worker.is_alive():
                raise RuntimeError('Enrollment '+label+' worker still active; ownership retained')
        live=self._enroll_live
        if live is not None:
            stream=getattr(live,'stream',None)
            try:active=bool(stream and stream.active)
            except Exception:active=bool(stream and not getattr(stream,'closed',False))
            if active or (live.status().get('started') and not live.status().get('finished')):
                raise RuntimeError('Enrollment microphone still active; ownership retained')

    def _discard_enrollment_buffers(self):
        # Metadata-only integrity/provenance survives; audio and unsaved
        # per-window embeddings are released only after all owners finish.
        self._assert_enrollment_quiet()
        self._enroll_audio=[];self._enroll_vector=None
        self._enroll_live=None;self._quality=None;self._quality_queue=None
        self._enroll_thread=None;self._quality_thread=None

    def enrollment_cancel(self):self._enqueue('enrollment_cancel')
    def _do_enrollment_cancel(self):
        self._enroll_stop.set()
        self.enrollment['can_save']=False
        try:
            # Unstarted Thread objects occur when startup fails; joining them
            # raises before any cleanup. Started/completed workers are joined.
            if self._enroll_thread and getattr(self._enroll_thread,'ident',1) is not None:self._enroll_thread.join(30)
            if self._enroll_thread and self._enroll_thread.is_alive():raise RuntimeError('Enrollment capture still active; cancellation pending')
            integrity=None
            if self._enroll_live:
                from .live_audio import summarize_live_integrity
                self._enroll_live.stop()
                integrity=self._enroll_integrity=summarize_live_integrity(self._enroll_live)
            if self._quality_thread and getattr(self._quality_thread,'ident',1) is not None:self._quality_thread.join(60)
            if self._quality_thread and self._quality_thread.is_alive():raise RuntimeError('Enrollment quality still active; cancellation pending')
            self._discard_enrollment_buffers()
            if integrity and not integrity['ok']:
                raise RuntimeError('Enrollment shutdown integrity failed: '+', '.join(integrity['reasons']))
            self.enrollment={'state':'IDLE','can_save':False}
            self.state='IDLE';self.status='Enrollment cancelled; temporary audio discarded.'
        except Exception as exc:
            self.enrollment.update(state='ERROR',can_save=False,gaps=1,error=str(exc))
            self.state='ERROR';self.status='Enrollment shutdown needs review: '+str(exc)
            raise

    def rename_person(self,identifier,name):self._enqueue('person_mutation','rename',identifier,name)
    def delete_person(self,identifier):self._enqueue('person_mutation','delete',identifier)
    def _do_person_mutation(self,operation,*args):
        self._ensure_no_enrollment();self._stop_session();getattr(self.store,operation)(*args)
        self.selected_ids=[i for i in self.selected_ids if i in {p['id'] for p in self.store.list()}]
        if not self.selected_ids:self.strict=False
        # Invalidate cached identity spelling/UUID assignments; old acoustic words survive.
        with self.lock:
            for row in self.rows.values():
                row.update(known_profile_id=None,known_name=None,naming_state='invalidated',label='Unknown')
                for segment in row.get('segments',[]):segment.update(known_profile_id=None,known_name=None,naming_state='invalidated',label='Unknown')
        self.state='IDLE';self.status='People updated. Start creates a fresh identity epoch.'

    def export_people(self,path,consent=False):self._enqueue('export_people',str(path),consent)
    def _do_export_people(self,path,consent):self.store.export(path,consent);self.status='Private unencrypted export saved.'
    def import_people(self,path,consent=False):self._enqueue('import_people',str(path),consent)
    def _do_import_people(self,path,consent):
        self._ensure_no_enrollment();self._stop_session();self.store.import_archive(path,consent);self.state='IDLE';self.status='Compatible personal profiles imported.'

    def settings_update(self,values):self._enqueue('settings',dict(values))
    def _do_settings(self,values):
        permitted={'caption_size','theme','preview_zoom','direction','layout','session_quota_mib','completed_session_limit','ram_horizon_sec'}
        if set(values)-permitted:raise ValueError('Unknown UI setting')
        if values.get('direction') not in (None,'off',False):raise ValueError('Live direction calibration unavailable; arrows are disabled')
        for key,allowed in {'session_quota_mib':(64,128,256),'completed_session_limit':(3,10,20),'ram_horizon_sec':(60,120)}.items():
            if key in values and values[key] not in allowed:raise ValueError('Unsupported retention setting '+key)
        self.settings.update(values);atomic_json(self.data_root/'settings.json',self.settings)

    def mark_problem(self,save_audio=False):self._enqueue('mark_problem',save_audio is True)
    def _do_mark_problem(self,save_audio):
        # User-requested diagnostics are pinned outside automatic field retention.
        folder=self.data_root/'problems'/str(uuid.uuid4());folder.mkdir(parents=True)
        receipt={'created_utc':datetime.now(timezone.utc).isoformat(),'mode':self.mode,'recipe':self.recipe,
            'tap':self.tap,'epoch':self.epoch,'audio_saved':False,'private':True,'user_requested':True}
        if save_audio:
            if self.engine is None:raise ValueError('No retained audio is available; start a session first')
            journal=self.engine._journal;end=journal.committed_samples;start=max(0,end-30*16000)
            if not end:raise ValueError('No audio received yet')
            audio=journal.read(start,end-start,wait_sec=0)
            import soundfile as sf
            sf.write(folder/'excerpt.wav',audio,16000,subtype='PCM_16')
            receipt.update(audio_saved=True,source_start_sec=start/16000,source_end_sec=end/16000,
                sample_rate=16000,gain_policy=self.route()['gain_policy'],session=str(self.engine.session_dir))
        with self.lock:receipt['caption_rows']=deepcopy(list(self.rows.values())[-20:])
        atomic_json(folder/'PROBLEM.json',receipt);(folder/'PINNED').touch()
        self.status='Private problem excerpt saved: '+str(folder)
        self.metrics['last_problem_path']=str(folder)

    def _retention(self):
        if shutil.disk_usage(self.data_root).free<2*1024**3:raise RuntimeError('Less than2GiB free; capture not started')
        root=self.data_root/'sessions';root.mkdir(exist_ok=True)
        folders=sorted([p for p in root.glob('edge_prototype_*') if p.is_dir()],key=lambda p:p.stat().st_mtime)
        sizes={p:sum(x.stat().st_size for x in p.rglob('*') if x.is_file()) for p in folders}
        for p in folders:
            if len(sizes)<=self.settings.get('completed_session_limit',10) and sum(sizes.values())<=self.settings.get('session_quota_mib',256)*1024**2:break
            if (p/'PINNED').exists() or not (p/'session_finalization_v3.json').exists():continue
            if p.resolve().parent!=root.resolve():raise ValueError('Invalid retention path')
            shutil.rmtree(p);sizes.pop(p)
        if sum(sizes.values())>512*1024**2:raise RuntimeError('Protected session storage exceeds512MiB; review saved diagnostics')

    def snapshot(self):
        from .casing import provisional_case
        people=self.store.summaries()
        names=[p['name'] for p in people]
        with self.lock:raw=deepcopy(list(self.rows.values()))
        rows=[]
        for row in raw:
            segments=row.get('segments') or [row]
            provisional=provisional_case(row.get('text',''),names=names)
            final_display=row.get('display_text') if row.get('punctuation_for_text_revision') else None
            def partition(display,part,index):
                if display is None:return None
                if len(segments)==1:return display
                a,b=part.get('token_range',(0,0))
                words=list(re.finditer(r'\S+',display));raw_words=row.get('text','').split()
                normalize=lambda s:''.join(c.lower() for c in s if c.isalnum())
                if len(words)!=len(raw_words) or any(normalize(m.group())!=normalize(w) for m,w in zip(words,raw_words)):
                    return None
                if not 0<=a<=b<=len(words):return None
                start=words[a].start() if a<len(words) else len(display)
                end=words[b].start() if b<len(words) else len(display)
                return display[start:end]
            # Segment ownership remains S7 supported-prefix_v2; never assign a whole
            # utterance to the last speaker merely because its final words arrived later.
            for i,part in enumerate(segments):
                text=part.get('raw_text',row.get('text',''))
                known=part.get('known_profile_id') if part.get('naming_state')=='confirmed' else None
                selected=known in self.selected_ids
                if self.mode=='caption_only':label='Caption'
                elif self.mode=='anonymous_conversation':label=part.get('anonymous_label',row.get('anonymous_label','Unknown'))
                elif self.mode=='enrolled_names':label=next((p['name'] for p in people if p['id']==known),'Unknown')
                else:label=next((p['name'] for p in people if p['id']==known),part.get('anonymous_label','Unknown'))
                punct=partition(final_display,part,i)
                rows.append({'id':part.get('segment_id',row.get('caption_key',str(row.get('utterance_id')))),
                    'utterance_id':row.get('utterance_id'),'raw_asr_text':text,
                    'provisional_display_text':partition(provisional,part,i) or provisional_case(text,names=names),
                    'final_punctuated_display_text':punct,'label':label,'final':row.get('final',False),
                    'selected':selected,'visible':not(self.mode=='selected_focus' and self.strict) or selected,
                    'identity_version':row.get('identity_version'),'profile_id':known})
        metrics=dict(self.metrics)
        metrics['free_disk_gib']=round(shutil.disk_usage(self.data_root).free/1024**3,2)
        if self.engine:metrics.update(source_seconds=self.engine._source_time(),asr_lag_sec=self.engine.telemetry().get('asr_lag_sec'),session=str(self.engine.session_dir))
        try:
            import psutil
            proc=psutil.Process();metrics.update(rss_mib=proc.memory_info().rss/1024**2,threads=proc.num_threads(),cpu_seconds=sum(proc.cpu_times()[:2]))
        except ImportError:pass
        live = getattr(self, '_enroll_live', None) or getattr(getattr(self.engine, '_source', None), 'live', None)
        diagnostic = getattr(live, 'beam_diagnostics', None)
        beam_snapshot = diagnostic.snapshot() if diagnostic is not None else {
            'state':'OFF', 'arrows':[], 'reason':'Start the XVF with microphone consent to see beam diagnostics.'}
        return {'state':self.state,'status':self.status,'error':self.error,'rows':rows,'people':people,
            'mode':self.mode,'recipe':self.recipe,'tap':self.tap,'recipes':deepcopy(RECIPES),
            'selected_ids':self.selected_ids[:],'strict':self.strict,'settings':dict(
                {'completed_session_limit':10,'session_quota_mib':256,'ram_horizon_sec':120},**self.settings,
                retention=f"{self.settings.get('completed_session_limit',10)} completed unpinned sessions; {self.settings.get('session_quota_mib',256)}MiB target; 2GiB free floor",
                ram_horizon=f"{self.settings.get('ram_horizon_sec',120)} seconds of live inference audio",
                audio_retention='No ambient WAV archive; enrollment samples discarded after analysis'),
            'enrollment':deepcopy(self.enrollment),'metrics':metrics,'epoch':self.epoch,
            'pending_actions':self.commands.qsize(),'direction':'unavailable',
            'beam_diagnostics':beam_snapshot,'closed':self.closed}

    def close(self):self._enqueue('close')
    def _do_close(self):
        self._do_enrollment_cancel();self._stop_session();self._observe_output('application_exit')
        atomic_json(self.data_root/'last_application.json',{'closed_utc':datetime.now(timezone.utc).isoformat(),
            'metrics':self.metrics,'transitions':self.transitions,'output_defaults':self.output_defaults,
            'microphone_open':False,'private_data_not_in_release':True,'terminal_error':self.error})
        self.closed=True;self.state='CLOSED';self.owner.close();self.commands.put_nowait(None)
