"""Accepted same-pass beam inputs and native hooks. See README_RESEARCH_S6D_BEAMS.md."""
from __future__ import annotations
from contextlib import ExitStack
from bisect import bisect_right
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import threading
import time
import numpy as np

from .audio import AudioJournal
from .research_audio_v3 import PairedJournal,PairedWavSource
from .research_evidence_v3 import EvidenceAdmissionV3
from .research_identity_v3 import ResearchIdentityResolver,union_intervals
from .research_tracking_v3 import S6CTracker
from .research_profiles import segmentation_gate
from .runtime import PipelineEngine


def binding(path):
    path=Path(path).resolve();digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':digest.hexdigest()}


def verified(ref):
    if not isinstance(ref,dict) or binding(ref['path'])!=ref:raise ValueError('Changed or malformed beam evidence binding')
    return json.loads(Path(ref['path']).read_text(encoding='utf-8-sig'))


def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def verify_cli_inputs(paths,receipt_path,expected_sha256):
    receipt=binding(receipt_path)
    if receipt['sha256']!=expected_sha256:raise ValueError('Changed frozen capture job input receipt')
    value=verified(receipt)
    if value.get('schema_version')!='edge-s6d-beam-job-inputs.v1' or set(value.get('inputs',{}))!=set(paths):
        raise ValueError('Incomplete capture job input binding')
    for key,path in paths.items():
        if binding(path)!=value['inputs'][key]:raise ValueError('Changed frozen capture job input: '+key)
    return receipt


@dataclass(frozen=True)
class BeamSettings:
    schema_version:str='edge-s6d-beams.v1'
    mode:str='mono_asr_beam_identity'
    asr_stream:str='auto_asr'
    identity_streams:tuple[str,...]=('focus0_asr','focus1_asr')
    selected_profile_ids:tuple[str,...]=()
    maximum_evidence_age_sec:float=.75
    calibration:dict|None=None

    def validate(self):
        if self.schema_version!='edge-s6d-beams.v1' or self.mode not in {'same_pass_auto_control','mono_asr_beam_identity','selected_beam_association','calibration_collection'}:
            raise ValueError('Unsupported explicit beam mode')
        if self.asr_stream not in {'auto_asr','auto_pp'}:raise ValueError('This low-cost route retains one continuous auto decoder')
        if not 1<=len(self.identity_streams)<=2 or len(set(self.identity_streams))!=len(self.identity_streams):
            raise ValueError('One or two focused identity streams required; no six permanent stacks')
        allowed={'focus0_asr','focus0_pp','focus1_asr','focus1_pp'} if self.mode!='same_pass_auto_control' else {self.asr_stream}
        if any(s not in allowed for s in self.identity_streams):
            raise ValueError('Unsupported focused identity stream')
        if len({s.split('_')[0] for s in self.identity_streams})!=len(self.identity_streams):
            raise ValueError('ASR and PP copies of one beam are not two independent identity lanes')
        if not finite(self.maximum_evidence_age_sec) or not 0<self.maximum_evidence_age_sec<=2:
            raise ValueError('Finite bounded evidence freshness required')
        if any(not isinstance(x,str) or not x for x in self.selected_profile_ids) or len(set(self.selected_profile_ids))!=len(self.selected_profile_ids):
            raise ValueError('Selected profile IDs must be fixed unique strings')
        if self.mode=='selected_beam_association' and not self.selected_profile_ids:
            raise ValueError('Selected-beam mode requires explicit admitted profile IDs')
        if self.mode=='calibration_collection' and self.calibration is not None:
            raise ValueError('C collection disables calibrated selectors explicitly')
        return self

    @classmethod
    def load(cls,path):
        raw=json.loads(Path(path).read_text(encoding='utf-8-sig'))
        for key in ('identity_streams','selected_profile_ids'):
            if key in raw:raw[key]=tuple(raw[key])
        return cls(**raw).validate()


