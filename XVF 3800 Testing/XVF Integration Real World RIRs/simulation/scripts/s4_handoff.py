"""Validate S4 completion evidence and package the authored compact handoff. README_S4_PIPELINE.md."""
import argparse, csv, datetime, io, subprocess, zipfile
from s4_common import *
from s4_h2_run import baseline_contract, verified_restoration, stable_hash, alignment_for
from s4_h2_analysis import normalize as normalize_text
from s4_capture_selection import accepted_cases

RUN_STARTED_UTC='2026-09-09T00:21:40+00:00'
REPORT_FILES=['START_HERE.md','S4_REPORT.md','NEXT_PHASE_INPUTS.md','WORKBOOK_UPDATE.md',
    'SOURCE_AND_SPLIT_MANIFEST.json','SCENE_MANIFEST.json','scene_validation.json','S3_ISSUE_CLOSURE.json',
    'SOURCE_LEVEL_POLICY.json','OUTPUT_LEVEL_POLICY.json','INITIALIZATION_POLICY.json','ANGLE_LABEL_POLICY.json',
    'TIMING_TELEMETRY_POLICY.json','SPATIAL_SCORING_POLICY.json','CALIBRATION_PLAN.json','CALIBRATION_DECISION.json',
    'summary_metrics.json','per_case_metrics.csv','preflight.json','resource_observation.json','transport_regressions.json',
    'ACCEPTED_FINAL_CAPTURES.json','TELEMETRY_RETRY_DIAGNOSIS.json','TELEMETRY_RETRY_RESOLUTION.json',
    'H2_SUMMARY_RECOVERY.json','output_alignment.json']
COMPACT_EVIDENCE_REPORT_FILES=['ANALYSIS_TEST_RECEIPT.json','ANALYSIS_TEST_RECEIPT.original_25.json',
    'test_evidence/s4_summary.tested_25.py','SPATIAL_FINDINGS.md','plots/FIGURE_INDEX.json',
    'INDEPENDENT_AGGREGATE_AUDIT.json','PLOT_VISUAL_QA.json']

def bound_json(reference, expected_path=None):
    if expected_path is not None:
        assert Path(reference['path']).resolve()==Path(expected_path).resolve(),'Evidence binding points to another artifact'
    bind(reference['path'],reference['sha256'])
    return read(reference['path'])

def assert_audio_integrity(case):
    assert case['payload']['status']=='PASS' and case['audio_integrity_status']=='PASS'
    payload=case['payload'];assert payload['payload_mismatches']==0
    if case['case_id']=='S4_22':
        # A fully zero source has no unique anchor. Preserve that limitation;
        # verify every decoded microphone sample is zero without inventing lag.
        assert payload['alignment_status']=='UNIDENTIFIABLE_ALL_ZERO_INPUT'
        assert payload['capture_minus_source_offset_samples'] is None
        assert payload['all_nonzero_source_payload_captured'] is None
        assert payload['compared_mic_samples']==4*case['framing']['decoded_frames']
    else:
        assert payload['all_nonzero_source_payload_captured'] is True
    assert case['framing']['marker_error_count']==0
    assert not case['callback_errors'] and not case['callback_flags']

def assert_no_critical_issue(closure):
    dispositions=[]
    def visit(value):
        if isinstance(value,dict):
            if 'disposition' in value:dispositions.append(value['disposition'])
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(closure)
    allowed={'FIXED_WITH_EVIDENCE','IMPLEMENTED_WITH_MEASURED_LIMITATION','UNAVAILABLE_OPTIONAL'}
    assert dispositions and all(d in allowed for d in dispositions),'Missing, unknown or critical blocked issue disposition'

def validate_retry_resolution(selection, all_cases, chosen):
    excluded=selection.get('excluded_attempts',[])
    assert len(excluded)==1 and (excluded[0]['batch'],excluded[0]['case_id'])==('final','S4_19'),'Only the diagnosed final/S4_19 telemetry failure may be excluded'
    item=excluded[0];assert item.get('reason')
    failed=all_cases[('final','S4_19')]
    assert failed['status']=='FAIL' and failed['telemetry_status']=='FAIL'
    assert_audio_integrity(failed)
    replacement=chosen['S4_19']
    assert replacement['batch']=='final_completion'
    resolution=bound_json(item['resolution_receipt'],REPORT/'TELEMETRY_RETRY_RESOLUTION.json')
    assert resolution['status']=='RESOLVED_TELEMETRY_ONLY_RECAPTURE'
    assert bound_json(resolution['failed_case_result'],REPORT/'hardware/final/S4_19/case_result.json')==failed
    assert bound_json(resolution['replacement_case_result'],replacement['folder']/'case_result.json')==replacement['case_result']
    bound_json(resolution['diagnosis'],REPORT/'TELEMETRY_RETRY_DIAGNOSIS.json')
    if 'case_result' in item:assert bound_json(item['case_result'],REPORT/'hardware/final/S4_19/case_result.json')==failed
    for key in ['transport_integrity_preserved','hardware_restore_verified','no_historical_evidence_overwritten']:
        assert resolution.get(key) is True,'Telemetry retry resolution did not establish '+key
    for key in ['input_scene_sha256','code_key','recipe','final_recipe_capture']:
        assert failed[key]==replacement['case_result'][key],'Retry changed '+key
    return [{'batch':'final','case_id':'S4_19','reason':item['reason'],
             'resolution':bind(REPORT/'TELEMETRY_RETRY_RESOLUTION.json'),'replacement_batch':replacement['batch']}]

