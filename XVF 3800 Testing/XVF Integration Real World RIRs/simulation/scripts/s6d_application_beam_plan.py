"""Freeze exact future native jobs from accepted physical inputs only. See README_S6D_APPLICATION_BEAM_PLAN.md."""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil
import sys

REPO=next(p for p in Path(__file__).resolve().parents if (p/'Software Validation from Datasets/Evaluation Tool/app').is_dir())
SIM=REPO/'XVF 3800 Testing/XVF Integration Real World RIRs/simulation'
APP=REPO/'Software Validation from Datasets/Evaluation Tool/app'
if (Path(__file__).resolve().parent.parent/'source/edge_speech_pipeline').is_dir():APP=Path(__file__).resolve().parent.parent/'source'
sys.path.insert(0,str(APP))
from edge_speech_pipeline.research_beams_s6d import binding,verified,BeamSettings,CaptureAdmission,BeamSelector,BeamPipelineEngine
from edge_speech_pipeline.research_profiles import ResearchProfile
from edge_speech_pipeline.research_s6d import S6DSettings
from edge_speech_pipeline.config import PipelineConfig,AssetSpec
from dataclasses import replace


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n')


def prepare(request_path,directory,payload):
    request_binding=binding(request_path);request=verified(request_binding)
    if request.get('schema')!='s6d-beam-native-request.v1' or set(request)-{'schema','jobs','declared_job_limit','purpose'}:
        raise ValueError('Explicit bounded native beam request required')
    jobs=request.get('jobs');limit=request.get('declared_job_limit')
    if not isinstance(jobs,list) or type(limit) is not int or not 0<=len(jobs)<=limit<=4096:
        raise ValueError('Finite predeclared job count required')
    if directory.exists() or payload.exists():raise ValueError('Fresh plan and proposed payload directories required')
    epoch_ref=binding(SIM/'reports/S6C/20260910T123540Z/EPOCH4_EXECUTION_MANIFEST.json');epoch=verified(epoch_ref)
    assets=tuple(AssetSpec(r['component_id'],Path(r['path']),r['sha256'],r['deployment_relative_path']) for r in epoch['assets'])
    base=PipelineConfig()
    if {a.component_id:a.sha256 for a in assets}!={a.component_id:a.sha256 for a in base.assets}:
        raise ValueError('Existing fixed eight-asset model family changed')
    prepared=[];groups=defaultdict(list);ids=set();captures=set()
    required={'job_id','control_group','role','admission','beam_settings','research_profile','research_gallery','s6d_settings'}
    for row in jobs:
        if not isinstance(row,dict) or set(row)!=required:raise ValueError('Each job must bind every requested input explicitly')
        job_id=row['job_id']
        if not isinstance(job_id,str) or not job_id or len(job_id)>128 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in job_id) or job_id in ids:
            raise ValueError('Unique path-safe predeclared job ID required')
        ids.add(job_id)
        if not isinstance(row['control_group'],str) or not row['control_group']:raise ValueError('Explicit matched control group required')
        for key in ('admission','beam_settings','research_profile','research_gallery','s6d_settings'):verified(row[key])
        profile=ResearchProfile.load(row['research_profile']['path']);settings=BeamSettings.load(row['beam_settings']['path'])
        s6d=S6DSettings.load(row['s6d_settings']['path'])
        if settings.mode!=row['role']:raise ValueError('Job role differs from the implemented beam mode')
        config=replace(base,assets=assets,session_root=payload/job_id/'sessions',profile_root=payload/job_id/'unused_private_profiles')
        engine=BeamPipelineEngine(config,research_profile=profile,research_gallery=row['research_gallery']['path'],s6d_settings=s6d,beam_settings=settings)
        if any(getattr(engine.config,k)!=1 for k in ('asr_threads','speaker_threads','punctuation_threads')):raise ValueError('Native confirmation requires explicit single CPU threads')
        capture=CaptureAdmission(row['admission']['path'],settings)
        selector=BeamSelector(settings,engine._research_gallery.receipt['manifest'],profile_digest=profile.digest(),capture_profile=capture.capture_profile,
            capture_identity=(capture.data['capture_source_id'],capture.data['route_id']))
        if settings.mode not in {'same_pass_auto_control','calibration_collection'} and selector.calibration is None:
            raise ValueError('Do not launch an uncalibrated nominal selector as a failed beam-family experiment')
        duration=capture.frames/16000
        if duration>600:raise ValueError('This bounded panel/full-bank planner does not declare continuous long-session jobs')
        capture_key=capture.data['case_result']['sha256'];captures.add(capture_key)
        item={**row,'capture_result':capture.data['case_result'],'capture_profile':capture.capture_profile,'duration_sec':duration,
            'stream_bindings':[capture.provenance(n) for n in capture.names],'profile_sha256':profile.digest(),
            'calibration':settings.calibration,'calibration_partition':capture.calibration_partition,'direction_capability':capture.direction_status,
            'output':str(payload/job_id),'asr_stream':settings.asr_stream,'identity_streams':list(settings.identity_streams),
            'native_tested':False,'gui_tested':False,'cm5_tested':False,'physical_input_qualification_is_upstream_only':True}
        prepared.append(item);groups[row['control_group']].append(item)
    for group,rows in groups.items():
        if any(r['role']=='calibration_collection' for r in rows):
            if any(r['role']!='calibration_collection' for r in rows):raise ValueError('C collection and evaluation must be separate groups')
            continue
        controls=[r for r in rows if r['role']=='same_pass_auto_control']
        if len(controls)!=1 or len(rows)<2:raise ValueError('Every comparison group needs exactly one same-pass auto parent and at least one explicit variant')
        for key in ('capture_result','profile_sha256','research_gallery','asr_stream','s6d_settings'):
            if any(r[key]!=controls[0][key] for r in rows):raise ValueError('Unmatched '+key+' inside control group '+group)
    directory.mkdir(parents=True,exist_ok=False)
    helper_root=directory/'helpers';helper_root.mkdir()
    for name in ('s6d_application_beam_plan.py','s6d_application_beam_plan_checks.py','README_S6D_APPLICATION_BEAM_PLAN.md'):
        shutil.copy2(Path(__file__).with_name(name),helper_root/name)
    source=directory/'source/edge_speech_pipeline';source.mkdir(parents=True)
    source_files=[]
    for path in sorted((APP/'edge_speech_pipeline').iterdir()):
        if path.suffix in {'.py','.md'}:shutil.copy2(path,source/path.name);source_files.append(binding(source/path.name))
    save(directory/'ASSETS.json',epoch['assets']);asset_ref=binding(directory/'ASSETS.json')
    for row in prepared:
        input_receipt=directory/(row['job_id']+'_INPUTS.json')
        save(input_receipt,{'schema_version':'edge-s6d-beam-job-inputs.v1','inputs':
            {k:row[k] for k in ('admission','beam_settings','research_profile','research_gallery','s6d_settings')}|{'asset_manifest':asset_ref}})
        row['input_receipt']=binding(input_receipt)
        row['argv']=[str(REPO/'.edge-speech-env/python.exe'),'-B','-m','edge_speech_pipeline','capture',row['admission']['path'],
            '--beam-settings',row['beam_settings']['path'],'--research-profile',row['research_profile']['path'],
            '--research-gallery',row['research_gallery']['path'],'--s6d-settings',row['s6d_settings']['path'],
            '--asset-manifest',asset_ref['path'],'--session-root',str(Path(row['output'])/'sessions'),
            '--input-bindings',str(input_receipt),'--input-bindings-sha256',row['input_receipt']['sha256']]
        row['model_free_admission_argv']=row['argv']+['--check-only']
    result={'schema':'s6d-beam-native-plan.v1','status':'PREDECLARED_PENDING_REVIEW' if prepared else 'INTERFACE_FROZEN_NO_ADMITTED_INPUTS',
        'request':request_binding,'purpose':request.get('purpose'),'jobs':prepared,'job_count':len(prepared),'unique_physical_capture_results':len(captures),
        'job_source_duration_sum_sec':sum(r['duration_sec'] for r in prepared),'source_root':str(source.parent),'source_files':source_files,
        'assets':asset_ref,'asset_authority':epoch_ref,'helper':binding(helper_root/'s6d_application_beam_plan.py'),'readme':binding(helper_root/'README_S6D_APPLICATION_BEAM_PLAN.md'),
        'planner_checks':binding(helper_root/'s6d_application_beam_plan_checks.py'),
        'environment':{'PYTHONPATH':str(source.parent),'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'},
        'execution_limits':{'serial_jobs':True,'one_continuous_sherpa_stream_per_job':True,'shared_serial_pyannote_redimnet_owner':True,
            'maximum_focus_identity_states':2,'no_waveform_switching':True,'source_paced_cpu_confirmation':True,'cell_wall_limit_sec':600},
        'model_jobs_started':0,'capture_jobs_started':0,'no_cached_O0_O1_predictions_reused':True,
        'remaining':['Root source/matrix/supervisor review before launch.','Existing recordings require independent physical route/tail acceptance and C-only selector calibration.','Native beam timing/accuracy, GUI, CM5 and continuous long sessions remain untested by this plan.']}
    save(directory/'MANIFEST.json',result);print(json.dumps({'status':result['status'],'jobs':len(prepared),'manifest':binding(directory/'MANIFEST.json')}))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);p.add_argument('--directory',type=Path,required=True);p.add_argument('--payload',type=Path,required=True)
    args=p.parse_args();prepare(args.request,args.directory,args.payload)
