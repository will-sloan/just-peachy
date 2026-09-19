"""Exact evidence through the actual v3 incremental API. README_S6C_REPLAY.md."""
from __future__ import annotations
from copy import deepcopy
import argparse
import bisect
import gzip
import itertools
import math
import os
from pathlib import Path
import sys
import time
import numpy as np
from s6c_common import *

def legacy_clean(evidence,feature):
    """Reconstruct the admitted R0 frame support, not reference speech support."""
    eligible=[s for s in evidence['segmentation'] if s['source_end_sec']<=feature['source_end_sec']+1e-9 and s['available_at_sec']<=feature['available_at_sec']+1e-9]
    if not eligible:raise ValueError('Legacy feature has no arrived segmentation context')
    seg=eligible[-1]
    if seg['post_policy']!='hard_argmax_fraction':raise ValueError('N00 is exact R0 hard powerset context')
    mask=np.asarray(seg['speech_frames'],bool)&~np.asarray(seg['overlap_frames'],bool)
    centers=seg['source_end_sec']-10.+.0619375/2+np.arange(len(mask))*.016875
    spans=[];start=feature['source_start_sec'];end=feature['source_end_sec']
    for center,good in zip(centers,mask):
        a=max(0.,start,float(center-.016875/2));b=min(end,float(center+.016875/2))
        if good and b>a:
            if spans and a<=spans[-1][1]+1e-9:spans[-1][1]=b
            else:spans.append([a,b])
    fraction=sum(b-a for a,b in spans)/(end-start)
    expected=feature.get('admission',{}).get('clean_fraction')
    if expected is None or not math.isclose(fraction,expected,rel_tol=0,abs_tol=1e-8):
        raise ValueError('Reconstructed actual R0 clean support disagrees with native admission')
    return spans

def scheduler_inputs(evidence,vectors):
    rows=[]
    if evidence.get('embedding_observations') is not None:
        observations=evidence['embedding_observations']
        if len(observations)!=len(vectors):raise ValueError('Observation/vector count mismatch')
        for observation,vector in zip(observations,vectors):
            row=deepcopy(observation);row['vector']=vector.tolist();rows.append(row)
    else:
        for i,(feature,vector) in enumerate(zip(evidence['features'],vectors)):
            eid=feature.get('evidence_event_id',f'embedding:{i+1:08d}')
            rows.append(dict(kind='embedding',event_id=eid,observation_id=eid,vector=vector.tolist(),
                source_start_sec=feature['source_start_sec'],source_end_sec=feature['source_end_sec'],
                receptive_start_sec=feature.get('receptive_start_sec',feature['source_start_sec']),
                receptive_end_sec=feature.get('receptive_end_sec',feature['source_end_sec']),
                available_at_sec=feature['available_at_sec'],speech=feature.get('speech',True),overlap=feature.get('overlap',False),
                evidence_kind='mature',clean_intervals=legacy_clean(evidence,feature),rms=feature['admission']['selected_rms'],
                clean_fraction=feature['admission']['clean_fraction']))
    for i,s in enumerate(evidence['segmentation']):
        rows.append(dict(kind='segmentation',event_id=s.get('event_id',f'seg:{i+1:08d}'),
            source_start_sec=s['source_start_sec'],source_end_sec=s['source_end_sec'],available_at_sec=s['available_at_sec'],
            speech=s['speech'],overlap=s['overlap']))
    rows.extend(deepcopy(evidence['asr_observations']))
    for row in rows:
        if row['kind']=='asr':row['utterance_id']=str(row['utterance_id'])
    return sorted(rows,key=lambda r:(r['available_at_sec'],{'segmentation':0,'embedding':1,'asr':2}[r['kind']],r['event_id']))