def validate_analyses(case, spatial_policy):
    folder=REPORT/'hardware'/case['batch']/case['case_id']
    audio=read(folder/'audio_metrics.json');spatial=read(folder/'spatial_metrics.json')
    for analysis in [audio,spatial]:
        assert analysis['case_id']==case['case_id'] and analysis['batch']==case['batch']
    assert audio['input_scene_sha256']==case['input_scene_sha256'] and audio['input_payload']==case['payload']
    assert audio['recipe']==case['recipe']
    converter=audio['converter'];assert converter['conversion_status']=='EXACT_NATIVE_COUNTS'
    assert Path(converter['case_dir']).resolve()==folder.resolve()
    for stream in ['O0','O1']:
        assert converter['outputs'][stream]['mismatched_saved_vs_native_counts']==0
        assert audio['streams'][stream]['sample_count']==case['framing']['decoded_frames']
    b=converter['native_file'];assert Path(b['path']).resolve()==(folder/'native_packed.wav').resolve();bind(b['path'],b['sha256'])
    code=audio['analysis_code'];assert Path(code['path']).resolve()==(SIM/'scripts/s4_audio_analysis.py').resolve();bind(code['path'],code['sha256'])
    assert spatial['hardware_status']=='PASS' and spatial['telemetry_status']=='PASS'
    assert spatial['scoring_policy']==spatial_policy
    assert spatial['callback_availability']['capture_minus_source_offset_samples']==case['payload']['capture_minus_source_offset_samples']
    required={(folder/'case_result.json').resolve(),(folder/'capture_metadata.json').resolve()}
    bound_paths=set()
    for b in spatial['bindings']:
        p=Path(b['path']).resolve();assert p.is_relative_to(folder.resolve())
        bind(p,b['sha256']);bound_paths.add(p)
    assert required<=bound_paths,'Spatial metrics lost capture/callback provenance'
    return [folder/'case_result.json',folder/'audio_metrics.json',folder/'spatial_metrics.json']

def validate_summary(summary, chosen, required_paths, policy, source):
    assert summary['schema']=='jp_s4_summary_v1' and summary['run_id']==RUN_ID
    assert summary['status']=='COMPLETE_EVIDENCE_COUNTS' and not summary['omissions']
    expected={'planned_scenes':24,'rendered_scenes':24,'valid_final_captures':24,'audio_analyzed_final_scenes':24,
        'spatial_analyzed_final_scenes':24,'planned_ordinary_H2_jobs':48,'complete_valid_H2_jobs':48,'complete_H2_pairs':24,
        'fully_analyzed_final_scenes':24,'planned_nominal_repeat_attempts':2,'valid_nominal_repeats':2,'analyzed_nominal_repeats':2}
    for key,want in expected.items():assert summary['counts'][key]==want,'Incomplete aggregate count: '+key
    assert summary['accepted_capture_batches']=={cid:row['batch'] for cid,row in chosen.items()}
    assert summary['output_level_policy']==policy and summary['source_cohort']==source['actual_S4_contribution']
    assert summary['no_output_accuracy_winner'] is True and summary['S6_fusion_benefit_established'] is False
    consumed={}
    for b in summary['consumed_json_bindings']:
        p=Path(b['path']).resolve();assert p not in consumed,'Duplicate consumed JSON binding'
        bind(p,b['sha256']);consumed[p]=b['sha256']
    assert {Path(p).resolve() for p in required_paths}<=set(consumed),'Aggregate omitted required capture/analysis provenance'
    b=summary['analysis_code'];assert Path(b['path']).resolve()==(SIM/'scripts/s4_summary.py').resolve();bind(b['path'],b['sha256'])

def assert_h2_completion(job):
    assert job['status']=='COMPLETE' and job['exit_code']==0,'H2 invocation did not complete after exit zero'
    assert 'error' not in job and 'ended_utc' not in job,'Unresolved or stale top-level H2 failure remains'

def h2_recovery_paths():
    return [REPORT/'H2_SUMMARY_RECOVERY.json']+sorted(REPORT.glob('H2_SUMMARY_RECOVERY_S4_*_O*.json'))

