"""Saved-component publication/consumer checks. README_APPLICATION_PUBLICATION.md."""
import argparse
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import shutil
import sys

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import load,bind,verify,freeze,audio_only
from component_commands import asr_commands,d0_commands
from application_publication import replay_d0_publication,replay_d1_publication
from controller_projection import project_mode_result,forbid_inference
from probe_controller_projection import read_replay
from probe_component_s7 import read_events,save_private

FIELDS=('id','utterance_id','caption_key','raw_asr_text','provisional_display_text','final_punctuated_display_text',
    'label','final','optional_corrected_text','show_corrected_text','selected','visible','identity_assignment',
    'display_profile_id','closed_display_assignment','closed_group_display','identity_version','profile_id','track_id')


def semantics(rows):return [{k:r.get(k) for k in FIELDS} for r in rows]


def guard(output,policy):
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):raise TimeoutError('Packaging reserve reached')
    for drive,floor in [('C:/',50),('G:/',75)]:
        if shutil.disk_usage(drive).free<(floor*1024+512)*1024**2:raise ValueError('Campaign disk floor/reservation unavailable')
    size=sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) if output.exists() else 0
    if size+70*1024**2>512*1024**2:raise ValueError('512-MiB publication-probe allocation exhausted')


def main(args):
    import psutil
    from asr_full_bank import payload_inventory
    process=psutil.Process();process.cpu_affinity([14]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    here=Path(__file__).resolve().parent;public=load(here/'CONTROLLER_PROJECTION_CHECK_V1.json');verify(public['private_receipt'])
    parent=load(public['private_receipt']['path']);verify(parent['parent']);modes=load(parent['parent']['path'])
    if parent['status']!='PASS_160_ACTUAL_CONTROLLER_CONSUMER_PROJECTIONS_ONLY' or modes['checks_count']!=160:
        raise ValueError('Require complete sealed mode and Controller parents')
    for b in [parent['source_receipt'],parent['gallery_preparation'],*parent['code'],*modes['code'],*parent['runtime_inputs']]:verify(b)
    source_document=load(parent['source_receipt']['path']);source=Path(source_document['prototype'])
    for rel,b in source_document['files'].items():verify(dict(path=str((source/rel).resolve()),**b))
    sys.path[:0]=[str(source),str(source/'vendor')]
    import soundfile as sf
    runtimes={Path(b['path']).name:b for b in parent['runtime_inputs']}
    local=Path(parent['source_receipt']['path']).parents[2];policy=load(local/'supervision/campaign.json')
    if args.output.exists():raise ValueError('Preserve previous probes; choose a fresh output')
    guard(args.output,policy);inventory=payload_inventory(local)
    if inventory['total_logical_bytes']+6*1024**3>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared allowance cannot admit publication probe')
    code=[bind(here/n) for n in ('application_publication.py','probe_application_publication.py','test_application_publication.py',
        'README_APPLICATION_PUBLICATION.md','controller_projection.py','component_d1_replay.py','component_s7_replay.py',
        'mode_galleries.py','component_commands.py','probe_component_s7.py','probe_controller_projection.py','common.py')]
    selected=[r for r in parent['checks'] if args.scope=='all160' or (r['mode']=='selected_closed' and r['tap']=='O0')]
    required=160 if args.scope=='all160' else 16
    if len(selected)!=required:raise ValueError('Predeclared publication case census differs')
    key=lambda r:(r['backend'],r['mode'],r['job_id'])
    mode_index={key(r):r for r in modes['checks']};reused={}
    if args.reuse:
        prior=load(args.reuse)
        if (args.scope!='all160' or prior['scope']!='smoke16' or prior['checks_count']!=16
                or prior['status']!='PASS_ACTUAL_PUBLICATION_AND_CONSUMER_METHODS'
                or prior['parent']!=public['private_receipt'] or prior['code']!=code):
            raise ValueError('Reuse requires exact complete unchanged smoke16 evidence')
        for r in prior['checks']:
            for b in (r['publication']['compressed'],r['projection']['compressed'],r['consumer_closure']):verify(b)
            # Verify complete expanded artifacts too, before reusing any result.
            read_replay(r['publication']);read_replay(r['projection']);reused[key(r)]=r
    args.output.mkdir(parents=True,exist_ok=False)
    freeze(args.output/'ADMISSION.json',dict(scope=args.scope,required=required,parent=public['private_receipt'],code=code,
        reuse=bind(args.reuse) if args.reuse else None,source=parent['source_receipt'],
        owner=dict(pid=process.pid,create_time=process.create_time()),inventory=inventory,
        reservation_bytes=512*1024**2,conservative_pending_bytes=6*1024**3))
    summaries=[];cache={};waves={}
    try:
        for index,entry in enumerate(selected):
            guard(args.output,policy)
            if key(entry) in reused:
                summaries.append(dict(reused[key(entry)],reused_from=bind(args.reuse)));continue
            mr=mode_index[key(entry)]
            for b in mr['inputs']:verify(b)
            a,s=[load(b['path']) for b in mr['inputs']];job=audio_only(a['job'])
            if s['job']!=job or job['tap']!=entry['tap']:raise ValueError('Component source/tap differs')
            parent_projection=read_replay(entry['private_output'])
            old_mode=read_replay(mr['output']);contract=old_mode['contract']
            akey=mr['inputs'][0]['sha256'];skey=mr['inputs'][1]['sha256']
            if akey not in cache:
                events=read_events(a);cache[akey]=(asr_commands(events,variant=a['variant'],duration=job['frames']/16000),
                    [r['payload'] for r in events if r['event_type']=='component_final_punctuation'])
            if skey not in cache:cache[skey]=read_events(s)
            commands,formatting=cache[akey];speaker_rows=cache[skey]
            kwargs=dict(preparation=parent['gallery_preparation'],backend=entry['backend'],mode=entry['mode'],tap=job['tap'],
                namespace=s['namespace'],session_id=job['job_id'],formatting=formatting)
            if contract['diarization']=='D0':
                result=replay_d0_publication(commands,d0_commands(speaker_rows,duration=job['frames']/16000),duration=job['frames']/16000,**kwargs)
            else:
                if job['job_id'] not in waves:
                    if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Saved waveform changed')
                    wave,rate=sf.read(job['audio_path'],dtype='float32')
                    if rate!=16000 or wave.ndim!=1 or len(wave)!=job['frames']:raise ValueError('Saved waveform geometry differs')
                    waves[job['job_id']]=wave
                result=replay_d1_publication(commands,speaker_rows,wave=waves[job['job_id']],summary=s['summary'],**kwargs)
            if result['contract']!=contract or result['presentation']['raw_observations']!=mr['raw_observations'] or result['presentation']['final_utterances']!=mr['final_utterances']:
                raise ValueError('Publication raw/final/contract census differs')
            name=f'{index:03d}'
            with forbid_inference():
                projected=project_mode_result(result,tap=job['tap'],preparation=parent['gallery_preparation'],
                    n2_runtime=runtimes['n2_runtime.json'],n3_runtime=runtimes['n3_runtime.json'],data_root=args.output/'controllers'/name)
            before=[semantics(r['rows']) for r in parent_projection['history']]
            after=[semantics(r['rows']) for r in projected['history']]
            comparison=dict(fields=list(FIELDS),display_count_equal=len(before)==len(after),
                history_equal=before==after,final_rows_equal=semantics(parent_projection['final_rows'])==semantics(projected['final_rows']),
                mismatching_history_indices=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b],
                parent_method_scope='Earlier modeled mode/Controller development results, not observed gold or accuracy truth')
            publication=save_private(args.output/(name+'-publication.json.gz'),result)
            projection=save_private(args.output/(name+'-projection.json.gz'),projected)
            summaries.append(dict(backend=entry['backend'],mode=entry['mode'],tap=entry['tap'],job_id=entry['job_id'],
                inputs=mr['inputs'],parent_mode=mr['output'],parent_projection=entry['private_output'],publication=publication,
                projection=projection,consumer_closure=projected['actual_consumer_closure'],comparison=comparison,
                publications=len(result['publication_events']),displays=len(result['display_events']),
                raw_observations=result['presentation']['raw_observations'],final_utterances=result['presentation']['final_utterances'],
                worker_counts=result['worker_counts'],d1_worker_alive=result.get('d1_worker_alive'),controller_closed=projected['controller_closed'],
                new_neural_inference=False,integrated_N4_cells=0))
            if (index+1)%4==0:print(json.dumps(dict(completed=index+1,total=required)),flush=True)
        for b in code:verify(b)
        if len(summaries)!=required:raise ValueError('Incomplete publication case census')
        receipt=dict(status='PASS_ACTUAL_PUBLICATION_AND_CONSUMER_METHODS',utc=datetime.now(timezone.utc).isoformat(),scope=args.scope,
            parent=public['private_receipt'],source_receipt=parent['source_receipt'],gallery_preparation=parent['gallery_preparation'],
            code=code,checks=summaries,checks_count=required,reused_checks=len(reused),
            unchanged_projected_history_cases=sum(r['comparison']['history_equal'] for r in summaries),
            unchanged_projected_final_cases=sum(r['comparison']['final_rows_equal'] for r in summaries),
            models_loaded=0,physical_widget_observed=False,complete_Controller_parity=False,integrated_N4_cells=0,
            limitations='Modeled publication/consumer methods; startup/source/model/I-O and D0/ASR diagnostic traces omitted; no live latency, accuracy or resource acceptance')
        freeze(args.output/'RESULT.json',receipt)
        print(json.dumps(dict(status=receipt['status'],checks=required,history_equal=receipt['unchanged_projected_history_cases'],
            final_equal=receipt['unchanged_projected_final_cases'],receipt=bind(args.output/'RESULT.json')),indent=2))
    except BaseException as exc:
        freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),completed=len(summaries)));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scope',choices=('smoke16','all160'),required=True);parser.add_argument('--reuse',type=Path)
    main(parser.parse_args())
