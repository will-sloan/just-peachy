"""Build and verify the compact S6A handoff after final analysis. README_S6A_HANDOFF.md."""
from __future__ import annotations
import collections
import difflib
import hashlib
import json
import re
from pathlib import Path
import shutil
import zipfile
from s6a_common import *

REQUIRED_TEXT=('START_HERE.md','S6A_JOINT_REPORT.md','NEXT_STAGE_INPUTS.md','WORKBOOK_UPDATE.md')
SKIP_ROOT={'JOB_MANIFEST.json','PROBE_JOB_MANIFEST.json','PROBE_JOB_MANIFEST_V2.json','PROBE_PROGRESS_ROWS.json',
           'WORKBOOK_CONTEXT.txt','COMPONENT_API_TESTS.json','COMPONENT_API_TESTS_FINAL.json','COMPONENT_API_TESTS_READY.json',
           'PROBE_COORDINATOR.json','BASELINE_COORDINATOR.json','PACKAGING_RECEIPT.json','LOCAL_ARTIFACT_INDEX.json','heartbeat.jsonl'}
ALLOWED={'.md','.json','.csv','.py','.png','.diff'}

def owned_alive(records):
    import psutil
    live=[]
    for pid,created in records:
        try:
            process=psutil.Process(pid)
            if abs(process.create_time()-created)<.05:live.append({'pid':pid,'creation_time':created,'name':process.name()})
        except psutil.NoSuchProcess:pass
    return live