def validate_h2_summary_recovery(job):
    """Check one bound derived export against its preserved primary evidence."""
    import numpy as np
    from s4_h2_analysis import journal_audio
    from s4_recover_h2_summary import json_sequence, validate_primary
    assert_h2_completion(job)
    case_id,stream=job['case_id'],job['stream']
    assert case_id in {f'S4_{i:02}' for i in range(1,25)} and stream in ['O0','O1']
    folder=REPORT/'h2'/case_id/stream
    receipt_path=REPORT/('H2_SUMMARY_RECOVERY.json' if (case_id,stream)==('S4_18','O1') else f'H2_SUMMARY_RECOVERY_{case_id}_{stream}.json')
    recovery=bound_json(job['summary_recovery_receipt'],receipt_path)
    assert recovery['schema']=='jp_s4_h2_summary_recovery_v1' and recovery['status']=='RECOVERED_FROM_COMPLETION_EVIDENCE'
    assert (recovery['case_id'],recovery['stream'])==(case_id,stream)
    assert recovery['no_model_rerun'] is True and recovery['frozen_execution_code_unchanged'] is True
    assert recovery['hardware_accessed'] is False
    session=Path(recovery['session_dir']).resolve()
    assert session==Path(job['session_dir']).resolve()
    assert list((folder/'empty_data/edge_speech_sessions').iterdir())==[session],'Unexpected replacement H2 session'
    sources=recovery['source_bindings']
    expected={'original_empty_summary':folder/'recovery_evidence/session_summary.original_empty.json',
        'original_failed_run_receipt':folder/'recovery_evidence/run_receipt.original_failed.json',
        'events':session/'events.jsonl','stdout':folder/'stdout.jsonl','labelled_transcript':session/'labelled_transcript.jsonl',
        'audio_spool':session/'audio_spool.pcm16','adapter':folder/f'input_{stream}_fixed_gain.wav',
        'execution_contract':REPORT/'h2/execution_contract.json',
        'original_runtime':H2/'app/edge_speech_pipeline/runtime.py','original_cli':H2/'app/edge_speech_pipeline/cli.py',
        'original_models':H2/'app/edge_speech_pipeline/models.py','original_asset_validator':H2/'app/edge_speech_pipeline/assets.py'}
    if Path(recovery['recovery_code']['path']).name=='s4_recover_h2_summary_v2.py':
        chosen=accepted_cases()[case_id]
        expected.update(accepted_capture_selection=REPORT/'ACCEPTED_FINAL_CAPTURES.json',
            accepted_case_result=chosen['folder']/'case_result.json',output_level_policy=REPORT/'OUTPUT_LEVEL_POLICY.json')
        assert job['raw_audio']['sha256']==chosen['case_result']['output_audio'][stream]['sha256']
        assert Path(job['raw_audio']['path']).resolve()==Path(chosen['case_result']['output_audio'][stream]['path']).resolve()
    assert set(sources)==set(expected)
    for key,path in expected.items():
        b=sources[key];assert Path(b['path']).resolve()==path.resolve()
        actual=bind(path,b['sha256']);assert actual['bytes']==b['bytes']
    empty=expected['original_empty_summary'].read_bytes();assert empty==b''
    failed=bound_json(job['original_failure_receipt'],expected['original_failed_run_receipt'])
    assert job['original_failure_receipt']['sha256']==sources['original_failed_run_receipt']['sha256']
    for key in ['job_key','identity','created_utc','raw_audio','adapter','argv','cwd','isolated_data_root',
                'initial_profile_files','labels_or_transcripts_sent_to_model','external_asset_hash_passes',
                'owned_process_pid','exit_code','model_wall_s']:
        assert job[key]==failed[key],'Recovery replaced original invocation identity: '+key
    assert job['original_failure_provenance']=={key:failed[key] for key in ['status','error','ended_utc']}
    assert job['session_summary_binding']['sha256']==recovery['derived_summary']['sha256']
    derived=bound_json(job['session_summary_binding'],session/'session_summary.json')
    assert bound_json(recovery['derived_summary'],session/'session_summary.json')==derived
    provenance=derived['reconstruction_provenance']
    assert provenance['status']=='DERIVED_FROM_PRIMARY_COMPLETION_EVIDENCE'
    assert provenance['original_runtime_summary_was_written'] is False and provenance['original_summary_bytes']==0
    assert provenance['model_rerun'] is False and provenance['original_summary_elapsed_wall_sec'] is None
    assert provenance['source_bindings']==sources and provenance['asset_evidence_scope']==recovery['asset_evidence_scope']
    assert provenance['reconstructed_utc']==recovery['created_utc']==job['summary_recovered_utc']
    events=json_sequence(expected['events'].read_text(encoding='utf-8-sig'))
    stdout=json_sequence(expected['stdout'].read_text(encoding='utf-8-sig'))
    labelled=json_sequence(expected['labelled_transcript'].read_text(encoding='utf-8-sig'))
    spool=np.fromfile(expected['audio_spool'],dtype='<i2')
    adapter_pcm16=(journal_audio(expected['adapter'])*32768).astype('<i2')
    completion,validation=validate_primary(failed,empty,events,stdout,spool,adapter_pcm16,labelled,session)
    validation.update(source_config_baseline_unchanged=True,frozen_execution_code_unchanged=True)
    assert recovery['validation']==validation
    assert completion['wall_time_utc']==recovery['original_completion_event_utc']==job['model_completed_utc']
    assert derived['state']=='COMPLETED' and derived['telemetry']==completion['payload']['telemetry']
    contract=read(expected['execution_contract']);baseline_sources={Path(b['path']).resolve():b['sha256'] for b in contract['baseline']['source_identities']}
    for key in ['original_runtime','original_cli','original_models','original_asset_validator']:
        assert sources[key]['sha256']==baseline_sources[expected[key].resolve()]
    for b in contract['runner_code']:bind(b['path'],b['sha256'])
    assert job['identity']['contract_sha256']==stable_hash(contract) and job['job_key']==stable_hash(job['identity'])
    config=contract['baseline']['scientific_config']
    assert derived['assets']==[{'component_id':a['component_id'],'sha256':a['sha256']} for a in config['assets']]
    assert derived['scientific_policy']=={k:config[k] for k in ['identity_score_threshold','identity_margin_threshold','identity_minimum_evidence_sec','clustering_threshold']}
    metrics=bound_json(job['metrics_binding'],folder/'metrics.json')
    assert (metrics['case_id'],metrics['stream'])==(case_id,stream) and Path(metrics['session_dir']).resolve()==session
    assert metrics['state']=='COMPLETED' and not metrics['failure_events']
    assert metrics['telemetry']==derived['telemetry'] and metrics['scientific_policy']==derived['scientific_policy']
    b=recovery['recovery_code'];assert Path(b['path']).resolve() in {(SIM/'scripts'/name).resolve() for name in ['s4_recover_h2_summary.py','s4_recover_h2_summary_v2.py']};bind(b['path'],b['sha256'])
    return {'case_id':case_id,'stream':stream,'status':recovery['status'],'recovery_receipt':bind(receipt_path),
        'derived_summary':recovery['derived_summary'],'original_failure_receipt':sources['original_failed_run_receipt'],
        'original_empty_summary':sources['original_empty_summary'],'original_model_process_pid':job['owned_process_pid'],
        'no_model_rerun':True,'native_runtime_summary':False,'primary_completion_revalidated':True}

def validate_h2_summary_recoveries(jobs):
    recovered=[j for j in jobs if 'summary_recovery_receipt' in j or 'original_failure_receipt' in j]
    assert recovered and len({(j['case_id'],j['stream']) for j in recovered})==len(recovered)
    referenced={Path(j['summary_recovery_receipt']['path']).resolve() for j in recovered}
    assert referenced=={p.resolve() for p in h2_recovery_paths()},'Unbound or missing H2 recovery receipt'
    return [validate_h2_summary_recovery(j) for j in recovered]

def verify_embedded_bindings(value):
    """Verify explicitly bound compact evidence; never discover unrelated files."""
    found={}
    def visit(item):
        if isinstance(item,dict):
            if {'path','sha256'}<=set(item):
                p=Path(item['path']).resolve();actual=bind(p,item['sha256'])
                if 'bytes' in item:assert actual['bytes']==item['bytes']
                assert p not in found or found[p]==item['sha256'],'Conflicting evidence binding'
                found[p]=item['sha256']
            for child in item.values():visit(child)
        elif isinstance(item,list):
            for child in item:visit(child)
    visit(value);return found

