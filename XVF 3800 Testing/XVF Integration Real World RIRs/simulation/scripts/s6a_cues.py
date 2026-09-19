"""S6A causal reference trackers and shared physical cues. README_S6A_CUES.md."""
from __future__ import annotations
import argparse
import bisect
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
import numpy as np

SIM = Path(__file__).resolve().parents[1]
REPO = SIM.parents[2]
H2 = REPO/'Software Validation from Datasets/Evaluation Tool'
if str(H2) not in sys.path: sys.path.insert(0, str(H2))
from app.edge_speech_pipeline.research_tracking import ResearchTracker, TrackingConfig, SpatialObservation, MODES

DEFAULT_REPORT = SIM/'reports/S6A/20260909T202250Z'
BANK = SIM/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
PRIOR = SIM/'reports/S4_5/20260909T031300Z'
RATE = 16000
PROFILES = {'B0':'exact_native', 'R1_voice_time':'voice_time', 'R2_angle_diagnostic':'angle_diagnostic',
            'R3_sustained_angle':'sustained_angle', 'R4_decaying_memory':'decaying_memory',
            'R5_reliability_adaptive':'reliability_adaptive'}
FEATURE_SCHEMA = 'jp_s6a_baseline_redim_cache_v1'
_BIND_CACHE = {}


def now(): return datetime.now(timezone.utc).isoformat()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
def save(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name('.'+path.name+'.'+str(os.getpid())+'.tmp')
    with temporary.open('w',encoding='utf-8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n');handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,path)
def binding(path, expected=None):
    path=Path(path).resolve();st=path.stat();key=(str(path),st.st_size,st.st_mtime_ns)
    if key not in _BIND_CACHE:
        h=hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda:handle.read(1024*1024),b''): h.update(block)
        end=path.stat()
        if (st.st_size,st.st_mtime_ns)!=(end.st_size,end.st_mtime_ns): raise ValueError('input changed: '+str(path))
        _BIND_CACHE[key]=dict(path=str(path),sha256=h.hexdigest(),bytes=st.st_size)
    result=_BIND_CACHE[key]
    if expected is not None and result['sha256']!=expected: raise ValueError('binding mismatch: '+str(path))
    return dict(result)
def verified(record):
    binding(record['path'],record['sha256']);return Path(record['path'])
def write_csv(path, rows):
    import csv
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fields);writer.writeheader();writer.writerows(rows)


def load_jobs(report):
    value=read(report/'JOB_MANIFEST.json');jobs=value['jobs']
    bank=read(BANK);ids={s['case_id'] for s in bank['scenes']}
    if len(ids)!=240 or len(jobs)!=480 or {(j['case_id'],j['stream']) for j in jobs}!={(i,o) for i in ids for o in ('O0','O1')}:
        raise ValueError('S6A requires exactly the authorized 240 scenes and both taps')
    return jobs,bank


def resolve_native(job):
    path=Path(job['report_dir'])/'run_receipt.json'
    if not path.exists(): return None
    wrapper_binding=binding(path);value=read(path);chain=[wrapper_binding]
    if value.get('status')!='COMPLETE': return None
    visited={str(path.resolve()).lower()}
    while value.get('reused_receipt'):
        bound=value['reused_receipt'];path=verified(bound)
        if str(path.resolve()).lower() in visited:raise ValueError('cyclic native receipt')
        visited.add(str(path.resolve()).lower());chain.append(binding(path));value=read(path)
        if value.get('status')!='COMPLETE':raise ValueError('incomplete reused native')
    if value['raw_audio']['sha256']!=job['raw_audio']['sha256'] or value['adapter']['gain_scalar']!=job['gain']:
        raise ValueError('native source or once-only gain differs')
    summary=read(verified(value['session_summary_binding']))
    if summary.get('state')!='COMPLETED':raise ValueError('native summary incomplete')
    events=[json.loads(line) for line in verified(value['events_binding']).read_text(encoding='utf-8').splitlines() if line.strip()]
    if sum(e['event_type']=='session_completed' for e in events)!=1 or any(e['event_type']=='failure' for e in events):
        raise ValueError('native event completion invalid')
    journal=value['completion_evidence']['journal'];verified(journal)
    if journal['bytes']!=value['adapter']['samples']*2:raise ValueError('native journal duration differs')
    return dict(receipt=value,receipt_chain=chain,events=events,journal=journal,summary=summary)