def completion_audit():
    base=read(REPORT/'BASELINE_SCORE_RECEIPT.json');probes=read(REPORT/'PROBE_ANALYSIS_RECEIPT.json')
    refs=read(REPORT/'REFERENCE_PROFILE_RECEIPT.json');native=read(REPORT/'PROBE_JOB_MANIFEST_V2.json')
    assert base['status']=='COMPLETE' and base['complete']==480
    assert probes['status']=='COMPLETE' and probes['complete']==720
    assert refs['status']=='COMPLETE' and refs['outputs']==3840 and refs['six_reference_outputs']==2880
    assert read(REPORT/'baseline_results/AGGREGATION_RECEIPT.json')['status']=='COMPLETE_480_BASELINE'
    assert read(REPORT/'probe_results/PROBE_REPORT_RECEIPT.json')['status']=='COMPLETE'
    runtime=read(REPORT/'RUNTIME_EXPERIMENT.json')
    assert runtime['status']=='COMPLETE' and all(r['no_drops'] and r['owned_process_closed'] for r in runtime['rows'])
    assert read(REPORT/'COMPONENT_API_TESTS_V2.json')['status']=='PASS'
    required_tests={
        'TRANSCRIPT_COVERAGE_RECEIPT.json':'PASS','CAUSALITY_DELIVERY_RECEIPT.json':'COMPLETE',
        'NATIVE_CACHE_MUTATION_RECEIPT.json':'PASS','PROBE_RESUME_GUARD_TESTS.json':'PASS',
        'CUE_TEST_RECEIPT.json':'PASS','CUE_FIXTURE_TEST_RECEIPT.json':'PASS',
        'CUE_FEATURE_B0_PARITY.json':'PASS','CUE_REFERENCE_COVERAGE_PARITY.json':'PASS',
        'CUE_PHYSICAL_INTEGRITY.json':'PASS','CUE_COMPLETION_CHECK.json':'PASS',
        'design/PLANNED_NATIVE_SCHEMA_VALIDATION.json':'PASS',
        'design/DESIGN_BUILD_RECEIPT.json':'PASS_STRUCTURAL_VALIDATION',
        'COMPONENT_PLUMBING_RECEIPT.json':'PASS','probe_results/ANALYSIS_FIXTURE_RECEIPT.json':'PASS'}
    for name,status in required_tests.items():assert read(REPORT/name)['status']==status,name
    assert read(REPORT/'CAUSALITY_DELIVERY_RECEIPT.json')['engineering_prefix_check_pass'] is True
    assert read(REPORT/'CAUSALITY_DELIVERY_RECEIPT.json')['owned_workers_closed'] is True
    coverage=read(REPORT/'TRANSCRIPT_COVERAGE_RECEIPT.json')
    assert coverage['scheduled_instances']==777 and coverage['all_scene_count']==240 and not coverage['unknown_ambient_filled']
    features=read(REPORT/'CUE_FEATURE_B0_PARITY.json')
    assert features['outputs']==480 and features['windows']==15649 and features['mismatches']==0
    test_coverage=read(REPORT/'S6A_REQUIRED_VALIDATION_AUDIT.json')
    assert not test_coverage['missing_required_fixture_tests']
    assert test_coverage['snapshot_native_complete']==720,'Refresh the final requirement snapshot after native completion'
    for requirement in test_coverage['requirements']:
        assert requirement['status']=='COMPLETE',requirement['id']
        for evidence in requirement['evidence']:bind(evidence['path'],evidence['sha256'])
    for name,key in [('baseline_results/AGGREGATION_RECEIPT.json','outputs'),
                     ('probe_results/PROBE_REPORT_RECEIPT.json','tables'),('REFERENCE_PROFILE_RECEIPT.json','tables'),
                     ('CUE_HANDOFF_INDEX.json','files'),('design/DESIGN_BUILD_RECEIPT.json','outputs')]:
        for item in read(REPORT/name)[key]:bind(item['path'],item['sha256'])
    cue_closed=read(REPORT/'CUE_COMPLETION_CHECK.json')['compact_index']
    bind(cue_closed['path'],cue_closed['sha256'])
    for b in native['execution_code']:bind(b['path'],b['sha256'])
    from s6a_probe_resume import verify_manifest
    final_dependencies=verify_manifest(REPORT/'PROBE_JOB_MANIFEST_V2.json')
    contract=read(REPORT/'execution_contract.json')
    for b in contract['snapshot']:bind(b['snapshot'],b['sha256'])
    for b in contract.get('code',[]):
        if isinstance(b,dict) and 'path' in b:bind(b['path'],b['sha256'])
    historical=0
    for row in base['rows']:
        b=row['result'];bind(b['path'],b['sha256'])
        historical+=read(b['path']).get('prior_s5_parity')=='EXACT_S5_NUMERIC_AND_POPULATION_PARITY'
        original,final_binding,chain=native_receipt(REPORT/'h2'/row['case_id']/row['stream']/'run_receipt.json')
        for key in ('events_binding','session_summary_binding','metrics_binding'):
            if key in original:bind(original[key]['path'],original[key]['sha256'])
    assert historical==360
    for row in probes['rows']:
        b=row['result'];bind(b['path'],b['sha256'])
    process_ids=set();native_counts=collections.Counter();native_bindings=[];attempts=0
    baseline_coordinator=read(REPORT/'baseline_coordinator.json');baseline_cleanup=read(REPORT/'BASELINE_CLEANUP.json')
    assert baseline_cleanup['child_registry']['pid'] is None
    assert baseline_cleanup['coordinator_pid']==baseline_coordinator['pid'] and baseline_cleanup['creation_time']==baseline_coordinator['creation_time']
    process_ids.add((baseline_coordinator['pid'],baseline_coordinator['creation_time']))
    coordinator=read(REPORT/'PROBE_COORDINATOR.json');cleanup=read(REPORT/'PROBE_CLEANUP.json')
    assert cleanup['worker_pool_joined'] is True
    assert cleanup['coordinator_pid']==coordinator['pid'] and cleanup['creation_time']==coordinator['creation_time']
    process_ids.add((coordinator['pid'],coordinator['creation_time']))
    guard=read(REPORT/'PROBE_RESUME_GUARD_LATEST.json')
    assert guard['mode']=='RUN','Final guarded invocation must have returned before packaging'
    bind(guard['guard_launch']['path'],guard['guard_launch']['sha256'])
    bind(guard['guard_source']['path'],guard['guard_source']['sha256'])
    launch=read(guard['guard_launch']['path'])
    assert launch['pid']==coordinator['pid'] and launch['creation_time']==coordinator['creation_time']
    assert launch['verification']['status']=='PASS' and launch['verification']['jobs']==720
    process_ids.add((launch['pid'],launch['creation_time']))
    for job in native['jobs']:
        path=Path(job['report_dir'])/'run_receipt.json';receipt=read(path)
        assert receipt['status']=='COMPLETE' and receipt['job_key']==job['job_key'] and receipt['identity']==job['identity']
        for name in ('events_binding','session_summary_binding','metrics_binding','resources_binding'):
            b=receipt[name];bind(b['path'],b['sha256'])
        summary=read(receipt['session_summary_binding']['path'])
        for name in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):
            assert name in summary['telemetry'] and summary['telemetry'][name]==0
        assert not receipt['owned_child_alive']
        process_ids.add((receipt['owned_process_pid'],receipt['owned_process_creation_time']))
        for sample in read(receipt['resources_binding']['path'])['rows']:
            for p in sample['processes']:process_ids.add((p['pid'],p['creation_time']))
        native_counts[(job['profile_id'],job['stream'])]+=1;native_bindings.append(bind(path))
        attempts+=len(list(Path(job['report_dir']).glob('attempt_*/attempt_receipt.json')))
    assert len(native_counts)==20 and set(native_counts.values())=={36}
    for folder in (REPORT/'h2',REPORT/'probes',REPORT/'probes_v2'):
        for path in folder.rglob('attempt_receipt.json'):
            r=read(path)
            if r.get('owned_process_pid') and r.get('owned_process_creation_time'):
                process_ids.add((r['owned_process_pid'],r['owned_process_creation_time']))
    live=owned_alive(process_ids);assert not live,live
    result={'status':'PASS','utc':now(),'baseline_outputs':480,'historical_exact_score_parity':historical,
            'probe_outputs':720,'probe_attempts':attempts,'six_reference_outputs':2880,'diagnostic_control_outputs':960,
            'required_validation_receipts':[bind(REPORT/name) for name in required_tests],
            'probe_per_profile_and_output':{a+'/'+b:n for (a,b),n in sorted(native_counts.items())},
            'owned_native_process_identities_checked':len(process_ids),'owned_native_processes_still_alive':live,
            'native_final_dependency_verification':final_dependencies,
            'fresh_native_probe_receipts':native_bindings,'resources':resources(scan=True),
            'audit_scope':'Rehash final scored files, live code, native events/summary/resources and final drop counters; prior audio-journal verification remains bound in native completion receipts. No new inference/hardware.',
            'code':bind(__file__)}
    save(REPORT/'FINAL_COMPLETION_AUDIT.json',result);return result

