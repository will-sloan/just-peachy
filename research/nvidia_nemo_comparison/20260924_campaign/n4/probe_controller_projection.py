"""Project 160 sealed mode results through Controller. README_CONTROLLER_PROJECTION.md."""
import argparse
from datetime import datetime,timezone,timedelta
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import audio_only,bind,freeze,load,verify
from controller_projection import project_mode_result,forbid_inference
from probe_component_s7 import save_private


def read_replay(binding):
    verify(binding['compressed'])
    with gzip.open(binding['compressed']['path'],'rb') as stream:raw=stream.read(32*1024**2+1)
    if len(raw)!=binding['expanded_bytes'] or hashlib.sha256(raw).hexdigest()!=binding['expanded_sha256']:
        raise ValueError('Sealed mode replay expanded hash/size mismatch')
    return json.loads(raw)


def resource_guard(output,policy):
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    for drive,floor in [('C:\\',50),('G:\\',75)]:
        if shutil.disk_usage(drive).free<floor*1024**3+512*1024**2:
            raise ValueError('Insufficient space under campaign floors and projection reservation')
    size=sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) if output.exists() else 0
    if size+34*1024**2>512*1024**2:raise ValueError('Private projection allocation exhausted')


def main(args):
    import psutil
    from asr_full_bank import payload_inventory
    proc=psutil.Process();proc.cpu_affinity([14]);proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    here=Path(__file__).resolve().parent
    public=load(here/'COMPONENT_MODES_CHECK_V1.json');verify(public['private_receipt'])
    parent=load(public['private_receipt']['path'])
    if parent['status']!='PASS_160_MODELED_CATALOG_MODE_DEVELOPMENT_REPLAYS' or parent['checks_count']!=160:
        raise ValueError('Require all 160 sealed mode-development results')
    for b in [parent['source_receipt'],parent['gallery_preparation'],*parent['code']]:verify(b)
    s=load(parent['source_receipt']['path']);source=Path(s['prototype'])
    for rel,b in s['files'].items():verify(dict(path=str((source/rel).resolve()),**b))
    prepared=load(parent['gallery_preparation']['path']);wiring=load(here/'ACCEPTED_SOURCE_CATALOG_CHECK.json')
    if wiring['source_catalog']!=prepared['catalog']:raise ValueError('Controller and mode catalogs differ')
    for b in wiring['inputs']:verify(b)
    runtimes={Path(b['path']).name:b for b in wiring['inputs']}
    local=Path(parent['source_receipt']['path']).parents[2];policy=load(local/'supervision/campaign.json')
    if args.output.exists():raise ValueError('Preserve previous probes; choose a fresh output')
    resource_guard(args.output,policy);inventory=payload_inventory(local)
    conservative=inventory['total_logical_bytes']+6*1024**3
    if conservative>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared payload allowance cannot admit the projection probe')
    sys.path[:0]=[str(source),str(source/'vendor')]
    args.output.mkdir(parents=True,exist_ok=False);summaries=[]
    try:
        with forbid_inference():
            for index,entry in enumerate(parent['checks']):
                resource_guard(args.output,policy)
                for b in entry['inputs']:verify(b)
                job=audio_only(load(entry['inputs'][0]['path'])['job'])
                if job['job_id']!=entry['job_id']:raise ValueError('Mode/source parent identity changed')
                replay=read_replay(entry['output'])
                if (replay['contract']['backend_key']!=entry['backend'] or replay['contract']['mode']!=entry['mode']
                        or len(replay['display_events'])!=entry['display_events']):raise ValueError('Mode replay census differs')
                name=f'{index:03d}'
                result=project_mode_result(replay,tap=job['tap'],preparation=parent['gallery_preparation'],
                    n2_runtime=runtimes['n2_runtime.json'],n3_runtime=runtimes['n3_runtime.json'],data_root=args.output/'controllers'/name)
                artifact=save_private(args.output/(name+'.json.gz'),result)
                projected=[r for h in result['history'] for r in h['rows']]
                summaries.append(dict(backend=entry['backend'],mode=entry['mode'],job_id=entry['job_id'],tap=job['tap'],
                    input=entry['output'],private_output=artifact,display_inputs=result['display_inputs'],
                    projected_rows_including_unchanged_context=len(projected),final_fragments=len(result['final_rows']),
                    assumed_projected_rows=sum(r['identity_assignment'] in ('closed_assumed','forced','assumed_unlinked') for r in projected),
                    selected_focus_numbered_fallback_rows=sum(entry['mode']=='selected_focus' and r['profile_id'] is None
                        and str(r['label']).startswith('Speaker') for r in projected),
                    consumer_closure=result['actual_consumer_closure'],controller_closed=result['controller_closed'],
                    model_loads=result['model_loads'],integrated_N4_cells=0))
                if (index+1)%20==0:print(json.dumps(dict(completed=index+1,total=160)),flush=True)
        if len(summaries)!=160:raise ValueError('Controller projection census incomplete')
        receipt=dict(status='PASS_160_ACTUAL_CONTROLLER_CONSUMER_PROJECTIONS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
            parent=public['private_receipt'],source_receipt=parent['source_receipt'],gallery_preparation=parent['gallery_preparation'],
            runtime_inputs=wiring['inputs'],code=[bind(here/n) for n in ('controller_projection.py','probe_controller_projection.py',
                'test_controller_projection.py','README_CONTROLLER_PROJECTION.md','mode_galleries.py','probe_component_s7.py','common.py')],
            resource_admission=dict(inventory=inventory,conservative_existing_and_reserved_bytes=conservative,
                run_limit_bytes=512*1024**2,expanded_cell_limit_bytes=32*1024**2,history_limit_bytes=24*1024**2),
            checks=summaries,checks_count=len(summaries),models_loaded=0,hardware_calls=0,physical_widget_observed=False,
            upstream_publication_parity=False,complete_Controller_parity=False,integrated_N4_cells=0,
            scope='Actual Controller constructor/selection/switch/consumer/snapshot/close over sealed modeled displays; no producer/model/GUI/latency/accuracy acceptance.')
        freeze(args.output/'RESULT.json',receipt)
        print(json.dumps(dict(status=receipt['status'],receipt=bind(args.output/'RESULT.json')),indent=2))
    except BaseException as exc:
        freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),completed=len(summaries)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    main(parser.parse_args())
