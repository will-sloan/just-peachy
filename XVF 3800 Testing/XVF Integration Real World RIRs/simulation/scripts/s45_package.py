"""Compact analysis-first S4.5 handoff, including honest partial checkpoints. README_S45_EXECUTE.md."""
import collections, csv, zipfile
from s45_common import *

def optional(relative,default=None):
    path=REPORT/relative
    return read(path) if path.exists() else default

def put(name,text):
    path=REPORT/name;path.write_text(text.rstrip()+'\n',encoding='utf-8');return path

def verified_analysis_summary(counts):
    try:
        summary=optional('summary_metrics.json',{})
        assert summary.get('schema')=='jp_s45_summary_v1' and summary.get('status')=='COMPLETE_WITH_LIMITATIONS','Detailed analysis is pending/partial'
        assert summary.get('run_id')==RUN_ID,'Detailed analysis belongs to a different run'
        actual=summary['actual']
        assert actual['canonical_accepted']==counts['accepted'] and actual['audio_analyzed']==counts['canonical_analyzed'] and actual['development_spatial_analyzed']==180
        assert summary['reserve_task_metrics_read'] is False
        assert summary['consumed_json_bindings'],'No analysis provenance'
        for binding in summary['consumed_json_bindings']+[summary['per_scene_metrics_binding'],summary['aggregation_code']]:bind(binding['path'],binding['sha256'])
        consumed={Path(b['path']).resolve():b['sha256'] for b in summary['consumed_json_bindings']}
        for path in [BANK/'SCENE_MANIFEST.json',REPORT/'ACCEPTED_CAPTURES.json',REPORT/'CAPTURE_ANALYSIS.json',REPORT/'COVERAGE_SUMMARY.json',REPORT/'SENTINEL_PLAN.json',REPORT/'DRY_CONTROL_PLAN.json',REPORT/'h2/execution_contract.json']:
            assert path.resolve() in consumed,'Detailed analysis omits current critical input '+str(path)
            bind(path,consumed[path.resolve()])
        assert Path(summary['per_scene_metrics_binding']['path']).resolve()==(REPORT/'per_scene_metrics.csv').resolve()
        assert Path(summary['aggregation_code']['path']).resolve()==(SIM/'scripts/s45_results.py').resolve()
        return {'status':'PASS','summary':bind(REPORT/'summary_metrics.json')}
    except (AssertionError,KeyError,ValueError,FileNotFoundError) as exc:
        return {'status':'PENDING_OR_STALE','error':str(exc)}


def verified_plot_artifacts():
    """Verify the index against current evidence; stale checkpoint plots stay out."""
    try:
        index=optional('plots/FIGURE_INDEX.json',{})
        assert index.get('schema')=='jp_s45_figures_v1','Missing or unsupported figure index'
        assert index['no_reserve_task_plots'] is True,'Figure index does not preserve reserve guard'
        figures=index['figures']
        assert isinstance(figures,list) and 1<=len(figures)<=4,'Require one to four indexed figures'
        assert index['figure_count']==len(figures) and index['maximum_figures']==4,'Figure count/cap differs'
        for key,path in [('summary_metrics',REPORT/'summary_metrics.json'),('plot_code',SIM/'scripts/s45_results.py'),('plotted_data',REPORT/'plots/plotted_data.csv')]:
            binding=index[key]
            assert Path(binding['path']).resolve()==path.resolve(),'Figure '+key+' points to a different artifact'
            bind(path,binding['sha256'])
        files=[];seen=set()
        for figure in figures:
            name=figure['file']
            assert isinstance(name,str) and Path(name).name==name and Path(name).suffix.lower()=='.png','Figure name must be a local PNG basename'
            path=(REPORT/'plots'/name).resolve()
            assert path.parent==(REPORT/'plots').resolve() and path not in seen,'Duplicate or nonlocal figure'
            assert Path(figure['binding']['path']).resolve()==path,'Figure binding points to a different file'
            files.append(bind(path,figure['binding']['sha256']));seen.add(path)
        files.append(bind(REPORT/'plots/plotted_data.csv',index['plotted_data']['sha256']))
        index_binding=bind(REPORT/'plots/FIGURE_INDEX.json');files.append(index_binding)
        return {'status':'PASS','visual_QA':index.get('visual_QA'),'figure_count':len(figures),'files':files,'index':index_binding,
                'scope':'Current summary/code and indexed PNG/CSV identities verified. Only these indexed plot files may enter the package.'}
    except (AssertionError,KeyError,ValueError,TypeError,AttributeError,OSError) as exc:
        return {'status':'PENDING_OR_STALE','visual_QA':None,'figure_count':0,'files':[],'error':str(exc),
                'scope':'Unverified plot artifacts excluded from this checkpoint; no stale glob files included.'}