class CaptureAdmission:
    """No transport PASS alone licenses scientific route identity or tail validity."""
    def __init__(self,path,settings):
        import soundfile as sf
        settings.validate();self.binding=binding(path);data=verified(self.binding)
        if data.get('schema_version')!='edge-s6d-capture-admission.v1' or data.get('status')!='ACCEPTED_FOR_NATIVE_ANALYSIS':
            raise ValueError('Explicit accepted physical capture admission required')
        for key in ('capture_source_id','route_id','capture_epoch','common_origin'):
            if not isinstance(data.get(key),str) or not data[key]:raise ValueError('Missing capture provenance '+key)
        self.data=data;self.result=verified(data['case_result']);proof=verified(data['qualification'])
        if self.result.get('status')!='PASS' or self.result.get('transport_integrity_status')!='PASS':
            raise ValueError('Rejected physical transport cannot enter native analysis')
        if proof.get('schema_version')!='edge-s6d-route-qualification.v1' or proof.get('status')!='PASS':
            raise ValueError('Independent physical stream/clock/tail qualification missing')
        if proof.get('case_result')!=data['case_result'] or proof.get('configuration')!=self.result.get('configuration'):
            raise ValueError('Qualification belongs to another physical pass or route')
        for key in ('stream_identity_verified','common_frame_origin_verified','source_tail_validity_verified'):
            if proof.get(key) is not True:raise ValueError('Physical qualification missing: '+key)
        if data.get('configuration')!=self.result.get('configuration'):raise ValueError('Capture configuration mismatch')
        configuration=verified(data['configuration']);self.capture_profile=configuration.get('profile')
        if self.capture_profile not in {'P_MAIN6','P_SCAN6'}:raise ValueError('Unsupported physical capture profile')
        self.streams={r['name']:r for r in self.result['streams']}
        if len(self.streams)!=len(self.result['streams']):raise ValueError('Duplicate logical capture stream name')
        names=tuple(dict.fromkeys((settings.asr_stream,)+settings.identity_streams))
        if not set(names)<=set(self.streams):raise ValueError('Requested stream was not captured in this pass')
        sample_counts=[];origins=[];expected_routes={'auto_asr':(7,3),'auto_pp':(6,3),'focus0_asr':(7,0),'focus1_asr':(7,1),'focus0_pp':(6,0),'focus1_pp':(6,1)}
        for name in names:
            row=self.streams[name]
            if (row.get('category'),row.get('source'))!=expected_routes[name]:raise ValueError('Logical stream/category/source route mismatch')
            if not finite(row.get('raw_gain')) or row['raw_gain']!=1. or binding(row['audio']['path'])!=row['audio']:raise ValueError('Changed or normalized capture derivative')
            info=sf.info(row['audio']['path'])
            if info.samplerate!=16000 or info.channels!=1 or info.subtype not in {'PCM_16','PCM_24','PCM_32','FLOAT'}:
                raise ValueError('Only lossless mono16kHz capture derivatives; no resampling/downmix')
            sample_counts.append(info.frames);origins.append(row.get('common_capture_start_native_frame'))
        if len(set(sample_counts))!=1 or sample_counts[0]<=0 or len(set(origins))!=1 or type(origins[0]) is not int or origins[0]<0:
            raise ValueError('Streams do not share complete sample count and proven capture frame origin')
        if data.get('sample_count')!=sample_counts[0]:raise ValueError('Admitted complete sample count changed')
        if data.get('stream_names')!=list(self.streams):raise ValueError('Captured route order must be explicit and predeclared')
        if not set(names)<=set(proof.get('stream_names',[])):raise ValueError('Requested route was not physically qualified')
        self.names=names;self.frames=sample_counts[0]
        self.calibration_partition=None
        if settings.mode=='calibration_collection':
            self.calibration_partition=data.get('calibration_partition')
            partition=verified(self.calibration_partition)
            if (partition.get('schema_version')!='edge-s6d-beam-calibration-partition.v1' or partition.get('partition')!='C' or
                partition.get('Q_used') is not False or partition.get('disjoint_from_E_Q_verified') is not True or
                data['case_result'] not in partition.get('accepted_case_results',[])):
                raise ValueError('C collection requires disjoint partition proof binding this accepted physical pass')
        self.directions=[];self.direction_index={};self.direction_status='UNAVAILABLE_NO_QUALIFIED_SPATIAL_SOURCE_SUPPORT'
        if data.get('direction_observations') is not None:
            value=verified(data['direction_observations'])
            if value.get('capture_source_id')!=data['capture_source_id'] or value.get('route_id')!=data['route_id']:
                raise ValueError('Spatial observations belong to another capture route')
            if value.get('source_support_qualification') is not None:
                spatial=verified(value['source_support_qualification'])
                if spatial.get('schema_version')!='edge-s6d-spatial-source-qualification.v1' or spatial.get('status')!='PASS' or spatial.get('case_result')!=data['case_result'] or spatial.get('source_span_not_reply_time_only') is not True:
                    raise ValueError('Spatial source support belongs to another pass or lacks independent timing evidence')
                self.directions=value.get('observations',[])
                if not isinstance(self.directions,list) or len(self.directions)>100000:raise ValueError('Bounded spatial observation list required')
                self.direction_status='QUALIFIED_SPATIAL_SOURCE_SUPPORT_AVAILABLE'
                for stream in names:
                    rows=sorted([r for r in self.directions if r.get('stream_id')==stream and r.get('capture_source_id')==data['capture_source_id'] and
                        r.get('route_id')==data['route_id'] and finite(r.get('available_at_sec'))],key=lambda r:r['available_at_sec'])
                    self.direction_index[stream]=([r['available_at_sec'] for r in rows],rows)

    def provenance(self,stream):
        return {k:self.data[k] for k in ('capture_source_id','route_id','capture_epoch','common_origin')}|{'stream_id':stream,
            'capture_audio':self.streams[stream]['audio'],'same_pass_capture':self.binding}