def run_policy(profile,provider,evidence,vectors,gallery=None,cutoff=None):
    from edge_speech_pipeline.research_scheduler_v3 import build_s6c_policy
    scheduler=build_s6c_policy(profile,gallery,provider)
    records=[];inputs=scheduler_inputs(evidence,vectors);start=time.perf_counter()
    if cutoff is not None:inputs=[r for r in inputs if r['available_at_sec']<=cutoff]
    for ready,group in itertools.groupby(inputs,key=lambda r:r['available_at_sec']):
        for row in group:records.extend(scheduler.push(row,lane='asr' if row['kind']=='asr' else 'speaker'))
        bound=math.nextafter(ready,math.inf)
        records.extend(scheduler.advance({'asr':bound,'speaker':bound}))
    if cutoff is None:records.extend(scheduler.finish())
    snapshot=scheduler.snapshot();elapsed=time.perf_counter()-start
    utterances=[u for u in snapshot['utterances'] if u.get('is_final')]
    def finals(label):
        return [dict(utterance_index=str(u['utterance_id']),text=u['text'],speaker=u.get(label) or 'Unknown',
            source_cursor_s=u['source_end_sec'],source_start_sec=u['source_start_sec'],
            first_display_time=u['first_display_time'],first_final_time=u['first_final_time'],latest_label_time=u['latest_label_time'],
            tracker_id=u.get('tracker_id'),first_anonymous_label=u.get('first_anonymous_label'),
            latest_anonymous_label=u.get('latest_anonymous_label'),first_known_name=u.get('first_known_name'),
            first_known_name_time=u.get('first_known_name_time'),latest_known_name=u.get('latest_known_name'),
            latest_known_profile_id=u.get('latest_known_profile_id')) for u in utterances]
    result=dict(decisions=[r['decision'] for r in records if r['event_type']=='speaker_decision'],
        final_transcripts_first=finals('first_final_label'),final_transcripts_latest=finals('latest_label'),
        final_transcripts_first_display=finals('first_display_label'),
        transcript_events=[r for r in records if r['event_type'].startswith('transcript_')],
        identity_events=[r for r in records if r['event_type']=='identity_decision'],
        snapshot=dict(scheduler=snapshot,tracker=scheduler.tracker.snapshot()),
        policy_wall_sec=elapsed,scheduler_input_events=len(inputs),features=evidence['features'],
        segmentation=[{k:v for k,v in s.items() if not k.endswith('_frames')} for s in evidence['segmentation']],
        recipe_costs=evidence['costs'],prefix_cutoff=cutoff)
    words=lambda key:[(f['utterance_index'],f['text']) for f in result[key]]
    if words('final_transcripts_first')!=words('final_transcripts_latest'):raise ValueError('Label-only replay changed raw ASR words')
    return result

def load_evidence(receipt_path,expected_epoch_digest=None,expected_audio=None,expected_receipt=None):
    if expected_receipt is not None:bind(receipt_path,expected_receipt['sha256'])
    receipt=read(receipt_path)
    if receipt['status']!='COMPLETE' or digest(receipt['identity'])!=receipt['job_key']:raise ValueError('Native source receipt invalid')
    if expected_epoch_digest and receipt['identity']['execution_digest']!=expected_epoch_digest:raise ValueError('Native source epoch mismatch')
    if expected_audio and receipt['identity'].get('audio',receipt['identity'].get('asr_audio'))!=expected_audio:raise ValueError('Native source audio differs')
    for key in ('evidence','vectors','events','summary'):bind(receipt[key]['path'],receipt[key]['sha256'])
    if receipt.get('full_journal'):bind(receipt['full_journal']['path'],receipt['full_journal']['sha256'])
    for b in receipt.get('journals',{}).values():bind(b['path'],b['sha256'])
    evidence=verified(receipt['evidence']);bind(evidence['vectors']['path'],evidence['vectors']['sha256'])
    if evidence['job_key']!=receipt['job_key'] or evidence['identity']!=receipt['identity']:raise ValueError('Receipt/evidence identity differs')
    vectors=np.load(evidence['vectors']['path'],allow_pickle=False)['vectors']
    if vectors.shape!=(len(evidence['features']),192) or not np.all(np.isfinite(vectors)):raise ValueError('Actual native vector array invalid')
    return evidence,vectors,bind(receipt_path)

