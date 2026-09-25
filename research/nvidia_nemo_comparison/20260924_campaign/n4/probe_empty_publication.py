"""Check all 19 closed A0 empty outputs in two modes. README_CONTROLLER_PROJECTION_V2.md."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import load,verify,bind,freeze,audio_only
from component_commands import asr_commands,d0_commands
from application_publication import replay_d0_publication
from controller_projection_v2 import project_mode_result,forbid_inference
from probe_application_publication import guard
from probe_component_s7 import read_events,save_private


def main(args):
    import psutil
    from asr_full_bank import payload_inventory
    process=psutil.Process();process.cpu_affinity([14]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    here=Path(__file__).resolve().parent;parent=load(here/'CONTROLLER_PROJECTION_CHECK_V1.json')
    verify(parent['private_receipt']);controller=load(parent['private_receipt']['path'])
    local=Path(parent['source_receipt']['path']).parents[2];policy=load(local/'supervision/campaign.json')
    audit=load(local/'n4/EMPTY_ASR_OUTPUT_AUDIT_V1.json');verify(audit['index'])
    if audit['cells']!=480 or len(audit['empty_output_cells'])!=19:raise ValueError('Predeclared A0 empty census differs')
    admission_binding=bind(local/'n4/asr-full-bank-v1/ADMISSION.json');admission=load(admission_binding['path'])
    d0=load(here/'D0_FULL_BANK_REVIEW_V1.json')
    if d0['status']!='PASS_MATCHED_FULL_BANK_COMPONENTS_ONLY':raise ValueError('D0 bank review required')
    for b in d0['inputs']:verify(b)
    d0ad=next(b for b in d0['inputs'] if Path(b['path']).name=='ADMISSION.json')
    if admission['component_contract']['source_receipt']!=parent['source_receipt'] or load(d0ad['path'])['source_receipt']!=parent['source_receipt']:
        raise ValueError('Different application sources')
    verify(parent['source_receipt']);source_receipt=load(parent['source_receipt']['path']);source=Path(source_receipt['prototype'])
    for rel,b in source_receipt['files'].items():verify(dict(path=str((source/rel).resolve()),**b))
    sys.path[:0]=[str(source),str(source/'vendor')]
    d0index=load(next(b['path'] for b in d0['inputs'] if Path(b['path']).name=='RESULT_INDEX.json' and Path(b['path']).parent.name=='E0'))
    runtime={Path(b['path']).name:b for b in controller['runtime_inputs']}
    for b in [controller['gallery_preparation'],*controller['runtime_inputs']]:verify(b)
    if args.output.exists():raise ValueError('Preserve previous empty probes; choose fresh output')
    guard(args.output,policy);inventory=payload_inventory(local)
    if inventory['total_logical_bytes']+6*1024**3>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared payload allowance unavailable')
    code=[bind(here/n) for n in ('controller_projection_v2.py','test_controller_projection_v2.py','probe_empty_publication.py',
        'README_CONTROLLER_PROJECTION_V2.md','application_publication.py','component_commands.py','probe_application_publication.py',
        'probe_component_s7.py','common.py')]
    args.output.mkdir(parents=True,exist_ok=False);checks=[]
    freeze(args.output/'ADMISSION.json',dict(owner=dict(pid=process.pid,create_time=process.create_time()),code=code,
        empty_audit=bind(local/'n4/EMPTY_ASR_OUTPUT_AUDIT_V1.json'),source=parent['source_receipt'],
        ASR_terminal_review_pending=True,inventory=inventory,scope='19 closed A0 zero-output cells x anonymous/closed baseline; development only'))
    try:
        for empty in audit['empty_output_cells']:
            verify(empty['cell']);a=load(empty['cell']['path']);job=audio_only(a['job']);duration=job['frames']/16000
            if (a['status']!='COMPLETE' or a['variant']!='A0' or a['admission_sha256']!=admission_binding['sha256']
                    or a['summary']['predictor_observations']!=0 or a['summary']['final_utterances'] or a['summary']['raw_final_text']):
                raise ValueError('Closed A0 empty parent changed')
            if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Saved waveform binding changed')
            sb=d0index['cells'][job['job_id']];verify(sb);s=load(sb['path'])
            if s['status']!='COMPLETE' or s['encoder']!='E0' or s['job']!=job or s['admission_sha256']!=d0ad['sha256']:
                raise ValueError('Speaker parent differs')
            arows=read_events(a);srows=read_events(s)
            if any(r['event_type'] in ('research_asr_observation','component_final_punctuation') for r in arows):
                raise ValueError('Empty summary concealed actual text')
            ac=asr_commands(arows,variant='A0',duration=duration);sc=d0_commands(srows,duration=duration)
            for mode in ('anonymous_conversation','selected_closed'):
                guard(args.output,policy);name=f'{len(checks):03d}'
                publication=replay_d0_publication(ac,sc,duration=duration,preparation=controller['gallery_preparation'],
                    backend='baseline',mode=mode,tap=job['tap'],namespace=s['namespace'],session_id=job['job_id'])
                with forbid_inference():
                    projection=project_mode_result(publication,tap=job['tap'],preparation=controller['gallery_preparation'],
                        n2_runtime=runtime['n2_runtime.json'],n3_runtime=runtime['n3_runtime.json'],data_root=args.output/'controllers'/name)
                if not projection['empty_caption_session'] or projection['display_inputs'] or projection['final_rows'] or not projection['controller_closed']:
                    raise ValueError('Empty Controller session produced text or did not close')
                checks.append(dict(job_id=job['job_id'],mode=mode,inputs=[empty['cell'],sb],
                    publication=save_private(args.output/(name+'-publication.json.gz'),publication),
                    projection=save_private(args.output/(name+'-projection.json.gz'),projection),
                    closure=projection['actual_consumer_closure'],display_inputs=0,controller_closed=True,integrated_N4_cells=0))
            if len(checks)%10==0:print(json.dumps(dict(completed=len(checks),total=38)),flush=True)
        for b in code:verify(b)
        if len(checks)!=38:raise ValueError('Incomplete empty-case census')
        result=dict(status='PASS_38_REAL_EMPTY_OUTPUT_METHOD_CHECKS',utc=datetime.now(timezone.utc).isoformat(),code=code,
            source_receipt=parent['source_receipt'],empty_audit=bind(local/'n4/EMPTY_ASR_OUTPUT_AUDIT_V1.json'),
            ASR_terminal_review_pending=True,checks=checks,checks_count=38,closed_A0_files=19,
            models_loaded=0,physical_widget_observed=False,integrated_N4_cells=0,
            scope='Closed A0 empty evidence through modeled actual publication and empty-safe Controller; no bank acceptance, new inference or accuracy claim')
        freeze(args.output/'RESULT.json',result);print(json.dumps(dict(status=result['status'],receipt=bind(args.output/'RESULT.json')),indent=2))
    except BaseException as exc:
        freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),completed=len(checks)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