class MultiJournal(PairedJournal):
    def __init__(self,journals):
        super().__init__(journals[0],journals[-1]);self.journals=tuple(journals)

    def append(self,*blocks):
        if len(blocks)!=len(self.journals) or len({len(x) for x in blocks})!=1:
            raise ValueError('All captured stream blocks must commit at one source boundary')
        if any(not np.isfinite(x).all() or np.any(np.abs(x)>1.) for x in blocks):raise ValueError('Nonfinite/out-of-range captured audio')
        with self.condition:
            if self.finished:raise RuntimeError('Capture journals are closed')
            try:
                for journal,block in zip(self.journals,blocks):journal.append(block)
            except Exception as exc:
                self.finish(str(exc));raise
            self.committed_samples+=len(blocks[0]);self.condition.notify_all()


class CapturedSource(PairedWavSource):
    def __init__(self,multi,admission,*,status_callback,realtime=True):
        self.pair=multi;self.admission=admission
        self.paths=tuple(Path(admission.streams[n]['audio']['path']) for n in admission.names)
        self.expected_samples=admission.frames;self.realtime=realtime;self.accelerated_factor=0.
        self.block_samples=1600;self.status_callback=status_callback
        self.stop_event=threading.Event();self.pause_event=threading.Event();self.thread=None

    def _run(self):
        import soundfile as sf
        try:
            with ExitStack() as stack:
                handles=[stack.enter_context(sf.SoundFile(p)) for p in self.paths]
                self.status_callback('source_started',{'mode':'accepted_multistream_capture','streams':list(self.admission.names),
                    'capture_admission':self.admission.binding,'expected_samples':self.expected_samples,
                    'common_origin':self.admission.data['common_origin'],'gain_in_producer':1.,
                    'source_block_sec':.1,'publication_policy':'all journals written then common block committed before sleep'})
                while not self.stop_event.is_set():
                    while self.pause_event.is_set() and not self.stop_event.is_set():self.stop_event.wait(.05)
                    if self.stop_event.is_set():break
                    blocks=[h.read(self.block_samples,dtype='float32') for h in handles]
                    if len({len(x) for x in blocks})!=1:raise RuntimeError('Captured streams ended asynchronously')
                    if not len(blocks[0]):break
                    self.pair.append(*blocks)
                    if self.realtime:self.stop_event.wait(len(blocks[0])/16000)
                if not self.stop_event.is_set() and self.pair.committed_samples!=self.expected_samples:
                    raise RuntimeError('Captured source did not deliver admitted full length')
            self.pair.finish()
        except Exception as exc:
            self.pair.finish(str(exc));self.status_callback('fatal',{'reason':'CAPTURED_SOURCE_FAILED','detail':str(exc)})


def waveform_similarity(a,b):
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64)
    if a.shape!=b.shape or a.size<8000 or not np.isfinite(a).all() or not np.isfinite(b).all():return None
    a=a-a.mean();b=b-b.mean();den=float(np.linalg.norm(a)*np.linalg.norm(b))
    return float(a@b/den) if den>1e-12 else None