def validate_supporting_evidence(summary,recoveries):
    audit_path=REPORT/'INDEPENDENT_AGGREGATE_AUDIT.json';audit=read(audit_path)
    assert audit['schema']=='jp_s4_independent_aggregate_audit_v1' and audit['status']=='PASS'
    assert audit['checks'] and all(value is True for value in audit['checks'].values())
    required={p.resolve() for p in [REPORT/'summary_metrics.json',REPORT/'per_case_metrics.csv',REPORT/'plots/FIGURE_INDEX.json']}
    assert set(verify_embedded_bindings(audit['input_bindings']))==required,'Independent audit inputs differ from final aggregate/figures'
    assert audit['counts']['accepted_final_cases']==24 and audit['counts']['ordinary_jobs_audited']==48 and audit['counts']['nominal_repeats']==2
    assert audit['counts']['derived_summaries']==len(recoveries) and audit['counts']['native_summaries']==48-len(recoveries)
    assert set(audit['derived_summary_jobs'])=={r['case_id']+'/'+r['stream'] for r in recoveries}
    for output in ['O0','O1']:
        for observed,metric in [('observed_word_counts','word_counts'),('observed_character_counts','character_counts')]:
            assert audit[observed][output]==summary['paired_weighted_text'][output][metric]
    export=summary['summary_export_evidence']
    assert export['derived_completion_evidence_summary_count']==len(recoveries) and export['native_runtime_summary_count']==48-len(recoveries)
    rows={(r['case_id'],r['stream']):r for r in export['derived_summaries']}
    assert len(rows)==len(export['derived_summaries'])==len(recoveries)
    for recovery in recoveries:
        row=rows[(recovery['case_id'],recovery['stream'])];assert row['model_rerun'] is False
        for key in ['recovery_receipt','derived_summary','original_empty_summary']:
            assert Path(row[key]['path']).resolve()==Path(recovery[key]['path']).resolve() and row[key]['sha256']==recovery[key]['sha256']
    qa_path=REPORT/'PLOT_VISUAL_QA.json';qa=read(qa_path);assert qa['status']=='PASS'
    assert (REPORT/'plots/FIGURE_INDEX.json').resolve() in verify_embedded_bindings(qa),'Visual review does not bind final figure index'
    tests_path=REPORT/'ANALYSIS_TEST_RECEIPT.json';tests=read(tests_path)
    assert tests['status']=='PASS' and tests['tests_total']==sum(suite['tests_run'] for suite in tests['test_suites'])
    assert all(suite['status']=='PASS' and suite['observed_process_exit_code']==0 for suite in tests['test_suites'])
    assert tests['hardware_opened'] is False and tests['model_jobs_started']==0
    verify_embedded_bindings(tests['code_bindings'])
    original=bound_json(tests['original_25_test_receipt'],REPORT/'ANALYSIS_TEST_RECEIPT.original_25.json')
    assert original['status']=='PASS' and original['tests_total']==25
    return {'independent_aggregate_audit':bind(audit_path),'plot_visual_qa':bind(qa_path),
        'analysis_test_receipt':bind(tests_path),'audit_bound_inputs_verified':True}

