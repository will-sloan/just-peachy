"""Replay exact neural evidence through the actual frozen APP scheduler. README_S6B_REPLAY.md."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import itertools
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from s6b_common import *

def api(spec):
    sys.path.insert(0,str(Path(spec['root'])/'app'))
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.research_tracking_v2 import S6BTracker
    from edge_speech_pipeline.research_scheduler import CausalScheduler
    return ResearchProfile,JsonSpatialProvider,S6BTracker,CausalScheduler

def scheduler_inputs(evidence,vectors):
    rows=[]
    for i,f in enumerate(evidence['features']):
        rows.append(dict(kind='embedding',event_id=f.get('evidence_event_id',f'embedding:{i+1:08d}'),source_start_sec=f['source_start_sec'],
            source_end_sec=f['source_end_sec'],available_at_sec=f['available_at_sec'],vector=vectors[i].tolist(),
            speech=f.get('speech',True),overlap=f.get('overlap',False)))
    for i,s in enumerate(evidence['segmentation']):
        rows.append(dict(kind='segmentation',event_id=s.get('event_id',f'seg:{i+1:08d}'),source_start_sec=s['source_start_sec'],
            source_end_sec=s['source_end_sec'],available_at_sec=s['available_at_sec'],speech=s['speech'],overlap=s['overlap']))
    for i,a in enumerate(evidence['asr_observations']):
        row=deepcopy(a);row.update(kind='asr',event_id=a.get('event_id',f'asr:{i+1:08d}'))
        row['utterance_id']=str(row['utterance_id'])
        rows.append(row)
    return sorted(rows,key=lambda r:(r['available_at_sec'],{'segmentation':0,'embedding':1,'asr':2}[r['kind']],r['event_id']))

def run_scheduler(profile,provider,evidence,vectors,classes):
    _,_,Tracker,Scheduler=classes
    tracker=Tracker(profile.tracker)
    settings=profile.scheduler
    # Core kwargs shared with the actual native adapter. Optional validated
    # budget/expiry fields are passed only when exposed by the installed API.
    import inspect
    supported=inspect.signature(Scheduler).parameters
    kwargs=dict(spatial_provider=provider,cues_enabled=profile.tracker.cues_enabled,
        revision_horizon_sec=settings.revision_horizon_sec)
    for name in ('max_pending_events','evidence_expiry_sec','max_events','max_utterances','max_revisions_per_utterance'):
        if name in supported and hasattr(settings,name):kwargs[name]=getattr(settings,name)
    scheduler=Scheduler(tracker,**kwargs)
    records=[];inputs=scheduler_inputs(evidence,vectors)
    started=time.perf_counter()
    for ready,group in itertools.groupby(inputs,key=lambda r:r['available_at_sec']):
        for event in group:records.extend(scheduler.push(event,lane='asr' if event['kind']=='asr' else 'speaker'))
        bound=math.nextafter(ready,math.inf)
        records.extend(scheduler.advance({'speaker':bound,'asr':bound}))
    records.extend(scheduler.finish())
    cost=time.perf_counter()-started;snapshot=scheduler.snapshot()
    decisions=[r['decision'] for r in records if r['event_type']=='speaker_decision']
    utterances=[r for r in snapshot['utterances'] if r.get('is_final')]
    def finals(label):
        return [dict(utterance_index=str(r['utterance_id']),text=r['text'],speaker=r[label] or 'Unknown',
            source_cursor_s=r['source_end_sec'],source_start_sec=r['source_start_sec'],
            first_display_time=r['first_display_time'],first_final_time=r['first_final_time'],latest_label_time=r['latest_label_time']) for r in utterances]
    return dict(decisions=decisions,final_transcripts_first=finals('first_final_label'),
        final_transcripts_latest=finals('latest_label'),final_transcripts_first_display=finals('first_display_label'),
        transcript_events=[r for r in records if r['event_type'].startswith('transcript_')],
        snapshot=dict(scheduler=snapshot,tracker=tracker.snapshot()),policy_wall_sec=cost,
        scheduler_input_events=len(inputs),features=evidence['features'],
        segmentation=[{k:v for k,v in s.items() if not k.endswith('_frames')} for s in evidence['segmentation']],
        recipe_costs=evidence['costs'])

def historical(item):
    events=[json.loads(s) for s in Path(item['baseline_events']['path']).read_text(encoding='utf-8').splitlines() if s.strip()]
    features=read(item['baseline_features']['path'])
    decisions=[dict(source_start_sec=max(0,e['source_time_sec']-.5),source_end_sec=e['source_time_sec'],
        available_at_sec=e['source_time_sec'],**e['payload']) for e in events if e['event_type']=='speaker_decision']
    finals=[dict(source_cursor_s=e['source_time_sec'],**e['payload']) for e in events if e['event_type']=='transcript_final']
    first={}
    for e in events:
        if e['event_type'] in ('transcript_partial','transcript_final') and e['payload']['text'].strip():
            first.setdefault(e['payload']['utterance_index'],e['payload'].get('speaker') or 'Unknown')
    return dict(decisions=decisions,final_transcripts_first=finals,final_transcripts_latest=deepcopy(finals),
        final_transcripts_first_display=[dict(f,speaker=first.get(f['utterance_index'],'Unknown')) for f in finals],
        transcript_events=[],snapshot=dict(scope='immutable historical B0 source-cursor attribution, distinct from common scheduler'),
        policy_wall_sec=0.,features=features['features'],segmentation=[],recipe_costs={},
        historical_timing_limitation='Historical labels remain exact. Source-cursor display is not common-scheduler modeled availability or measured native latency.')

def replay(epoch='epoch1',panel='challenge',profile_ids=None,index_name=None):
    spec_path=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json');spec=read(spec_path)
    for b in spec['execution_files']:bind(b['path'],b['sha256'])
    script_binding=next(b for b in spec['execution_files'] if Path(b['path']).name=='s6b_replay.py')
    bind(__file__,script_binding['sha256'])
    classes=api(spec);Profile,Provider,_,_=classes
    for key in ('input_index','gain_index','effective_profile_registry','challenge_panel','recipe_registry'):
        bind(spec[key]['path'],spec[key]['sha256'])
    candidates=read(spec['effective_profile_registry']['path'])['profiles']
    if profile_ids:candidates=[p for p in candidates if p['profile_id'] in profile_ids]
    inputs=read(spec['input_index']['path'])['rows']
    alternate={(r['case_id'],r['stream']):r for r in read(spec['gain_index']['path'])['rows']}
    recipe_specs={r['recipe_id']:r for r in spec['recipes']}
    from s6b_execution import make_job,verify_cached
    ids=set(read(spec['challenge_panel']['path'])['case_ids']) if panel=='challenge' else {r['case_id'] for r in inputs}
    rows=[];started=time.perf_counter();neural_cache={};providers={}
    folder=REPORT/epoch/'predictions'
    requested=len(candidates)*len(ids)*2
    for item in inputs:
        cid,out=item['case_id'],item['stream']
        if cid not in ids:continue
        for c in candidates:
            pid=c['profile_id'];recipe=c['recipe_id']
            target=folder/pid/cid/(out+'.json')
            if pid=='B00':
                for b in (item['baseline_events'],item['baseline_features']):bind(b['path'],b['sha256'])
                source_key=dict(events=item['baseline_events'],features=item['baseline_features'],historical=True)
                evidence=None
            else:
                rec_path=PAYLOAD/epoch/'neural'/recipe/cid/out/'run_receipt.json'
                if not rec_path.exists():raise ValueError('Missing actual neural recipe: '+str(rec_path))
                receipt=read(rec_path)
                if receipt['status']!='COMPLETE':raise ValueError('Incomplete neural source')
                cache_key=(recipe,cid,out)
                if cache_key not in neural_cache:
                    expected_job=make_job(spec,recipe_specs[recipe],item,alternate)
                    if verify_cached(expected_job) is None:raise ValueError('Exact neural cache receipt missing')
                    b=receipt['evidence'];bind(b['path'],b['sha256']);e=read(b['path'])
                    bind(e['vectors']['path'],e['vectors']['sha256'])
                    vectors=np.load(e['vectors']['path'],allow_pickle=False)['vectors']
                    if len(vectors)!=len(e['features']):raise ValueError('Vector/feature count mismatch')
                    neural_cache[cache_key]=(e,vectors)
                evidence,vectors=neural_cache[cache_key];source_key=dict(evidence=receipt['evidence'],recipe_job_key=receipt['job_key'])
            identity=dict(schema='jp_s6b_actual_app_causal_replay_v1',profile=c['profile'],source=source_key,
                execution_digest=spec['execution_digest'],scheduler='same incremental module as native; sealed causal event availability',
                cue_input=item['telemetry'] if c.get('profile',{}).get('tracker',{}).get('cues_enabled') else None,
                analysis_truth_dependency=False)
            prediction_key=digest(identity)
            if target.exists():
                value=read(target)
                if value['prediction_key']!=prediction_key:raise ValueError('Changed prediction identity requires named revision, no overwrite')
            else:
                if pid=='B00':value=historical(item)
                else:
                    p=Profile.from_dict(c['profile']);provider=None
                    if p.tracker.cues_enabled:
                        if cid not in providers:
                            bind(item['telemetry']['path'],item['telemetry']['sha256']);providers[cid]=Provider(Path(item['telemetry']['path']))
                        provider=providers[cid]
                    value=run_scheduler(p,provider,evidence,vectors,classes)
                expected_words=[a['text'] for a in value['final_transcripts_first']]
                if expected_words!=[a['text'] for a in value['final_transcripts_latest']]:raise ValueError('Label revisions changed words')
                value.update(schema='jp_s6b_profile_prediction_v1',status='COMPLETE',prediction_key=prediction_key,identity=identity,
                    case_id=cid,stream=out,profile_id=pid,recipe_id=recipe,duration_sec=item['duration_sec'],
                    timing_scope='Shared measured upstream warm modeled availability; actual policy cost reported separately. Historical B00 retains original timing.',created_utc=utc())
                save(target,value)
            rows.append(dict(case_id=cid,stream=out,profile_id=pid,recipe_id=recipe,status='COMPLETE',result=bind(target)))
        # Scene-local caching retains model-free evidence only until the next output.
        neural_cache.clear()
        if len(rows)%max(1,len(candidates)*10)==0:
            progress=dict(phase='COMMON_SCHEDULER_REPLAY',requested=requested,completed=len(rows),case_id=cid,stream=out,elapsed_sec=time.perf_counter()-started,utc=utc())
            save(REPORT/'REPLAY_HEARTBEAT.json',progress);print(json.dumps(progress),flush=True)
    result=dict(schema='jp_s6b_prediction_index_v1',status='COMPLETE' if len(rows)==requested else 'PARTIAL_RESUMABLE',
        requested=requested,completed=len(rows),profiles=[c['profile_id'] for c in candidates],case_ids=sorted(ids),panel=panel,epoch=epoch,rows=rows,
        execution_manifest=bind(spec_path),effective_profiles=bind(REPORT/'EFFECTIVE_PROFILE_REGISTRY.json'),elapsed_sec=time.perf_counter()-started,created_utc=utc())
    target=REPORT/(index_name or ('CHALLENGE_PREDICTION_INDEX.json' if panel=='challenge' else 'PREDICTION_INDEX.json'))
    save(target,result)
    return dict(status=result['status'],requested=requested,completed=len(rows),index=str(target))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epoch',default='epoch1');p.add_argument('--panel',choices=('challenge','all'),default='challenge')
    p.add_argument('--profiles',nargs='*');p.add_argument('--index-name');a=p.parse_args()
    print(json.dumps(replay(a.epoch,a.panel,a.profiles,a.index_name),indent=2))