def feature_identity(journal, events_binding, checkpoint, runtime_version, threads, model_source):
    """Only dependencies of actual accepted-window vectors and their costs."""
    return dict(schema=FEATURE_SCHEMA,audio_sha256=journal['sha256'],audio_bytes=journal['bytes'],
                rate=RATE,channels=1,format='little_endian_PCM16',normalization='float32(samples)/32768; no additional gain',
                native_events_sha256=events_binding['sha256'],window_samples=8000,
                window_selection='exact chronological baseline speaker_decision ends; [end-8000,end)',
                checkpoint_sha256=checkpoint,provider='CPUExecutionProvider',onnxruntime_version=runtime_version,
                intra_op_threads=threads,inter_op_threads=1,numeric_mode='float32',
                frontend='checkpoint waveform frontend unchanged; unit L2 output',
                model_embed_and_session_source_sha256=model_source,
                extraction_semantics_sha256=digest(inspect.getsource(extract_vectors)),
                earliest_availability='serial speaker lane max(input end, previous availability)+segment/embed measured costs',
                policy_or_truth_dependency=False)


def extract_vectors(native, model):
    pcm=np.memmap(native['journal']['path'],dtype='<i2',mode='r')
    vectors=[];features=[];tasks=[];last_end=-1.;speech=overlap=False
    for event in native['events']:
        kind=event['event_type'];end=float(event['source_time_sec']);payload=event['payload']
        if kind=='segmentation':
            speech,overlap=bool(payload['speech']),bool(payload['overlap'])
            tasks.append(dict(kind='segmentation',source_end_sec=end,
                              receptive_start_sec=max(0.,end-10.),left_zero_padding_sec=max(0.,10.-end),
                              compute_sec=float(payload['compute_ms'])/1000.,cost_source='historical_exact_native_call'))
        elif kind=='speaker_decision':
            stop=round(end*RATE);start=stop-8000
            if end<=last_end or start<0 or stop>pcm.size or not speech or overlap:
                raise ValueError('baseline accepted embedding chronology/gate invalid')
            last_end=end
            samples=np.asarray(pcm[start:stop],np.float32)/np.float32(32768.)
            vector=model.embed(samples);cost=float(model.last_embed_ms)/1000.
            features.append(dict(index=len(features),source_start_sec=start/RATE,source_end_sec=end,
                                 speech=True,overlap=False,embedding_compute_sec=cost,
                                 historical_embedding_compute_sec=float(payload['embedding_compute_ms'])/1000.,
                                 rms=float(np.sqrt(np.mean(np.square(samples,dtype=np.float64)))),
                                 native_anonymous_label=payload['anonymous_label']))
            vectors.append(vector)
            tasks.append(dict(kind='embedding',source_end_sec=end,index=len(features)-1,compute_sec=cost,
                              cost_source='new_exact_window_actual_ReDim_call'))
    # Log order is causal within the speaker lane, independently of ASR events.
    ready=0.
    for task in tasks:
        ready=max(ready,task['source_end_sec'])+task['compute_sec']
        task['modeled_available_at_sec']=ready
        if task['kind']=='embedding':features[task['index']]['available_at_sec']=ready
    return np.asarray(vectors,np.float32).reshape((-1,192)),features,tasks


class ExactReDim:
    def __init__(self,threads=2):
        import onnxruntime
        from app.edge_speech_pipeline.config import PipelineConfig
        # Execute the immutable B0 methods while research app wrappers evolve.
        # Only the current app's unchanged asset bindings supply absolute paths.
        from s6a_common import SNAPSHOT
        if str(SNAPSHOT) not in sys.path:sys.path.insert(0,str(SNAPSHOT))
        from edge_speech_pipeline.models import SpeakerModels,_ort_session
        config=PipelineConfig();asset=config.asset('redimnet2_b2_fp32')
        self.checkpoint=binding(asset.path,asset.sha256)
        self._redim=_ort_session(str(asset.path),threads);self._lock=threading.Lock();self.last_embed_ms=0.
        self.runtime_version=onnxruntime.__version__;self.threads=threads
        self.source=digest(inspect.getsource(SpeakerModels.embed)+inspect.getsource(_ort_session))
        self._embed=SpeakerModels.embed
        inputs=self._redim.get_inputs()
        if len(inputs)!=1 or inputs[0].name!='waveform':raise ValueError('unexpected ReDim frontend')
    def embed(self,samples):return self._embed(self,samples)