def code_diff():
    before=SNAPSHOT/'edge_speech_pipeline';after=H2/'app/edge_speech_pipeline';lines=[]
    for name in sorted({p.name for p in before.glob('*.py')}|{p.name for p in after.glob('*.py')}):
        a=(before/name).read_text(encoding='utf-8').splitlines(True) if (before/name).exists() else []
        b=(after/name).read_text(encoding='utf-8').splitlines(True) if (after/name).exists() else []
        lines.extend(difflib.unified_diff(a,b,fromfile='B0/app/edge_speech_pipeline/'+name,tofile='S6A/app/edge_speech_pipeline/'+name))
    path=REPORT/'S6_APP_CHANGE_FROM_B0.diff';path.write_text(''.join(lines),encoding='utf-8')
    return path

def collect():
    files={}
    for p in REPORT.iterdir():
        if p.is_file() and p.suffix in ALLOWED and p.name not in SKIP_ROOT and not p.name.endswith('_status.json'):
            files[Path(p.name)]=p
    for folder in ('baseline_results','design','probe_results','profiles','figures'):
        for p in (REPORT/folder).rglob('*'):
            if p.is_file() and p.suffix in ALLOWED:files[p.relative_to(REPORT)]=p
    for p in (REPORT/'resume_guards').glob('*/LAUNCH.json'):files[p.relative_to(REPORT)]=p
    for p in (SIM/'scripts').glob('s6a*.py'):files[Path('code/scripts')/p.name]=p
    for p in (SIM/'scripts').glob('test_s6a*.py'):files[Path('code/scripts')/p.name]=p
    for p in (SIM/'scripts').glob('README_S6A*.md'):files[Path('code/scripts')/p.name]=p
    for p in (H2/'app/edge_speech_pipeline').glob('*.py'):files[Path('code/application')/p.name]=p
    for p in (H2/'app/edge_speech_pipeline').glob('README*.md'):files[Path('code/application')/p.name]=p
    legacy_test=H2/'tests/edge_speech_pipeline/test_edge_runtime.py'
    files[Path('code/existing_tests')/legacy_test.name]=legacy_test
    for p in (SNAPSHOT/'edge_speech_pipeline').glob('*.py'):files[Path('code/B0_application')/p.name]=p
    for p in (SNAPSHOT/'edge_speech_pipeline').glob('README*.md'):files[Path('code/B0_application')/p.name]=p
    assert sum(p.suffix=='.png' for p in files)<=6,'Maximum six scientific figures'
    return files