def verified_findings():
    files=[];pending=[]
    for name in ['ANALYSIS_FINDINGS.md','WORKBOOK_FINDINGS.md']:
        path=REPORT/name
        try:
            assert path.read_text(encoding='utf-8').strip(),'Findings file is empty'
            files.append(bind(path))
        except (AssertionError,OSError,UnicodeError) as exc:
            pending.append({'file':name,'error':str(exc)})
    return {'status':'PASS' if not pending else 'PENDING','files':files,'pending':pending,
            'scope':'Both human-readable findings inputs must be nonempty. The coordinator reviews their scientific content against fresh metrics before final delivery.'}


def final_review_ready(plots,findings):
    return plots['status']=='PASS' and plots.get('visual_QA')=='PASS_TOOL_INSPECTION' and findings['status']=='PASS'


def main():
    REPORT.mkdir(parents=True,exist_ok=True)
    manifest=read(BANK/'SCENE_MANIFEST.json') if (BANK/'SCENE_MANIFEST.json').exists() else {'scenes':[]}
    accepted=optional('ACCEPTED_CAPTURES.json',{'accepted':[],'failed_attempts':[]})
    references=optional('REFERENCE_CAPTURES.json',{'accepted':[],'failed_attempts':[]})
    analysis=optional('CAPTURE_ANALYSIS.json',{'count':0})
    ledger=optional('physical_ledger.json',{'passes':[]})
    source_path=SIM/'staging/s45_sources/SOURCE_AND_SPLIT_MANIFEST.json'
    sm=read(source_path) if source_path.exists() else {'sources':[]}
    noise_path=SIM/'staging/s45_noise/NOISE_CATALOG.json'
    nm=read(noise_path) if noise_path.exists() else {'prepared_segments':[]}
    jobs=[read(p) for p in (REPORT/'h2').glob('*/*/run_receipt.json')]
    dry=[read(p) for p in (REPORT/'h2_dry').glob('*/run_receipt.json')]
    dryplan=optional('DRY_CONTROL_PLAN.json',{})
    batch_execution=[{'summary_binding':bind(p),**{k:read(p).get(k) for k in ['batch','status','error','elapsed_s','restoration_status']}} for p in sorted(HARDWARE.glob('*/hardware_summary.json'))]
    counts={'planned_canonical':240,'rendered':len(manifest['scenes']),'accepted':len(accepted['accepted']),
        'development_accepted':sum(x['split']=='development' for x in accepted['accepted']),
        'reserve_accepted':sum(x['split']=='reserve' for x in accepted['accepted']),
        'failed_capture_attempts':len(accepted['failed_attempts']),'recorded_hardware_batch_errors':sum(bool(b.get('error')) for b in batch_execution),'canonical_analyzed':analysis['count'],
        'optional_reference_accepted':len(references['accepted']),'physical_passes':len(ledger['passes']),
        'charged_active_playback_s':sum(x['charged_playback_s'] for x in ledger['passes']),
        'H2_output_statuses':dict(collections.Counter(x['status'] for x in jobs)),
        'H2_dry_statuses':dict(collections.Counter(x['status'] for x in dry)),
        'H2_model_wall_s':sum(x.get('model_wall_s',0) for x in jobs+dry),
        'model_invocation_attempt_receipts':sum(x.get('status')!='QUARANTINED' for x in jobs+dry),
        'observed_model_child_PIDs':sum(isinstance(x.get('owned_process_pid'),int) for x in jobs+dry),
        'unconfirmed_model_starts':sum(x.get('status')!='QUARANTINED' and not isinstance(x.get('owned_process_pid'),int) for x in jobs+dry),
        'run_elapsed_s':elapsed_s(),'prepared_new_source_clips':len(sm['sources']),
        'prepared_noise_parents':len({x['parent_id'] for x in nm.get('prepared_segments',[])})}
    restored=False;restoration_error=None
    try:
        from s45_campaign import validate_restorations
        validate_restorations();restored=True
    except BaseException as exc:restoration_error=repr(exc)
    owner=optional('owned_process.json',{})
    unresolved_child=optional('UNRESOLVED_SUPERVISOR_CHILD.json')
    restored=restored and not owner.get('pid') and unresolved_child is None
    dry_expected=dryplan.get('count',24)
    analysis_validation=verified_analysis_summary(counts)
    plot_validation=verified_plot_artifacts();findings_validation=verified_findings()
    review_ready=final_review_ready(plot_validation,findings_validation)
    complete=counts['rendered']==240 and counts['accepted']==240 and counts['canonical_analyzed']==240 and sum(x['status'] in ['COMPLETE','QUARANTINED'] for x in jobs)==48 and sum(x['status']=='COMPLETE' for x in dry)==dry_expected and restored and analysis_validation['status']=='PASS' and review_ready
    status='COMPLETE_WITH_SOURCE_GAPS' if complete else 'PARTIAL_TIME_BUDGET' if not launch_allowed() else 'BLOCKED'
    total_bytes=sum(p.stat().st_size for root in [PAYLOAD,REPORT,BANK] if root.exists() for p in root.rglob('*') if p.is_file())
    state={'stage':'S4.5','status':status,'updated_utc':now(),'counts':counts,'ssd':storage(),'new_job_bytes':total_bytes,
        'restoration':'PASS' if restored else 'UNVERIFIED','restoration_error':restoration_error,'hardware_owner':owner.get('pid'),
        'reserve_task_scored':False,'unresolved_supervisor_child':unresolved_child,'analysis_summary_validation':analysis_validation,
        'plot_artifact_validation':plot_validation,'findings_validation':findings_validation,'final_report_review_ready':review_ready,
        'S4_status':'COMPLETE_WITH_LIMITATIONS','next_stage_started':False}
    save(REPORT/'status.json',state)
    fixed=[p for p in (SIM/'staging/s45_h2_fix').glob('v*/FIX_RECEIPT.json')]
    executed_contract=REPORT/'h2/execution_contract.json'
    if executed_contract.exists():
        executed_fix=read(executed_contract)['baseline']['durability_fix']
        bind(executed_fix['path'],executed_fix['sha256']);fixed=[Path(executed_fix['path'])]
    fix=read(sorted(fixed)[-1]) if fixed else {}
    save(REPORT/'FIX_RECEIPTS.json',{'active_h2_fix':fix,'active_receipt_binding':bind(sorted(fixed)[-1]) if fixed else None,'hardware_review':read(SIM/'staging/s45_hardware_review/v1/REVIEW_RECEIPT.json') if (SIM/'staging/s45_hardware_review/v1/REVIEW_RECEIPT.json').exists() else None,'historical_S4_reconstructed_summaries_remain_historical':True})
    history_bindings={};resume_contexts=[];incident_reviews={};resume_ids=set()
    for path in sorted(REPORT.glob('RESUME_AFTER_INCIDENT_[0-9][0-9].json')):
        incident=path.stem.rsplit('_',1)[-1];resume=read(path);resume_ids.add(incident)
        history_bindings['incident_'+incident+'_resume']=bind(path)
        for key in ['previous_supervisor','checkpoint','recovery_driver','recovery','prepared_supervisor_v2','supervisor_v2','bank']:
            if key in resume:history_bindings['incident_'+incident+'_'+key]=bind(resume[key]['path'],resume[key]['sha256'])
        resume_contexts.append({'incident':incident,'resume':resume,'binding':history_bindings['incident_'+incident+'_resume']})
        for suffix in ['REVIEW','CLOSURE_REVIEW']:
            name='INCIDENT_'+incident+'_'+suffix+'.json';incident_reviews[name]=optional(name)
            if (REPORT/name).exists():history_bindings[name]=bind(REPORT/name)
    for stamp in ['20260909T091333','20260909T092453']:
        for path in sorted((REPORT/'supervisor').glob('capture_'+stamp+'_*.json')):
            history_bindings[path.name]=bind(path)
    host_stalls=optional('HOST_STALL_OBSERVATIONS.json')
    if host_stalls:history_bindings['host_stall_observations']=bind(REPORT/'HOST_STALL_OBSERVATIONS.json')
    history_paragraphs=['The versioned supervisor lifecycle fixtures describe model-free exception bookkeeping checks. They remain distinct from actual capture/control interruptions; execution history and current outcomes come from the bound stage, incident and acceptance receipts.']
    if '02' in resume_ids:
        history_paragraphs.append('The initial s45_execute.py v1 supervisor ran from 04:34:38 UTC and closed at 09:10:34 UTC with 232 canonical captures accepted. Incident 02 was a pre-playback GPO_PIN_PWM_DUTY query timeout followed by an AEC_FIXEDBEAMSELEVATION_VALUES restoration-readback timeout; its original FAIL and blocked checkpoint are preserved. Bounded recovery with the unchanged S4 restorer verified exact exposed state at 09:12:44 UTC without setting reapplication or audio playback. The already-tested s45_execute_v2.py was launched at 09:13:33 UTC for the same bank and remaining eight canonical scenes.')
    if '03' in resume_ids:
        history_paragraphs.append('Incident 03 was the first failed physical take: S45_12_16 timed out during finite capture despite retaining the full frame count and exact payload. The failed take remains ineligible; payload equality alone does not override capture failure. A restoration-readback timeout also occurred. That v2 supervisor closed at 09:23:02 UTC with 235 accepted scenes and one failed physical attempt. Exact exposed-state recovery passed at 09:23:47 UTC, reapplying only PP_AGCGAIN. The same unchanged v2 supervisor resumed at 09:24:53 UTC with five intended scenes remaining, including the one allowed identical retry of S45_12_16. Both blocked checkpoints and original failure/recovery evidence remain preserved; the latest acceptance and job receipts determine the eventual outcome.')
    if host_stalls:
        history_paragraphs.append('HOST_STALL_OBSERVATIONS.json records VSS/shadow-copy and Acronis-related activity around the two observed stall windows. Their temporal association is a possible host-side explanation, not proof of causation. It does not establish that USB, the device or another component was fault-free; no backup/service/security change or scientific retuning followed from this observation.')
    history_paragraphs.append('Every resume retains the original bank, source/scientific policies, deadline and global pass/time budgets. Actual batch errors and failed physical takes are counted separately above; earlier zero-failed-take checkpoints must not be presented as the final run total.')
    supervisor_history='\n\n'.join(history_paragraphs)
    if (SIM/'staging/s45_supervisor_fix/v2/FIX_RECEIPT.json').exists():
        fixes=read(REPORT/'FIX_RECEIPTS.json');fixes['supervisor_v2_lifecycle_fix']=read(SIM/'staging/s45_supervisor_fix/v2/FIX_RECEIPT.json');fixes['supervisor_scope']=supervisor_history;save(REPORT/'FIX_RECEIPTS.json',fixes)
    fixes=read(REPORT/'FIX_RECEIPTS.json');fixes['hardware_batch_execution']=batch_execution;fixes['execution_incidents']=optional('EXECUTION_INCIDENTS.json',{'incidents':[]})
    fixes['supervisor_execution_history']={'description':supervisor_history,'bindings':history_bindings,'resume_contexts':resume_contexts,
        'v2_launch_evidence_scope':'Coordinating-agent tool-observed launches at 09:13:33 UTC and 09:24:53 UTC, with bound readiness and actual resumed capture-stage receipts; readiness alone is not a completion receipt.',
        'incident_reviews':incident_reviews,
        'host_stall_observations':{'binding':history_bindings.get('host_stall_observations'),**{key:host_stalls.get(key) for key in ['status','observations','inferences','limits']}} if host_stalls else None,
        'scope':'Prior incident files and both blocked checkpoints remain historical. Pre-playback batch errors, failed physical takes, restoration failures/recovery and model-free supervisor fixtures are separate evidence.'}
    save(REPORT/'FIX_RECEIPTS.json',fixes)
    primary=[p for p in [source_path,noise_path,BANK/'SCENE_MANIFEST.json',BANK/'REFERENCE_SCENE_MANIFEST.json',BANK/'FUTURE_TRAINING_MANIFEST.jsonl',REPORT/'CAPTURE_ANALYSIS.json',REPORT/'REFERENCE_CAPTURE_ANALYSIS.json',REPORT/'H2_RELEASE.json',executed_contract,REPORT/'supervisor_receipt.json',REPORT/'preflight.json',REPORT/'INPUT_REVISION_RECEIPT.json',REPORT/'PRE_CAPTURE_VERIFICATION.json',SIM/'staging/s45_noise/NOISE_FINAL_RECEIPT.json'] if p.exists()]
    primary += [p for p in [REPORT/'PRESERVATION_CHECKPOINT.json',REPORT/'RESOURCE_CHECKPOINT_60.json',REPORT/'FINAL_RESOURCE_AND_RESTORATION.json',REPORT/'EXECUTION_INCIDENTS.json',REPORT/'INCIDENT_REVIEW.json',REPORT/'SPATIAL_INTERPRETATION_REVIEW.md',SIM/'staging/s45_results_review/v1/REVIEW_RECEIPT.json',SIM/'staging/s45_package_review/v1/TEST_RECEIPT.json',SIM/'staging/s45_final_audit_review/v1/FIXTURE_RECEIPT.json'] if p.exists()]
    primary += [Path(binding['path']) for binding in history_bindings.values()]
    primary += [p for p in [REPORT/'INCIDENT_02_REVIEW.json',REPORT/'INCIDENT_02_CLOSURE_REVIEW.json',REPORT/'INCIDENT_03_REVIEW.json',REPORT/'INCIDENT_03_CLOSURE_REVIEW.json',REPORT/'HOST_STALL_OBSERVATIONS.json',SIM/'staging/s45_package_review/v2_execution_history/COMPILE_RECEIPT.json',SIM/'staging/s45_package_review/v3_multiple_resumes/COMPILE_RECEIPT.json'] if p.exists()]
    primary += [p for p in [REPORT/'FINAL_SOURCE_COVERAGE_REVIEW.json',REPORT/'FINAL_SPATIAL_AND_TRANSPORT_REVIEW.json',REPORT/'H2_FIRST_NATIVE_REVIEW.json',REPORT/'H2_FINAL_NATIVE_REVIEW.json',SIM/'staging/s45_package_review/v4_final_reviews/COMPILE_RECEIPT.json'] if p.exists()]
    primary += [p for p in [SIM/'scripts/s45_native_review.py',SIM/'scripts/README_S45_NATIVE_REVIEW.md',SIM/'staging/s45_native_review/v2/TEST_RECEIPT.json',SIM/'staging/s45_package_review/v5_final_resume_scope/COMPILE_RECEIPT.json'] if p.exists()]
    primary += [p for p in [REPORT/'BANK_SIZE_REVIEW.json',SIM/'staging/s45_results_review/v2_plot_layout/LAYOUT_RECEIPT.json',SIM/'staging/s45_results_review/v2_plot_layout/RENDER_RECEIPT.json',SIM/'staging/s45_package_review/v6_final_storage_and_plots/COMPILE_RECEIPT.json'] + sorted((SIM/'staging/s45_final_audit_review/v2_storage_provider').glob('*RECEIPT.json')) if p.exists()]
    primary += [p for p in [REPORT/'PID_REUSE_OBSERVATION.json',SIM/'staging/s45_package_review/v7_pid_audit_history/COMPILE_RECEIPT.json'] + sorted((SIM/'staging/s45_final_audit_review/v3_pid_reuse').glob('*RECEIPT.json')) if p.exists()]
    primary=list(dict.fromkeys(primary))
    index={'root':str(SIM),'payload_root':str(PAYLOAD),'primary_manifests':[bind(p) for p in primary],
        'code_and_readmes':[bind(p) for p in sorted((SIM/'scripts').glob('*s45*')) if p.is_file()]+[bind(p) for p in sorted((SIM/'scripts').glob('README_S45*.md'))],
        'local_only':{'canonical_audio':str(PAYLOAD/'canonical_v2'),'unplayed_input_QC_revision1':str(PAYLOAD/'canonical'),'input_revision_receipt':str(REPORT/'INPUT_REVISION_RECEIPT.json'),'physical_native_outputs_and_telemetry':str(HARDWARE),'model_artifacts':str(PAYLOAD/'h2'),'dry_model_artifacts':str(PAYLOAD/'h2_dry'),'source_metadata':str(SIM/'staging/s45_sources'),'noise_archive_and_attribution':str(SIM/'staging/s45_noise')},
        'reference_policy':'Full orthographic references, rights and exact waveform/scene hashes are in the local bound manifests; no raw audio or exhaustive transcript dump in this ZIP.'}
    save(REPORT/'LOCAL_ARTIFACT_INDEX.json',index)
    save(REPORT/'run_manifest.json',{'run_id':RUN_ID,'start_utc':START_UTC.isoformat(),'deadline_utc':DEADLINE.isoformat(),'launch_cutoff_utc':LAUNCH_CUTOFF.isoformat(),'limits':LIMITS,'status':status,'counts':counts,'new_job_bytes':total_bytes,'source_override':'Original CMU ARCTIC + HiFiTTS + Common Voice; no L2 ARCTIC','canonical_RIR_manifest':bind(SIM/'rir_library/v1/RIR_MANIFEST.json','468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546'),'master_workbook':bind(Path('C:/Users/amiri/Downloads/XVF_Measurement_V9.docx'),'af393d71060ee25fd2f1d4398dfc1fb52daaa7cb20d182b284a348fc974d72f2'),'no_training_or_next_stage':True})
    table='\n'.join('| '+key+' | '+str(value)+' |' for key,value in counts.items() if not isinstance(value,dict))
    findings=(REPORT/'ANALYSIS_FINDINGS.md').read_text(encoding='utf-8') if (REPORT/'ANALYSIS_FINDINGS.md').exists() else 'Detailed task interpretation is pending. Treat this package as a checkpoint unless all completion denominators above are satisfied.'
    context=(REPORT/'CONTEXT_DETAILS.md').read_text(encoding='utf-8') if (REPORT/'CONTEXT_DETAILS.md').exists() else ''
    workbook_findings=(REPORT/'WORKBOOK_FINDINGS.md').read_text(encoding='utf-8') if (REPORT/'WORKBOOK_FINDINGS.md').exists() else findings
    resume_script='s45_execute_v2.py' if (SIM/'scripts/s45_execute_v2.py').exists() else 's45_execute.py'
    report=f"""# S4.5 analysis-first handoff

Status: **{status}**. S4 remains **COMPLETE_WITH_LIMITATIONS**. This run uses original CMU ARCTIC, HiFiTTS and older English Common Voice, as the user requested. L2 ARCTIC is excluded. The unchanged Revision 9 workbook is the planning/results guide; WORKBOOK_UPDATE.md is proposed insertion text.

| Observation | Actual |
|---|---:|
{table}

## Observed analysis

{findings}

## What this stage establishes

The canonical input bank targets 240 new scenes, 180 development and 60 protected reserve in 12 families. The scenes are measured-path simulations, not independent rooms or an enclosure qualification. Each source retains its native transcript, quality partition, pseudonymous identity, preparation scalar and exact schedule. Four microphones share one family headroom scalar. RIRs are not normalized independently, and no extra distance attenuation or artificial generic reverb is added.

The approved RIR set contains 120 HIL-eligible inputs out of 121 canonical records. The clock-sensitive R13 path remains excluded. Only qualified PASS/REVIEW acquisition data is eligible; pilots, retakes, Loeb Caf and historical testing remain excluded. Upper Loeb is an acoustic reserve. The two user-confirmed 100 cm distance corrections remain 1.00 m; no selected distance exceeds 5 m. Manual bearing uncertainty remains ±5 degrees and is separate from XVF directional error. Folded linear-array direction retains front/rear ambiguity.

Source preparation follows the existing active-RMS numerical rule with 12 dB maximum boost and 0.5 FS dry peak cap. Source quality does not certify anechoic audio. HiFiTTS has three clean-branch voices and seven other-only voices; the eight/two split preserves the quality strata. Common Voice age/accent/gender is available self-reported metadata, not inferred identity or a causal age/accent experiment. The roster was frozen before waveform QC; its fourth newly targeted CV reserve contributor failed clip QC and was not replaced after inspection.

CMU ARCTIC recording basenames can repeat across voices while containing different text. The normalized transcript prompt group is the lexical split authority; a bare arctic_a/bNNNN basename is not a globally unique prompt. The final source-coverage review retains this namespace caveat alongside the short-clip, isolated-development, partner and optional-reference gaps. Independent source, spatial/transport and native-H2 review receipts are bound in the local artifact index when available. A first-job native review does not certify completion of the full model set.

Real-noise parents come from verified official MUSAN material and retain per-parent attribution/rights and speech-content evidence. Generic environmental sounds with uncertain speech are not strict speech-free ground truth. DEMAND access was unavailable during bounded official-source attempts; no DEMAND recording or license is invented. Noise SNR is measured over the same target-active windows across all four microphones. Transient timing/excerpts are frozen from source-only evidence. Noise-only/speech pairs reuse an exact noise component. Full rights and corpus/split caveats are in RIGHTS_AND_SPLITS.json and the local catalogues.

Canonical hardware capture uses the frozen S4 PCM24 packed path and simultaneous O0/O1, recaptured microphones and continuous telemetry. Original output files retain all rail samples. Gross saturation is quarantined for downstream task use; residual rails are LIMITED. The numerical recipe is fixed, with O0 +3dB only in the H2 adapter and O1 unity. No target truth steers the device. Reserve files receive only coverage/level/transport/integrity checks. Optional isolated references are separate from 240, unscored and not enrolled.

{context}

## Lifecycle repair and preservation

The active versioned H2 repair changes artifact export/lifecycle only: atomic summary replacement, explicit completion, failure propagation and startup terminal-state ordering. Original and intermediate bytes, exact diffs and model-free fixtures remain local and are indexed. Actual new native completion counts are reported separately from failed/quarantined/pending jobs. The four historically reconstructed S4 summaries remain historical reconstructions. Scientific configurations/model assets and the 121 canonical RIRs are preserved.

{supervisor_history}

## Limits and reuse

DER, exact phonetic word latency, enrolled-name accuracy and real moving-tablet performance are not established. Causal direction availability uses the frozen 250-ms policy and the retained RIR origin once; host delivery times are not internal DSP sample times. Multi-talker overlap and untranscribed ambient speech remain explicit limitations. This stage does not select an O0/O1 winner, tune fusion, train models or begin S5/S6.

XVF exposed-state restoration: **{state['restoration']}**. Recorded hardware owner: **{owner.get('pid')}**. See actual stage/failed-attempt receipts in LOCAL_ARTIFACT_INDEX.json before reusing incomplete work.
"""
    put('S4_5_REPORT.md',report)
    put('START_HERE.md',f"""# Read this first

S4.5 is **{status}**. Read S4_5_REPORT.md, summary_metrics.json and per_scene_metrics.csv together. Coverage and rights are separate from task accuracy. Reserve task results remain unscored.

Actual canonical capture: {counts['accepted']}/240; offline capture analysis: {counts['canonical_analyzed']}/240. Optional references: {counts['optional_reference_accepted']}/34. New model output statuses: {counts['H2_output_statuses']}; dry statuses: {counts['H2_dry_statuses']}.

Plot artifacts: {plot_validation['status']}; visual QA: {plot_validation.get('visual_QA')}; findings: {findings_validation['status']}. Final report review ready: {review_ready}. Unverified/stale plot artifacts are excluded from checkpoint packages. Complete execution counts alone do not close the final report review.

Use LOCAL_ARTIFACT_INDEX.json to find full local audio, telemetry, source truth and code. Do not reinterpret this as completion when any required denominator remains pending. No next stage is started automatically.
""")
    put('WORKBOOK_UPDATE.md',f"""# Proposed Revision 9 workbook update

Insert only after review, using the requested light-yellow results highlighting. The Word master was not rewritten.

S4 remains COMPLETE_WITH_LIMITATIONS. S4.5: **{status}**.

| Measurement | Actual |
|---|---:|
{table}

Use the analysis and limitations in S4_5_REPORT.md and the four plot captions, if present. Preserve the distinction between prepared, rendered, physically captured, task-scored and protected reserve. The user-selected original CMU/HiFiTTS/Common Voice scope supersedes the pack's conditional L2 target. DEMAND access and the CV reserve QC gap must remain visible. No O0/O1 winner, fusion benefit or training/generalization result is claimed.

{workbook_findings}
""")
    put('NEXT_PHASE_INPUTS.md',f"""# Next-stage context and exact resume

This packet closes only S4.5. Plan S5 after reviewing actual accepted-capture, task-use and rights/split rows. Reuse the frozen canonical library, protected reserve, final capture mappings and unchanged H2 science. Keep limited overlap/ambient-reference scores outside ordinary WER and quarantine gross saturation. Direction/identity fusion and enrollment remain future work.

Current pending canonical captures: {240-counts['accepted']}. Pending output jobs: {48-sum(x['status'] in ['COMPLETE','QUARANTINED'] for x in jobs)}. Restoration: {state['restoration']}.

When all 240 canonical captures, 48 output jobs and 24 dry controls are complete and exposed-state restoration is PASS, no mandatory execution resume is needed. The commands below apply only to a compatible incomplete checkpoint after verified closure; they are not a request to rerun completed work. The 34 prepared optional references were deliberately skipped to preserve analysis time and are not unfinished mandatory work. Any later reference capture requires a separately authorized stage. Final report and audit review still govern handoff completion.

Only after the current supervisor and owned children have ended with verified cleanup, an exact resume within this run's original deadline uses PowerShell:
Set-Location '{SIM / 'scripts'}'
& '{BASE_PYTHON}' {resume_script}

Anaconda/CMD:
cd /d "{SIM / 'scripts'}"
"{BASE_PYTHON}" {resume_script}

These commands reuse only compatible completed artifacts and do not reset the deadline or retry failed H2 jobs blindly. After deadline, obtain a new explicitly authorized timing overlay while preserving the input version. If restoration is not PASS or a failed invocation remains, inspect the indexed receipt before any hardware/model resume. See README_S45_EXECUTE.md and component READMEs locally.
""")
    if not (REPORT/'summary_metrics.json').exists():save(REPORT/'summary_metrics.json',{'status':'PENDING_DETAILED_ANALYSIS','counts':counts,'reserve_task_scored':False})
    if not (REPORT/'per_scene_metrics.csv').exists():
        with (REPORT/'per_scene_metrics.csv').open('w',encoding='utf-8',newline='') as f:
            writer=csv.writer(f);writer.writerow(['case_id','split','capture_status','task_scored'])
            chosen={x['case_id'] for x in accepted['accepted']}
            for s in manifest['scenes']:writer.writerow([s['case_id'],s['split'],'ACCEPTED' if s['case_id'] in chosen else 'PENDING',False])
    names=['START_HERE.md','S4_5_REPORT.md','WORKBOOK_UPDATE.md','NEXT_PHASE_INPUTS.md','summary_metrics.json','per_scene_metrics.csv','SOURCE_COVERAGE.csv','NOISE_CATALOG.csv','SCENE_MANIFEST_COMPACT.json','ACCEPTED_CAPTURES_COMPACT.json','RIGHTS_AND_SPLITS.json','FIX_RECEIPTS.json','run_manifest.json','status.json','LOCAL_ARTIFACT_INDEX.json']
    files=[REPORT/n for n in names if (REPORT/n).exists()]
    files += [Path(binding['path']) for binding in plot_validation['files']]
    tests=sorted((REPORT/'tests').glob('final_pre_freeze_*.json'))
    readiness=sorted((REPORT/'tests').glob('reporting_readiness_*/TEST_RECEIPT.json'))
    component_tests=[SIM/'staging/s45_sources/SOURCE_TEST_RECEIPT.json',SIM/'staging/s45_noise/NOISE_FINAL_RECEIPT.json',SIM/'staging/s45_h2_fix/v3/RUNNER_TEST_RECEIPT.json',SIM/'staging/s45_results_review/v1/REVIEW_RECEIPT.json',SIM/'staging/s45_package_review/v1/TEST_RECEIPT.json',SIM/'staging/s45_final_audit_review/v1/FIXTURE_RECEIPT.json']
    save(REPORT/'test_receipt.json',{'historical_pre_freeze_fixtures':[read(p) for p in tests],
        'historical_scope':'These earlier receipts bind their exact tested versions; they do not assert that every later source revision is identical.',
        'current_reporting_readiness':[{'receipt':bind(p),'result':read(p)} for p in readiness],
        'component_receipts':[{'receipt':bind(p),'result':read(p)} for p in component_tests if p.exists()],
        'hardware_and_H2_tests':'See bound FIX_RECEIPTS.json for active lifecycle/hardware reviews, historical model-free supervisor fixtures and the separately documented actual v1-to-v2 resume.',
        'no_model_free_fixture_is_a_physical_pass':True})
    files.append(REPORT/'test_receipt.json')
    # The full exact durability diff remains bound by FIX_RECEIPTS, with one
    # compact active diff included when its recorded path is available.
    if fixed:
        candidates=list(sorted(fixed)[-1].parent.glob('*.patch'))+list(sorted(fixed)[-1].parent.glob('*.diff'))
        if candidates:
            dest=REPORT/'durability.patch';shutil.copyfile(candidates[0],dest);files.append(dest)
    sums='\n'.join(bind(p)['sha256']+'  '+p.name for p in files)+'\n';checks=put('SHA256SUMS.txt',sums);files.append(checks)
    assert len(files)<=25,'Compact handoff file-count cap'
    dest=SIM/'handoffs'/('S4_5_CHATGPT_HANDOFF_'+RUN_ID+'.zip');dest.parent.mkdir(exist_ok=True)
    temp=dest.with_name(dest.name+'.'+uuid.uuid4().hex+'.tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,p.name)
    assert temp.stat().st_size<=20*2**20,'Handoff exceeds20MiB'
    os.replace(temp,dest)
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for line in sums.splitlines():
            sha,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==sha
    save(REPORT/'HANDOFF_RECEIPT.json',{'status':status,'zip':bind(dest),'files':len(files),'target_10_MiB_met':dest.stat().st_size<=10*2**20,'zip_integrity':'PASS','raw_audio_in_zip':False,'created_utc':now()})
    print(json.dumps(read(REPORT/'HANDOFF_RECEIPT.json'),indent=2))

if __name__=='__main__':main()