def extract(report,limit=None):
    import psutil
    from s6a_common import resources,launch_allowed
    jobs,_=load_jobs(report);folder=report/'cues';payload=Path('G:/Just_Peachy_S6A')/report.name/'cue_features'
    folder.mkdir(parents=True,exist_ok=True);payload.mkdir(parents=True,exist_ok=True)
    process=psutil.Process();started=time.perf_counter();created=process.create_time()
    invocation=folder/'invocations'/('extract_'+str(os.getpid())+'_'+str(round(created*1000))+'.json')
    initial=dict(pid=os.getpid(),creation_time=created,started_utc=now(),status='RUNNING',threads=2,
                 argv=sys.argv,requested_limit=limit)
    save(folder/'EXTRACT_PROCESS.json',initial);save(invocation,initial)
    model=ExactReDim(2);rows=[];done=cached=waiting=calls=0;compute=0.;peak=process.memory_info().rss
    try:
        for job in jobs:
            if not launch_allowed(60):break
            if (done+cached)%20==0:resources()
            native=resolve_native(job)
            if native is None:
                waiting+=1;rows.append(dict(case_id=job['case_id'],stream=job['stream'],status='WAITING_NATIVE'));continue
            identity=feature_identity(native['journal'],native['receipt']['events_binding'],model.checkpoint['sha256'],
                                      model.runtime_version,model.threads,model.source)
            key=digest(identity);target=folder/'features'/job['case_id']/(job['stream']+'.json')
            if target.exists():
                record=read(target)
                if record['feature_key']!=key:raise ValueError('feature cache identity changed; use versioned output: '+str(target))
                verified(record['vectors']);cached+=1
            else:
                vectors,features,tasks=extract_vectors(native,model)
                dest=payload/job['case_id']/(job['stream']+'_'+key[:16]+'.npz');dest.parent.mkdir(parents=True,exist_ok=True)
                temporary=dest.with_suffix('.tmp.npz');np.savez_compressed(temporary,vectors=vectors);os.replace(temporary,dest)
                record=dict(schema=FEATURE_SCHEMA,feature_key=key,identity=identity,case_id=job['case_id'],stream=job['stream'],
                            vectors=binding(dest),features=features,speaker_lane_tasks=tasks,native_receipts=native['receipt_chain'],
                            checkpoint=model.checkpoint,created_utc=now(),new_embedding_calls=len(features),
                            total_embedding_compute_sec=sum(f['embedding_compute_sec'] for f in features),
                            historical_segmentation_compute_sec=sum(t['compute_sec'] for t in tasks if t['kind']=='segmentation'),
                            availability_scope='Modeled serial CPU speaker lane from source endpoints and measured call costs; not live latency',
                            source_code=binding(__file__))
                save(target,record);calls+=len(features);compute+=record['total_embedding_compute_sec'];done+=1
            peak=max(peak,process.memory_info().rss)
            rows.append(dict(case_id=job['case_id'],stream=job['stream'],status='COMPLETE',result=binding(target),
                             features=len(record['features']),feature_key=key))
            if (done+cached)%10==0 or done+cached==1:
                progress=dict(updated_utc=now(),phase='BASELINE_FEATURE_EXTRACTION',completed=done+cached,new=done,cached=cached,
                              waiting=waiting,new_calls=calls,new_compute_sec=compute,elapsed_sec=time.perf_counter()-started,
                              process_peak_rss_bytes=peak,pid=os.getpid(),creation_time=created)
                save(folder/'EXTRACT_PROGRESS.json',progress);print(json.dumps(progress),flush=True)
            if limit is not None and done+cached>=limit:break
        result=dict(schema=FEATURE_SCHEMA,status='COMPLETE' if len(rows)==480 and waiting==0 else 'PARTIAL_RESUMABLE',
                    finished_utc=now(),requested_outputs=480,completed=sum(r['status']=='COMPLETE' for r in rows),
                    new_outputs=done,cache_hits=cached,waiting_native=waiting,new_embedding_calls=calls,new_compute_sec=compute,
                    elapsed_sec=time.perf_counter()-started,peak_rss_bytes=peak,model_threads=2,rows=rows,
                    original_jobs=binding(report/'JOB_MANIFEST.json'),exact_resume='s6a_cues.py extract --report "'+str(report)+'"')
        save(folder/'FEATURE_INDEX.json',result);save(invocation,dict(initial,status='FINISHED',result=result));return result
    finally:
        del model
        save(folder/'EXTRACT_PROCESS.json',dict(pid=os.getpid(),creation_time=created,closed_utc=now(),status='CLOSED',
                                               process_exit_pending=True,hardware_opened=False,model_handles_released=True))


