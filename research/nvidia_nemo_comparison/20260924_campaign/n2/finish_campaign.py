"""Validate a stopped N2 campaign and publish redacted checks. See README_FINISH.md."""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import run_campaign as campaign

COMBINATIONS=('D0_E0','D1_E0','D0_E1','D1_E1')
EXPECTED={**{'screen-'+c:96 for c in COMBINATIONS},**{'regression-'+c:8 for c in COMBINATIONS},'gui-panel':6}
PUBLIC_NAMES=('SCREEN_SUMMARY.json','SCREEN_SUMMARY.md','REGRESSION_SUMMARY.json','REGRESSION_SUMMARY.md','FINAL_CHECKS.json','FINAL_CHECKS.md')


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def binding(path):
    path=Path(path).resolve(strict=True)
    return dict(path=str(path),sha256=campaign.digest(path),bytes=path.stat().st_size)


def public_binding(path):
    return {k:v for k,v in binding(path).items() if k!='path'}


def require(condition,message):
    if not condition:raise ValueError(message)


def verify_bound(record):
    actual=binding(record['path'])
    require(actual['sha256']==record['sha256'] and ('bytes' not in record or actual['bytes']==record['bytes']),'Bound evidence changed')


def file_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def runtime_files(files):
    return {k:v['sha256'] for k,v in files.items() if k.startswith(('app/','vendor/','config/','release_tools/'))
            or k=='main.py' or '/' not in k and Path(k).suffix.lower() in {'.cmd','.bat','.ps1','.sh'}}


