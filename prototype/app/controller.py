"""Single application owner: commands, models, capture, people and caption epochs."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import os
import json
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
from .enrollment_progress import ReadProgress, reference_text
from .session_controller import SessionWorkflow
from .mode_policy import MODE_METADATA,SELECTED_MODES,NAMED_MODES,SPATIAL_PARENTS,SEAT_MODES,PARAMETERS,validate_overrides
from .seat_controller import SeatWorkflow
from .text_assistance import TextAssistance, corrected_partition
from .adaptation_controller import AdaptationWorkflow
from .transcript_review_controller import TranscriptReviewWorkflow
from .backends import BASELINE_BACKEND_ID, backend_catalog, backend_status, require_backend, backend_manifest

class Controller(TranscriptReviewWorkflow,AdaptationWorkflow,SeatWorkflow,SessionWorkflow):
    def __init__(self,data_root,models_root,*,writer_delay=0,saved_audio_only=False):
        self.saved_audio_only=bool(saved_audio_only)
        self.backend_id=BASELINE_BACKEND_ID
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
        self._baseline_store=self.store
        self._n2_components=None
        self._n3_components=None
        self.lock=threading.RLock();self.commands=queue.Queue(32)
        self.engine=None;self.consumer=None;self.epoch=0;self.rows=OrderedDict()
        self.source_kind=None;self.file_path=None;self.file_offset=0;self.live_consent=False
        self.mode='caption_only';self.recipe='fast';self.tap='O0';self.selected_ids=[];self.strict=False
        self.state='IDLE';self.status='Ready. Microphone is off.';self.error=None
        self.closed=False;self.transitions=[];self.metrics={'completed_sessions':0,'events_consumed':0,'retired_rows':0}
        self.settings=read_json(self.data_root/'settings.json') if (self.data_root/'settings.json').exists() else {}
        available_ids={p['id'] for p in self.store.list()}
        self.selected_ids=[i for i in self.settings.get('roster_ids',[]) if i in available_ids]
        self.display_ids=[i for i in self.settings.get('display_roster_ids',[]) if i in available_ids]
        self.identity_overrides=validate_overrides(self.settings.get('identity_overrides',{}))
        self._seats_initialize()
        self._adaptation_initialize()
        self._review_initialize()
        self.enrollment={'state':'IDLE','can_save':False};self._enroll_audio=[];self._enroll_vector=None
        self._enroll_thread=None;self._enroll_stop=threading.Event();self._enroll_live=None
        self._quality_thread=None;self._quality_queue=None;self._quality=None;self._enroll_integrity=None
        self.output_defaults=[];self._observe_output('application_open')
        self._sessions_initialize()
        self.text_assistance=TextAssistance(self.data_root/'text_assistance.json')
        self.worker=threading.Thread(target=self._commands,name='proto-controller',daemon=True);self.worker.start()
        self.imu=None
        motion_config=self.data_root/'imu_config.json'
        if motion_config.exists() and not self.saved_audio_only:
            try:
                from .imu import BMI270Worker
                self.imu=BMI270Worker(read_json(motion_config),self.motion_event).start()
            except Exception as exc:
                from .imu_unavailable import UnavailableMotion
                self.imu=UnavailableMotion(exc);self.metrics['motion_configuration_error']=str(exc)

    def _observe_output(self,stage):
        if getattr(self,'saved_audio_only',False):
            self.output_defaults.append({'stage':stage,'status':'DISABLED_SAVED_AUDIO_ONLY'})
            return
        try:
            from .windows_audio import endpoint_snapshot
            value=endpoint_snapshot()
            self.output_defaults.append({'stage':stage,'value':value})
            self.output_defaults=self.output_defaults[-64:]
        except Exception as exc:self.output_defaults.append({'stage':stage,'error':str(exc)})

    def record_presentation(self,receipt):
        """Record Tk application separately from source events and physical scanout."""
        value=deepcopy(receipt)
        value['caption_epoch']=self.epoch
        value['scope']='Tk text applied; viewport visibility and physical scanout not measured'
        with self.lock:
            recent=self.metrics.setdefault('gui_presentation_recent',[])
            recent.append(value)
            del recent[:-256]
            self.metrics['gui_presentation_count']=self.metrics.get('gui_presentation_count',0)+1
            session=getattr(self.engine,'session_dir',None) if self.engine is not None else None
            if session:
                try:
                    path=Path(session)/'gui_presentation.jsonl'
                    with path.open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')
                    self.metrics['gui_presentation_log']=str(path)
                except (OSError,ValueError) as exc:
                    self.metrics['gui_presentation_log_error']=str(exc)

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
        from .enhancement import identity_binding
        result={'tap':self.tap,'sample_rate':16000,'gain_policy':'O0_host_plus3dB_once' if self.tap=='O0' else 'O1_unity',
                'preprocessing':getattr(self.store,'preprocessing',PREPROCESSING),'waveform_domain':'xvf_ua',
                'source':'verified_live_or_already_gained_file'}
        result.update(identity_binding(getattr(self,'settings',{}).get('enhancement_route','bypass')))
        return result

    def _live_config(self):
        from .live_audio import LiveConfig
        path=self.data_root/'live_config.json'
        if not path.exists():raise ValueError('XVF site configuration missing. See docs/LIVE_AUDIO.md')
        value=read_json(path);value.update(tap=self.tap,evidence_dir=str(self.data_root/'device_receipts'))
        return LiveConfig(**value)

    def start_live(self,consent=False):
        if self.saved_audio_only:raise RuntimeError('Live hardware is disabled in this saved-audio campaign')
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
        require_backend(getattr(self,'backend_id',BASELINE_BACKEND_ID),self.mode,self.tap,
                        recorded_spatial=self.source_kind=='live')
        if getattr(self,'_n2_components',None) and self._n2_components['diarization']=='D1' and self.recipe=='classic':
            raise ValueError('Classic uses the D0 tracker. Select Balanced or Patient for the Nemotron backend.')
        self._review_cancel('new capture epoch; discard optional review')
        self._retention()
        # Previous failure remains in its journal and terminal metrics. Only
        # after old ownership is released may a new epoch clear the GUI error.
        self.error=None
        self.state='STARTING';self.status='Loading the selected recipe…';self.epoch+=1
        if self.mode in SEAT_MODES and not self.seats.snapshot()['valid']:raise ValueError('Seat layout needs Apply / re-anchor at this location before Start')
        profile=effective_profile(self.recipe,self.mode,self.tap,self._effective_identity_overrides(),getattr(getattr(self,'seats',None),'strength','soft'))
        gallery=self.store.gallery(self.route(),self.selected_ids if self.mode in SELECTED_MODES else None,
            alternate_advisory=self.settings.get('text_aware_references',False)) if self.mode in NAMED_MODES and self.mode!='assigned_direction' else None
        self._adaptation_start(gallery)
        from .live_spatial import LiveSpatialProvider
        from .imu import mounted_array_motion
        spatial_type=LiveSpatialProvider
        spatial_args={}
        if self.mode in SEAT_MODES:
            from .seats import SeatSpatialProvider
            spatial_type=SeatSpatialProvider;spatial_args={'seats':self.seats}
        spatial = spatial_type(self.tap, profile.tracker,**spatial_args,
            enabled=self.mode in SPATIAL_PARENTS,
            display=self.settings.get('spatial_visualization', False),
            motion=mounted_array_motion(getattr(self,'imu',None),self.source_kind))
        engine_type=PrototypeEngine;engine_args={}
        if getattr(self,'_n2_components',None):
            from .n2_pipeline import N2Engine
            engine_type=N2Engine;engine_args['diarization']=self._n2_components['diarization']
            engine_args['n2_observer_factory']=getattr(self,'n2_observer_factory',None)
        if getattr(self,'_n3_components',None):
            from .n3_pipeline import N3Engine,N3IdentityEngine
            engine_type=N3IdentityEngine if self._n2_components else N3Engine
        engine=engine_type(self.config,self.models,profile,gallery,self.mode,writer_delay=self.writer_delay,
                               ram_horizon_sec=self.settings.get('ram_horizon_sec',120), spatial_provider=spatial,
                               enhancement_route=self.settings.get('enhancement_route','bypass'),
                               seats=self.seats if self.mode in SEAT_MODES else None,seat_names={p['id']:p['name'] for p in self.store.list()},**engine_args)
        self.engine=engine
        engine.mode_configuration=self.mode_configuration(profile,gallery)
        engine.mode_configuration['backend']=backend_manifest(getattr(self,'backend_id',BASELINE_BACKEND_ID))
        try:archive=self._archive_prepare(profile)
        except OSError as exc:
            archive=None;self.metrics['last_archive']={'archive_error':'Archive unavailable; live captions continue: '+str(exc),'audio_recording':False}
        engine.archive=archive
        if archive is not None:
            archive.engine=engine;archive.metadata['pipeline_input_gain']=engine.config.input_gain
            archive.caption_names=[p['name'] for p in self.store.summaries()]
        self.engine=engine
        try:
            if self.source_kind=='file':engine.start_prepared_file(self.file_path,self.file_offset)
            else:engine.start_xvf(self._live_config())
        except BaseException:
            self._stop_session()
            raise
        epoch=self.epoch
        self._adaptation_bind_engine(engine)
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
                    self._adaptation_event(engine,event)
                    if getattr(engine,'archive',None) is not None:
                        try:engine.archive.event(event)
                        except Exception as exc:engine.archive.fail('Archive event unavailable: '+str(exc))
                    spatial = getattr(engine, 'live_spatial', None)
                    if spatial is not None:
                        if event.event_type == 'speaker_decision':spatial.observe_decision(event.payload)
                        elif event.event_type == 'research_segmentation':spatial.observe_segmentation(event.payload)
                    if event.event_type == 'speaker_decision':
                        # Existing metadata only; keep scores/tentative choices visible
                        # while the GUI uses calm labels. No vectors or new decisions.
                        with self.lock:
                            recent = self.metrics.setdefault('recent_identity_decisions', [])
                            observed=deepcopy(event.payload)
                            observed['prototype_configuration']=dict(mode=engine.mode,recipe=engine.recipe,tap=engine._research_profile.input.identity_tap,
                                overrides=dict(engine.mode_configuration.get('overrides',{})))
                            recent.append(observed)
                            del recent[:-12]
                    if event.event_type=='s6d_display':
                        row=dict(event.payload)
                        key=row.get('caption_key') or str(row.get('session_id'))+'/'+str(row.get('utterance_id'))
                        if epoch==self.epoch:
                            with self.lock:
                                self.rows[key]=dict(row)
                                while len(self.rows)>512:
                                    self.rows.popitem(last=False);self.metrics['retired_rows']+=1
                        if hasattr(self,'text_assistance') and row.get('final') and row.get('punctuation_for_text_revision'):
                            # Optional text work follows publication of raw ASR. It
                            # cannot mutate upstream text, identity or audio.
                            try:
                                row['text_assistance']=self.text_assistance.analyze(row.get('display_text') or row.get('text',''),self.store.summaries())
                                row['text_assistance']['source']={'caption_key':row.get('caption_key'),'text_revision_id':row.get('text_revision_id'),
                                    'utterance_id':row.get('utterance_id'),'archive_epoch_id':getattr(getattr(engine,'archive',None),'path',Path('')).name,
                                    'start_sample':round(row.get('source_start_sec',0)*16000),'end_sample':round(row.get('source_end_sec',0)*16000)}
                            except Exception as exc:row['text_assistance']={'status':'unavailable','error':str(exc),'corrected_text':None}
                        if getattr(engine,'archive',None) is not None:
                            try:engine.archive.formatted(row,getattr(engine.archive,'caption_names',[]))
                            except Exception as exc:engine.archive.fail('Formatting archive unavailable: '+str(exc))
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
            self._archive_end(getattr(engine,'archive',None))
            self.metrics['completed_sessions']+=1
            self.metrics['last_session']=str(engine.session_dir)
            self.metrics['last_state']=engine.state
            self.metrics['last_telemetry']=engine.telemetry()
            if getattr(engine, 'live_spatial', None) is not None:
                self.metrics['last_spatial']=engine.live_spatial.snapshot()
            self.metrics['model_cache']={'asr_loads':self.models.asr_loads,'speaker_loads':self.models.speaker_loads,'streams':self.models.streams}
            self.metrics['gallery_queries']=engine._research_gallery.query_count if engine._research_gallery else 0
            if epoch==self.epoch:
                if engine.state=='FAILED' or engine._finalization_error:
                    self.state='ERROR';self.error=self.error or str(engine._finalization_error or engine.telemetry());self.status='Session failed. Stop/restart for a fresh audio epoch.'
                elif self.state not in ('SWITCHING','STOPPING'):
                    self.state='STOPPED';self.status='Stopped. Microphone released.'
                    if engine.mode in SEAT_MODES:engine.seats.invalidate('source_session_closed; re-anchor before next Start')
        except Exception as exc:
            self.error=repr(exc);self.state='ERROR';self.status='Caption consumer failed: '+str(exc)

    def stop(self):self._enqueue('stop')
    def _do_stop(self):
        self._stop_playback()
        if self.enrollment.get('state')=='RECORDING':self._do_enrollment_stop()
        self._stop_session();self.source_kind=None;self.state='STOPPED';self.status='Stopped. Microphone released.'
        if self.mode in SEAT_MODES:self._invalidate_seats('user_stopped_session; re-anchor before next Start')

    def _stop_session(self):
        engine=self.engine
        if engine is None:return
        self.state='STOPPING';self.status='Stopping capture and finishing pending words…'
        failures=[]
        try:engine.stop()
        except Exception as exc:failures.append(repr(exc))
        live=getattr(engine._source,'live',None)
        if live and live.status().get('started') and not live.status().get('finished'):
            # FAILED engines may intentionally no-op stop(); retain their owner
            # and retry an incomplete device close before considering release.
            try:engine._source.stop()
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
        enhancer=getattr(engine,'enhancement_router',None)
        if enhancer is not None and enhancer.thread is not None:owned_threads.append(enhancer.thread)
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
            while not engine.events.empty():
                event=engine.events.get(block=False)
                if getattr(engine,'archive',None) is not None:
                    try:engine.archive.event(event)
                    except Exception as exc:engine.archive.fail(str(exc))
            if engine.session_dir:engine.record_s6d_consumer_closure('PROTO1 failed-start cleanup')
        if getattr(engine,'archive',None) is not None and engine.archive.metadata['conversation_id'] in self.session_store.active:
            self._archive_end(engine.archive)
        if self.source_kind=='file':self.file_offset+=getattr(engine._source,'sent',0)
        if failures:
            if getattr(self,'reference_bank',None):self.reference_bank.freeze('source_shutdown_failure')
            self.error=self.error or '; '.join(failures);self.metrics['last_terminal_failures']=failures
        self.engine=None;self.consumer=None
        if getattr(self,'reference_bank',None):self.reference_bank.log_match=None
        self._observe_output('session_stop')

    def select_backend(self,backend_id):
        backend_manifest(backend_id)
        self._enqueue('select_backend',backend_id)

    def _do_select_backend(self,backend_id):
        composition=backend_manifest(backend_id)['composition']
        self._ensure_no_enrollment();self._stop_session()
        # Selections belong to a compatible embedding store. Remember them in
        # this Controller so visiting an empty alternative cannot erase the
        # previous store's selected or highlighted people.
        rosters=getattr(self,'_backend_store_rosters',{})
        previous=dict(selected_ids=list(self.selected_ids),display_ids=list(self.display_ids))
        rosters[str(self.store.root.resolve())]=previous
        components=composition.get('n2')
        if components:
            from .n2_models import N2ResidentModels,load_runtime
            document=load_runtime(self.data_root)
            document['streaming_profile']=components.get('streaming_profile','low_latency')
            new_models=N2ResidentModels(components['diarization'],components['embedding'],document)
            if components['embedding']=='E1':
                from .n2_people import titanet_store
                new_store=titanet_store(self.data_root,document['embedding_namespace'])
            else:new_store=self._baseline_store
        else:new_models=ResidentModels();new_store=self._baseline_store
        asr_components=composition.get('n3')
        if asr_components:
            from .n3_models import N3ResidentModels,load_asr_runtime
            asr_document=load_asr_runtime(self.data_root,asr_components)
            new_models=N3ResidentModels(asr_document,identity=components,
                identity_document=document if components else None)
        available={row['id'] for row in new_store.list()}
        remembered=rosters.get(str(new_store.root.resolve()),previous)
        missing=(set(remembered['selected_ids'])|set(remembered['display_ids']))-available
        selected=[identifier for identifier in remembered['selected_ids'] if identifier in available]
        displayed=[identifier for identifier in remembered['display_ids'] if identifier in available]
        if backend_id!=getattr(self,'backend_id',None):self._adaptation_backend_changed()
        if hasattr(self.models,'close'):self.models.close()
        self.models=new_models;self.store=new_store;self._n2_components=components
        self._n3_components=asr_components
        self._backend_store_rosters=rosters;self.selected_ids=selected;self.display_ids=displayed
        if not displayed:self.strict=False
        self.backend_id=backend_id
        self.state='IDLE';self.status='Backend selected. Choose Start or a saved file explicitly.'
        if missing:self.status+=' Selected voice references are unavailable here; re-enroll them for this backend before named use. Full captions remain available.'

    def switch(self,mode=None,recipe=None,tap=None,selected_ids=None,strict=None):
        self._enqueue('switch',mode,recipe,tap,selected_ids,strict)
    def _do_switch(self,mode,recipe,tap,selected_ids,strict):
        self._ensure_no_enrollment()
        mode=mode or self.mode;recipe=recipe or self.recipe;tap=tap or self.tap
        if mode not in MODES:raise ValueError('Unknown mode')
        if recipe=='fast' and mode!='caption_only' and recipe==self.recipe:recipe='balanced'
        profile=effective_profile(recipe,mode,tap,self._effective_identity_overrides(),getattr(getattr(self,'seats',None),'strength','soft'))
        if self.state=='RUNNING' and self.source_kind=='file' and tap!=self.tap:
            raise ValueError('Stop file replay and load the actual other-tap prepared WAV before changing its audio domain.')
        ids=self.selected_ids if selected_ids is None else list(dict.fromkeys(selected_ids))
        if set(ids)-{p['id'] for p in self.store.list()}:raise ValueError('Selected person no longer exists')
        if strict and (mode not in NAMED_MODES or not self.display_ids):raise ValueError('Experimental hiding requires a named mode and a separate display roster')
        if strict is not None and selected_ids is None and (mode,recipe,tap)==(self.mode,self.recipe,self.tap):
            self.strict=bool(strict);self._record_display_configuration()
            self.status='Display visibility updated; matching roster unchanged.';return
        if mode in SEAT_MODES:
            seat=self.seats.snapshot()
            if not seat['valid']:raise ValueError('Open Assigned seats and Apply / re-anchor first')
            if set(ids)!={r['person_id'] for r in seat['rows']}:raise ValueError('Assigned-seat roster must match the applied layout')
        if mode in SELECTED_MODES:
            route=self.route()
            if tap!=self.tap:route={**route,'tap':tap,'gain_policy':'O0_host_plus3dB_once' if tap=='O0' else 'O1_unity'}
            self.store.gallery(route,ids)  # Validate before changing/stopping the current mode.
        running=self.state=='RUNNING'
        old={'mode':self.mode,'recipe':self.recipe,'tap':self.tap,'epoch':self.epoch}
        self._stop_session();self.state='SWITCHING'
        self.mode,self.recipe,self.tap=mode,recipe,tap;self.selected_ids=ids
        if old['tap']!=tap and getattr(self,'reference_bank',None):self.reference_bank.freeze('reference_tap_changed')
        if old['mode'] in SEAT_MODES and mode not in SEAT_MODES:self._invalidate_seats('left_assigned_seat_mode; re-anchor on return')
        self.strict=bool(strict if strict is not None else self.strict) if mode in NAMED_MODES else False
        if selected_ids is not None:
            self.settings['roster_ids']=ids[:];atomic_json(self.data_root/'settings.json',self.settings)
        self.transitions.append({'from':old,'to':{'mode':mode,'recipe':recipe,'tap':tap},'monotonic':time.perf_counter()})
        self.transitions=self.transitions[-128:]
        self._observe_output('mode_switch')
        if running:
            if self.source_kind=='file':
                import soundfile as sf
                if self.file_offset>=sf.info(self.file_path).frames:running=False
            if running:self._start_session()
        if not running:self.state='IDLE';self.status='Selection ready. Press Start to listen.'

    def _effective_identity_overrides(self):
        return {} if getattr(self,'_n2_components',None) else getattr(self,'identity_overrides',{})

    def mode_configuration(self,profile=None,gallery=None):
        from dataclasses import asdict
        profile=profile or effective_profile(self.recipe,self.mode,self.tap,self._effective_identity_overrides(),getattr(getattr(self,'seats',None),'strength','soft'))
        return dict(mode=self.mode,semantics=deepcopy(MODE_METADATA[self.mode]),recipe=self.recipe,tap=self.tap,
            selected_ids=list(self.selected_ids),display_ids=list(getattr(self,'display_ids',[])),gallery=deepcopy(gallery.receipt) if gallery else None,
            overrides=dict(self._effective_identity_overrides()),effective_profile=asdict(profile),
            n2_policy=(dict(anonymous_components=deepcopy(self._n2_components),
                naming='N2NameMap with model/domain/roster-specific C gate; baseline naming thresholds unused',
                calibration=deepcopy(getattr(gallery,'calibration',{'status':'UNCALIBRATED'})))
                if getattr(self,'_n2_components',None) else None),
            seating=self.seating_snapshot() if self.mode in SEAT_MODES else None,
            strict_display=self.strict,highlight_selected=bool(self.settings.get('highlight_selected',False)),
            label_hysteresis_sec=.2,identity_threshold_is_not_UI_hysteresis=True,
            closed_assignment=(('N2 supported voice chooses a selected-name assumption; unresolved, missing or mixed evidence stays Unknown; no verified match without a valid C gate; no profile adaptation'
                if getattr(self,'_n2_components',None) else
                'Current clean voice cosine winner; missing ownership uses separate assumed selected-name display; no profile adaptation')
                if self.mode=='selected_closed' else None))

    def identity_parameters(self,values=None):self._enqueue('identity_parameters',values)
    def _do_identity_parameters(self,values):
        self._ensure_no_enrollment()
        if getattr(self,'_n2_components',None) and values:
            raise ValueError('N2 uses fixed comparison settings and model-specific C calibration. Baseline identity overrides are unavailable for this backend.')
        proposed={} if values is None else validate_overrides(values)
        effective_profile(self.recipe,self.mode,self.tap,proposed)
        previous=getattr(self,'identity_overrides',{});self.identity_overrides=proposed
        try:self._do_switch(None,None,None,None,None)
        except Exception:self.identity_overrides=previous;raise
        self.settings['identity_overrides']=proposed;atomic_json(self.data_root/'settings.json',self.settings)
        self.status='Developer identity parameters applied at a fresh epoch.' if proposed else 'Frozen recipe defaults restored at a fresh epoch.'

    def display_roster(self,ids):self._enqueue('display_roster',list(ids))
    def _do_display_roster(self,ids):
        ids=list(dict.fromkeys(ids))
        if set(ids)-{p['id'] for p in self.store.list()}:raise ValueError('Display person no longer exists')
        self.display_ids=ids
        if not ids:self.strict=False
        self.settings['display_roster_ids']=ids[:];atomic_json(self.data_root/'settings.json',self.settings)
        self._record_display_configuration();self.status='Display roster updated; identification gallery and capture unchanged.'

    def _record_display_configuration(self):
        detail=dict(display_ids=list(getattr(self,'display_ids',[])),strict_display=self.strict,
            highlight_selected=bool(self.settings.get('highlight_selected',False)),matching_ids=self.selected_ids[:],
            mode=self.mode,recipe=self.recipe,tap=self.tap,monotonic_sec=time.perf_counter(),scope='display only; no gallery or source restart')
        self.metrics['display_configuration']=detail
        archive=getattr(self,'archive',None)
        if archive is not None:
            from edge_speech_pipeline.contracts import PipelineEvent
            archive.event(PipelineEvent('prototype_display_configuration',archive.source_samples/16000,detail))

    def _ensure_no_enrollment(self):
        if self.enrollment.get('state') in ('RECORDING','DRAINING','ANALYZING','READY'):
            raise ValueError('Save or cancel the current enrollment first')
        # A failed cancellation may still own capture/quality workers. The
        # ERROR label alone must never permit overwriting that live owner.
        self._assert_enrollment_quiet()

    def enrollment_start(self,name,target_sec=30,consent=False,person_id=None,paragraph=None):
        if getattr(self,'saved_audio_only',False):raise RuntimeError('Live enrollment is disabled in this saved-audio campaign')
        if consent is not True:raise ValueError('Explicit person/enrollment microphone consent required')
        self._enqueue('enrollment_start',name,target_sec,person_id,paragraph)
    def _do_enrollment_start(self,name,target_sec,person_id,paragraph=None):
        self._review_cancel('enrollment started')
        from .people import clean_name
        from .live_audio import XVFLiveSource
        self._stop_playback()
        name=clean_name(name)
        if target_sec not in (None,15,30,60):raise ValueError('Choose paragraph Done or15,30,60 seconds')
        offered=reference_text(paragraph or '') if target_sec is None else None
        self._ensure_no_enrollment();self._stop_session();self.source_kind=None
        self.enrollment={'state':'LOADING','name':name,'person_id':person_id,'target_sec':target_sec,
            'elapsed_s':0.,'usable_s':0.,'analyzed_s':0.,'activity_s':0.,'level':0.,'clipping':0.,'can_save':False,'gaps':0,
            'capture_mode':'paragraph' if target_sec is None else 'timed'}
        self.models.enrollment_models(self.config)
        self._enroll_enhancer=None
        self._enroll_enhancement_route=getattr(self,'settings',{}).get('enhancement_route','bypass')
        if self._enroll_enhancement_route in ('identity','both') or (self._enroll_enhancement_route=='asr' and offered is not None):
            self._enroll_enhancer=self.models.enhancement_model(self.config)
        self._enroll_audio=[];self._enroll_vector=None;self._enroll_stop.clear()
        self._script_bank=None
        self._enroll_script_enabled=offered is not None and self.settings.get('text_aware_references',False) is True
        self._enroll_live=None;self._enroll_thread=None;self._quality_thread=None
        self._quality=None;self._quality_queue=None;self._enroll_integrity=None;self._enroll_read=None
        try:
            if offered is not None:
                self.enrollment['offered_reference']=offered
                try:
                    if not getattr(self.models,'supports_read_progress',True):
                        raise RuntimeError('Read-along progress is not yet supported by this streaming ASR backend')
                    _,asr=self.models.acquire(self.config,caption_only=True)
                    self._enroll_read=ReadProgress(asr,offered['offered_text'],token_timing=self._enroll_script_enabled)
                except Exception as exc:
                    self.enrollment['script_estimate']={'state':'unavailable','error':str(exc),'affects_voice_quality':False}
            self._enroll_live=XVFLiveSource(self._live_config());self._enroll_live.start(consent=True)
            self._enroll_route={**self.route(),'live_capture':deepcopy(self._enroll_live.metadata),
                'source_session_id':str(uuid.uuid4()),'native_rate':self._enroll_live.config.native_rate}
            self._quality=EnrollmentQuality(self.models.speakers,self.config,target_sec)
            self._quality_queue=queue.Queue(20)
            self._quality_thread=threading.Thread(target=self._quality_loop,name='proto-enrollment-quality',daemon=True)
            self._quality_thread.start()
            self.enrollment['state']='RECORDING';self.state='ENROLLING';self.status='Recording enrollment; read or speak naturally.'
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
        helper=getattr(self,'_enroll_enhancer',None)
        route=getattr(self,'_enroll_enhancement_route','both')
        enhance_identity=helper is not None and route in ('identity','both')
        enhance_asr=helper is not None and route in ('asr','both')
        pending=np.empty(0,np.float32);emitted=source_seen=0
        def process(offset,samples):
            if self._quality.process(samples,source_start=offset,publish=self.enrollment.update):
                if getattr(self,'_enroll_script_enabled',False):self._enroll_audio.append(samples.copy())
        def enhanced(samples):
            nonlocal pending,emitted
            if enhance_asr and len(samples):self._update_enrollment_read(samples)
            if enhance_identity:
                pending=np.concatenate((pending,samples))
                while len(pending)>=160000:
                    process(emitted,pending[:160000]);pending=pending[160000:];emitted+=160000
        while True:
            block=self._quality_queue.get()
            try:
                if block is None:
                    if helper:
                        enhanced(helper.flush())
                        if enhance_identity and len(pending):process(emitted,pending)
                    self._update_enrollment_read(final=True)
                    return
                offset,samples=block
                if not enhance_identity:process(offset,samples)
                if not enhance_asr:self._update_enrollment_read(samples)
                if helper:
                    if offset!=source_seen:raise ValueError('Enhanced enrollment source gap or duplicate')
                    source_seen+=len(samples);enhanced(helper.run(samples))
            except Exception as exc:
                self.enrollment.update(error=repr(exc),gaps=1,can_save=False)
                if block is None:return
            finally:self._quality_queue.task_done()

    def _update_enrollment_read(self,samples=None,final=False):
        reader=getattr(self,'_enroll_read',None)
        if reader is None:return
        try:
            if final:estimate=reader.finish()
            else:
                reader.accept(samples);estimate=reader.snapshot()
            self.enrollment['script_estimate']=estimate
        except Exception as exc:
            # Optional lexical estimates must never reject useful voice audio.
            self.enrollment['script_estimate']={'state':'unavailable','error':str(exc),'affects_voice_quality':False}
            self._enroll_read=None

    def _record_enrollment(self):
        count=0;pending=[];pending_count=0;activity=0
        try:
            while not self._enroll_stop.is_set() and count<180*16000:
                block=self._enroll_live.read(.25)
                if block is None:continue
                if block.model_start_sample!=count:raise ValueError('Enrollment capture source gap or repeated samples')
                if not np.isfinite(block.audio).all():raise ValueError('Non-finite enrollment capture')
                # Capture drainage performs no inference. Only complete unique10s
                # chunks go to one bounded quality worker; each is analyzed once.
                pending.append(block.audio.copy());count+=len(block.audio);pending_count+=len(block.audio)
                level=float(np.sqrt(np.mean(block.audio.astype(np.float64)**2)))
                if level>=self.config.minimum_rms:activity+=len(block.audio)
                self.enrollment.update(elapsed_s=count/16000,level=level,activity_s=activity/16000)
                if pending_count>=160000:
                    samples=np.concatenate(pending)
                    self._quality_queue.put_nowait((count-pending_count,samples[:160000]))
                    tail=samples[160000:];pending=[tail] if len(tail) else [];pending_count=len(tail)
        except Exception as exc:
            self.enrollment.update(error=str(exc),gaps=1,can_save=False);self.error=str(exc)
        finally:
            try:
                if pending_count:self._quality_queue.put_nowait((count-pending_count,np.concatenate(pending)))
            except Exception as exc:self.enrollment.update(gaps=1,error=repr(exc),can_save=False)
            # Closing capture must not depend on successfully queuing analysis.
            try:
                from .live_audio import summarize_live_integrity
                self._enroll_live.stop()
                self._enroll_integrity=summarize_live_integrity(self._enroll_live)
                if not self._enroll_integrity['ok']:
                    self.enrollment.update(gaps=1,can_save=False,error='Live capture/restore integrity failed')
            except Exception as exc:self.enrollment.update(gaps=1,error=repr(exc),can_save=False)
            try:self._quality_queue.put(None,timeout=10)
            except Exception as exc:self.enrollment.update(gaps=1,error=repr(exc),can_save=False)
            if not self._enroll_stop.is_set():self._enqueue('enrollment_stop')

    def enrollment_stop(self):self._enqueue('enrollment_stop')
    def _do_enrollment_stop(self):
        if self._quality is None or self.enrollment.get('state') in ('READY','SAVED','IDLE'):return
        self.enrollment.update(state='DRAINING',can_save=False);self.status='Stopping capture; draining collected audio…'
        self._enroll_stop.set()
        if self._enroll_thread:self._enroll_thread.join(30)
        if self._enroll_thread and self._enroll_thread.is_alive():raise RuntimeError('Enrollment capture did not stop')
        self.enrollment['state']='ANALYZING';self.status='Checking unique usable speech and pending analysis…'
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
        if getattr(self,'_enroll_script_enabled',False):
            try:
                from .script_evidence import build_evidence,preview
                hashes={a.component_id:a.sha256 for a in self.config.assets}
                if self._enroll_enhancer is not None:
                    from .enhancement import specification
                    hashes['optional_enhancer']=specification()['sha256']
                self._script_bank=build_evidence(np.concatenate(self._enroll_audio),quality,
                    self.enrollment.get('script_estimate',{}),self.enrollment['offered_reference']['offered_text'],
                    self._enroll_route,self.models.speakers,hashes)
                self.enrollment['script_evidence']=preview(self._script_bank)
            except Exception as exc:
                self._script_bank=None
                self.enrollment['script_evidence']={'selection_state':'unavailable_use_base','error':str(exc)}
            finally:self._enroll_audio=[]
        self.enrollment.update(quality,state='READY');self.state='IDLE'
        self.status=('Enrollment ready to save.'+(' Limited short reference; more varied speech may help.' if quality['evidence_status']=='limited_short_reference' else '')) if quality['can_save'] else 'Quality check not satisfied. Discard and record clean speech again.'
        self._observe_output('enrollment_stop')

    def enrollment_save(self):self._enqueue('enrollment_save')
    def _do_enrollment_save(self):
        self._assert_enrollment_quiet()
        if self.enrollment.get('state')!='READY':raise RuntimeError('Finish enrollment analysis before saving')
        if not self._enroll_integrity or not self._enroll_integrity['ok']:
            raise RuntimeError('Enrollment capture integrity must pass before saving')
        quality=dict(self.enrollment);quality.pop('script_evidence',None)
        if getattr(self,'_script_bank',None):quality['script_evidence']=self._script_bank
        row=self.store.save(self.enrollment['name'],self._enroll_vector,quality,self._enroll_route,person_id=self.enrollment.get('person_id'))
        if getattr(self,'reference_bank',None):self.reference_bank.freeze('original_enrollment_changed')
        self._discard_enrollment_buffers()
        self.enrollment.update(state='SAVED',can_save=False,person_id=row['id'])
        self.status='Person saved. Try different fresh speech in Enrolled names mode.'

    def enrollment_script_note(self,text):self._enqueue('enrollment_script_note',text)
    def script_review(self,person_id):self._enqueue('script_review',person_id)
    def _do_script_review(self,person_id):
        from .script_evidence import preview
        self.metrics.pop('stored_script_review',None)
        row=next((r for r in self.store.list(refresh=True) if r['id']==person_id),None)
        if row is None:raise ValueError('Person no longer exists')
        ref=next((r for r in reversed(row['references']) if r.get('script_evidence')),None)
        document=preview(read_json(self.store.root/person_id/ref['script_evidence']['file'])) if ref else None
        self.metrics['stored_script_review']=dict(person_id=person_id,document=document)
    def _do_enrollment_script_note(self,text):
        if self.enrollment.get('state')!='READY' or not getattr(self,'_script_bank',None):raise ValueError('Finish paragraph review first')
        if not isinstance(text,str) or not 1<=len(text)<=500:raise ValueError('Use a review note of 1–500 characters')
        notes=self._script_bank['user_corrections']
        if len(notes)>=16:raise ValueError('Maximum 16 review notes')
        from .script_evidence import MAX_BYTES,stored_size
        note=dict(text=text,role='user correction/note; does not change raw ASR, timing or voice admission',revision=len(notes)+1)
        candidate=dict(self._script_bank,user_corrections=notes+[note])
        if stored_size(candidate)>MAX_BYTES-512:raise ValueError('Evidence is full; keep this note outside the profile')
        notes.append(note)
        self.enrollment['script_evidence']['user_corrections']=deepcopy(notes)
        self.status='Review note saved separately from decoded speech.'

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
        self._enroll_read=None
        self._script_bank=None
        self._enroll_enhancer=None

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
        self.metrics.pop('stored_script_review',None)
        self._invalidate_seats('people_changed; review UUID layout and re-anchor')
        self.selected_ids=[i for i in self.selected_ids if i in {p['id'] for p in self.store.list()}]
        self.display_ids=[i for i in getattr(self,'display_ids',[]) if i in {p['id'] for p in self.store.list()}]
        self.settings['display_roster_ids']=self.display_ids[:]
        self.settings['roster_ids']=self.selected_ids[:];atomic_json(self.data_root/'settings.json',self.settings)
        if not self.display_ids:self.strict=False
        # Invalidate cached identity spelling/UUID assignments; old acoustic words survive.
        with self.lock:
            for row in self.rows.values():
                row.update(known_profile_id=None,known_name=None,naming_state='invalidated',label='Unknown')
                row.pop('closed_display_assignment',None)
                for segment in row.get('segments',[]):
                    segment.update(known_profile_id=None,known_name=None,naming_state='invalidated',label='Unknown')
                    segment.pop('closed_display_assignment',None)
        self.state='IDLE';self.status='People updated. Start creates a fresh identity epoch.'

    def export_people(self,path,consent=False):self._enqueue('export_people',str(path),consent)
    def _do_export_people(self,path,consent):self.store.export(path,consent);self.status='Private unencrypted export saved.'
    def import_people(self,path,consent=False):self._enqueue('import_people',str(path),consent)
    def _do_import_people(self,path,consent):
        self._ensure_no_enrollment();self._stop_session();self.store.import_archive(path,consent);self.state='IDLE';self.status='Compatible personal profiles imported.'
        if getattr(self,'reference_bank',None):self.reference_bank.freeze('personal_gallery_imported')
        self.metrics.pop('stored_script_review',None)

    def settings_update(self,values):self._enqueue('settings',dict(values))
    def noise_route(self,value):self._enqueue('noise_route',value)
    def noise_snapshot(self):
        engine=self.engine
        router=getattr(engine,'enhancement_router',None)
        if router is not None:return router.snapshot()
        coordinator=getattr(engine,'coordinator',None)
        if coordinator is not None:return coordinator.snapshot(getattr(getattr(engine,'_journal',None),'committed_samples',0))
        return dict(route=self.settings.get('enhancement_route','bypass'),observations={},actions=['No running observations.'])
    def _do_noise_route(self,value):
        from .enhancement import ROUTES
        if value not in ROUTES:raise ValueError('Unknown enhancement route')
        self._ensure_no_enrollment()
        self._stop_session();self.source_kind=None
        if getattr(self,'reference_bank',None):self.reference_bank.freeze('reference_domain_changed')
        if value!='bypass':self.models.enhancement_model(self.config)
        self.settings['enhancement_route']=value;atomic_json(self.data_root/'settings.json',self.settings)
        self.state='IDLE';self.status='Noise route selected. Microphone off; press Start for a fresh epoch. Enhanced identity needs matching references.'
    def text_assistance_action(self,action,**values):self._enqueue('text_assistance',action,values)
    def _do_text_assistance(self,action,values):
        self.text_assistance.change(action,values,self.store.summaries())
        self.status='Text preferences saved; apply to future final text. Raw speech and identity are unchanged.'
    def _do_settings(self,values):
        permitted={'caption_size','theme','preview_zoom','direction','layout','session_quota_mib','completed_session_limit','ram_horizon_sec','spatial_visualization','display_smoothing_ms','numbered_unknowns','highlight_selected','text_aware_references','microphone_preapproved','auto_start_listening'}
        for key in ('microphone_preapproved','auto_start_listening'):
            if key in values and type(values[key]) is not bool:raise ValueError(key+' must be boolean')
        proposed={**self.settings,**values}
        if proposed.get('auto_start_listening') is True and proposed.get('microphone_preapproved') is not True:
            raise ValueError('Automatic listening requires saved microphone permission')
        if 'text_aware_references' in values and type(values['text_aware_references']) is not bool:raise ValueError('Text-aware reference selection must be boolean')
        if 'highlight_selected' in values and type(values['highlight_selected']) is not bool:raise ValueError('Highlight must be boolean')
        if set(values)-permitted:raise ValueError('Unknown UI setting')
        if values.get('direction') not in (None,'off',False):raise ValueError('Live direction calibration unavailable; arrows are disabled')
        if 'spatial_visualization' in values and type(values['spatial_visualization']) is not bool:
            raise ValueError('spatial_visualization must be a boolean')
        if 'numbered_unknowns' in values and type(values['numbered_unknowns']) is not bool:
            raise ValueError('numbered_unknowns must be a boolean')
        if 'display_smoothing_ms' in values and (type(values['display_smoothing_ms']) is not int or values['display_smoothing_ms'] not in (0,150,300)):
            raise ValueError('Unsupported display smoothing')
        for key,allowed in {'session_quota_mib':(64,128,256),'completed_session_limit':(3,10,20),'ram_horizon_sec':(60,120)}.items():
            if key in values and values[key] not in allowed:raise ValueError('Unsupported retention setting '+key)
        self.settings.update(values);atomic_json(self.data_root/'settings.json',self.settings)
        if 'text_aware_references' in values:self.status='Text-aware reference comparison updated for next enrollment / Start. Original voice matching retained.'
        if 'highlight_selected' in values:self._record_display_configuration()
        if 'spatial_visualization' in values and getattr(self.engine, 'live_spatial', None) is not None:
            self.engine.live_spatial.set_display(values['spatial_visualization'])

    def motion_configure(self,compensate):self._enqueue('motion_configure',compensate)
    def motion_mount_configure(self,mounted):self._enqueue('motion_mount_configure',mounted)
    def _do_motion_mount_configure(self,mounted):
        self._ensure_no_enrollment()
        if type(mounted) is not bool:raise ValueError('Mount status must be boolean')
        imu=getattr(self,'imu',None)
        if not hasattr(imu,'motion'):raise ValueError('Fix motion configuration before confirming installation')
        if mounted and not imu.motion.mount.verified:raise ValueError('Configure the fixed sensor and microphone axes first')
        config=read_json(self.data_root/'imu_config.json')
        running=self.state=='RUNNING';self._stop_session()
        config['fixed_mount']=mounted;atomic_json(self.data_root/'imu_config.json',config)
        with imu.lock:imu.motion.fixed_mount=mounted
        self._do_reset_spatial()
        if running and self.mode not in SEAT_MODES:self._start_session()
        self.status=('Fixed mounting saved. Automatic startup reference enabled.' if mounted else
                     'Loose sensor: native XVF angles remain available; motion compensation is inactive.')

    def _do_motion_configure(self,compensate):
        self._ensure_no_enrollment()
        if type(compensate) is not bool:raise ValueError('Rotation assistance must be boolean')
        if getattr(self,'imu',None) is None:raise ValueError('No configured motion sensor')
        if not hasattr(self.imu,'motion'):raise ValueError('Fix motion configuration and restart the app first')
        config=read_json(self.data_root/'imu_config.json')
        running=self.state=='RUNNING'
        self._stop_session()
        config['rotation_compensation']=compensate
        atomic_json(self.data_root/'imu_config.json',config)
        with self.imu.lock:self.imu.motion.compensate=compensate
        self._do_reset_spatial()
        if running and self.mode not in SEAT_MODES:self._start_session()

    def reset_spatial(self):self._enqueue('reset_spatial')
    def _do_reset_spatial(self):
        self._ensure_no_enrollment()
        if getattr(self,'imu',None) is not None:
            running=self.state=='RUNNING';self._stop_session();self.imu.reset()
            self._invalidate_seats('motion_reference_reset; re-anchor seats after calibration')
            self.state='STOPPED';self.status='A new direction reference starts automatically after two quiet seconds. Apply seat layout again if used.'
            if running and self.mode not in SEAT_MODES:self._start_session()
            return
        if getattr(self,'reference_bank',None):self.reference_bank.freeze('tablet_moved')
        if self.mode in SEAT_MODES:
            self._invalidate_seats('manual_tablet_moved')
            self.status='Seat anchor invalidated. Captions continue; re-anchor manually. Voice memory retained.'
            return
        running = self.state == 'RUNNING'
        self._stop_session()
        if running:self._start_session()
        else:self.state='IDLE'
        self.status='Positions reset in a fresh session; saved people retained.'

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
        assistance=self.text_assistance.snapshot(people) if hasattr(self,'text_assistance') else {'enabled':False,'entries':[]}
        active_rules={e['id'] for e in assistance['entries'] if e.get('active') and e.get('approved_auto')}
        edits=getattr(self,'session_annotations',{}).get('corrections',[])
        undone={e.get('reverts') for e in edits}
        manual={e['row_id']:e for e in edits if not e.get('reverts') and e['id'] not in undone}
        for row in raw:row['manual_edit']=deepcopy(manual.get(row.get('caption_key')))
        rows=[]
        for row in raw:
            segments=row.get('segments') or [row]
            provisional=row.get('archived_provisional_display_text',provisional_case(row.get('text',''),names=names))
            final_display=row.get('archived_final_formatted_text',row.get('display_text') if row.get('punctuation_for_text_revision') else None)
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
                closed_choice=deepcopy(part.get('closed_display_assignment')) if self.mode=='selected_closed' else None
                if closed_choice and (part.get('naming_state')=='invalidated' or closed_choice.get('profile_id') not in self.selected_ids
                    or not any(p['id']==closed_choice.get('profile_id') for p in people)):closed_choice=None
                display_known=closed_choice['profile_id'] if closed_choice else known
                selected=display_known in getattr(self,'display_ids',[])
                if self.mode=='caption_only':label='Transcription'
                elif self.mode=='anonymous_conversation':label=part.get('anonymous_label',row.get('anonymous_label','Unknown'))
                elif self.mode=='enrolled_names':label=next((p['name'] for p in people if p['id']==known),'Unknown')
                else:label=next((p['name'] for p in people if p['id']==known),part.get('anonymous_label','Unknown'))
                assignment=part.get('prototype_assignment')
                if closed_choice:
                    label=next(p['name'] for p in people if p['id']==display_known)+' · assumed'
                    assignment='closed_assumed'
                if self.mode in NAMED_MODES and known and assignment in ('forced','assumed_unlinked'):label+=' · assumed'
                if self.mode in NAMED_MODES and known and assignment=='seat_assumed':label+=' · seat assumed'
                if self.mode in NAMED_MODES and known and assignment=='spatial_supported':label+=' · spatial support'
                punct=partition(final_display,part,i)
                aid=row.get('text_assistance') or {}
                corrected=aid.get('corrected_text')
                if len(segments)>1:
                    corrected=corrected_partition(aid.get('input_text',''),corrected,part.get('token_range',(0,0)))
                rows.append({'id':part.get('segment_id',row.get('caption_key',str(row.get('utterance_id')))),
                    'utterance_id':row.get('utterance_id'),'raw_asr_text':text,
                    'provisional_display_text':partition(provisional,part,i) or provisional_case(text,names=names),
                    'final_punctuated_display_text':punct,'label':label,'final':row.get('final',False),
                    'optional_corrected_text':corrected,'show_corrected_text':bool(assistance.get('enabled') and assistance.get('automatic')
                        and aid.get('applied') and all(e.get('rule_id') in active_rules for e in aid['applied'])),
                    'text_assistance_status':aid.get('status'),'manual_edit':deepcopy(row.get('manual_edit')),
                    'selected':selected,'visible':not self.strict or selected,'identity_assignment':assignment,
                    'display_profile_id':display_known,'closed_display_assignment':closed_choice,
                    'closed_group_display':self.mode=='selected_closed' and part.get('prototype_closed_group',False) and display_known is not None,
                    'identity_version':row.get('identity_version'),'profile_id':known,
                    'caption_key':row.get('caption_key'), 'track_id':part.get('track_id'),
                    'span_ids':deepcopy(part.get('span_ids',part.get('token_ids',[]))),
                    'source_start_sec':part.get('source_start_sec',row.get('source_start_sec')),
                    'source_end_sec':part.get('source_end_sec',row.get('source_end_sec')),
                    'timing_kind':part.get('timing_kind','UNAVAILABLE'),
                    'word_spans':deepcopy(part.get('word_spans',[])),
                    'speaker_revision':part.get('speaker_revision'),
                    'first_shown_label':part.get('first_shown_label'),
                    'committed_label':part.get('committed_label'),
                    'speaker_history':deepcopy(part.get('speaker_history',[])),
                    'token_range':deepcopy(part.get('token_range')), 'ownership_state':part.get('ownership_state'),
                    'naming_state':part.get('naming_state'),
                    'identity_status':('unavailable' if part.get('naming_state')=='invalidated' or part.get('voice_available') is False else
                                       'supported' if part.get('ownership_state')=='supported_history' else 'collecting'),
                    'raw_identity':{key:deepcopy(part.get(key)) for key in ('label','anonymous_label','naming_state','known_name',
                                    'known_profile_id','identity_version','identity_event_id','evidence_ids','identity_source_span')}})
        with self.lock:
            metrics=dict(self.metrics)
            if 'recent_identity_decisions' in metrics:
                metrics['recent_identity_decisions']=deepcopy(metrics['recent_identity_decisions'])
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
        spatial = getattr(self.engine, 'live_spatial', None)
        spatial_view = spatial.snapshot() if spatial is not None else {
            'state':'OFF', 'arrows':[], 'associations':[], 'message':'Start live XVF input to see directions.'}
        for association in spatial_view.get('associations', []):
            profile = association.get('profile_id')
            if profile:
                association['label'] = next((p['name'] for p in people if p['id'] == profile), 'Unknown')
                if association.get('seat_assumption'):association['label']+=' · seat assumed'
        assistance['recent']=[{'caption_key':r.get('caption_key'),'raw':r.get('text',''),
                              'final':r.get('display_text'),'assistance':deepcopy(r.get('text_assistance',{})),
                              'manual_edit':deepcopy(r.get('manual_edit'))} for r in raw if r.get('final')][-8:]
        return {'state':self.state,'status':self.status,'error':self.error,'rows':rows,'people':people,'sessions':self.session_snapshot(),
            'audio_review':self.review_snapshot(),
            'adaptation':self.adaptation_snapshot(),
            'noise':self.noise_snapshot(),
            'text_assistance':assistance,
            'reference_comparison':deepcopy(getattr(getattr(self.engine,'_research_gallery',None),'last_alternate',None)) if self.settings.get('text_aware_references',False) else None,
            'motion':self.imu.snapshot() if getattr(self,'imu',None) is not None else {'enabled':False,'state':'NOT_CONFIGURED','error':self.metrics.get('motion_configuration_error')},
            'mode':self.mode,'recipe':self.recipe,'tap':self.tap,'recipes':deepcopy(RECIPES),
            'backend_id':getattr(self,'backend_id',BASELINE_BACKEND_ID),
            'backend':backend_status(getattr(self,'backend_id',BASELINE_BACKEND_ID),self.mode,self.tap,
                                     recorded_spatial=getattr(self,'source_kind',None)=='live'),
            'backends':backend_catalog(), 'saved_audio_only':getattr(self,'saved_audio_only',False),
            'mode_metadata':deepcopy(MODE_METADATA), 'spatial_view':spatial_view,
            'roster_compatibility':self.store.summaries(self.route()) if isinstance(self.store,PersonalStore) else people,
            'identity_overrides':dict(getattr(self,'identity_overrides',{})), 'seating':self.seating_snapshot(),
            'selected_ids':self.selected_ids[:],'display_ids':list(getattr(self,'display_ids',[])),'strict':self.strict,'settings':dict(
                {'completed_session_limit':10,'session_quota_mib':256,'ram_horizon_sec':120,'spatial_visualization':False},**self.settings,
                retention=f"{self.settings.get('completed_session_limit',10)} completed unpinned sessions; {self.settings.get('session_quota_mib',256)}MiB target; 2GiB free floor",
                ram_horizon=f"{self.settings.get('ram_horizon_sec',120)} seconds of live inference audio",
                audio_retention='No ambient WAV archive; enrollment samples discarded after analysis'),
            'enrollment':deepcopy(self.enrollment),'metrics':metrics,'epoch':self.epoch,
            'pending_actions':self.commands.qsize(),'direction':'unavailable',
            'beam_diagnostics':beam_snapshot,'closed':self.closed}

    def close(self):self._enqueue('close')
    def _do_close(self):
        if getattr(self,'imu',None) is not None and not self.imu.close():
            raise RuntimeError('Motion sensor worker still closing; retry Close')
        self._review_cancel('application closed')
        self._stop_playback();self._do_enrollment_cancel();self._stop_session();self._observe_output('application_exit')
        if getattr(self,'reference_bank',None):self.reference_bank.discard();self.reference_bank=None
        if hasattr(self,'session_store'):
            for identifier,archive in list(self.session_store.active.items()):self._archive_end(archive)
        atomic_json(self.data_root/'last_application.json',{'closed_utc':datetime.now(timezone.utc).isoformat(),
            'metrics':self.metrics,'transitions':self.transitions,'output_defaults':self.output_defaults,
            'microphone_open':False,'private_data_not_in_release':True,'terminal_error':self.error})
        if hasattr(self.models,'close'):self.models.close()
        self.closed=True;self.state='CLOSED';self.owner.close();self.commands.put_nowait(None)