class HistoricalCueBridge:
    """Conservative historic callback mapping; no inference wall-clock joins.

    Query only metadata already received by the callback containing the final
    input sample. Extra modeled computation ages that observation. Metadata
    arriving during compute is deliberately not borrowed, so this is a lower
    availability replay. Native DSP sample time remains unknown.
    """
    def __init__(self,metadata,capture,rows):
        from s4_spatial_analysis import ReceiptTimeline
        self.timeline=ReceiptTimeline(rows);self.callbacks=metadata['callback_times']
        self.starts=[r['first_native_frame'] for r in self.callbacks]
        self.startup=capture['framing']['startup_frames_excluded']
        self.times=[r.get('host_copy_complete_monotonic_ns',r['host_callback_monotonic_ns']) for r in self.callbacks]
        if any(a>b for a,b in zip(self.times,self.times[1:])):raise ValueError('nonmonotonic callback receipt')
    def observation(self,source_end_sec,available_at_sec):
        native_end=self.startup+round(source_end_sec*48000)-1
        i=bisect.bisect_right(self.starts,native_end)-1
        if i<0 or native_end>=self.starts[i]+self.callbacks[i]['frames']:return None
        when=self.times[i];state=self.timeline.state('selected_processed',when)
        receipt=state['receipt_ns']
        if receipt is None:return None
        # This is an age-preserving conservative conversion, not interpolation
        # of a device observation time or a fitted source schedule.
        source_receipt=source_end_sec-(when-receipt)/1e9
        energy=self.timeline.state('raw_auto',when)['energy']
        auto=self.timeline.state('selected_auto',when)
        disagreement=abs(state['angle_deg']-auto['angle_deg']) if state['angle_deg'] is not None and auto['angle_deg'] is not None else None
        quality=1. if disagreement is None else max(.2,1.-disagreement/90.)
        return SpatialObservation(state['angle_deg'],source_receipt,energy,quality,bool(state['available']),int(receipt))