def build():
    for name in REQUIRED_TEXT:
        assert (REPORT/name).exists(),name
        assert not re.search(r'\{\{[A-Z0-9_]+\}\}',(REPORT/name).read_text(encoding='utf-8')),name+' contains unfinished report placeholders'
    audit=completion_audit();code_diff();files=collect()
    # Keep exact native/cache locations outside the portable analysis bundle.
    local=[]
    for p in [REPORT/'JOB_MANIFEST.json',REPORT/'PROBE_JOB_MANIFEST_V2.json',REPORT/'execution_contract.json',
              REPORT/'cues/FEATURE_INDEX.json',REPORT/'cues/REFERENCE_INDEX.json',REPORT/'support/FROZEN_SUPPORT_INDEX.json',
              STAGING/'probe_revision_v1/ARCHIVE_RECEIPT.json',STAGING/'probe_analysis_v3/ARCHIVE_RECEIPT.json']:
        local.append(bind(p))
    index={'status':'COMPLETE','run_id':RUN_ID,'report_root':str(REPORT),'payload_root':str(PAYLOAD),'staging_root':str(STAGING),
           'local_only_manifests':local,'audio_and_vectors_included':False,'included_sources':[{'member':str(k).replace('\\','/'),'source':bind(v)} for k,v in sorted(files.items())]}
    save(REPORT/'LOCAL_ARTIFACT_INDEX.json',index);files[Path('LOCAL_ARTIFACT_INDEX.json')]=REPORT/'LOCAL_ARTIFACT_INDEX.json'
    output=SIM/'handoffs'/('S6A_JOINT_CHATGPT_HANDOFF_'+RUN_ID+'.zip');output.parent.mkdir(exist_ok=True)
    if output.exists():raise FileExistsError('Preserve prior package; explicitly version a corrected package')
    temporary=output.with_suffix('.zip.building')
    if temporary.exists():raise FileExistsError('Preserve previous interrupted build; explicitly inspect/version it')
    members=[]
    with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for member,path in sorted(files.items()):
            assert path.suffix in ALLOWED
            raw=path.read_bytes();name=member.as_posix();archive.writestr(name,raw)
            members.append({'member':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        archive.writestr('HANDOFF_MANIFEST.json',json.dumps({'run_id':RUN_ID,'members':members},indent=2)+'\n')
    assert temporary.stat().st_size<=20*2**20,'Maximum handoff size20MiB'
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None
        for item in members:assert hashlib.sha256(archive.read(item['member'])).hexdigest()==item['sha256']
        assert not any(Path(n).suffix.lower() in ('.wav','.pcm16','.onnx','.npz','.npy','.docx','.jsonl') for n in archive.namelist())
    assert temporary.resolve().parent==output.resolve().parent==(SIM/'handoffs').resolve()
    temporary.rename(output)
    result={'status':'COMPLETE','utc':now(),'archive':bind(output),'members':len(members)+1,'size_mib':output.stat().st_size/2**20,
            'under_target_10_mib':output.stat().st_size<=10*2**20,'maximum_20_mib_pass':True,
            'crc_and_member_sha_verification':'PASS','raw_audio_vectors_models_Word_full_event_logs_included':False,
            'final_completion_audit':bind(REPORT/'FINAL_COMPLETION_AUDIT.json'),'code':bind(__file__)}
    save(REPORT/'PACKAGING_RECEIPT.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':build()