def validate_source(path):
    receipt=load(path);source=Path(receipt['prototype']).resolve(strict=True);files=receipt['files']
    require(receipt.get('schema')=='just-peachy.n1.frozen-source.v1','Unsupported frozen source receipt')
    require(type(receipt.get('file_count')) is int and receipt['file_count']==len(files)>0,'Frozen source file denominator differs')
    for name,record in files.items():
        file=(source/name).resolve();require(file.is_relative_to(source),'Frozen source path escaped')
        require(public_binding(file)==record,'Frozen source file changed')
    for name,record in receipt.get('auxiliary_files',{}).items():
        file=(source.parent/name).resolve()
        require(file.is_relative_to(source.parent),'Frozen auxiliary path escaped')
        require(public_binding(file)==record,'Frozen auxiliary file changed')
    runtime=runtime_files(files)
    require(campaign.canonical(runtime)==receipt['frontend_runtime_sha256'],'Frozen runtime digest differs')
    actual={str(p.relative_to(source)).replace('\\','/'):campaign.digest(p)
            for folder in ('app','vendor','config','release_tools') for p in (source/folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}
    actual.update({p.name:campaign.digest(p) for p in source.iterdir() if p.is_file() and (p.name=='main.py' or p.suffix.lower() in ('.cmd','.bat','.ps1','.sh'))})
    require(actual==runtime,'Frozen runtime file set differs')
    ui=receipt['common_ui_files']
    require(all(files[k]['sha256']==value for k,value in ui.items()) and campaign.canonical(ui)==receipt['common_ui_source_sha256'],'Common UI digest differs')
    verify_bound(receipt['archive'])
    return receipt,source,runtime


def validate_coordinator(spec_path,result_path):
    spec=load(spec_path);keys,_=campaign.admit(spec);jobs={j['id']:j for lane in spec['lanes'] for j in lane['jobs']}
    require(set(keys)==set(EXPECTED),'Exactly eight Controller jobs and one GUI job required')
    for key,job in jobs.items():
        require(job['cells']==EXPECTED[key] and job['result_kind']==('gui' if key=='gui-panel' else 'controller'),'Job kind/cell denominator differs')
    result=load(result_path);admission=load(Path(result_path).with_name('ADMISSION.json'))
    contract=admission['contract'];checksum=campaign.canonical(contract)
    require(contract['spec']==spec and checksum==admission['contract_sha256']==result['contract_sha256'],'Coordinator contract differs')
    require(contract.get('runner_sha256')==campaign.digest(HERE/'run_campaign.py') and contract.get('io_helper_sha256')==campaign.digest(HERE/'io_utils.py') and contract.get('io_version')==campaign.IO_VERSION,'Coordinator code binding differs')
    require(contract.get('supervisor_sha256')==campaign.digest(HERE.parent/'supervision/supervisor.py'),'Coordinator supervisor binding differs')
    require(result.get('schema')=='n2-numerical-coordinator-result-v1' and result.get('status')=='COMPLETE','Coordinator is not COMPLETE')
    require(not result.get('active') and not result.get('errors') and result.get('completed')==422 and result.get('total')==422,'Coordinator incomplete/error denominator')
    require(set(result.get('jobs',{}))==set(EXPECTED),'Coordinator result job set differs')
    require(type(result.get('pid')) is int and result['pid']>0,'Missing coordinator process identity')
    require(campaign.process_identity_state(result['pid'],None)=='ABSENT','Coordinator process still active or unverified')
    for key,job in jobs.items():
        row=result['jobs'][key]
        require(row.get('status')=='COMPLETE' and row.get('exit_code')==0 and row.get('cells')==EXPECTED[key] and not row.get('timeout_reached'),'Job did not exit successfully')
        if row.get('owner'):
            owner=row['owner'];require(campaign.process_identity_state(owner['pid'],owner.get('create_time')) in ('ABSENT','PID_REUSED'),'Job process still active or unverified')
        require(campaign.completion(job)==row.get('result'),'Completed job hash changed')
    return jobs,result


def validate_controller_inputs(jobs,source,runtime):
    manifests={};indexes={kind:[] for kind in ('screen','regression')}
    for kind in indexes:
        for combo in COMBINATIONS:
            job=jobs[kind+'-'+combo];path=Path(job['result']);admission=load(path.with_name('ADMISSION.json'));contract=admission['contract']
            require(campaign.canonical(contract)==admission['contract_sha256']==load(path)['contract_sha256'],'Controller admission hash differs')
            require(contract['combination']==combo and contract['source_bindings']==runtime,'Controller combination/frozen source differs')
            require(contract.get('supervisor_sha256')==campaign.digest(HERE.parent/'supervision/supervisor.py'),'Controller supervisor binding differs')
            argv=job['argv'];require(argv.count('--source')==1 and Path(argv[argv.index('--source')+1]).resolve()==source,'Controller command source differs')
            verify_bound(contract['manifest']);manifest=Path(contract['manifest']['path']).resolve()
            require(manifest.name==('AUDIO_ONLY.json' if kind=='screen' else 'REGRESSION_AUDIO_ONLY.json'),'Expected normalized evaluation manifest required')
            require(manifest.parent.name=='evaluation','Expected private evaluation directory')
            if kind in manifests:require(manifests[kind]==manifest,'Controller population manifests differ')
            manifests[kind]=manifest;indexes[kind].append(path)
            expected=load(manifest)['jobs'];require(len(expected)==EXPECTED[kind+'-'+combo],'Manifest denominator differs')
            ids=[row['job_id'] for row in expected];require(len(set(ids))==len(ids) and set(load(path)['completed'])==set(ids),'Controller exact completed population differs')
    require(manifests['screen'].parent==manifests['regression'].parent,'Evaluation directories differ')
    truth=manifests['screen'].with_name('EVALUATOR_TRUTH.json');require(truth.is_file(),'Missing frozen evaluator truth')
    return indexes,manifests,truth


def validate_gui(path,job,source,runtime):
    require(Path(path).resolve()==Path(job['result']).resolve(),'GUI report differs from coordinator job')
    panel=file_module('_n2_finish_gui',HERE/'gui/panel.py');report=load(path);admission=load(Path(path).with_name('ADMISSION.json'))
    expected={'D1_E1_boundary','D1_E1_short','D1_E1_returning','D1_E1_noise','D1_E1_silence','D1_E0_boundary'}
    require(report.get('status')=='COMPLETE' and report.get('full_panel') is True and report.get('completed')==6 and report.get('requested_cells')==6 and not report.get('missing_cells'),'GUI panel is not exact six-cell COMPLETE')
    require({j['cell_id'] for j in admission['jobs']}==expected and len(admission['jobs'])==6,'GUI cell set differs')
    require(Path(admission['source']).resolve()==source,'GUI frozen source differs')
    require(admission['source_bindings']=={k:v for k,v in runtime.items() if '/' in k},'GUI source binding differs')
    panel.check_binding(admission)
    runs=[dict(cell_id=row['cell_id'],output=row['output'],launcher_returncode=0) for row in report['private_processes']]
    verified=panel.aggregate_cell_reports(admission,runs)
    for key in ('cells','private_processes','admission','full_panel','completed','requested_cells'):
        require(verified[key]==report[key],'GUI aggregate evidence differs')
    return dict(status='COMPLETE',cells=6,device='cpu',archive_integrity_passed=True,physical_scanout='NOT_MEASURED')


def validate_tests(path,source_receipt):
    # The isolated-suite producer validates its module census and child receipts.
    suite=file_module('_n2_finish_suite',HERE/'check_suite.py')
    result=suite.validate_completed_report(Path(path),Path(source_receipt))
    # Test IDs, skip reasons, commands and bound paths stay in the private suite.
    return {key:result[key] for key in ('status','successful','requested_modules','finished_modules','successful_modules',
        'tests','planned_tests','failures','errors','skipped','expected_failures','unexpected_successes')}


def summarize(indexes,truth,out_dir,public_dir,manifest,scope):
    sys.path.insert(0,str(HERE/'evaluation'))
    from summarize_screen import summarize as aggregate
    return aggregate(indexes,truth,out_dir,public_dir,manifest,scope)


def validate_summary(summary,cells):
    return (summary.get('status')=='COMPLETE' and summary.get('collection_status')=='COMPLETE'
        and summary.get('scored_total_cells')==cells*4 and summary.get('expected_total_cells')==cells*4
        and summary.get('matched_four_way_cells')==cells and summary.get('ASR_invariance_status')=='PASS_ALL_MATCHED'
        and summary.get('caption_invariance_status')=='PASS_OBSERVED_ONLY' and not summary.get('failure_counts'))


def _run_locked(args):
    output=args.output.resolve();public=args.public_out.resolve()
    require(not output.exists(),'Private output must be fresh')
    source_path=Path(load(args.source_receipt)['prototype']).resolve()
    require(not output.is_relative_to(source_path) and not public.is_relative_to(source_path),'Outputs must be outside frozen source')
    require(not output.is_relative_to(public) and not public.is_relative_to(output),'Private and public output trees must be separate')
    require(not any((public/name).exists() for name in PUBLIC_NAMES),'Public reports already exist; preserve them and choose a fresh public directory')
    output.mkdir(parents=True);public.mkdir(parents=True,exist_ok=True)
    checks=dict(schema='n2-final-checks-v1',created_utc=datetime.now(timezone.utc).isoformat(),status='FAILED',
        expected_controller_cells=416,expected_gui_cells=6,expected_jobs=9,checks={},summaries={},input_hashes={},failures=[],
        model_calls=False,git_actions=False,packaging_performed=False,stage_completion_claimed=False,
        qualification='Post-run evidence and quality checks only; no Pi, total-system memory, physical scanout or calibrated open-name claim')
    private_errors=[]
    def error(stage,exc):
        checks['failures'].append(dict(stage=stage,error_type=type(exc).__name__))
        private_errors.append(dict(stage=stage,error=repr(exc)))
    try:
        for name in ('spec','coordinator_result','source_receipt','test_report','gui_report'):
            checks['input_hashes'][name]=public_binding(getattr(args,name))
        owner_lock=args.coordinator_result.with_name('owner.lock');require(owner_lock.is_file(),'Missing coordinator lifetime lock')
        jobs,coordinator=validate_coordinator(args.spec,args.coordinator_result)
        receipt,source,runtime=validate_source(args.source_receipt)
        indexes,manifests,truth=validate_controller_inputs(jobs,source,runtime)
        evaluation_inputs={**manifests,'truth':truth,'rosters':truth.with_name('ROSTERS.json'),'manifest_receipt':truth.with_name('MANIFEST_RECEIPT.json')}
        checks['evaluation_input_hashes']={key:public_binding(path) for key,path in evaluation_inputs.items()}
        checks['checks']['coordinator']=dict(status='COMPLETE',jobs=9,cells=422,contract_sha256=coordinator['contract_sha256'])
        checks['checks']['source']=dict(status='VERIFIED',file_count=receipt['file_count'],auxiliary_file_count=len(receipt.get('auxiliary_files',{})),frontend_runtime_sha256=receipt['frontend_runtime_sha256'],common_ui_source_sha256=receipt['common_ui_source_sha256'])
        checks['checks']['gui']=validate_gui(args.gui_report,jobs['gui-panel'],source,runtime)
        checks['checks']['tests']=validate_tests(args.test_report,args.source_receipt)
        checks['job_result_hashes']={key:{k:v for k,v in coordinator['jobs'][key]['result'].items() if k!='path'} for key in EXPECTED}
        for kind,cells,scope in (('screen',96,'screen48'),('regression',8,'regression')):
            try:
                stage=output/kind;redacted=stage/'redacted'
                summary=summarize(indexes[kind],truth,stage,redacted,manifests[kind],scope)
                checks['summaries'][kind]={key:summary.get(key) for key in ('status','collection_status','scored_total_cells','expected_total_cells','matched_four_way_cells','ASR_invariance_status','caption_invariance_status')}
                for suffix in ('json','md'):
                    origin=redacted/('SCREEN_SUMMARY.'+suffix);target=public/(kind.upper()+'_SUMMARY.'+suffix)
                    shutil.copyfile(origin,target)
                    checks.setdefault('report_hashes',{})[target.name]=public_binding(target)
                checks['report_hashes'][kind+'_private_evidence']=public_binding(stage/'SCREEN_EVIDENCE.json')
                if not validate_summary(summary,cells):error(kind+'_quality',ValueError('Required complete population/invariance gate failed'))
            except Exception as exc:error(kind+'_summary',exc)
        # Final immutable input check catches drift during offline scoring.
        for name,record in checks['input_hashes'].items():require(public_binding(getattr(args,name))==record,'Input changed during final checks')
        for job in jobs.values():require(campaign.completion(job)==coordinator['jobs'][job['id']]['result'],'Job evidence changed during final checks')
        for key,path in evaluation_inputs.items():require(public_binding(path)==checks['evaluation_input_hashes'][key],'Evaluation input changed during final checks')
        validate_source(args.source_receipt)
    except Exception as exc:error('admission_or_evidence',exc)
    checks['status']='PASS' if not checks['failures'] and len(checks['summaries'])==2 else 'FAILED'
    checks['finisher_sha256']=campaign.digest(__file__)
    campaign.atomic(output/'PRIVATE_ERRORS.json',private_errors)
    checks.setdefault('report_hashes',{})['private_errors']=public_binding(output/'PRIVATE_ERRORS.json')
    campaign.atomic(output/'FINAL_CHECKS.json',checks);campaign.atomic(public/'FINAL_CHECKS.json',checks)
    markdown=['# N2 final evidence checks','',f"Status: **{checks['status']}**.",'',
        'Required: eight Controller jobs (384 screen + 32 regression cells), six GUI cells, the exact frozen source and isolated test suite.',
        'No model execution, packaging, Git action or project-stage completion claim is performed.','',
        '| Population | Status | Scored / expected | ASR invariance | Caption invariance |',
        '| --- | --- | ---: | --- | --- |']
    for kind,row in checks['summaries'].items():markdown.append(f"| {kind} | {row['status']} | {row['scored_total_cells']} / {row['expected_total_cells']} | {row['ASR_invariance_status']} | {row['caption_invariance_status']} |")
    markdown+=['',f"Failed checks: {len(checks['failures'])}. See FINAL_CHECKS.json for redacted report hashes and failure stages.",checks['qualification']]
    text='\n'.join(markdown)+'\n'
    for folder in (output,public):(folder/'FINAL_CHECKS.md').write_text(text,encoding='utf-8')
    return 0 if checks['status']=='PASS' else 2


def run(args):
    # Keep the coordinator lifetime lock through publication; never wait or
    # steal ownership, and do not inspect mutable running results.
    owner_lock=args.coordinator_result.with_name('owner.lock')
    require(owner_lock.is_file(),'Missing coordinator lifetime lock')
    with campaign.lock(owner_lock):
        return _run_locked(args)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('spec','coordinator-result','source-receipt','test-report','gui-report','output','public-out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--cpu',type=int,default=4,help='Lightweight offline checks only; default CPU4')
    args=parser.parse_args()
    import psutil
    process=psutil.Process();process.cpu_affinity([args.cpu])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    return run(args)


if __name__=='__main__':raise SystemExit(main())