def load_bridge(job):
    folder=Path(job['input_provenance']['accepted_record']['folder'])
    capture=read(verified(job['input_provenance']['case_result']))
    metadata_path=folder/'capture_metadata.json';telemetry_path=folder/'telemetry/received_telemetry.jsonl'
    meta_binding=binding(metadata_path);tel_binding=binding(telemetry_path)
    rows=[json.loads(line) for line in telemetry_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    return HistoricalCueBridge(read(metadata_path),capture,rows),[meta_binding,tel_binding]


def run_policy(features,vectors,mode,bridge=None,config=None):
    tracker=ResearchTracker(config or TrackingConfig(mode=mode));decisions=[]
    for feature,vector in zip(features,vectors):
        end=feature['source_end_sec'];available=feature['available_at_sec']
        spatial=bridge.observation(end,available) if bridge is not None and mode!='voice_time' else None
        decisions.append(tracker.update(vector,feature['source_start_sec'],end,available,spatial,
                                        feature['speech'],feature['overlap']))
    return decisions,tracker.snapshot()


def assign_finals(native_events,decisions):
    stamps=[d['available_at_sec'] for d in decisions];finals=[]
    for event in native_events:
        if event['event_type']!='transcript_final':continue
        end=float(event['source_time_sec']);i=bisect.bisect_right(stamps,end)-1
        label=decisions[i]['anonymous_label'] if i>=0 else 'Unknown'
        finals.append(dict(source_cursor_s=end,**{**event['payload'],'speaker':label,
                                                  'speaker_state':decisions[i]['state'] if i>=0 else 'unknown'},
                           attribution_available_at_source_sec=end,attribution_feature_index=i,
                           native_speaker=event['payload'].get('speaker')))
    return finals


def replay(report):
    jobs,_=load_jobs(report);folder=report/'cues';index=read(folder/'FEATURE_INDEX.json')
    lookup={(r['case_id'],r['stream']):r for r in index['rows'] if r['status']=='COMPLETE'}
    rows=[];started=time.perf_counter();bridge=None;bridge_case=None;bridge_bindings=[]
    tracker_source=binding(H2/'app/edge_speech_pipeline/research_tracking.py')
    for job in jobs:
        row=lookup.get((job['case_id'],job['stream']))
        if row is None:continue
        feature_record=read(verified(row['result']));vectors=np.load(verified(feature_record['vectors']),allow_pickle=False)['vectors']
        features=feature_record['features'];native=resolve_native(job)
        if native is None:raise ValueError('completed native disappeared')
        if bridge_case!=job['case_id']:bridge,bridge_bindings=load_bridge(job);bridge_case=job['case_id']
        for profile,mode in PROFILES.items():
            target=folder/'profiles'/job['case_id']/job['stream']/(profile+'.json')
            config=None if profile=='B0' else asdict(TrackingConfig(mode=mode))
            identity=dict(feature_key=feature_record['feature_key'],profile=profile,config=config,
                          tracker_source_sha256=tracker_source['sha256'],replay_source_sha256=digest(inspect.getsource(run_policy)+inspect.getsource(assign_finals)+inspect.getsource(HistoricalCueBridge)),
                          telemetry=bridge_bindings,native_events=native['receipt']['events_binding'])
            key=digest(identity)
            if target.exists():
                result=read(target)
                if result['prediction_key']!=key:raise ValueError('versioned replay required after mutation: '+str(target))
            else:
                t=time.perf_counter()
                if profile=='B0':
                    decisions=[dict(source_start_sec=e['source_time_sec']-.5,source_end_sec=e['source_time_sec'],
                                    available_at_sec=e['source_time_sec'],**e['payload']) for e in native['events'] if e['event_type']=='speaker_decision']
                    finals=[dict(source_cursor_s=e['source_time_sec'],**e['payload']) for e in native['events'] if e['event_type']=='transcript_final']
                    snapshot=dict(track_count=len({d['anonymous_label'] for d in decisions}),scope='Exact historical native labels; availability source cursor is a plotting coordinate, not actual live availability')
                else:
                    decisions,snapshot=run_policy(features,vectors,mode,bridge)
                    finals=assign_finals(native['events'],decisions)
                if [f['text'] for f in finals]!=[e['payload']['text'] for e in native['events'] if e['event_type']=='transcript_final']:
                    raise ValueError('reference profile changed ASR words')
                result=dict(schema='jp_s6a_reference_profile_v1',prediction_key=key,identity=identity,
                            case_id=job['case_id'],stream=job['stream'],profile=profile,mode=mode,final_transcripts=finals,
                            decisions=decisions,snapshot=snapshot,policy_wall_sec=time.perf_counter()-t,
                            feature_model_cost_sec=feature_record['total_embedding_compute_sec'],
                            inherited_segmentation_cost_sec=feature_record['historical_segmentation_compute_sec'],
                            reference_oracle_inputs=False,native_final_words_unchanged=True,
                            time_scope='B0 exact native attribution; candidate replay is modeled causal availability, not live latency',created_utc=now())
                save(target,result)
            rows.append(dict(case_id=job['case_id'],stream=job['stream'],profile=profile,status='COMPLETE',
                             result=binding(target),decisions=len(result['decisions']),tracks=result['snapshot']['track_count']))
        if len(rows)%120==0:print(json.dumps(dict(phase='REFERENCE_REPLAY',completed_profiles=len(rows),elapsed_sec=time.perf_counter()-started)),flush=True)
    result=dict(schema='jp_s6a_reference_index_v1',status='COMPLETE' if len(rows)==2880 else 'PARTIAL_RESUMABLE',
                requested_scene_tap_profiles=2880,completed=len(rows),rows=rows,profiles=PROFILES,
                feature_index=binding(folder/'FEATURE_INDEX.json'),tracker_source=tracker_source,
                policy_wall_sec=time.perf_counter()-started,created_utc=now())
    save(folder/'REFERENCE_INDEX.json',result);return result


def telemetry(report):
    """Score physical traces once each; model predictions are never inputs."""
    from s4_spatial_analysis import analyze_case,STREAMS
    bank=read(BANK);scenes={s['case_id']:s for s in bank['scenes']}
    captures=read(PRIOR/'CAPTURE_ANALYSIS.json')['cases'];folder=report/'cues/shared_telemetry'
    if len(captures)!=240 or {r['case_id'] for r in captures}!=set(scenes):raise ValueError('capture bank differs')
    rows=[];turn_rows=[];field_rows=[];started=time.perf_counter();reused=new=0
    for capture in sorted(captures,key=lambda x:x['case_id']):
        cid=capture['case_id'];target=folder/(cid+'.json');cap_path=verified(capture['case_result'])
        if target.exists():result=read(target)
        elif capture.get('spatial_metrics'):
            prior=read(verified(capture['spatial_metrics']))
            for b in prior['bindings']:verified(b)
            result=dict(schema='jp_s6a_physical_trace_v1',case_id=cid,evidence=prior,
                        source='REUSED_S45_PHYSICAL_DIAGNOSTIC',prior_binding=capture['spatial_metrics'],
                        inference_timings_measured=False,created_utc=now());save(target,result);reused+=1
        else:
            evidence=analyze_case(cap_path.parent,scenes[cid],bank['selected_rirs'])
            result=dict(schema='jp_s6a_physical_trace_v1',case_id=cid,evidence=evidence,
                        source='NEW_S6_ALL240_AUTHORIZED_SPATIAL_ANALYSIS',inference_timings_measured=False,created_utc=now())
            save(target,result);new+=1
        value=result['evidence']
        rows.append(dict(case_id=cid,split=scenes[cid]['split'],result=binding(target),physical_trace_units=1,
                         shared_O0_O1=True,source=result['source']))
        for stream,metric in value['whole_capture_availability'].items():
            field_rows.append(dict(case_id=cid,split=scenes[cid]['split'],stream=stream,**{k:v for k,v in metric.items() if not isinstance(v,(dict,list))}))
        for label,turn in value['turns'].items():
            for stream,metric in turn.get('streams',{}).items():
                turn_rows.append(dict(case_id=cid,split=scenes[cid]['split'],utterance_label=label,stream=stream,
                                      reference_status=turn['status'],**{k:v for k,v in metric.items() if not isinstance(v,(dict,list))}))
        if len(rows)%20==0:print(json.dumps(dict(phase='SHARED_TELEMETRY',completed=len(rows),elapsed_sec=time.perf_counter()-started)),flush=True)
    write_csv(report/'CUE_WHOLE_CAPTURE.csv',field_rows);write_csv(report/'CUE_UTTERANCE_RELIABILITY.csv',turn_rows)
    summary=[]
    for stream in STREAMS:
        population=[r for r in turn_rows if r['stream']==stream]
        duration=sum(r.get('support_duration_s',0.) for r in population)
        valid=sum((r.get('speech_energy_gated_coverage') or 0.)*r.get('support_duration_s',0.) for r in population)
        matched=sum((r.get('matching_sector_occupancy') or 0.)*r.get('support_duration_s',0.) for r in population)
        summary.append(dict(stream=stream,utterance_rows=len(population),source_support_sec=duration,
                            usable_sec=valid,usable_fraction=valid/duration if duration else None,
                            matching_sector_sec=matched,matching_sector_fraction=matched/duration if duration else None,
                            wrong_sector_sec=sum(r.get('wrong_sector_duration_s') or 0. for r in population),
                            held_wrong_sector_sec=sum(r.get('held_wrong_sector_duration_s') or 0. for r in population),
                            sustained_never_acquired=sum(r.get('sustained_acquisition_censored') is True for r in population)))
    write_csv(report/'CUE_RELIABILITY_SUMMARY.csv',summary)
    result=dict(schema='jp_s6a_shared_cue_foundation_v1',status='COMPLETE',physical_trace_count=len(rows),
                newly_analyzed=new,reused_historical=reused,physical_trace_units=240,paired_output_evidence_units=0,
                rows=rows,summary=summary,created_utc=now(),elapsed_sec=time.perf_counter()-started,
                limitations=['Internal DSP observation/frame freshness is not exposed','AEC/AGC state and RT60 unavailable historically',
                             'Angles use folded linear 0..180 native geometry; beam is not identity',
                             'Stable wrong means numeric persistence in wrong coarse sector, not evidence of stale DSP',
                             'Source activity and callback timing are estimates; no physical latency claim',
                             'Manual +/-5 degrees describes geometry uncertainty, not sensor accuracy'])
    save(report/'CUE_FOUNDATION.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('extract','replay','telemetry','score'))
    parser.add_argument('--report',type=Path,default=DEFAULT_REPORT)
    parser.add_argument('--limit',type=int,help='Explicit smoke-test cap on processed outputs; never marks full completion')
    args=parser.parse_args()
    if args.mode=='extract':result=extract(args.report,args.limit)
    elif args.mode=='replay':result=replay(args.report)
    elif args.mode=='telemetry':result=telemetry(args.report)
    else:
        from s6a_cue_score import score
        result=score(args.report)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','summary')},indent=2))


if __name__=='__main__':main()