class BeamSelector:
    """Calibration is separate from unchanged single-stream gallery thresholds."""
    def __init__(self,settings,gallery_binding,*,profile_digest=None,capture_profile=None,capture_identity=None):
        self.settings=settings;self.calibration=None;self.last_stream=None;self.last_time=-math.inf
        self.capture_identity=capture_identity
        if settings.calibration is not None:
            raw=verified(settings.calibration)
            if raw.get('schema_version')!='edge-s6d-beam-calibration.v1' or raw.get('status')!='ACCEPTED_C_ONLY' or raw.get('gallery')!=gallery_binding:
                raise ValueError('Exact-gallery disjoint-C multiple-beam calibration required')
            proof=verified(raw['calibration_evidence'])
            if proof.get('partition')!='C' or proof.get('Q_used') is not False or proof.get('disjoint_from_E_Q_verified') is not True:
                raise ValueError('Calibration must have disjoint C evidence and no Q selection')
            if raw.get('identity_streams')!=list(settings.identity_streams):raise ValueError('Calibration beam multiplicity/taps mismatch')
            if not profile_digest or raw.get('profile_sha256')!=profile_digest or not capture_profile or raw.get('capture_profile')!=capture_profile:
                raise ValueError('Calibration model/window/profile or capture-mode context mismatch')
            if raw.get('selected_profile_ids')!=list(settings.selected_profile_ids):raise ValueError('Calibrated selected-gallery opportunity count differs')
            duplicate_enabled=raw.get('duplicate_resolution_enabled',False)
            if type(duplicate_enabled) is not bool:raise ValueError('Duplicate resolution must be explicitly capability scoped')
            keys=('minimum_selected_score','minimum_selected_margin','minimum_beam_margin','minimum_auto_correlation','minimum_auto_margin')
            if duplicate_enabled:keys+=('duplicate_waveform_correlation','duplicate_voice_cosine','continuity_bonus')
            if any(not finite(raw.get(k)) or not 0<=raw[k]<=1 for k in keys):raise ValueError('Invalid calibrated selector thresholds')
            if duplicate_enabled and raw['continuity_bonus']>raw['minimum_beam_margin']:raise ValueError('Continuity cannot override the calibrated no-match margin')
            self.calibration={k:raw[k] for k in keys}|{'duplicate_resolution_enabled':duplicate_enabled}

    def choose(self,candidates,now,*,auto_wave=None,auto_support=None,auto_speech=False):
        base={'selected_stream':None,'known_profile_id':None,'status':'NO_MATCH','calibrated':self.calibration is not None}
        if self.calibration is None:return base|{'reason':'multiple_beam_C_calibration_unavailable'}
        c=self.calibration
        if not finite(now):return base|{'reason':'invalid_clock'}
        eligible=[r for r in candidates if r.get('speech') is True and r.get('overlap') is False and
            all(finite(r.get(k)) for k in ('source_start_sec','source_end_sec','available_at_sec')) and
            0<=r['source_start_sec']<r['source_end_sec']<=r['available_at_sec'] and
            0<=now-r['available_at_sec']<=self.settings.maximum_evidence_age_sec and
            0<=now-r['source_end_sec']<=self.settings.maximum_evidence_age_sec and
            r.get('stream_id') in self.settings.identity_streams and
            all(isinstance(r.get(k),str) and r[k] for k in ('capture_source_id','route_id'))]
        if len({(r['capture_source_id'],r['route_id']) for r in eligible})>1:return base|{'reason':'mixed_capture_or_route_evidence'}
        if self.capture_identity is not None and any((r['capture_source_id'],r['route_id'])!=self.capture_identity for r in eligible):
            return base|{'reason':'foreign_capture_or_route_evidence'}
        if auto_wave is not None:
            if auto_speech is not True:return base|{'reason':'no_exclusive_auto_speech'}
            if not isinstance(auto_support,(tuple,list)) or len(auto_support)!=2 or not all(finite(x) for x in auto_support):
                return base|{'reason':'auto_source_support_unavailable'}
            scored=[]
            for row in eligible:
                if any(abs(row[k]-auto_support[i])>1/16000 for i,k in enumerate(('source_start_sec','source_end_sec'))):continue
                score=waveform_similarity(auto_wave,row['waveform'])
                if score is not None:scored.append((score,row))
            scored.sort(key=lambda x:x[0],reverse=True)
            if not scored or scored[0][0]<c['minimum_auto_correlation']:return base|{'reason':'auto_focus_association_unavailable'}
            if len(scored)>1 and scored[0][0]-scored[1][0]<c['minimum_auto_margin']:
                return base|{'reason':'competing_auto_focus_associations','scores':[x[0] for x in scored]}
        else:
            scored=[]
            for row in eligible:
                identity=row.get('identity',{})
                if identity.get('naming_state')!='confirmed' or identity.get('known_profile_id') not in self.settings.selected_profile_ids:continue
                score=identity.get('current_query_name_cosine');margin=identity.get('margin')
                if not finite(score) or not finite(margin) or score<c['minimum_selected_score'] or margin<c['minimum_selected_margin']:continue
                scored.append((score,row))
            scored.sort(key=lambda x:x[0],reverse=True)
            if not scored:return base|{'reason':'no_current_selected_voice'}
            if len(scored)>1:
                a,b=scored[0][1],scored[1][1];similarity=waveform_similarity(a['waveform'],b['waveform'])
                same=a['identity'].get('known_profile_id')==b['identity'].get('known_profile_id')
                same_span=all(abs(a[k]-b[k])<=1/16000 for k in ('source_start_sec','source_end_sec'))
                duplicate=c.get('duplicate_resolution_enabled',False) and same and same_span and similarity is not None and similarity>=c['duplicate_waveform_correlation'] and float(np.asarray(a['vector'])@np.asarray(b['vector']))>=c['duplicate_voice_cosine']
                if not duplicate and scored[0][0]-scored[1][0]<c['minimum_beam_margin']:
                    return base|{'reason':'competing_selected_beams','duplicate_proven':False}
                if duplicate:
                    # Select one copy; never sum unique duration or create a second named arrow.
                    previous=next((x for x in scored if x[1]['stream_id']==self.last_stream and now-self.last_time<=self.settings.maximum_evidence_age_sec),None)
                    if previous and scored[0][0]-previous[0]<=c['continuity_bonus']:scored.remove(previous);scored.insert(0,previous)
        chosen=scored[0][1]
        if auto_wave is None:self.last_stream=chosen['stream_id'];self.last_time=now
        return base|{'status':'ASSOCIATED','selected_stream':chosen['stream_id'],'known_profile_id':chosen.get('identity',{}).get('known_profile_id'),
            'known_name':chosen.get('identity',{}).get('known_name'),'evidence_id':chosen['event_id'],
            'source_start_sec':chosen['source_start_sec'],'source_end_sec':chosen['source_end_sec'],
            'available_at_sec':now,'score':scored[0][0],'reason':'calibrated_current_voice_and_source_support',
            'waveform_switched':False,'unique_evidence_not_summed_across_beams':True}


