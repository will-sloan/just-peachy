"""S7 native pipeline with portable sources, private galleries and bounded buffers."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import math
import hashlib
import threading
import time
import numpy as np
import soundfile as sf
from .paths import ROOT, read_json
from .buffers import MemoryJournal, AsyncText
from .live_timing import CaptureTimeline, LiveTimingError
from edge_speech_pipeline.runtime import PipelineEngine
from edge_speech_pipeline.models import SherpaStream, SpeakerModels
from edge_speech_pipeline.research_profiles import ResearchProfile
from edge_speech_pipeline.research_s6d import S6DSettings
from edge_speech_pipeline.research_s7 import S7Settings, AbsolutePacer
from .mode_policy import MODES, SPATIAL_PARENTS, NAMED_MODES, SEAT_MODES, apply_overrides
RECIPES=[
 {'id':'fast','name':'Fast captions','description':'Accepted greedy ASR; no speaker model calls.',
  'compatible_modes':['caption_only'],'parent':'S7 C065 / M0'},
 {'id':'classic','name':'Classic continuity','description':'Actual B36 original tracker inside the corrected scheduler; anonymous only.',
  'compatible_modes':['caption_only','anonymous_conversation'],'parent':'B36 original_common'},
 {'id':'balanced','name':'Balanced identity','description':'C065 dual short/mature evidence; C088 safe naming with your compatible profiles.',
  'compatible_modes':list(MODES),'parent':'C065 + C088'},
 {'id':'patient','name':'Patient identity','description':'C067/N03 longer mature evidence with a short path; slower initial identity.',
  'compatible_modes':list(MODES),'parent':'C067/N03 + C088 naming'},
]
for row in RECIPES:
    row.setdefault('available',True);row.setdefault('reason','')
    row.update(taps=['O0','O1'],evidence_status='PROTO1 adaptation of existing recipe; live accuracy unqualified')


def effective_profile(recipe,mode,tap,overrides=None,seat_strength='soft'):
    if seat_strength not in ('soft','strong'):raise ValueError('Unknown seat prior strength')
    if mode=='assigned_direction':seat_strength='soft'  # No hidden voice/seat prior tuning in direction-only.
    if mode not in MODES or tap not in ('O0','O1'):raise ValueError('Unknown mode or tap')
    info=next((r for r in RECIPES if r['id']==recipe),None)
    if info is None or mode not in info['compatible_modes']: raise ValueError('Recipe is unavailable for this mode')
    profiles=read_json(ROOT/'config/s7_profiles.json')
    p=deepcopy(read_json(ROOT/'config/parent_C067.json') if recipe=='patient' else profiles['C065'])
    naming=mode in NAMED_MODES and mode!='assigned_direction'
    p['identity']=deepcopy(profiles['C088']['identity'] if naming else profiles['C065']['identity'])
    if mode in SPATIAL_PARENTS:
        # Reuse the complete frozen tracker, not a new angle-to-person rule.
        # Frontend timing still follows the user's Balanced/Patient recipe;
        # naming remains the independent C088 post-association voice resolver.
        parent_id='C060' if mode in SEAT_MODES and seat_strength=='strong' else SPATIAL_PARENTS[mode]
        parent=read_json(ROOT/('config/parent_'+parent_id+'.json'))
        p['tracker']=deepcopy(parent['tracker'])
        p['xvf']=deepcopy(parent['xvf'])
    if recipe=='classic':
        parent=read_json(ROOT/'config/parent_B36.json')
        p['asr']=parent['asr'];p['segmentation']=parent['segmentation']
        p['embedding'].update(evidence_policy='mature_only',window_sec=.5,hop_sec=.25,
            mature_hop_sec=.25,short_hop_sec=.25,rms_policy='dispatch',purity_policy='gate_only')
    p['profile_id']='PROTO1_'+recipe+'_'+mode+'_'+tap
    # All sources hand the native engine normalized16k once-gained samples.
    # File inputs already carry gain; the verified live adapter applies it once.
    p['input'].update(asr_tap=tap,identity_tap=tap,source_block_ms=20)
    p['runtime'].update(lane_drain_timeout_sec=60.)
    apply_overrides(p,mode,overrides)
    return ResearchProfile.from_dict(p)


class ResidentModels:
    """One recognizer/punctuator; optional speaker sessions are shared and lazy."""
    def __init__(self):
        self.asr=None;self.speakers=None;self.signature=None
        self.enhancer=None;self.enhancer_loads=0
        self.asr_loads=self.speaker_loads=self.streams=0

    def acquire(self,config,caption_only=False):
        signature=tuple((k,v) for k,v in asdict(config).items() if k.startswith('asr_') or k.startswith('endpoint_'))
        if self.asr is None or signature!=self.signature:
            self.asr=None
            self.asr=SherpaStream(config);self.signature=signature;self.asr_loads+=1
        if not caption_only and self.speakers is None:
            self.speakers=SpeakerModels(config);self.speaker_loads+=1
        self.streams+=1
        return (None if caption_only else self.speakers),SherpaStream(config,resident=self.asr)

    def enrollment_models(self,config):
        if self.speakers is None:self.speakers=SpeakerModels(config);self.speaker_loads+=1
        return self.speakers

    def enhancement_model(self,config):
        if self.enhancer is None:
            from .enhancement import DpdfStream
            self.enhancer=DpdfStream(config.asset('redimnet2_b2_fp32').path.parent.parent)
            self.enhancer_loads+=1
        self.enhancer.reset()
        return self.enhancer


class LegacyTracker:
    """Invoke the actual B36 tracker; adapt only the v3 scheduler interface."""
    def __init__(self):
        from edge_speech_pipeline.research_tracking_v2 import S6BTracker
        parent=ResearchProfile.from_dict(read_json(ROOT/'config/parent_B36.json'))
        self.legacy=S6BTracker(parent.tracker)
        self.last=[]

    def update(self,vector,start,end,now,**kwargs):
        kwargs={k:v for k,v in kwargs.items() if k in ('spatial','speech','overlap')}
        result=self.legacy.update(vector,start,end,now,**kwargs)
        self.last=[{'track_id':c.cluster_id,'last_source_sec':c.last_source_sec,
                    'committed':True,'prototype':c.center.copy()} for c in self.legacy._legacy.clusters]
        return result

    def scheduling_state(self,now):return self.last
    def snapshot(self):return self.legacy.snapshot()


class FileSource:
    def __init__(self,journal,path,status_callback,*,start_sample=0,maximum_seconds=3600):
        self.journal=journal;self.path=Path(path);self.callback=status_callback
        self.stop_event=threading.Event();self.thread=None;self.start_sample=start_sample
        self.sent=0;self.maximum_seconds=maximum_seconds
        info=sf.info(self.path)
        if info.samplerate!=16000 or info.channels!=1 or info.subtype!='PCM_16':
            raise ValueError('Choose an already-prepared mono16k PCM16 WAV; no implicit mixing/gain')
        if not 0<=start_sample<info.frames:raise ValueError('Invalid file start sample')
        if info.frames-start_sample>maximum_seconds*16000:raise ValueError('File exceeds bounded1h source session')

    def start(self):
        self.thread=threading.Thread(target=self._run,name='proto-file-source',daemon=True);self.thread.start()

    def _run(self):
        try:
            with sf.SoundFile(self.path) as handle:
                handle.seek(self.start_sample)
                origin=time.perf_counter();pacer=AbsolutePacer(origin,16000,self.stop_event)
                self.callback('source_started',{'source_epoch_monotonic_sec':origin,'mode':'file',
                    'path':str(self.path),'start_sample':self.start_sample,'gain':1.,'pacing':'absolute'})
                while not self.stop_event.is_set():
                    block=handle.read(320,dtype='float32')
                    if not len(block):break
                    if pacer.wait_for_end(self.sent+len(block)) is None:break
                    self.journal.append(block);self.sent+=len(block)
            self.journal.finish()
        except Exception as exc:
            self.journal.finish(str(exc));self.callback('fatal',{'reason':str(exc)})

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(5)
        self.journal.finish()


class LivePipelineSource:
    def __init__(self,journal,live_config,callback,spatial_provider=None):
        from .live_audio import XVFLiveSource
        self.live=XVFLiveSource(live_config)
        self.spatial_provider=spatial_provider
        self.journal=journal;self.callback=callback;self.thread=None;self.stop_event=threading.Event()
        self.start_metadata=None;self.stop_receipt=None;self.integrity=None
        self.sent=0;self.error=None;self._done=threading.Event()
        self.secondary_errors=[]
        self.clock_metadata=None
        self.timing=None
        self._close_lock=threading.RLock()

    def start(self):
        try:
            self.start_metadata=self.live.start(consent=True)
            # perf_counter and monotonic use the same Windows clock, but retain
            # an explicit mapping for other supported Python/platform builds.
            self._clock_offset=time.perf_counter()-time.monotonic()
            self.thread=threading.Thread(target=self._run,name='proto-live-source',daemon=True)
            self.thread.start()
        except Exception as exc:
            self.error='LIVE_START_FAILED: '+str(exc)
            try:self._close_live()
            except Exception as cleanup:self.error+='; cleanup: '+str(cleanup)
            self.journal.finish(self.error);self._done.set()
            raise RuntimeError(self.error) from exc

    def _close_live(self):
        from .live_audio import summarize_live_integrity
        with self._close_lock:
            if self.stop_receipt is None:self.stop_receipt=self.live.stop()
            self.integrity=summarize_live_integrity(self.live)
            if not self.integrity['ok']:
                detail='LIVE_INTEGRITY: '+', '.join(self.integrity['reasons'])
                if not self.error:self.error=detail
                elif detail not in self.error:self.error+='; '+detail
            return self.stop_receipt

    def _source_origin(self,block):
        self.timing=CaptureTimeline(self.start_metadata,block)
        return self.timing.origin,self.timing.metadata()

    def _run(self):
        first=True
        try:
            while not self.stop_event.is_set():
                block=self.live.read(.25)
                if block is None:
                    if self.live.status()['finished']:break
                    continue
                if first:
                    origin,clock_metadata=self._source_origin(block)
                    self.clock_metadata={'source_epoch_monotonic_sec':origin,**clock_metadata}
                    self.callback('source_started',{'source_epoch_monotonic_sec':origin,'mode':'live',
                        'route':self.start_metadata['route'],'endpoint':self.start_metadata['endpoint'],
                        'capture_metadata':self.start_metadata,'clock':'counted XVF samples; immutable stream-start feasibility bound',
                        **clock_metadata,
                        'first_block_source_lag_sec':block.source_lag_seconds,
                        'resampler_delay_seconds':block.resampler_delay_seconds,
                        'clock_not_calibrated_to_acoustic_arrival':True})
                    first=False
                # Validate canonical counts against callback time before journal
                # admission. Consumer delay cannot hide an impossible block.
                self.timing.accept(block,time.perf_counter_ns())
                if (self.sent+len(block.audio))/16000>time.perf_counter()-origin:
                    raise RuntimeError('LIVE_SOURCE_TIMING: source support is ahead of the fixed capture timeline')
                if self.spatial_provider is not None:self.spatial_provider.advance_audio(block)
                self.journal.append(block.audio);self.sent+=len(block.audio)
                if self.journal.duration_sec>=3600:
                    self.callback('source_limit',{'reason':'1h application session boundary; press Start for a fresh session'})
                    break
        except Exception as exc:
            if isinstance(exc,LiveTimingError):
                self.callback('source_timing',{'failure':exc.check,'evidence':exc.evidence,
                    'timing':self.timing.snapshot() if self.timing else None})
            primary=getattr(self.journal,'fatal_error',None)
            if primary:
                self.error=primary
                if str(exc) not in primary:self.secondary_errors.append(str(exc))
            else:self.error='LIVE_GAP_OR_DEVICE_ERROR: '+str(exc)
        finally:
            try:self._close_live()
            except Exception as exc:
                detail='LIVE_STOP_FAILED: '+str(exc)
                self.error=(self.error+'; '+detail) if self.error else detail
            try:
                self.callback('source_stopped',{'integrity':self.integrity,'converted_samples_delivered':self.sent,
                    'secondary_errors':self.secondary_errors,
                    'timing':self.timing.snapshot() if self.timing else None})
                if self.error:self.callback('fatal',{'reason':self.error,'integrity':self.integrity,
                    'secondary_errors':self.secondary_errors})
            finally:
                self.journal.finish(self.error)
                self._done.set()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            # Route reads/setters are bounded individually. The source owns
            # their completion; never report stopped with its thread alive.
            self.thread.join(3)
            if self.thread.is_alive():
                self._close_live()
                self.thread.join(3)
            if self.thread.is_alive():
                self.error='LIVE_SOURCE_THREAD_DID_NOT_EXIT'
                self.journal.finish(self.error)
                raise RuntimeError(self.error)
        else:self._close_live()
        self.journal.finish(self.error)
        self._done.set()
        if self.error:raise RuntimeError(self.error)

    def wait(self,timeout=None):return self._done.wait(timeout)


class PrototypeEngine(PipelineEngine):
    def __init__(self,config,models,profile,gallery,mode,*,writer_delay=0,ram_horizon_sec=120,
                 spatial_provider=None,archive=None,seats=None,seat_names=None,enhancement_route='bypass'):
        from .enhancement import ROUTES
        from .noise_coordination import NoiseCoordinator
        if enhancement_route not in ROUTES:raise ValueError('Unknown enhancement route')
        self.enhancement_route=enhancement_route;self.enhancement_router=None
        self.coordinator=NoiseCoordinator(enhancement_route)
        self.archive=archive
        self.mode=mode;self.prototype_identity=None;self.mode_configuration={};self.seats=seats;self.seat_names=seat_names or {}
        self.live_spatial = spatial_provider
        self.resident=models;self.writer_delay=writer_delay;self.text_writers=[]
        self.ram_horizon_sec=ram_horizon_sec
        self.recipe=profile.profile_id.split('_')[1]
        s7=S7Settings(pacing='absolute',instrumentation='light',mode='M0' if mode=='caption_only' else 'M1' if mode=='anonymous_conversation' else 'M2',
                     presentation_enabled=True,availability_clock='observed',ownership_mode='timestamped_spans_v3')
        super().__init__(config,research_profile=profile,research_gallery=gallery,spatial_provider=spatial_provider,
            s6d_settings=S6DSettings(text_delivery=True,boundary_repair=True,max_display_rows=512),s7_settings=s7)

    def _make_audio_journal(self,path):
        self._quality_next=0
        def observe(start,x):
            if self.archive is not None:self.archive.audio_block(start,x)
            end=start+len(x)
            if end>=self._quality_next:
                self.coordinator.observe('waveform',start/16000,end/16000,
                    dict(rms=float(np.sqrt(np.mean(x.astype(np.float64)**2))),clipped_fraction=float(np.mean(np.abs(x)>=.999))),
                    'actual unenhanced post-XVF samples; no SNR/voice inference')
                self._quality_next=end+8000
        journal=MemoryJournal(path,self.config.sample_rate,self.ram_horizon_sec,observer=observe)
        self._telemetry['proto1_audio_reserve_seconds']=self.ram_horizon_sec
        return journal
    def _open_journal_text(self,path):
        writer=AsyncText(path,delay_once=self.writer_delay if Path(path).name=='events.jsonl' else 0)
        self.text_writers.append(writer);return writer
    def _prepare_native_models(self,caption_only):return self.resident.acquire(self.config,caption_only)

    def _source_status(self,kind,payload):
        if kind=='source_started' and self._spatial_provider is not None:
            self._spatial_provider.bind_origin(payload['source_epoch_monotonic_sec'])
        super()._source_status(kind,payload)

    def begin(self):
        self._begin_session('prototype')
        if self.live_spatial is not None and self.live_spatial.motion is not None and self.recipe!='classic':
            from .live_spatial import MotionFrameTracker
            delegate=self._scheduler.scheduler.tracker
            delegate.target=MotionFrameTracker(delegate.target,self.live_spatial.motion)
        if self.mode in NAMED_MODES:
            from .identity_policy import PrototypeIdentityResolver,DiagnosticTracker
            from edge_speech_pipeline.research_s7_policy import _MeasuredDelegate
            if self.mode in SEAT_MODES:
                from .seat_identity import SeatIdentityResolver
                self.prototype_identity=SeatIdentityResolver(self._research_profile.identity,self._research_gallery,
                    seats=self.seats,names=self.seat_names,provider=self.live_spatial,tracker_config=self._research_profile.tracker,
                    direction_only=self.mode=='assigned_direction',clock=self._s7_observed_clock.relative)
            else:
                self.prototype_identity=PrototypeIdentityResolver(self._research_profile.identity,self._research_gallery,
                    closed=self.mode=='selected_closed',clock=self._s7_observed_clock.relative)
            self._scheduler.scheduler.identity_resolver=_MeasuredDelegate(self.prototype_identity,self._s7_observed_clock,'identity')
            self._scheduler.scheduler.tracker.target=DiagnosticTracker(self._scheduler.scheduler.tracker.target)
        self._emit('prototype_mode_configuration',0.,self.mode_configuration)
        self._emit('prototype_runtime_binding',0.,{'files':{
            name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('app/pipeline.py','app/live_audio.py','app/live_timing.py','app/controller.py',
             'vendor/edge_speech_pipeline/runtime.py','config/assets.json')},
            'scope':'actual loaded prototype source/configuration; no personal data'})
        self._identity_journal=self._journal
        self._input_journal=self._journal
        if self.enhancement_route!='bypass':
            from .enhancement import EnhancementRouter,route_binding
            helper=self.resident.enhancement_model(self.config)
            self.enhancement_router=EnhancementRouter(self._journal.path,self.ram_horizon_sec,self.enhancement_route,helper,
                archive=self.archive,emit=self._emit,coordinator=self.coordinator)
            self._input_journal=self.enhancement_router
            self._journal=self.enhancement_router.asr;self._identity_journal=self.enhancement_router.identity
            self.enhancement_router.start()
            self._emit('enhancement_route',0.,route_binding(self.enhancement_route))
        if self.recipe=='classic':
            # Dispatcher already measures the tracker's calls; replace its delegate target.
            from edge_speech_pipeline.research_s7_policy import _MeasuredDelegate
            self._scheduler.scheduler.tracker=_MeasuredDelegate(LegacyTracker(),self._s7_observed_clock,'tracker')

    def _emit(self,event_type,source_sec,payload):
        self.coordinator.event(event_type,source_sec,payload)
        if event_type=='research_embedding_admission' and self.live_spatial is not None:
            cue=self.live_spatial.evidence(max(0,source_sec-.5),source_sec)
            a,b=getattr(cue,'source_start_sec',None),getattr(cue,'source_end_sec',None)
            if a is not None and b is not None:
                self.coordinator.observe('beam',a,b,dict(valid=cue.valid,angle_deg=cue.angle_deg,reliability=cue.reliability,
                    upstream_available_at_sec=cue.available_at_sec),'existing XVF mapped source evidence; direction supports a request, never identity proof')
        if event_type=='s6d_display' and getattr(self,'prototype_identity',None) is not None and self.mode!='selected_closed':
            payload=self.prototype_identity.annotate_caption(payload)
        router=self.enhancement_router
        if event_type=='s6d_display' and router is not None and router.identity_limit is not None:
            # Enhanced identity stopped at the failure boundary. Keep all words
            # while preventing stale pre-failure names from labelling raw fallback.
            from copy import deepcopy
            payload=deepcopy(payload)
            for row in [payload]+payload.get('segments',[]):
                end=row.get('source_end_sec',payload.get('source_end_sec',source_sec))
                if end*16000>router.identity_limit:
                    row.update(known_profile_id=None,known_name=None,track_id=None,speaker='Unknown',label='Unknown',
                               anonymous_label=None,voice_available=False,ownership_status='unknown',
                               naming_state='unavailable',identity_reason='enhancement failed; new Start required for identity')
        if event_type=='s6d_display' and getattr(self,'prototype_identity',None) is not None and self.mode=='selected_closed':
            payload=self.prototype_identity.annotate_caption(payload)
        super()._emit(event_type,source_sec,payload)

    def start_prepared_file(self,path,start_sample=0):
        source=FileSource(None,path,self._source_status,start_sample=start_sample)
        self.begin()
        source.journal=self._input_journal
        return self._launch(source)

    def start_xvf(self,live_config):
        self.begin()
        source=LivePipelineSource(self._input_journal,live_config,self._source_status,self._spatial_provider)
        if self._spatial_provider is not None:self._spatial_provider.attach(source.live)
        return self._launch(source)

    def _watch_session(self):
        try:super()._watch_session()
        finally:
            if self.enhancement_router is not None:
                try:self.enhancement_router.finish();self.enhancement_router.join()
                except Exception as exc:self._finalization_error=exc;self._state='FAILED'
            if self._s7_trace is not None:
                try:self._s7_trace.close()
                except Exception as exc:self._finalization_error=exc;self._state='FAILED'