def validate():
    manifest=read(BANK/'SCENE_MANIFEST.json');source=read(BANK/'SOURCE_AND_SPLIT_MANIFEST.json');policy=read(REPORT/'OUTPUT_LEVEL_POLICY.json')
    assert len(manifest['scenes'])==24 and manifest['validation']['status']=='PASS'
    assert source['release']=='cv-corpus-26.0-2026-06-12' and source['locale']=='en'
    source_rows={s['source_id']:s for s in source['sources']}
    used=set();contributors=set();instances=0;scheduled_seconds=0.
    for scene in manifest['scenes']:
        for segment in scene['segments']:
            if segment['kind']!='utterance':continue
            s=source_rows[segment['source_id']]
            assert s['dataset']=='Common Voice' and s['split']=='development' and s['usage']=='probe'
            assert s['identity']==segment['speaker_key']==scene['cast'][segment['participant_id']]
            assert s['transcript']==segment['transcript'] and hashlib.sha256(s['transcript'].encode()).hexdigest()==s['transcript_sha256']
            assert segment['source_stop_sample']-segment['source_start_sample']==s['samples']
            used.add(s['source_id']);contributors.add(s['identity']);instances+=1;scheduled_seconds+=s['duration_sec']
    actual=source['actual_S4_contribution']
    assert len(used)==actual['unique_probe_utterances_used']==23 and len(contributors)==actual['development_contributors']==6
    assert instances==actual['total_scheduled_utterance_instances']==64
    assert abs(scheduled_seconds-actual['total_scheduled_dry_speech_s'])<1e-6
    assert actual['common_voice_fraction_of_used_utterances']==1 and not actual['other_datasets_used']
    for source_id in used:
        for field in ['source_binding','decoded_16k_binding']:
            b=source_rows[source_id][field];bind(b['path'],b['sha256'])
    for field in ['license_binding','materialization_binding','split_freeze_binding']:
        b=source[field];bind(b['path'],b['sha256'])
    bind(SIM/'rir_library/v1/RIR_MANIFEST.json','468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546')
    for r in manifest['selected_rirs']:bind(r['file']['path'],r['file']['sha256'])
    for scene in manifest['scenes']:bind(scene['canonical_audio']['path'],scene['canonical_audio']['sha256'])
    for b in policy['calibration_bindings']:bind(b['path'],b['sha256'])
    for name in ['SCENE_MANIFEST.json','SOURCE_AND_SPLIT_MANIFEST.json','SOURCE_LEVEL_POLICY.json','ANGLE_LABEL_POLICY.json']:
        assert (REPORT/name).read_bytes()==(BANK/name).read_bytes(),'Report/bank contract differs: '+name
    chosen=accepted_cases();assert len(chosen)==24
    selection=read(REPORT/'ACCEPTED_FINAL_CAPTURES.json')
    ledger=read(REPORT/'physical_ledger.json');passes=ledger['passes']
    assert len(passes)<=40 and sum(p['charged_playback_s'] for p in passes)<=2700
    ledger_keys=[(p['batch'],p['case_id']) for p in passes]
    assert len(ledger_keys)==len(set(ledger_keys)),'Duplicate physical ledger identity'
    cases=[];restorations=[];all_cases={}
    folders=[p for p in (REPORT/'hardware').iterdir() if p.is_dir()]
    for folder in sorted(folders):
        physical_paths=list(folder.glob('*/case_result.json'))
        if physical_paths or folder.name in {p['batch'] for p in passes}:
            assert (folder/'restoration.json').is_file(),'Missing restoration receipt for '+folder.name
            restorations.append(verified_restoration(folder/'restoration.json'))
        for path in sorted(folder.glob('*/case_result.json')):
            r=read(path);assert r['batch']==folder.name and r['case_id']==path.parent.name
            assert_audio_integrity(r)
            key=(r['batch'],r['case_id']);assert key not in all_cases
            all_cases[key]=r;cases.append(r)
    assert set(all_cases)==set(ledger_keys),'Physical receipts and charged ledger differ'
    for p in passes:
        c=all_cases[(p['batch'],p['case_id'])]
        assert p['status']==c['status'] and p['status'] in ['PASS','FAIL']
        assert 0<p['charged_playback_s']<=60 and abs(p['charged_playback_s']-c['duration_s'])<1e-6
    resolved_failures=validate_retry_resolution(selection,all_cases,chosen)
    for key,c in all_cases.items():
        if key!=('final','S4_19'):assert c['status']=='PASS' and c['telemetry_status']=='PASS'
    final=[row['case_result'] for row in chosen.values()]
    scene_by_id={s['case_id']:s for s in manifest['scenes']}
    assert {c['case_id'] for c in final}==set(scene_by_id)
    assert all(c['final_recipe_capture'] and c['recipe']==policy['hardware_recipe'] for c in final)
    repeat=[c for c in cases if c['batch'] in ['repeat1','repeat2']]
    assert len(repeat)==2 and all(c['case_id']=='S4_01' and c['final_recipe_capture'] and c['recipe']==policy['hardware_recipe'] for c in repeat)
    assert len({c['code_key'] for c in final+repeat})==1,'Final capture/repeat code identities differ'
    spatial_policy=read(REPORT/'SPATIAL_SCORING_POLICY.json')
    required_analysis_paths=[BANK/'SCENE_MANIFEST.json',BANK/'SOURCE_AND_SPLIT_MANIFEST.json',REPORT/'OUTPUT_LEVEL_POLICY.json',REPORT/'SPATIAL_SCORING_POLICY.json',REPORT/'ACCEPTED_FINAL_CAPTURES.json',REPORT/'h2/execution_contract.json']+h2_recovery_paths()
    for c in final+repeat:
        assert c['input_scene_sha256']==scene_by_id[c['case_id']]['canonical_audio']['sha256'],'Capture used another canonical scene'
        for b in c['output_audio'].values():bind(b['path'],b['sha256'])
        required_analysis_paths.extend(validate_analyses(c,spatial_policy))
    for batch,count in [('final',24),('repeat1',1),('repeat2',1)]:
        sm=read(REPORT/('spatial_analysis_'+batch+'.json'));assert sm['batch']==batch and sm['count']==count
        b=sm['scorer'];assert Path(b['path']).resolve()==(SIM/'scripts/s4_spatial_analysis.py').resolve();bind(b['path'],b['sha256'])
    baseline,_=baseline_contract();contract=read(REPORT/'h2/execution_contract.json')
    assert contract['baseline']==baseline and contract['scene_manifest_sha256']==bind(BANK/'SCENE_MANIFEST.json')['sha256']
    assert contract['output_policy_sha256']==bind(REPORT/'OUTPUT_LEVEL_POLICY.json')['sha256'] and contract['fixed_host_gain']==policy['fixed_host_gain']
    for b in contract['runner_code']:bind(b['path'],b['sha256'])
    scorer_code=next(b for b in contract['runner_code'] if Path(b['path']).name=='s4_h2_analysis.py')
    alignment=read(REPORT/'output_alignment.json');assert set(alignment)==set(scene_by_id)
    jobs=[read(p) for p in sorted((REPORT/'h2').glob('S4_*/O*/run_receipt.json'))]
    assert len(jobs)==48 and all(j['status']=='COMPLETE' for j in jobs)
    assert {(j['case_id'],j['stream']) for j in jobs}=={(s['case_id'],o) for s in manifest['scenes'] for o in ['O0','O1']}
    for j in jobs:
        assert_h2_completion(j)
        capture=chosen[j['case_id']]['case_result'];raw=capture['output_audio'][j['stream']]
        assert Path(j['raw_audio']['path']).resolve()==Path(raw['path']).resolve() and j['raw_audio']['sha256']==raw['sha256']
        assert j['identity']['raw_audio_sha256']==raw['sha256'] and j['identity']['gain_scalar']==policy['fixed_host_gain'][j['stream']]
        assert j['identity']['contract_sha256']==stable_hash(contract)
        assert j['identity']['case_id']==j['case_id'] and j['identity']['stream']==j['stream']
        assert j['job_key']==stable_hash(j['identity'])
        assert j['initial_profile_files']==0 and j['labels_or_transcripts_sent_to_model'] is False
        assert j.get('model_success_has_internal_asset_validation') is True
        b=j['adapter']['output_binding'];bind(b['path'],b['sha256'])
        assert Path(j['metrics_binding']['path']).resolve()==(REPORT/'h2'/j['case_id']/j['stream']/'metrics.json').resolve()
        for key in ['metrics_binding','session_summary_binding','events_binding']:bind(j[key]['path'],j[key]['sha256'])
        m=read(j['metrics_binding']['path']);assert m['state']=='COMPLETED' and not m['failure_events']
        session=Path(j['session_dir']).resolve();session_summary=bound_json(j['session_summary_binding'],session/'session_summary.json')
        assert Path(m['session_dir']).resolve()==session and m['telemetry']==session_summary['telemetry']
        assert m['scientific_policy']==session_summary['scientific_policy']
        assert ('reconstruction_provenance' in session_summary)==('summary_recovery_receipt' in j),'Derived summary lost recovery provenance'
        assert m['case_id']==j['case_id'] and m['stream']==j['stream']
        assert m['fixed_host_gain']==policy['fixed_host_gain'][j['stream']]==j['adapter']['gain_scalar']
        scene=scene_by_id[j['case_id']]
        speech=sorted([s for s in scene['segments'] if s['kind']=='utterance'],key=lambda s:s['source_start_sample'])
        assert m['text']['reference_normalized']==normalize_text(' '.join(s['transcript'] for s in speech))
        if scene['overlap_scoring_limited']:assert m['text']['status']=='LIMITED'
        elif not speech:assert m['text']['status']=='EMPTY_REFERENCE'
        else:assert m['text']['status']=='SCORED'
        align=alignment_for(alignment,j['case_id'],j['stream'],capture)
        assert j['analysis_identity']==stable_hash({'alignment':align,'scorer_code_sha256':scorer_code['sha256']})
        required_analysis_paths.extend([REPORT/'h2'/j['case_id']/j['stream']/'run_receipt.json',Path(j['metrics_binding']['path'])])
        assert not any(m['telemetry'].get(k,0) for k in ['audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'])
    summary_recoveries=validate_h2_summary_recoveries(jobs)
    summary=read(REPORT/'summary_metrics.json')
    validate_summary(summary,chosen,required_analysis_paths,policy,source)
    supporting_evidence=validate_supporting_evidence(summary,summary_recoveries)
    assert_no_critical_issue(read(REPORT/'S3_ISSUE_CLOSURE.json'))
    master=read(REPORT/'preflight.json')['workbook_v8']['file'];bind(master['path'],master['sha256'])
    # The authored report must carry a complete-with-limitations status because
    # the frozen calibration still contains device rails and timing is nominal.
    status='S4_COMPLETE_WITH_LIMITATIONS'
    for path in REPORT_FILES+COMPACT_EVIDENCE_REPORT_FILES:
        assert (REPORT/path).is_file(),'Required compact handoff file missing: '+path
    assert status in (REPORT/'S4_REPORT.md').read_text(encoding='utf-8')
    files=[p for root in [REPORT,BANK,SIM/'staging/s4_sources',SIM/'staging/s4_h2_audit'] for p in root.rglob('*') if p.is_file()]
    generated=sum(p.stat().st_size for p in files if 'final_packet' not in p.parts)
    assert generated<5*2**30 and storage()['C']['free_gib']>=50
    git={}
    for args in [['git','status','--short'],['git','rev-parse','HEAD']]:git[' '.join(args)]=subprocess.run(args,cwd=REPO,text=True,capture_output=True,check=True).stdout
    before=read(REPORT/'preflight.json')['git_before']
    assert git['git rev-parse HEAD']==before['git rev-parse HEAD'] and git['git status --short']==before['git status --short']
    validated_utc=now();elapsed_wall_s=(datetime.datetime.fromisoformat(validated_utc)-datetime.datetime.fromisoformat(RUN_STARTED_UTC)).total_seconds()
    assert elapsed_wall_s>=0
    return {'status':status,'run_id':RUN_ID,'validated_utc':validated_utc,'run_started_utc':RUN_STARTED_UTC,
        'elapsed_wall_s_at_validation':elapsed_wall_s,'elapsed_wall_scope':'Run start through completed validation; excludes subsequent ZIP packaging.',
        'canonical_rendered':24,'final_captured':len(final),'extra_nominal_repeats':len(repeat),
        'ordinary_H2_jobs':48,'all_physical_passes':len(cases),'charged_playback_s':sum(p['charged_playback_s'] for p in ledger['passes']),
        'physical_integrity_mismatches':sum(c['payload']['payload_mismatches'] for c in cases),
        'compared_mic_samples_all_cases':sum(c['payload']['compared_mic_samples'] for c in cases),
        'model_wall_s':sum(j.get('model_wall_s',0) for j in jobs),'generated_local_bytes_before_packet':generated,'storage_after':storage(),
        'restorations':restorations,'resolved_excluded_attempts':resolved_failures,'accepted_final_captures_binding':bind(REPORT/'ACCEPTED_FINAL_CAPTURES.json'),
        'git_after':git,'baseline_identity':baseline,'H2_summary_recoveries':summary_recoveries,'supporting_evidence':supporting_evidence,
        'H2_summary_provenance_counts':{'native_runtime_exports':len(jobs)-len(summary_recoveries),'derived_from_primary_completion_evidence':len(summary_recoveries)},
        'substatuses':{'data':'COMPLETE_DEVELOPMENT_DOMAIN_LIMITATIONS','scenes':'COMPLETE_24','transport':'PASS','H2':'COMPLETE_48_UNCHANGED_BASELINE',
        'output_headroom':'LIMITED_RESIDUAL_O1_SATURATION','spatial':'IMPLEMENTED_CAUSAL_FALLBACK_WITH_MEASURED_LIMITATIONS','restoration':'PASS_WITH_PRESERVED_EARLY_ROUNDTRIP_RECOVERY',
        'H2_summary_export':'LIMITED_DERIVED_SUMMARIES_WITH_PRESERVED_FAILED_NATIVE_EXPORTS'},
        'no_S5_S6_started':True}