class BeamIdentityState:
    def __init__(self,profile,gallery,stream):
        self.stream=stream;self.admission=EvidenceAdmissionV3(profile);self.tracker=S6CTracker(profile.tracker)
        self.resolver=ResearchIdentityResolver(profile.identity,gallery)
        self.rolling=np.empty(0,np.float32);self.since_seg=0;self.speech=self.overlap=False
        self.serial=0;self.segment_serial=0;self.latest=None;self.speech_record=None


class BeamPipelineEngine(PipelineEngine):
    """One Sherpa stream plus one serial shared Pyannote/ReDimNet owner, at most two focus states."""
    def __init__(self,*args,beam_settings,**kwargs):
        super().__init__(*args,**kwargs)
        self.beam_settings=beam_settings.validate()
        if self._s6d is None or not self._research_v3 or self._research_profile.xvf.mode!='none' or self._research_profile.embedding.cadence_cues_enabled:
            raise ValueError('Beam integration requires opt-in S6D/v3 with old selected-angle cues disabled')
        if self._research_gallery is None:raise ValueError('Beam identity requires the exact admitted original or device-domain gallery')
        if set(beam_settings.selected_profile_ids)-set(self._research_gallery.ids):raise ValueError('Selected beam profile outside admitted gallery')
        self.capture=None;self._beam_views={};self._beam_source_origin=None
        self._beam_stats={'model_instance_counts':{'sherpa_recognizer':1,'sherpa_decoder_states':1,'pyannote':1,'redimnet':1},
            'waveform_switches':0,'segmentation_calls':0,'embedding_calls':0,'serial_model_owner':True,'maximum_focus_lanes':2,
            'model_api_wall_sec':0.,'identity_policy_wall_sec':0.,'model_queue_depth':0,
            'direction_association':'UNAVAILABLE_WITHOUT_VERIFIED_SOURCE_SUPPORT'}

    def start_file(self,*args,**kwargs):raise ValueError('Beam engine starts only an accepted captured-input admission')
    def start_paired_files(self,*args,**kwargs):raise ValueError('Use start_capture; loose O0/O1 paths cannot license new beam inputs')

    def start_capture(self,admission_path,*,realtime=True):
        # Reject an active session before validation or any beam state publication.
        if self._state not in {'IDLE','COMPLETED','FAILED'}:
            raise RuntimeError(f'a session is already {self._state.lower()}')
        capture=CaptureAdmission(admission_path,self.beam_settings)
        # Gallery manifest is hashed by the gallery loader; calibration binds that same file.
        gallery_ref=self._research_gallery.receipt.get('manifest')
        if not isinstance(gallery_ref,dict):raise ValueError('Research gallery receipt lacks its source manifest binding')
        selector=BeamSelector(self.beam_settings,gallery_ref,profile_digest=self._research_profile.digest(),
            capture_profile=capture.capture_profile,capture_identity=(capture.data['capture_source_id'],capture.data['route_id']))
        # Recorder/finalizer/consumer-closure guards may also reject. Keep candidate
        # provenance local until the inherited session admission has succeeded.
        self._begin_session('s6d_captured_beams')
        self._beam_selector=selector;self.capture=capture;self._beam_source_origin=None
        try:
            journals=[self._journal]+[AudioJournal(self._session_dir/(name+'_audio_spool.pcm16'),16000) for name in capture.names[1:]]
            multi=MultiJournal(journals);self._paired_journal=multi
            self._beam_views={name:multi.view(i) for i,name in enumerate(capture.names)}
            self._journal=self._beam_views[self.beam_settings.asr_stream];self._identity_journal=self._beam_views[self.beam_settings.identity_streams[0]]
            source=CapturedSource(multi,capture,status_callback=self._source_status,realtime=realtime)
            self._emit('s6d_beam_input_route',0.,{'capture_admission':capture.binding,'stream_bindings':[capture.provenance(n) for n in capture.names],
                'beam_mode':self.beam_settings.mode,'profile_input_taps_are_parent_recipe_only':True,
                'actual_asr_stream':self.beam_settings.asr_stream,'actual_identity_streams':list(self.beam_settings.identity_streams),
                'selected_profile_ids':list(self.beam_settings.selected_profile_ids),'calibration':self.beam_settings.calibration,
                'new_waveform_requires_new_native_predictions':True,'shared_source_commit_barrier':True,'no_waveform_splicing':True,
                'main_focus_bridge_evidence':'mature_only_with_calibrated_auto_waveform_support',
                'direction_capability':capture.direction_status,'model_input_representation':'existing PCM16 journal quantization; original captured lossless files retained'})
            return self._launch(source)
        except Exception as exc:
            self._fail('S6D captured-input launch failed: '+str(exc));raise

    def _source_status(self,kind,payload):
        if kind=='source_started':self._beam_source_origin=time.perf_counter()
        return super()._source_status(kind,payload)

    def _speaker_loop(self,models):
        if self.beam_settings.mode=='same_pass_auto_control':
            from .research_evidence_v3 import run_speaker_lane_v3
            return run_speaker_lane_v3(self,models)
        profile=self._research_profile;step=round(profile.embedding.hop_sec*16000);seg_step=round(profile.segmentation.hop_sec*16000)
        states={name:BeamIdentityState(profile,self._research_gallery,name) for name in self.beam_settings.identity_streams}
        auto=BeamIdentityState(profile,self._research_gallery,self.beam_settings.asr_stream)
        cursor=0;pending={name:np.empty(0,np.float32) for name in self.capture.names};main_serial=0;bridged=set()
        self._beam_stats.update(segmentation_calls=0,embedding_calls=0,model_api_wall_sec=0.,identity_policy_wall_sec=0.,model_owner_object_id=str(id(models)))
        def now(end):return max(end,time.perf_counter()-self._beam_source_origin) if self._beam_source_origin is not None else end
        try:
            while True:
                if self._state=='FAILED':raise RuntimeError('Beam lane aborts after session failure')
                block=self._journal.read(cursor,step)
                if not block.size:
                    if self._journal.finished and cursor>=self._journal.committed_samples:break
                    continue
                inputs={name:view.read(cursor,len(block),wait_sec=0) for name,view in self._beam_views.items()}
                if any(len(x)!=len(block) for x in inputs.values()):raise RuntimeError('Capture journal common barrier violated')
                cursor+=len(block)
                for name in pending:pending[name]=np.concatenate((pending[name],inputs[name]))
                while len(pending[self.beam_settings.asr_stream])>=step:
                    end=(cursor-len(pending[self.beam_settings.asr_stream])+step)/16000
                    chunks={n:x[:step] for n,x in pending.items()};pending={n:x[step:] for n,x in pending.items()}
                    # One owner serializes all actual model calls; no concurrent mutable last-call metrics.
                    order=[auto]+[states[n] for n in self.beam_settings.identity_streams]
                    for state in order:
                        chunk=chunks[state.stream];state.rolling=np.concatenate((state.rolling,chunk))[-160000:];state.since_seg+=step
                        if state.since_seg>=seg_step:
                            state.since_seg%=seg_step;started=time.perf_counter()
                            views=models.segment(np.pad(state.rolling,(160000-len(state.rolling),0)),include_posteriors=True)
                            model_api=time.perf_counter()-started;self._beam_stats['model_api_wall_sec']+=model_api
                            gate=segmentation_gate(views,self.config,state.speech);state.speech,state.overlap=gate['speech'],gate['overlap']
                            state.admission.segmentation(views,end);state.segment_serial+=1;self._beam_stats['segmentation_calls']+=1
                            state.speech_record={**self.capture.provenance(state.stream),'evidence_id':f'{state.stream}:seg:{state.segment_serial:08d}',
                                'source_start_sec':max(0.,end-profile.segmentation.hop_sec),'source_end_sec':end,'available_at_sec':now(end),
                                'speech':state.speech,'overlap':state.overlap,'model_api_elapsed_sec':model_api}
                            self._emit('s6d_beam_speech',end,state.speech_record)
                            if state is auto:
                                self._scheduler.push({'kind':'segmentation','event_id':f'beam_auto_seg:{state.segment_serial:08d}',
                                    **{k:state.speech_record[k] for k in ('source_start_sec','source_end_sec','available_at_sec','speech','overlap')}},'speaker')
                        if state is auto:continue
                        context=state.tracker.scheduling_state(now(end)) if profile.embedding.cadence_policy=='uncertainty' else []
                        for diagnostic in state.admission.candidates(state.rolling,chunk,end,state.speech,state.overlap,tracking_context=context):
                            self._emit('s6d_beam_embedding_admission',end,{**self.capture.provenance(state.stream),**diagnostic})
                            if not diagnostic['admitted']:continue
                            started=time.perf_counter();waveform=state.rolling[-diagnostic['samples']:].copy();vector=models.embed(waveform)
                            model_api=time.perf_counter()-started;self._beam_stats['model_api_wall_sec']+=model_api
                            self._beam_stats['embedding_calls']+=1;state.admission.admitted(diagnostic['evidence_kind'],vector,end,diagnostic)
                            state.serial+=1;event={'kind':'embedding','event_id':f'{state.stream}:embedding:{state.serial:08d}',
                                'source_start_sec':diagnostic['source_start_sec'],'source_end_sec':end,'available_at_sec':now(end),
                                'vector':vector.tolist(),'speech':state.speech,'overlap':state.overlap,'evidence_kind':diagnostic['evidence_kind'],
                                'clean_intervals':diagnostic['clean_intervals'],'rms':diagnostic['selected_rms'],
                                'clipping_fraction':diagnostic['clipping_fraction'],'clean_fraction':diagnostic['clean_fraction']}
                            policy_started=time.perf_counter()
                            decision=state.tracker.update(vector,event['source_start_sec'],end,event['available_at_sec'],
                                speech=state.speech,overlap=state.overlap,evidence_kind=event['evidence_kind'],clean_intervals=event['clean_intervals'],observation_id=event['event_id'])
                            state.resolver.sync_tracks({r['track_id'] for r in state.tracker.scheduling_state(event['available_at_sec'])},event['available_at_sec'])
                            decision=state.resolver.resolve(decision,event)
                            policy_cost=time.perf_counter()-policy_started;self._beam_stats['identity_policy_wall_sec']+=policy_cost
                            self._emit('s6d_beam_identity',end,{**self.capture.provenance(state.stream),**event,'identity':decision['identity'],
                                'model_api_elapsed_sec':model_api,'identity_policy_elapsed_sec':policy_cost,'independent_unique_duration_not_summed':True})
                            if event['evidence_kind']=='mature':state.latest={**event,**self.capture.provenance(state.stream),'identity':decision['identity'],'waveform':waveform}
                    ready=now(end);candidates=[s.latest for s in states.values() if s.latest]
                    selected=self._beam_selector.choose(candidates,ready)
                    self._emit('s6d_selected_beam_association',end,{**selected,'capture_source_id':self.capture.data['capture_source_id'],'route_id':self.capture.data['route_id']})
                    size=round(profile.embedding.window_sec*16000)
                    auto_clean=sum(max(0.,min(end,b)-max(0.,end-size/16000,a)) for a,b in union_intervals(auto.admission.clean))
                    associate=self._beam_selector.choose([r for r in candidates if r['source_end_sec']==end],ready,auto_wave=auto.rolling[-size:],auto_support=(max(0.,end-size/16000),end),
                        auto_speech=auto.speech and not auto.overlap and auto_clean>=profile.embedding.minimum_clean_fraction*(size/16000))
                    self._emit('s6d_auto_beam_association',end,{**associate,'asr_stream':self.beam_settings.asr_stream,
                        'capture_source_id':self.capture.data['capture_source_id'],'route_id':self.capture.data['route_id']})
                    if associate['status']=='ASSOCIATED' and associate['evidence_id'] not in bridged:
                        chosen=next(r for r in candidates if r['event_id']==associate['evidence_id']);bridged.add(chosen['event_id']);main_serial+=1
                        if len(bridged)>profile.scheduler.max_events:raise RuntimeError('Bounded beam bridge event budget exhausted')
                        event={k:chosen[k] for k in ('kind','source_start_sec','source_end_sec','vector','speech','overlap','evidence_kind','clean_intervals','rms','clipping_fraction','clean_fraction')}
                        event.update(event_id=f'beam_bridge:{main_serial:08d}',available_at_sec=now(end))
                        self._scheduler.push(event,'speaker')
                    self._publish_beam_directions(states,ready)
                    self._scheduler_advance('speaker',end,now(end))
                    self._telemetry.update(speaker_cursor_sec=end,speaker_analyzed_through_sec=end,speaker_lag_sec=max(0.,self._journal.duration_sec-end))
                    self._beam_stats.update(source_cursor_sec=end,source_queue_age_sec=max(0.,self._journal.duration_sec-end),
                        model_owner_elapsed_sec=now(end),per_beam_identity={name:s.resolver.snapshot() for name,s in states.items()})
            self._telemetry.update(speaker_cursor_sec=cursor/16000,speaker_unanalyzed_short_tail_sec=len(pending[self.beam_settings.asr_stream])/16000,
                speaker_lag_sec=0.,identity_audio_samples=self._identity_journal.committed_samples,paired_audio_samples=self._journal.committed_samples)
        except Exception as exc:self._fail('S6D beam identity lane failed: '+str(exc))
        finally:self._scheduler_advance('speaker',float('inf'),now(cursor/16000))

    def _publish_beam_directions(self,states,now):
        observations=[];voices=[];speech=[]
        for stream,state in states.items():
            candidate=state.latest
            if state.speech_record:speech.append(state.speech_record)
            if candidate is None:continue
            voices.append({**self.capture.provenance(stream),**candidate['identity'],'evidence_id':candidate['event_id'],
                **{k:candidate[k] for k in ('source_start_sec','source_end_sec','available_at_sec')}})
            times,rows=self.capture.direction_index.get(stream,([],[]));index=bisect_right(times,now)-1
            if index>=0 and state.speech_record:
                row=rows[index]
                # Same independently qualified audio route binds actual native speech/voice IDs.
                # Source support/confidence come from the admitted spatial record, never invented here.
                observations.append({**row,'voice_evidence_id':candidate['event_id'],'speech_evidence_id':state.speech_record['evidence_id']})
        self.publish_s6d_direction(observations,speech,voices,now)

    def _emit(self,event_type,source_sec,payload):
        if hasattr(self,'beam_settings') and self.beam_settings.mode=='same_pass_auto_control' and hasattr(self,'_beam_stats'):
            if event_type=='research_segmentation':self._beam_stats['segmentation_calls']+=1
            if event_type=='research_embedding':self._beam_stats['embedding_calls']+=1
        return super()._emit(event_type,source_sec,payload)

    def telemetry(self):
        data=super().telemetry()
        if hasattr(self,'_beam_stats'):data['s6d_beams']=dict(self._beam_stats)
        return data