def save_prediction(path,value):
    import uuid
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():raise ValueError('Prediction overwrite forbidden')
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode('utf-8')
    temp=p.with_name('.'+p.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('wb') as f:
        f.write(gzip.compress(raw,compresslevel=5,mtime=0));f.flush();os.fsync(f.fileno())
    os.replace(temp,p);return bind(p)

def read_prediction(path):
    path=Path(path)
    return json.loads(gzip.decompress(path.read_bytes())) if path.suffix=='.gz' else read(path)

def replay_n00(epoch,panel='challenge',candidates=None):
    spec=read(REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json'))
    if Path(__file__).resolve().parent!=Path(spec['root'])/'scripts':raise ValueError('Use frozen replay helper')
    for b in spec['execution_files']:bind(b['path'],b['sha256'])
    sys.path.insert(0,str(Path(spec['root'])/'app'))
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    sealed=verified(dict(path=str(S6B/'LOCAL_ARTIFACT_INDEX.json'),sha256='2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e'))
    def sealed_file(path):
        binding=next(r for r in sealed['artifacts'] if Path(r['path']).resolve()==Path(path).resolve())
        return verified(binding)
    old=sealed_file(S6B/'EPOCH2_EXECUTION_MANIFEST.json')
    native_index=sealed_file(S6B/'epoch2/FULL_ALL_NEURAL_INDEX.json')
    native_receipts={(r['case_id'],r['stream']):r['receipt'] for r in native_index['rows'] if r['recipe_id']=='R0'}
    if len(native_receipts)!=480:raise ValueError('Sealed full R0 source index must contain all480')
    for b in old['execution_files']:bind(b['path'],b['sha256'])
    for b in old['assets']:bind(b['path'],b['sha256'])
    inputs=verified(spec['input_index'])['rows']
    ids=set(verified(spec['panel'])['case_ids']) if panel=='challenge' else {r['case_id'] for r in inputs}
    selected=[p for p in spec['profiles'] if p['recipe_id']=='N00' and p['gallery_condition']=='NONE' and p['route']=='SAME' and (not candidates or p['candidate_id'] in candidates)]
    if any(p['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES') for p in selected):
        # Diagnostic source files must be frozen, never generated from outcomes.
        if not spec.get('cue_variant_index'):raise ValueError('Epoch has no frozen cue variant index')
        cue_index=verified(spec['cue_variant_index'])
        variants={(r['case_id'],r['stream'],r['condition']):r['telemetry'] for r in cue_index['rows']}
    else:variants={}
    requested=sum(p['asr_tap']==i['stream'] for p in selected for i in inputs if i['case_id'] in ids)
    index=REPORT/epoch/(panel.upper()+'_N00_PREDICTION_INDEX.json')
    previous_bindings={(r['candidate_id'],r['case_id'],r['stream']):r['result'] for r in read(index)['rows']} if index.exists() else {}
    rows=[];started=time.perf_counter();last_heartbeat=0.
    for item in inputs:
        cid,tap=item['case_id'],item['stream']
        if cid not in ids:continue
        admit_work(full=False)
        bind(item['audio']['path'],item['audio']['sha256'])
        path=S6B_PAYLOAD/'epoch2/neural/R0'/cid/tap/'run_receipt.json'
        evidence,vectors,source=load_evidence(path,old['execution_digest'],item['audio'],native_receipts[cid,tap])
        # Extra compatibility check prevents borrowing another old recipe that
        # happens to point at the same waveform.
        expected=next(r['profile'] for r in old['recipes'] if r['recipe_id']=='R0')
        if evidence['identity']['profile']!=expected:raise ValueError('N00 requires exact R0 native recipe')
        providers={}
        for p in selected:
            if p['asr_tap']!=tap:continue
            condition=p['cue_condition'];provider=None;cue_binding=None
            if condition!='CUES_OFF':
                cue_binding=item['telemetry'] if condition=='REAL_ALIGNED_CUES' else variants[cid,tap,condition]
                bind(cue_binding['path'],cue_binding['sha256'])
                if condition not in providers:providers[condition]=JsonSpatialProvider(Path(cue_binding['path']))
                provider=providers[condition]
            identity=dict(schema='jp_s6c_policy_prediction.v1',execution_digest=spec['execution_digest'],
                profile=p['profile'],source=source,telemetry=cue_binding,cue_condition=condition,
                gallery=None,evidence_support='Exact R0 frame-support reconstruction with native clean_fraction parity',
                evidence_role='Legacy single .5s lane assigned mature API role; not new long-mature evidence',
                oracle_like=condition=='NOMINAL_GEOMETRY_DIAGNOSTIC')
            key=digest(identity);target=PAYLOAD/epoch/'predictions'/p['candidate_id']/cid/(tap+'.json.gz')
            if target.exists():
                old_binding=previous_bindings.get((p['candidate_id'],cid,tap))
                if old_binding:bind(target,old_binding['sha256'])
                value=read_prediction(target)
                expected_meta=dict(status='COMPLETE',schema='jp_s6c_prediction.v1',prediction_key=key,identity=identity,
                    case_id=cid,stream=tap,identity_tap=tap,profile_id=p['candidate_id'],candidate_id=p['candidate_id'],recipe_id='N00',duration_sec=item['duration_sec'])
                if any(value.get(k)!=v for k,v in expected_meta.items()):raise ValueError('Changed/incomplete prediction requires new epoch/revision')
                status='COMPLETE_REUSED'
            else:
                profile=ResearchProfile.from_dict(p['profile'])
                value=run_policy(profile,provider,evidence,vectors)
                value.update(status='COMPLETE',schema='jp_s6c_prediction.v1',prediction_key=key,identity=identity,
                    case_id=cid,stream=tap,identity_tap=tap,profile_id=p['candidate_id'],candidate_id=p['candidate_id'],recipe_id='N00',
                    duration_sec=item['duration_sec'],execution_mode='VERIFIED_NATIVE_CACHE_PLUS_INCREMENTAL_REPLAY',
                    oracle_like=identity['oracle_like'],created_utc=utc())
                save_prediction(target,value);status='COMPLETE'
            rows.append(dict(candidate_id=p['candidate_id'],case_id=cid,stream=tap,identity_tap=tap,status=status,result=bind(target),recipe_id='N00'))
            if time.monotonic()-last_heartbeat>20:
                progress=dict(status='RUNNING',phase='N00_VERIFIED_NATIVE_POLICY_REPLAY',requested=requested,completed=len(rows),
                    new_native_jobs=0,policy_replays=sum(r['status']=='COMPLETE' for r in rows),elapsed_sec=time.perf_counter()-started,
                    current_case=cid,current_candidate=p['candidate_id'],resources=resources(),utc=utc())
                save(REPORT/'HEARTBEAT.json',progress);print(json.dumps({k:v for k,v in progress.items() if k!='resources'}),flush=True)
                last_heartbeat=time.monotonic()
    result=dict(status='COMPLETE' if len(rows)==requested else 'PARTIAL_RESUMABLE',requested=requested,completed=len(rows),rows=rows,
        profiles=sorted({p['candidate_id'] for p in selected}),case_ids=sorted(ids),
        profile_routes=[dict(candidate_id=p['candidate_id'],stream=p['asr_tap'],identity_tap=p['identity_tap']) for p in selected],
        panel=panel,epoch=epoch,created_utc=utc(),elapsed_sec=time.perf_counter()-started)
    save(index,result)
    save(REPORT/'HEARTBEAT.json',dict(status=result['status'],phase='N00_REPLAY_CLOSED',index=bind(index),utc=utc()))
    return {k:v for k,v in result.items() if k!='rows'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epoch',default='epoch1');p.add_argument('--panel',choices=('challenge','all'),default='challenge')
    p.add_argument('--candidates',nargs='*');a=p.parse_args();print(json.dumps(replay_n00(a.epoch,a.panel,a.candidates),indent=2))