def local_index():
    entries=[]
    def add(path,role,command=None,existing=None):
        row=existing or bind(path);entries.append({**row,'role':role,'reproduce_or_inspect':command})
    add(BANK/'SCENE_MANIFEST.json','Authoritative canonical scene and RIR paths/hashes','Anaconda Python s4_bank.py verifies compatible bank without rewriting')
    add(BANK/'SOURCE_AND_SPLIT_MANIFEST.json','Local source, transcript, contributor and reserve bindings','See README_S4_SOURCES.md')
    add(REPORT/'physical_ledger.json','All charged physical passes and outcomes','Read only; never reset budget to repeat cases')
    for name in ['ACCEPTED_FINAL_CAPTURES.json','TELEMETRY_RETRY_DIAGNOSIS.json','TELEMETRY_RETRY_RESOLUTION.json','H2_SUMMARY_RECOVERY.json','output_alignment.json','h2/execution_contract.json']:
        add(REPORT/name,'Accepted-capture selection, preserved retry diagnosis, or frozen H2 timing/execution contract')
    for name in COMPACT_EVIDENCE_REPORT_FILES:add(REPORT/name,'Compact independent audit, observed tests, visual review or source/spatial evidence')
    for path in h2_recovery_paths():
        if path.name!='H2_SUMMARY_RECOVERY.json':add(path,'Additional bound H2 derived-summary recovery receipt')
        recovery=read(path);case_label=recovery['case_id']+'/'+recovery['stream']
        add(recovery['derived_summary']['path'],case_label+' derived completion summary; not a native runtime export',existing=recovery['derived_summary'])
        for name,b in recovery['source_bindings'].items():
            add(b['path'],case_label+' preserved primary recovery evidence: '+name,existing=b)
    for batch in sorted((REPORT/'hardware').iterdir()):
        if not (batch/'hardware_summary.json').exists():continue
        add(batch/'hardware_summary.json','Physical batch summary: '+batch.name)
        for name in ['restoration.json','restoration_recovery.json','initial_state.json','code_bindings.json']:
            if (batch/name).exists():add(batch/name,'Device state/code evidence: '+batch.name+'/'+name)
        for path in sorted(batch.glob('*/case_result.json')):
            r=read(path);add(path,'Per-case exact payload/framing and raw mono output bindings')
            for stream,b in r.get('output_audio',{}).items():add(b['path'],'Local raw preadapter '+stream+' '+batch.name+'/'+r['case_id'],existing=b)
            for name in ['audio_metrics.json','spatial_metrics.json','capture_metadata.json','telemetry_summary.json']:
                p=path.parent/name
                if p.exists():add(p,'Curated local analysis/availability/control summary')
    for path in sorted((REPORT/'h2').glob('S4_*/O*/run_receipt.json')):add(path,'Isolated H2 input/session/events/metrics bindings','Anaconda Python s4_h2_run.py --alignment-json <report/output_alignment.json> resumes compatible jobs')
    master=read(REPORT/'preflight.json')['workbook_v8']['file']
    add(master['path'],'Current V8 human workbook; unchanged',existing=bind(master['path'],master['sha256']))
    for p in sorted((SIM/'scripts').glob('s4_*.py')):add(p,'Current S4 implementation; historical executed owner versions retained per batch/source_snapshot')
    return {'schema':'s4_curated_local_artifact_index_v1','entries':entries,
        'raw_telemetry_location_rule':'Each hardware batch/case/telemetry contains raw received and normalized JSONL, native per-attempt TSV and source/DLL receipts; intentionally not an incidental-file inventory.',
        'raw_carrier_location_rule':'Each hardware batch/case/native_packed.wav and decoded_six.wav remain local; audio_metrics.converter binds and verifies native output counts.',
        'source_audio_models_rirs_kept_local':True}

