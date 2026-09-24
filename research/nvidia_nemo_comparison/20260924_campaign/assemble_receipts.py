"""Validate completed N1 evidence and assemble small receipts. See README.md."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def ref(path):
    path=Path(path).resolve();return dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size)
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def require(condition,message):
    if not condition:raise RuntimeError(message)
def verify_ref(binding,label):
    path=Path(binding['path']).resolve(strict=True)
    require(path.is_file() and sha(path)==binding['sha256'] and path.stat().st_size==binding['bytes'],
            label+' binding changed')
    return path
def verify_analysis(summary,label):
    for field in ('source_integrity','model_assets_integrity','runtime_versions_integrity',
                  'source_model_config_cache_keys','all_evidence_hashes'):
        require(summary.get(field)=='PASS',label+' '+field+' failed')
    require(summary.get('all_frames_delivered') is True and not summary.get('missing_job_ids'),
            label+' input coverage failed')
    return verify_ref(summary['admission'],label+' admission')
def verify_gui_binding(gui,admission_path):
    index_path=admission_path.parent/'RESULT_INDEX.json'
    require(Path(gui['index_path']).resolve()==index_path.resolve() and sha(index_path)==gui['index_sha256'],
            'GUI result index binding changed')
    index=load(index_path);admission=load(admission_path)
    require(gui['contract_sha256']==index['contract_sha256']==admission['contract_sha256'],
            'GUI/inference contract mismatch')
    require(index['status']=='COMPLETE' and not index['failed'] and index['total']==96 and len(index['completed'])==96,
            'GUI input index incomplete')
    require(not gui.get('allow_partial') and gui.get('completed_input_count')==96,
            'GUI partial inputs cannot satisfy acceptance')
    require(len(gui['cells'])==96 and len({cell['job_id'] for cell in gui['cells']})==96,
            'GUI input identities duplicated or missing')
    require({cell['job_id'] for cell in gui['cells']}==set(index['completed']),
            'GUI/input cell set mismatch')
    for cell in gui['cells']:
        require(cell['status']=='COMPLETE' and Path(cell['result']).resolve()==Path(index['completed'][cell['job_id']]).resolve()
                and sha(cell['result'])==cell['result_sha256'] and sha(cell['snapshot'])==cell['snapshot_sha256'],
                'GUI cell binding changed: '+cell['job_id'])
def unittest_text(path):
    text=Path(path).read_text(encoding='utf-8-sig')
    count=re.search(r'Ran (\d+) tests? in ([\d.]+)s',text)
    require(count is not None and re.search(r'(?m)^OK\s*$',text) is not None,'Test log incomplete/failed: '+str(path))
    return dict(tests=int(count[1]),elapsed_seconds=float(count[2]),status='PASS',receipt=ref(path))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).parent)
    parser.add_argument('--external',type=Path,default=Path('G:/Just_Peachy_N1/20260924_campaign'))
    a=parser.parse_args();root=a.root.resolve();external=a.external.resolve();local=external/'local'
    data=load(root/'data/DATA_AUDIT_SUMMARY.json')
    require(data['status']=='PASS' and data['scenes']==240 and data['waveform_tap_cells']==480,'Corpus audit incomplete')
    baseline=load(root/'data/BASELINE_ANALYSIS_SUMMARY.json')
    regression=load(root/'data/REGRESSION_ANALYSIS_SUMMARY.json')
    require(baseline['status']=='PASS' and baseline['completed_cells']==96 and baseline['complete_paired_scenes']==48,'Main screen incomplete')
    require(regression['status']=='PASS' and regression['completed_cells']==8,'Supplemental regressions incomplete')
    baseline_admission=verify_analysis(baseline,'Main screen')
    verify_analysis(regression,'Supplemental regressions')
    gui_path=external/'evidence/frontend/baseline_full_gui_v1/GUI_REPLAY_REPORT.json'
    gui=load(gui_path)
    require(gui['status']=='COMPLETE' and gui['rendered']==96 and not gui['failed'],'GUI replay incomplete')
    verify_gui_binding(gui,baseline_admission)
    entry_path=external/'evidence/frontend/installed_idle_v2/INSTALLED_MAIN_RECEIPT.json'
    entry=load(entry_path)
    require(entry['main_exit_code']==0 and entry['idle_state']=='IDLE' and not entry['guarded_forbidden_calls'] and entry['installed_source_unchanged'],'Installed main failed')
    tests=load(local/'checks/full-suite-v1/tests.json')
    require(tests['successful'] and tests['tests']==386 and not tests['failures'] and not tests['errors'],'Application suite failed')
    isolation=load(local/'checks/full-suite-v1/isolation.json')
    require(isolation['input_desktop_unchanged'] and not isolation['switch_desktop_called'],'Desktop isolation failed')
    notes=load(root/'review/NOTE_EXAMPLE_TESTS.json');coverage=load(root/'review/NOTE_COVERAGE_AUDIT.json')
    require(notes['status']=='PASS' and coverage['status']=='PASS' and coverage['rows']==73,'Note coverage failed')
    require(sha(root/'NOTE_COVERAGE.csv')==coverage['csv_sha256'],'Note coverage CSV changed after audit')
    release_tests=unittest_text(local/'checks/release-tools-v1.txt')
    supervisor_tests=unittest_text(local/'checks/supervisor-final-v3.txt')
    freeze=load(root/'FRONTEND_FREEZE.json');frozen=Path(freeze['prototype'])
    for path,item in freeze['files'].items():require(sha(frozen/path)==item['sha256'],'Frozen source modified: '+path)
    health=load(local/'checks/release-healthcheck.json');assets=load(local/'checks/release-assets.json')
    require(health['status']=='PASS' and assets['status']=='CONFIGURATION_AND_ASSETS_VALID','Installed release invalid')
    archive=load(local/'packages/just-peachy-n1-common-20260924-v1.receipt.json')
    require(sha(archive['archive'])==archive['sha256'],'Release archive changed')
    runtime=load(root/'assets/runtime_receipt.json')
    require(runtime['status']=='BUILT_AND_HELP_VERIFIED','Native runtime missing')
    checks=dict(schema='just-peachy.n1.code-checks.v1',application=tests,application_isolation=isolation,
        application_log=ref(local/'checks/full-suite-v1/unittest.txt'),hardware_guard=ref(local/'checks/full-suite-v1/hardware_guard.json'),
        release_tools=release_tests,supervisor=supervisor_tests,note_examples=notes,
        installed_entrypoint=entry,gui_final_snapshot_replay=dict(status=gui['status'],rendered=gui['rendered'],scope=gui['scope'],receipt=ref(gui_path)),
        historical_C105=load(root/'data/C105_REPLAY_RECEIPT.json'))
    save(root/'CODE_TESTS.json',checks)
    release=dict(schema='just-peachy.n1.release.v1',source_commit='2a8a2183c0050b6abf76ef27bbd803adad632a87',tag='n1-common-ui-20260924-v1',
        frontend_runtime_sha256=freeze['frontend_runtime_sha256'],common_ui_source_sha256=freeze['common_ui_source_sha256'],
        archive=archive,stage=load(local/'checks/release-stage.json'),activation=load(local/'checks/release-activate.json'),
        healthcheck=health,asset_validation=assets,installed_idle_entrypoint=ref(entry_path),
        launch='Start-N1.cmd or Start-N1.ps1; opens idle with isolated data root',rollback='Select original checkout/immutable baseline with separate data; no original activation was changed')
    save(root/'RELEASE_RECEIPT.json',release)
    old=load(local/'baseline/just-peachy-n1-baseline-20260924-rc5.receipt.json')
    require(sha(old['archive'])==old['sha256'],'Original baseline archive changed')
    inspection_path=Path('C:/Users/amiri/Documents/GitHub/just-peachy/research/nvidia_nemo_comparison/20260924_n1_inspection/evidence/source_inventory.json')
    inspection=load(inspection_path)
    preservation_path=local/'checks/original-source-preservation.json'
    preservation=load(preservation_path)
    require(preservation['status']=='PASS' and preservation['files_checked']==112
            and not preservation['missing'] and not preservation['changed']
            and preservation['prior_manifest_sha256']==inspection['source_manifest_sha256'],
            'Original source preservation failed or prior manifest changed')
    recovery=dict(schema='just-peachy.n1.baseline-recovery.v1',baseline_commit='509195b8c95c3a93eb63666e17038afc05a60d79',
        baseline_tag='n1-baseline-20260924-rc5',original_head='5b12f88430e619e37ce3397e005ca683b1fb9094',
        original_checkout='C:/Users/amiri/Documents/GitHub/just-peachy',original_checkout_reset=False,
        original_personal_data='C:/Users/amiri/JustPeachy/data',personal_gallery_modified=False,baseline_archive=old,
        prior_source_manifest_sha256=inspection['source_manifest_sha256'],prior_inspection=ref(inspection_path),
        original_source_preservation=dict(**preservation,receipt=ref(preservation_path)),
        pi_saved_source=inspection['pi_saved_source'],pi_comparison_kind=inspection['pi_comparison_kind'],
        pi_source_comparison=inspection['pi_source_differences'],pi_current_status='OFFLINE_NOT_CONTACTED',
        original_caption_bug_probe=ref(inspection_path.with_name('caption_ownership_probe.json')),
        original_caption_bug_finding='WHOLE_CAPTION_RELABEL_REPRODUCED in source-only A/B/A event fixture',
        selected_assets=load(frozen/'config/assets.json'),default_launch=dict(mode='caption_only',recipe='fast',tap='O0',state='IDLE',saved_audio_only=True),
        preserved_live_adapters='Explicit future-live opt-in; not exercised by N1; unassigned hardware fields remain disabled')
    save(root/'BASELINE_RECOVERY.json',recovery)
    state=load(local/'supervision/campaign.json');scheduler=load(local/'supervision/scheduler-inspect.json')
    require(len(scheduler['tasks'])==3 and all(t['last_result']==0 for t in scheduler['tasks']),'Scheduled probes not verified')
    supervision=dict(schema='just-peachy.n1.supervision-receipt.v1',campaign=state,latest_status=load(local/'supervision/status.json'),
        scheduler=scheduler,registration=load(local/'supervision/scheduler-register.json'),
        trigger_test=ref(local/'supervision/scheduler-test-trigger.json'),cleanup_test=load(local/'supervision/scheduler-test-cleanup.json'),
        process_contract_tests=supervisor_tests,code_sha256=sha(root/'supervision/supervisor.py'),
        llm_dispatch='MANUAL_REVIEW_ONLY_NO_VERIFIED_CROSS_TURN_IDLE_GUARD',automatic_llm_calls=0)
    save(root/'SUPERVISION_RECEIPT.json',supervision)
    metrics=dict(schema='just-peachy.n1.acceptance.v1',status='COMPLETE',completed_utc=datetime.now(timezone.utc).isoformat(),
        N2_may_proceed=True,stage_scope='N1 only; no global candidate ranking or hardware session',
        classification=dict(IMPLEMENTED=['common backend selector','stable timestamped caption spans','idle saved-audio startup','supervisor/checkpoint/locks'],
            ACTUALLY_RUN=['240-scene full local audit','48-scene/96-cell baseline','4-scene/8-cell saved regressions','96-cell final-state GUI replay','software and scheduler checks','native Windows CPU build'],
            UNAVAILABLE=['exact word/phonetic truth','independent conversation punctuation gold','automatic authenticated safe Codex resume','unverified standalone NVIDIA PnC weights'],
            NOT_TESTED=['Pi/physical hardware/2GB total-system performance','candidate model inference and ranking','N2-N5 efficacy','live enrollment'],FAILED=[]),
        corpus_scenes=240,corpus_waveform_cells=480,full_transcript_occurrences_audited=777,
        baseline_cells=96,baseline_paired_scenes=48,supplemental_regression_cells=8,gui_rendered_cells=96,note_coverage_rows=73,
        application_tests=tests['tests'],application_skips=tests['skipped'],application_failures=0,
        frontend_runtime_sha256=freeze['frontend_runtime_sha256'],common_ui_source_sha256=freeze['common_ui_source_sha256'],
        baseline_neural_output_reuse='No historical predictions; only new hash-bound N1 checkpoints',
        clock_order_findings=baseline['counter_totals']['observed_clock_order_violations'],
        evidence={name:ref(root/name) for name in ['CODE_TESTS.json','BASELINE_RECOVERY.json','RELEASE_RECEIPT.json','SUPERVISION_RECEIPT.json','data/BASELINE_ANALYSIS_SUMMARY.json','data/REGRESSION_ANALYSIS_SUMMARY.json','LIMITATIONS.md']})
    save(root/'N1_METRICS.json',metrics)
    print(json.dumps(dict(status='COMPLETE',baseline_cells=96,regression_cells=8,gui_cells=96,N2_may_proceed=True)))


if __name__=='__main__':main()
