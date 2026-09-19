"""Diagnostic-only dual-journal runner; see README_S6D_BEAM_DIAGNOSTIC_V2.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

RATE=16000
PINS={'protocol':'874d55b0449f5cb53d9b6bf476d7a8cf97d1022e1cffd5ef844f71af5f8c5084',
      'evidence':'bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2',
      'native_loop':'29ccc47374d8830d72b5214e64e62c08c41ad141265571fb149a5420fe0aed12',
      'beam':'deaf0af827c77afe9cfa9781eb70299e6833e1705d899b2fc228ea6bea0ba720'}
ROUTES={'auto_asr_raw':(7,3),'auto_pp_raw':(6,3),'focus0_asr_raw':(7,0),'focus1_asr_raw':(7,1),
        'focus0_pp_raw':(6,0),'focus1_pp_raw':(6,1),'scan_asr_raw':(7,2),'scan_pp_raw':(6,2)}

def need(value,message):
    if not value:raise ValueError(message)
def bind(path):
    path=Path(path).resolve();before=path.stat();h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    after=path.stat();need((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'File changed while hashing')
    return dict(path=str(path),bytes=after.st_size,sha256=h.hexdigest())
def verified(b):
    need(bind(b['path'])==b,'Changed input: '+b['path'])
    return json.loads(Path(b['path']).read_text(encoding='utf-8-sig'),parse_constant=lambda x:need(False,'Nonfinite JSON'))
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def module(b,name):
    verified(b) if b['path'].endswith('.json') else need(bind(b['path'])==b,'Changed module')
    spec=importlib.util.spec_from_file_location(name,b['path']);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def journal_representation(audio):
    """Hash exactly the frozen AudioJournal float32→PCM16 representation; write no audio."""
    import numpy as np
    import soundfile as sf
    need(bind(audio['path'])==audio,'Raw capture changed');h=hashlib.sha256();frames=0
    with sf.SoundFile(audio['path']) as f:
        need(f.samplerate==RATE and f.channels==1 and f.subtype in {'PCM_16','PCM_24','PCM_32','FLOAT'},'Lossless mono16k capture required')
        expected=f.frames
        while True:
            x=f.read(65536,dtype='float32')
            if not len(x):break
            need(np.isfinite(x).all() and np.all(np.abs(x)<=1),'Invalid capture samples')
            y=np.round(np.clip(x,-1.,.999969)*32768.).astype('<i2');h.update(y.tobytes());frames+=len(y)
    need(frames==expected and bind(audio['path'])==audio,'Truncated/changed source')
    return dict(audio=audio,frames=frames,bytes=frames*2,sha256=h.hexdigest(),gain=1.0,
        representation='Unchanged frozen AudioJournal float32 round(clip[-1,0.999969]*32768) little-endian PCM16 once; no saved derivative')

def validate_original_identity(original,case_id,capture_profile):
    attempt=original.get('attempt') or {};configuration=verified(original['configuration'])
    need(attempt.get('case_id')==case_id and attempt.get('profile')==capture_profile==configuration.get('profile'),'Actual physical case/profile differs from declared cell')
    source=attempt.get('source_audio')
    need(isinstance(source,dict) and source==original.get('source_input',{}).get('source')==configuration.get('source_input',{}).get('source'),'Attempt/input/configuration original source bindings disagree')
    need(bind(source['path'])==source,'Original microphone/source bytes changed')
    return source

def admitted_source(job):
    admission=verified(job['admission']);original=verified(admission['original_case_result']);q=verified(admission['original_qualification'])
    need(q.get('status')=='PASS' and q.get('case_result')==admission['original_case_result'] and q.get('configuration')==original['configuration'],'Actual root-qualified case required')
    need(all(q.get(k) is True for k in ('stream_identity_verified','common_frame_origin_verified','source_tail_validity_verified')),'Transport alone is insufficient')
    need(original.get('status')==original.get('transport_integrity_status')=='PASS','Original physical result rejected')
    validate_original_identity(original,job['case_id'],job['capture_profile'])
    actual={r['name']:r for r in original['streams']};need(len(actual)==len(original['streams']),'Duplicate raw stream')
    view=verified(admission['case_result']);view_q=verified(admission['qualification'])
    need(view.get('original_case_result')==admission['original_case_result'] and view_q.get('original_qualification')==admission['original_qualification'],'Native view lacks original provenance')
    need(view_q.get('case_result')==admission['case_result'] and view_q.get('configuration')==original['configuration'],'Projected qualification differs')
    projected=[]
    for r in original['streams']:
        projected.append({**r,'original_stream_name':r['name'],'name':r['name'].removesuffix('_raw')})
    need(view.get('streams')==projected and view.get('configuration')==original['configuration'],'Native view changed audio/order/route beyond declared aliases')
    if job['mode']=='calibration_collection':
        cp=verified(admission['calibration_partition']);base=verified(cp['original_partition'])
        need(base.get('partition')=='C' and base.get('Q_used') is False and base.get('disjoint_from_E_Q_verified') is True and admission['original_case_result'] in base.get('accepted_case_results',[]),'Original actual C partition absent')
    for name,proof in job['stream_proofs'].items():
        row=actual[name];need((row['category'],row['source'])==ROUTES[name] and row['raw_gain']==1,'Route/gain differs')
        need(name in q['stream_names'],'Requested stream not qualified')
        need(proof==journal_representation(row['audio']),'Predeclared full journal representation differs')
    need(len({x['frames'] for x in job['stream_proofs'].values()})==1,'Unequal full source lengths')
    if job['mode']=='stream_diagnostic':validate_diagnostic_source(job,original)
    return admission,original

def validate_diagnostic_source(job,original):
    """Tie the actual start_file input and both expected journals to one admitted stream."""
    name=job['asr_raw_stream'];proofs=job['stream_proofs']
    need(job['mode']=='stream_diagnostic' and set(proofs)=={name},'One exact diagnostic stream proof required')
    rows=[r for r in original['streams'] if r['name']==name];need(len(rows)==1,'Unique admitted diagnostic stream required')
    proof=proofs[name];n=job['expected_frames']
    need(type(n) is int and n>0 and type(job.get('expected_identity_frames')) is int and job['expected_identity_frames']==n==proof['frames'],'Both diagnostic full frame declarations required')
    need(job['audio']==proof['audio']==rows[0]['audio'],'Diagnostic input differs from exact admitted stream')
    need(proof['bytes']==n*2 and job['audio_pcm_sha256']==proof['sha256'],'Diagnostic source PCM declaration differs')
    return proof


def diagnostic_pair_proof(job,session):
    """Hash both existing closed native spools; no audio transformation or model work."""
    name=job['asr_raw_stream'];proof=job['stream_proofs'][name];session=Path(session).resolve()
    return dict(stream_name=name,source_audio=job['audio'],expected_frames=job['expected_frames'],source_pcm_sha256=proof['sha256'],
                asr=bind(session/'audio_spool.pcm16'),identity=bind(session/'identity_audio_spool.pcm16'))


def validate_multistream(result,job,finalization,closure,journals,dispatch,diagnostic_pair=None):
    errors=[]
    def check(v,m):
        if not v:errors.append(m)
    n=job['expected_frames'];t=result.get('telemetry') or {}
    check(type(n) is int and n>0,'positive full frames absent')
    check(result.get('job')==job and result.get('status')=='COMPLETE' and result.get('failure') is None,'Native result failed or literal job changed')
    check(result.get('native_tested') is True and result.get('resource_observer_closed') is True and result.get('event_consumer_drained') is True,'Native ownership/consumer not closed')
    check(result.get('observer_errors')==result.get('completion_errors')==[],'Observer/drain errors')
    for k in ('source_duration_sec','asr_cursor_sec','speaker_cursor_sec'):
        v=t.get(k);check(isinstance(v,(int,float)) and not isinstance(v,bool) and abs(v*RATE-n)<.001,'Incomplete cursor: '+k)
    for k in ('paired_audio_samples','identity_audio_samples'):check(type(t.get(k)) is int and t[k]==n,'Incomplete source count: '+k)
    for k in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):check(type(t.get(k)) is int and t[k]==0,'Nonzero/missing loss counter: '+k)
    check(t.get('state')=='COMPLETED' and t.get('live_lanes_at_finalization')==[] and t.get('bundle_retained_due_live_lanes') is False,'Engine/lane closure absent')
    scheduler=t.get('scheduler') or {};check(scheduler.get('closed') is True and scheduler.get('pending_events')==0 and scheduler.get('watermarks')=={'asr':'closed','speaker':'closed'},'Scheduler not drained')
    check(finalization.get('state')=='COMPLETED' and finalization.get('finalization_error','absent') is None and finalization.get('event_and_transcript_handles_closed') is True and finalization.get('live_lanes_at_finalization')==[] and finalization.get('resident_bundle_lease_retained') is False,'Finalizer not closed')
    check(finalization.get('source_samples')==finalization.get('identity_samples')==n,'Finalizer accepted only prefix')
    queues=t.get('s6d') or {}
    for lane in ('journal','punctuation','policy'):
        q=queues.get(lane) or {};check(q.get('closed') is True and q.get('thread_alive') is False and q.get('error','absent') is None and q.get('depth')==0 and type(q.get('accepted')) is int and q.get('accepted')==q.get('completed'),'Worker not drained: '+lane)
    check((queues.get('event_consumer') or {}).get('depth')==0 and closure.get('full_event_consumer_drained') is True and closure.get('queues')==queues,'Consumer closure absent')
    check(set(journals)==set(job['stream_proofs']),'Missing extra focus journal')
    for name,p in job['stream_proofs'].items():
        j=journals.get(name) or {};check(j.get('bytes')==p['bytes']==n*2 and j.get('sha256')==p['sha256'],'Incomplete/changed journal: '+name)
    if job['mode']=='stream_diagnostic':
        pair=diagnostic_pair or {};name=job.get('asr_raw_stream');proof=job['stream_proofs'].get(name) or {};session=Path(result.get('session_dir','')).resolve()
        check(set(job['stream_proofs'])=={name} and pair.get('stream_name')==name,'Diagnostic pair stream differs')
        check(pair.get('source_audio')==job.get('audio')==proof.get('audio'),'Diagnostic pair source differs')
        check(type(job.get('expected_identity_frames')) is int and job['expected_identity_frames']==n==pair.get('expected_frames'),'Diagnostic pair full frames differ')
        check(pair.get('source_pcm_sha256')==job.get('audio_pcm_sha256')==proof.get('sha256'),'Diagnostic pair source PCM differs')
        for lane,filename in (('asr','audio_spool.pcm16'),('identity','identity_audio_spool.pcm16')):
            record=pair.get(lane) or {}
            check(isinstance(result.get('session_dir'),str) and isinstance(record.get('path'),str) and Path(record.get('path','')).resolve()==session/filename,'Foreign diagnostic '+lane+' journal path')
            check(record.get('bytes')==proof.get('bytes')==n*2 and record.get('sha256')==proof.get('sha256'),'Incomplete/changed diagnostic '+lane+' journal')
        check(pair.get('asr')==journals.get(name),'Diagnostic ASR proof differs from shared audit')
    check(dispatch.get('frames')==n,'Full ASR dispatch absent')
    if job['mode']!='stream_diagnostic':
        beams=t.get('s6d_beams') or {};check(beams.get('waveform_switches')==0 and beams.get('serial_model_owner') is True and beams.get('model_instance_counts')=={'sherpa_recognizer':1,'sherpa_decoder_states':1,'pyannote':1,'redimnet':1},'Bounded beam model contract differs')
    return errors

class CalibrationProbe:
    """Passive C-only observation of actual selector arguments; delegate result is unchanged."""
    def __init__(self,delegate,emit,similarity):self.delegate,self.emit,self.similarity=delegate,emit,similarity;self.count=0
    def __getattr__(self,key):return getattr(self.delegate,key)
    def choose(self,candidates,now,**kwargs):
        result=self.delegate.choose(candidates,now,**kwargs);self.count+=1
        auto=kwargs.get('auto_wave');support=kwargs.get('auto_support');rows=[]
        for row in candidates:
            v={k:row.get(k) for k in ('event_id','stream_id','capture_source_id','route_id','source_start_sec','source_end_sec','available_at_sec','speech','overlap','identity')}
            same=auto is not None and isinstance(support,(tuple,list)) and len(support)==2 and all(abs(row[k]-support[i])<=1/16000 for i,k in enumerate(('source_start_sec','source_end_sec')))
            v['same_auto_window']=same;v['auto_waveform_correlation']=self.similarity(auto,row['waveform']) if same else None
            rows.append(v)
        self.emit('s6d_C_selector_probe',support[1] if support else max([r.get('source_end_sec',0.) for r in candidates]+[0.]),dict(probe_index=self.count,selector='auto' if auto is not None else 'selected',selector_now_sec=now,auto_support=list(support) if support else None,exclusive_auto_speech=kwargs.get('auto_speech',False),candidates=rows,actual_disabled_result=result,collection_only=True,thresholds_applied=False))
        return result

def run(manifest_path,manifest_sha,job_id):
    mb=bind(manifest_path);need(mb['sha256']==manifest_sha,'Manifest changed');m=verified(mb)
    need(m['schema']=='s6d-beam-execution.v1' and m['runner_helper']==bind(__file__),'Frozen execution helper mismatch')
    matches=[j for j in m['jobs'] if j['job_id']==job_id];need(len(matches)==1,'Exact job required');job=matches[0]
    need(m.get('stage')=='stream_diagnostics' and job.get('mode')=='stream_diagnostic','This additive wrapper is diagnostic-only; existing C/core epochs remain separate')
    for key in ('protocol','evidence','native_loop'):need(m['support'][key]['sha256']==PINS[key],'Accepted helper changed')
    for b in m['source_files']:need(bind(b['path'])==b,'Frozen application source changed')
    beam=next(b for b in m['source_files'] if Path(b['path']).name=='research_beams_s6d.py');need(beam['sha256']==PINS['beam'],'Accepted beam source differs')
    W=module(m['support']['protocol'],'beam_protocol_support');E=module(m['support']['evidence'],'beam_evidence_support');N=module(m['support']['native_loop'],'beam_native_loop_support')
    import psutil
    process=psutil.Process();affinity=W.admit_affinity(process,m)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    need(os.environ['S6D_JOB_ID']==job_id and os.environ['S6D_RUN_ID']==m['run_id'],'Supervisor job/run identity differs')
    identity=dict(run_id=os.environ['S6D_RUN_ID'],job_id=job_id,child_run_id=os.environ['S6D_CHILD_RUN_ID'],pid=os.getpid(),creation_time=process.create_time())
    hb,completion,stop=(Path(os.environ[k]) for k in ('S6D_HEARTBEAT_PATH','S6D_COMPLETION_PATH','S6D_STOP_REQUEST_PATH'))
    output=Path(job['output']);need(not output.exists() and not hb.exists() and not completion.exists(),'Fresh protocol/native output required')
    bridge=W.ProtocolBridge(identity,hb,stop,job);engine=None;failure=None
    try:
        bridge.thread.start();bridge.guard();admission,physical=admitted_source(job);bridge.update('FULL_CAPTURE_INPUT_VERIFIED');bridge.guard()
        for key in ('profile_binding','gallery','s6d_settings','beam_settings'):
            if job.get(key):verified(job[key])
        sys.dont_write_bytecode=True;sys.path.insert(0,m['source_root'])
        import edge_speech_pipeline.config as cfg
        import edge_speech_pipeline.research_profiles as profiles
        import edge_speech_pipeline.research_s6d as s6d
        import edge_speech_pipeline.research_beams_s6d as beams
        import edge_speech_pipeline.runtime as runtime
        for mod in (cfg,profiles,s6d,beams,runtime):need(Path(mod.__file__).resolve().parent==Path(m['source_root'])/'edge_speech_pipeline','Foreign module epoch imported')
        assets=verified(m['assets']);base=cfg.PipelineConfig(assets=tuple(cfg.AssetSpec(x['component_id'],Path(x['path']),x['sha256'],x['deployment_relative_path']) for x in assets),session_root=output/'sessions',profile_root=output/'unused_private_profiles')
        need({x.component_id:x.sha256 for x in base.assets}=={x.component_id:x.sha256 for x in cfg.PipelineConfig().assets},'Original eight weights changed')
        profile=profiles.ResearchProfile.load(job['profile_binding']['path']);settings=s6d.S6DSettings(**job['settings'])
        need(verified(job['profile_binding'])==job['profile'],'Inline original profile differs')
        common=dict(research_profile=profile,research_gallery=job['gallery']['path'],s6d_settings=settings)
        if job['mode']=='stream_diagnostic':
            class Instrumented(runtime.PipelineEngine):
                def _emit(self,kind,sec,payload):return super()._emit(kind,sec,{**payload,'pilot_publication_monotonic_sec':time.perf_counter()})
            engine=Instrumented(base,**common)
        else:
            class Instrumented(beams.BeamPipelineEngine):
                def _emit(self,kind,sec,payload):return super()._emit(kind,sec,{**payload,'pilot_publication_monotonic_sec':time.perf_counter()})
                def _launch(self,source):
                    if job['mode']=='calibration_collection':self._beam_selector=CalibrationProbe(self._beam_selector,self._emit,beams.waveform_similarity)
                    return super()._launch(source)
                def start_file(self,path,*,realtime=True):
                    need(Path(path).resolve()==Path(job['audio']['path']).resolve(),'Native-loop auto input differs')
                    return self.start_capture(job['admission']['path'],realtime=realtime)
            engine=Instrumented(base,beam_settings=beams.BeamSettings.load(job['beam_settings']['path']),**common)
        need(all(getattr(engine.config,k)==1 for k in ('asr_threads','speaker_threads','punctuation_threads')),'One thread per backend required')
        output.mkdir(parents=True,exist_ok=False)
        result=N.execute_cell(engine,job,m,manifest_path,output,bridge.checkpoint)
        need(result['helper']==m['support']['native_loop'] and result['pid']==identity['pid'] and abs(result['process_create_time']-identity['creation_time'])<.001,'Inner native owner/source changed')
        bridge.update('VALIDATING_ALL_CAPTURE_JOURNALS');bridge.guard()
        session=Path(result['session_dir']);journals={}
        for name in job['stream_proofs']:
            if job['mode']=='stream_diagnostic' or name==job['asr_raw_stream']:path=session/'audio_spool.pcm16'
            else:path=session/(name.removesuffix('_raw')+'_audio_spool.pcm16')
            journals[name]=bind(path)
        finalization=E.read_json(session/'session_finalization_v3.json')[0]
        closure=E.read_json(session/'s6d_consumer_closure.json')[0]
        eb=bind(output/'consumer_events.jsonl');dispatch=E.validate_dispatch(E.stream(eb['path']),job['expected_frames']);need(bind(eb['path'])==eb,'Consumer journal changed')
        pair=diagnostic_pair_proof(job,session)
        errors=validate_multistream(result,job,finalization,closure,journals,dispatch,pair)
        audit=dict(status='PASS_FULL_MULTISTREAM_EVIDENCE' if not errors else 'REJECTED',errors=errors,job_id=job_id,manifest=mb,physical_case_result=admission['original_case_result'],journals=journals,diagnostic_pair=pair,dispatch=dispatch,source_proofs=job['stream_proofs'],consumer_events=eb)
        save(output/'FULL_MULTISTREAM_AUDIT.json',audit);need(not errors,'; '.join(errors));bridge.close();bridge.guard()
        def final_guard():
            bridge.guard();need(not bridge.thread.is_alive() and process.cpu_affinity()==affinity,'Observer/affinity changed')
            need(bind(manifest_path)==mb and bind(__file__)==m['runner_helper'],'Final source changed')
            for b in m['source_files']+list(m['support'].values()):need(bind(b['path'])==b,'Final code/source graph changed')
            for key in ('profile_binding','gallery','s6d_settings','admission','beam_settings'):
                if job.get(key):verified(job[key])
        final_guard();bridge.heartbeat()
        result_bound=bind(output/'RESULT.json');audit_bound=bind(output/'FULL_MULTISTREAM_AUDIT.json')
        completed=dict(identity,status='COMPLETE',failure=None,native_job_id=job_id,manifest=mb,helper=m['runner_helper'],inner_native_loop=m['support']['native_loop'],result=result_bound,completion_audit=audit_bound,full_multistream_evidence_validated=True,affinity_verified=affinity,protocol_observer_closed=True,protocol_observer_errors=[],stop_requested=False,native_run_one_same_process=True,subprocess_spawned_by_wrapper=False,gui_tested=False,physical_scanout_tested=False,mode=job['mode'],raw_waveforms_unchanged=True)
        completed['diagnostic_dual_journal_evidence_validated']=True
        W.publish_exclusive(completion,completed,final_guard);print(json.dumps(dict(status='COMPLETE',completion=bind(completion))))
    except BaseException as exc:
        failure=repr(exc);bridge.failure=failure
        if engine is not None:
            try:engine.stop();engine.wait_for_completion(60)
            except BaseException:pass
        try:bridge.close()
        except BaseException:pass
        W.save(completion.parent/'BEAM_WRAPPER_FAILURE.json',dict(identity,status='FAILED',failure=failure,manifest=mb,completed=False))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha256',required=True);p.add_argument('--job-id',required=True);a=p.parse_args();run(a.manifest,a.manifest_sha256,a.job_id)