def verify_archive(path):
    """Check every member and checksum; accepts an in-memory ZIP for self-tests."""
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        names=archive.namelist();assert len(names)==len(set(names)),'Duplicate archive member'
        allowed={'.md','.json','.csv','.png','.py','.cs','.ps1','.txt'}
        for name in names:
            assert not name.startswith(('/', '\\')) and ':' not in name and '..' not in name.split('/')
            assert Path(name).suffix.lower() in allowed,'Forbidden binary/audio/model/archive member: '+name
        listed={}
        for line in archive.read('SHA256SUMS.txt').decode().splitlines():
            digest,name=line.split('  ',1);assert name not in listed
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest
            listed[name]=digest
        assert set(listed)==set(names)-{'SHA256SUMS.txt'},'Checksum list does not cover exactly the packet'
        plots=[name for name in names if name.startswith('plots/') and name.endswith('.png')]
        assert 1<=len(plots)<=3,'This handoff has at most three planned plots'
        return {'packet_files':len(names),'plots':len(plots)}

def finish_status(receipt):
    save(REPORT/'status.json',{'stage':'S4_DONE','status':receipt['status'],'updated_utc':now(),
        'canonical_scenes_complete':24,'H2_outputs_complete':48,'handoff':receipt['zip']['path'],'S5_S6_started':False})

