"""Score 32 saved main-mode checks and 19 empty outputs. README_INTEGRATED_SCORING.md."""
import argparse
from collections import Counter
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import bind,freeze,load,verify,fingerprint
from integrated_scoring_adapter import read_artifact,read_component_events,convert,score_prediction
from metrics import require_versions


def verify_environment(binding):
    verify(binding);environment=load(binding['path'])
    if environment['metric_versions']!=require_versions() or bind(sys.executable)!=environment['python']:
        raise ValueError('Require the original isolated metric environment')
    checked=0
    for package in environment['packages']:
        if fingerprint(package['files'])!=package['code_manifest_sha256']:raise ValueError('Environment manifest differs')
        for row in package['files']:
            verify({k:row[k] for k in ('path','sha256','bytes')});checked+=1
    return checked


def private_bytes(root):
    total=0
    def fail(error):raise error
    for directory,dirs,files in os.walk(root,followlinks=False,onerror=fail):
        dirs[:]=[d for d in dirs if not (Path(directory)/d).is_symlink()
            and not ((Path(directory)/d).lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)]
        for name in files:
            p=Path(directory)/name;s=p.lstat()
            if not p.is_symlink() and not (s.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):total+=s.st_size
    return total


def guard(output,policy,started):
    if time.monotonic()-started>12*60:raise TimeoutError('Development scoring exceeded the between-cell 12-minute budget')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    for drive,floor in [('C:/',50),('G:/',75)]:
        if shutil.disk_usage(drive).free<floor*1024**3+256*1024**2:raise ValueError('Campaign drive floor unavailable')
    if output.exists() and sum(p.stat().st_size for p in output.rglob('*') if p.is_file())>128*1024**2:
        raise ValueError('Development scoring storage bound exceeded')


def main(args):
    import psutil
    process=psutil.Process();process.cpu_affinity([14]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    here=Path(__file__).resolve().parent
    environment_binding=load(here/'METRIC_ENVIRONMENT.json')['environment'];files=verify_environment(environment_binding)
    p=load(here/'APPLICATION_PUBLICATION_CHECK_V1.json');e=load(here/'EMPTY_CONTROLLER_CHECK_V1.json')
    if p['checks_count']!=160 or e['checks_count']!=38:raise ValueError('Complete saved method qualification required')
    for receipt in (p,e):
        for b in (receipt['private_receipt'],*receipt['code']):verify(b)
    parent=load(p['private_receipt']['path']);empty=load(e['private_receipt']['path'])
    main_checks=[dict(r,kind='main-mode') for r in parent['checks'] if r['mode']=='open_with_names']
    empty_checks=[dict(r,kind='empty-output',backend='baseline',consumer_closure=r['closure'])
        for r in empty['checks'] if r['mode']=='anonymous_conversation']
    if len(main_checks)!=32 or len(empty_checks)!=19:raise ValueError('Predeclared scoring case census differs')
    prep_binding=load(here/'PREPARATION_V2_CHECK.json')['preparation'];verify(prep_binding);prep=load(prep_binding['path'])
    truth_binding=next(b for b in prep['inputs'] if Path(b['path']).name=='EVALUATOR_TRUTH.json');verify(truth_binding)
    truth_document=load(truth_binding['path'])
    if truth_document.get('NEVER_PASS_TO_RUNTIME') is not True:raise ValueError('Evaluator-only reference marker missing')
    truths={r['job_id']:r for r in truth_document['cells']}
    if len(truths)!=480 or len(truth_document['cells'])!=480:raise ValueError('Frozen truth population differs')
    local=Path(p['source_receipt']['path']).parents[2];policy=load(local/'supervision/campaign.json');started=time.monotonic()
    if args.output.exists() or not args.output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private N4 output required')
    guard(args.output,policy,started);size=private_bytes(local)
    if size+6*1024**3+256*1024**2>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared campaign allowance insufficient with pending reservations')
    code=[bind(here/n) for n in ('integrated_scoring_adapter.py','probe_integrated_scoring.py','test_integrated_scoring.py',
        'README_INTEGRATED_SCORING.md','metrics.py','common.py')]
    args.output.mkdir(parents=True,exist_ok=False);rows=[]
    freeze(args.output/'ADMISSION.json',dict(owner=dict(pid=process.pid,create_time=process.create_time()),
        code=code,environment=environment_binding,environment_files_verified=files,truth=truth_binding,
        parents=[p['private_receipt'],e['private_receipt']],cases=51,private_bytes_at_start=size,
        resource_scope='CPU14, no models, no GPU; original numerical worker left alone',integrated_N4_cells=0))
    try:
        for i,entry in enumerate(main_checks+empty_checks):
            guard(args.output,policy,started)
            for b in [*entry['inputs'],entry['consumer_closure']]:verify(b)
            a,s=[load(b['path']) for b in entry['inputs']];job=a['job'];truth=truths[job['job_id']]
            if s['job']!=job or truth['frames']!=job['frames'] or truth['tap']!=job['tap']:
                raise ValueError('Prediction/reference audio join differs')
            publication=read_artifact(entry['publication']);projection=read_artifact(entry['projection'])
            if not load(entry['consumer_closure']['path'])['full_event_consumer_drained']:
                raise ValueError('Saved Controller consumer not closed')
            before=time.monotonic()
            prediction=convert(publication,projection,read_component_events(s),job,publication['contract']['diarization'])
            score=score_prediction(truth,prediction)
            if entry['kind']=='empty-output' and (prediction['raw_text'] or score['hypothesis_words']):
                raise ValueError('Empty output invented text')
            result=dict(scope='DEVELOPMENT_METHOD_SCORING_ONLY',kind=entry['kind'],backend=entry['backend'],mode=entry['mode'],
                job_id=job['job_id'],tap=job['tap'],score=score,compute_seconds=time.monotonic()-before,
                inputs=entry['inputs'],publication=entry['publication'],projection=entry['projection'],
                consumer_closure=entry['consumer_closure'],integrated_N4_cells=0)
            path=args.output/f'{i:03d}-SCORE.json';freeze(path,result);rows.append(bind(path))
            if (i+1)%8==0:print(json.dumps(dict(completed=len(rows),total=51)),flush=True)
        for b in code:verify(b)
        freeze(args.output/'RESULT.json',dict(status='PASS_51_DEVELOPMENT_METHOD_SCORING_CHECKS',utc=datetime.now(timezone.utc).isoformat(),
            admission=bind(args.output/'ADMISSION.json'),code=code,cases=51,main_mode_cases=32,empty_output_cases=19,results=rows,
            metric_versions=require_versions(),models_loaded=0,integrated_N4_cells=0,
            scope='Two smoke sources reused across 16 tuples, plus 19 closed A0 empty outputs; no bank, independent coverage, GUI timing or recognition acceptance'))
        print(json.dumps(dict(status='PASS_51_DEVELOPMENT_METHOD_SCORING_CHECKS',receipt=bind(args.output/'RESULT.json'))))
    except BaseException as exc:
        freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),completed=len(rows),results=rows));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args())