def package():
    zip_path=SIM/'handoffs'/('S4_CHATGPT_HANDOFF_'+RUN_ID+'.zip')
    if zip_path.exists():
        # A crash after the atomic ZIP promotion but before the final receipt is
        # recovered from its already-written commit record without rerunning H2.
        receipt_path=REPORT/'package_receipt.json'
        receipt=read(receipt_path if receipt_path.exists() else REPORT/'package_commit_pending.json')
        assert Path(receipt['zip']['path']).resolve()==zip_path.resolve()
        bind(zip_path,receipt['zip']['sha256']);verify_archive(zip_path)
        if not receipt_path.exists():save(receipt_path,receipt)
        finish_status(receipt);print(json.dumps(receipt,indent=2));return
    with Progress('final_validation_and_package'):
        validation=validate();save(REPORT/'run_manifest.json',validation)
        save(REPORT/'LOCAL_ARTIFACT_INDEX.json',local_index())
        # Each interrupted packet/ZIP attempt stays local. A new bounded attempt
        # cannot collide with an earlier partial directory or .pending archive.
        attempt_id=uuid.uuid4().hex
        packet=REPORT/'packet_attempts'/attempt_id;packet.mkdir(parents=True,exist_ok=False)
        for name in REPORT_FILES+['run_manifest.json','LOCAL_ARTIFACT_INDEX.json']:
            shutil.copy2(REPORT/name,packet/name)
        for path in h2_recovery_paths():
            if path.name!='H2_SUMMARY_RECOVERY.json':shutil.copy2(path,packet/path.name)
        shutil.copy2(SIM/'scripts/README_S4_PIPELINE.md',packet/'README.md')
        plots=REPORT/'plots';pngs=list(plots.glob('*.png'));assert 1<=len(pngs)<=3
        for source in sorted(plots.iterdir()):
            if source.suffix.lower() in ['.png','.csv']:
                dest=packet/'plots'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        code=packet/'code';code.mkdir()
        wanted=list((SIM/'scripts').glob('s4_*.py'))+list((SIM/'scripts').glob('test_s4_*.py'))+list((SIM/'scripts').glob('README_S4*.md'))
        wanted += [SIM/'scripts/s4_native'/name for name in ['S4QueuedTelemetry.cs','Run-S4-Telemetry.ps1','offline_verification.json']]
        for src in wanted:
            relative=src.relative_to(SIM/'scripts');dest=code/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        evidence=packet/'evidence';evidence.mkdir()
        selected=[SIM/'staging/s4_sources'/n for n in ['SOURCE_NATIVE_METADATA_VERIFICATION.json','SOURCE_ADAPTER_TESTS.json','SHORTLIST_QUALITY.json','SOURCE_CALIBRATION_QC.json','S4_SOURCE_HANDOFF.md','SOURCE_ISSUE_CLOSURE.json']]
        selected += [SIM/'staging/s4_h2_audit'/n for n in ['S3_OFFLINE_H2_HEADROOM_AUDIT.json','AUDIT_FINDINGS.md']]
        selected += [REPORT/'review_staging/telemetry_spatial_fix/regression_receipt.json']
        selected += [REPORT/'h2/execution_contract.json']
        selected += [REPORT/name for name in COMPACT_EVIDENCE_REPORT_FILES]
        for src in selected:
            assert src.exists();shutil.copy2(src,evidence/src.name)
        lines=[]
        for path in sorted(p for p in packet.rglob('*') if p.is_file()):lines.append(bind(path)['sha256']+'  '+path.relative_to(packet).as_posix())
        (packet/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        zip_path.parent.mkdir(exist_ok=True);temporary=zip_path.with_name(zip_path.name+'.'+attempt_id+'.pending')
        with zipfile.ZipFile(temporary,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for path in sorted(p for p in packet.rglob('*') if p.is_file()):archive.write(path,path.relative_to(packet).as_posix())
        assert temporary.stat().st_size<=20*2**20
        archive_summary=verify_archive(temporary)
        zip_binding={**bind(temporary),'path':str(zip_path)}
        receipt={'status':validation['status'],'run_id':RUN_ID,'zip':zip_binding,**archive_summary,'packet_directory':str(packet),
            'target_10mib_met':temporary.stat().st_size<=10*2**20,'max_20mib_met':True,'all_archive_checksums_verified':True,
            'completed_utc':now(),'total_wall_s':(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(RUN_STARTED_UTC)).total_seconds(),
            'physical_playback_s':validation['charged_playback_s'],'H2_compute_s':validation['model_wall_s'],'stop_before':'S5'}
        save(REPORT/'package_commit_pending.json',receipt)
        assert not zip_path.exists(),'Another packet already finalized; preserve this attempt'
        os.replace(temporary,zip_path)
        save(REPORT/'package_receipt.json',receipt)
    finish_status(receipt)
    print(json.dumps(receipt,indent=2))

def self_test():
    """Pure checks only: no validation of unfinished data, files, models or Git."""
    assert_no_critical_issue({'issues':[{'disposition':'FIXED_WITH_EVIDENCE'}]})
    for value in [{'issues':[{'disposition':'BLOCKED_CRITICAL'}]}, {'issues':[]}]:
        try:assert_no_critical_issue(value)
        except AssertionError:pass
        else:raise AssertionError('Blocked or missing issue closure accepted')
    def fixture(extra=None,corrupt=False):
        content={'START_HERE.md':b'Bounded self-test','plots/one.png':b'not rendered; checksum test only'}
        if extra:content.update(extra)
        sums='\n'.join(('0'*64 if corrupt and n=='START_HERE.md' else hashlib.sha256(b).hexdigest())+'  '+n for n,b in content.items())+'\n'
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            for name,data in content.items():archive.writestr(name,data)
            archive.writestr('SHA256SUMS.txt',sums)
        buffer.seek(0);return buffer
    assert verify_archive(fixture())=={'packet_files':3,'plots':1}
    for bad in [fixture({'audio.wav':b'forbidden'}),fixture(corrupt=True),fixture({'../escape.json':b'{}'})]:
        try:verify_archive(bad)
        except AssertionError:pass
        else:raise AssertionError('Invalid compact archive accepted')
    silent={'case_id':'S4_22','audio_integrity_status':'PASS','payload':{'status':'PASS','payload_mismatches':0,
        'all_nonzero_source_payload_captured':None,'alignment_status':'UNIDENTIFIABLE_ALL_ZERO_INPUT',
        'capture_minus_source_offset_samples':None,'compared_mic_samples':400},
        'framing':{'decoded_frames':100,'marker_error_count':0},'callback_flags':[],'callback_errors':[]}
    assert_audio_integrity(silent)
    try:assert_audio_integrity({**silent,'case_id':'S4_01'})
    except AssertionError:pass
    else:raise AssertionError('Non-silent case accepted without active-payload proof')
    assert_h2_completion({'status':'COMPLETE','exit_code':0})
    for invalid in [{'status':'COMPLETE','exit_code':1},{'status':'COMPLETE','exit_code':0,'error':'preserved only elsewhere'},
                    {'status':'COMPLETE','exit_code':0,'ended_utc':'stale failure'}]:
        try:assert_h2_completion(invalid)
        except AssertionError:pass
        else:raise AssertionError('Incomplete or stale-error H2 receipt accepted')
    print(json.dumps({'status':'PASS','checks':13,'scope':'In-memory issue-disposition/checksum/forbidden-member/path-traversal/silent-alignment/H2-completion tests; no final-data validation, models, Git or hardware'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group();group.add_argument('--package',action='store_true');group.add_argument('--self-test',action='store_true');group.add_argument('--validate',action='store_true');a=p.parse_args()
    if a.self_test:self_test()
    elif a.package:package()
    else:print(json.dumps(validate(),indent=2))
