"""Package verified partial S6D evidence; see README_S6D_CHECKPOINT_HANDOFF.md."""
from __future__ import annotations
import argparse, csv, hashlib, json, shutil, zipfile
from datetime import datetime, timezone
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
R = SIM / 'reports/S6D/20260913T195357Z'
G = Path('G:/Just_Peachy_S6D/20260913T195357Z')
PACK = SIM.parent / 'Just_Peachy_S6D_Expanded_Capture_Pack_V2/Just_Peachy_S6D_Expanded_Capture_Pack_V2'

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def binding(p):
    p = Path(p).resolve()
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return dict(path=str(p), bytes=p.stat().st_size, sha256=h.hexdigest())

def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')

def table(p, rows, fields=None):
    rows = list(rows)
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    with p.open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)

def build(output, archive, protocol_review):
    output, archive = Path(output).resolve(), Path(archive).resolve()
    if not output.is_relative_to(R/'handoff_preparation_v1') or not archive.is_relative_to(SIM/'handoffs'):
        raise ValueError('Use a fresh handoff staging child and simulation/handoffs ZIP')
    if output.exists() or archive.exists():
        raise ValueError('Preserve existing packages; use new versioned paths')
    if (R/'physical_ledger.json').exists():
        raise ValueError('A physical ledger now exists. This zero-capture checkpoint builder must be updated, not used to conceal new evidence.')
    width_queue = read(R/'runner/width_queue_v1/QUEUE.json')
    width_index = Path(width_queue['jobs'][0]['expected_artifacts'][1]['path'])
    if width_index.parent.exists():
        raise ValueError('Width execution has started. This historical zero-width checkpoint builder is obsolete; update analysis before packaging.')
    appdocs = sorted((R/'handoff_preparation_v1/application').glob('*.md'))
    angledocs = sorted((R/'handoff_preparation_v1/physical_angles').glob('*.md'))
    if not 1 <= len(appdocs) <= 3 or len(angledocs) != 3:
        raise ValueError('Both bounded independently drafted handoff sections are required')
    protocol_review = Path(protocol_review).resolve()
    protocol_value = read(protocol_review)
    # The receipt is evidence, not an execution authorization. Root supplies the reviewed exact file.
    if not protocol_review.is_file():
        raise ValueError('Final independent scorer-protocol receipt required')
    native = read(R/'application/native_pilot_analysis_v1/RESULT.json')
    if len(native['cells']) != 12 or len(native['pairs']) != 13 or not all(p['all_raw_final_rows_equal'] for p in native['pairs']):
        raise ValueError('Pilot count/evidence changed; do not hardcode a replacement conclusion')
    if sum(len(p['raw_final_rows']) for p in native['pairs']) != 39:
        raise ValueError('Actual raw pair denominator changed')
    bank = read(SIM/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json')
    cases = bank['scenes']
    if len(cases) != 240 or len({x['case_id'] for x in cases}) != 240:
        raise ValueError('Exact canonical bank required')
    output.mkdir(parents=True)
    index = []
    def note(p, role):
        b = binding(p); index.append(dict(role=role, **b)); return b
    def copy(p, name, role):
        p = Path(p); target = output/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target); b = note(p, role)
        if binding(target)['sha256'] != b['sha256']:
            raise ValueError('Copied evidence changed')
    def md(name, text):
        (output/name).write_text(text.strip()+'\n', encoding='utf-8')
    now = datetime.now(timezone.utc).isoformat()
    disk = {drive: shutil.disk_usage(drive+':/').free for drive in ('C','G')}
    status = dict(schema='s6d-checkpoint-delivery.v1', status='INCOMPLETE_BLOCKED_CURRENT_STATE_HANDOFF',
        created_utc=now, run_id=R.name, whole_study_complete=False, newly_captured_scenes=0,
        physical_attempts=0, actual_charged_playback_seconds=0, width_predictions_completed=0,
        native_pilot_jobs_completed=12, native_pilot_pairs=13, raw_final_pairs_equal=39,
        prepared_additional_audio_files=75, disk_free_bytes=disk,
        unresolved=['Fresh XVF connected/powered and own analog outputs disconnected confirmation',
                    'C free space must reach50GiB; G floor75GiB and combined40GiB new-payload cap remain'],
        deadline_utc='2026-09-16T19:53:57Z', work_cutoff_utc='2026-09-16T19:08:57Z',
        note='This package supplies current evidence and a precise resumption contract. It is not a completed S6D study or a performance promotion.')
    save(output/'STATUS.json', status)
    md('START_HERE.md', f'''# S6D is INCOMPLETE — current-state handoff

Prepared {now}. No new physical beam captures or operational-width predictions exist. The only new native experiment completed so far is the12-cell diagnostic pilot. All75 additional microphone test-input files are prepared, but file construction and model-free tests do not establish physical or model performance.

The remaining execution is blocked by an unanswered fresh XVF setup confirmation and C: headroom. The latest package-time free space is {disk['C']/2**30:.2f}GiB on C and {disk['G']/2**30:.2f}GiB on G; required floors are50/75GiB. The XVF's OWN analog outputs must be disconnected. PC speakers/headphones/other microphones may remain connected. Seven installer/archive files totaling10.003GiB in Downloads were proposed for a verified move to G; no move was authorized or performed when this package was built.

Read S6D_REPORT.md for all eight requested answers, then EXECUTION_AND_RESUME.md and the two application/physical subdirectories. LOCAL_ARTIFACT_INDEX.json binds the local evidence. Machine-readable zero capture coverage is explicit; it is not failed-device data. Source files and README instructions remain local. The original full execution contract is included under source_contract; treat it as the authorized task scope, not evidence that it was executed.

Important reporting correction: the source-native analysis contains13 comparisons/39 paired final rows, not the14 earlier reported. All13 comparisons preserve raw word sequences. The original analysis is unchanged; the correction receipt is included.

No newly validated2–4 deployable profiles can yet be recommended. Historical defaults remain unchanged. New beam/focus/direction features have limited evidence classes stated here. The original72-hour run began2026-09-13T19:53:57Z and was not extended by the pause. Reserve45minutes before2026-09-16T19:53:57Z for closure. No S7–S9, training, RIR regeneration, firmware/driver change or default promotion is authorized by this handoff.
''')
    md('S6D_REPORT.md', '''# Current conclusions and the eight required answers

S6D remains incomplete. Mandatory physical collection, beam comparisons, operational-width scoring, retained-configuration full-bank native validation, balanced paced confirmations, continuous host correctness tests and profile qualification are outstanding. Missing results are not zero error, a hardware failure or a successful negative experiment. The current package makes these limits explicit so the next ChatGPT/Codex prompts can resume the same phase accurately.

1. **Angles.** The5/2/0-degree check changed evaluator intervals only; the original manual ±5-degree measurement metadata was preserved. The full historical cue evaluation still reports179 stable-wrong selected-direction occurrences across124 cases out of768 usable selected-direction turns. Narrower evaluation did not correct these. Fixed-prediction invariance checks reused1,920 existing predictions. Operational tracker widths2/5/10/20 are separately predeclared for C079/C120 on all240/both taps,3,840 cells, but that replay and its scores have not run. No operational-width performance conclusion is available.

2. **Listening and realism.** All240 playable mono pairs and transcript/reference links are available through the local listening index and compact CSV. There are480 prepared players, with raw and prepared source hashes verified. Listening access was statically verified; the browser tool blocked local-file preview, so browser playback itself remains unverified. Existing scene audio totals10,967seconds. The pacing audit records estimated20ms activity-support union1,851.6585seconds and overlap63.3415seconds, distinguished from2,830.589258seconds of whole probe-instance duration. These are synthetic/read-clip scenes, not natural uninterrupted dinner dialogue. Long concatenations of historical outputs inherit scene resets. New continuous input files are prepared, but no continuous XVF evidence has been captured.

3. **Selected voice.** The fixed-prediction T0/T1/T2 audit ran on960 original C088/C091 outputs, producing5,760 policy cells. It exposes substantial omissions. A15/O0 all-target mode retained576/2,500 target words versus1,485/2,500 in T0;191/280 target turns were never visible,13 unambiguous non-target words were visible, and173 mixed/unclassified visible words cannot be certified leak-free. B15/O0 selected-single retained11/162 versus85/162 in T0;12/17 target turns were never visible. Native cold/warm correctness and timing for retained modes remain unqualified. Filtering display metadata is not acoustic source separation.

4. **Direction.** Historical V1–V3 inputs lack independent current voice-to-direction binding. Their zero-arrow result is UNAVAILABLE, not evidence of successful music suppression. Current GUI/beam source implements stricter capture/route/stream/source-support and stale-event gates, with model-free tests. Useful target coverage, wrong-person arrow time, music-after-speech behavior and actual GUI timing still require new accepted evidence. Global speech detection does not identify which voice owns an angle.

5. **Physical/beam/enrollment.** Zero of240 scenes has new same-pass S6D six-output capture. Earlier read-only preflight observed XVF3.2.1 and its geometry/settings without setters/audio streams. MAIN/SCAN/QA routing, transport and telemetry have source/model-free checks; no route has yet passed physical S6D qualification. Prepared inputs comprise13 qualification/C files,60 E files and two900s continuous files. Device-domain enrollment comparisons, uninterrupted physical adaptation, scanner utility, observer effect and all BXR performance hypotheses remain untested. Exact-input QA will apply only to its own four-MIC echo pass; intervening processed-only MAIN/SCAN captures cannot claim bit-exact input recovery.

6. **Timing and ordering.** All12 predeclared native pilot jobs completed. The source analysis has13 comparisons, all39 paired final rows equal, and no missing observed final emission. Only two scenes/three utterances per cell were represented. C105 repaired versus matched C065 repaired had median added publication delay−0.261seconds and p95+0.398223seconds, missing the+0.25second target. The anonymous control's own repair repeat had p95+1.454seconds, demonstrating substantial timing variation. Neither a reliable speedup nor broad race elimination is established. The old C105 ordering flip did not recur in the two native C105 cells; controlled boundary regressions and actual GUI behavior are separate evidence. Independent GUI lifecycle/support tests passed; a later beam restart mutation was reproduced and fixed in a separate source epoch. Native name correctness/cpWER were not computed by the pilot timing analyzer.

7. **Profiles.** No new supported2–4-profile deployment set is qualified. Original C065/C067 anonymous and exact original C088 A15/C091 B15 controls remain preserved. GUI/focus/direction and beam prototypes are opt-in research features. Beam v3 has source/model-free review, not native/physical/GUI/CM5 efficacy. Actual calibration must use original disjoint C data, exact galleries/profiles/windows and accepted captured outputs; duplicate resolution remains independently disabled without sufficient evidence. No training, automatic default promotion or CM5 real-time claim occurred.

8. **Execution/cost/closure.** Completed work includes the listening/pacing audits, full historical angle rescore, fixed T/V audits, the12-cell source-paced native pilot, input materialization and software/protocol fixtures. The pilot ran2026-09-13T20:47:17Z to21:06:01Z; individual native jobs were approximately77–83seconds for44.7seconds of source, including startup. Maximum supervised process-tree RSS was498,827,264bytes and USS435,093,504bytes. Its exact owner lock and owned keep-awake state closed with receipts. PSS, target-CM5 performance and account-token percentages are unavailable. No current S6D experiment process, physical ledger or model restart was present at the latest status audit. The code supervisor is implemented/tested; automatic model continuation remains unqualified and must not be represented as installed. Adverse runs/tests and initial launcher/environment errors remain available locally.

These answers are a checkpoint, not a substitute for the remaining experiments. See the exact requirements and resumption order in EXECUTION_AND_RESUME.md.
''')
    md('EXECUTION_AND_RESUME.md', f'''# Resume the same S6D phase

1. Obtain the actual fresh XVF setup reply. Restore C>=50GiB, G>=75GiB and combined new-payload<=40GiB. The proposed7-file installer move is outside the experiment and needs the user's explicit approval. Preserve original files, sources and all evidence; no destructive cleanup.
2. Recheck deadline and exact input/source hashes. The reviewed3,840-cell offline width queue is already prepared: `{R/'runner/width_queue_v1/README_WIDTH_RUN.md'}`. Its actual CLI validate-only check passed; no predictions exist. Reuse that exact queue/approval and source epoch, preserve any interrupted namespace, and launch under runner v3 only. No direct helper invocation or hidden floor override.
3. Review the completed width index. The unchanged lower-API scoring plan and finalization-heartbeat protocol are prepared. Root must bind the actual completed index, exact scorer plan/protocol/source identities, pinned analysis interpreter and a fresh literal queue. Existing authorization templates are not executable approval. Score all3,840 new cells with1,920 exact parent/cue-off controls, all strata, adverse deltas and conditional cp-view uncertainty. Existing width25 shuffle diagnostics are context only. No native retention claim from policy-only evidence.
4. Physical admission is separate. Root first adopts the exact V4 plan with the real safety record and literal FIRST PRE-QA ONLY job. Its conservative charge is12.3413125seconds. Inspect actual sentinel, marker/frame/callback/MIC recovery and restoration evidence before advancing. Then admit the named qualification/observer/C controls, inspect real route/tail/level/observer behavior, and only then admit canonical bank batches. No speculative immediate all-bank launch.
5. Complete the required physical240MAIN,48SCAN+4matched repeats,60device-E and two900s uninterrupted DSP sessions, with QA and all failed attempts charged. The full forecast is427attempts/19,670.0340625charged seconds; including optional24hypothesis+8QA reserve it is459/20,952.9560625, leaving21attempts/647.0439375seconds. These are forecasts, not consumption. Firmware stops after8hours continuous use; bind actual reset/readiness age, reset between independent passes, never inside a conversation.
6. Use actual C captures for the separately admitted per-tap gain/selector calibration. Keep E/C/Q disjoint and all original A15/B15 identities/quality flags. Fresh beam waveforms require fresh model evidence. Evaluate BXR1–12 and at least3 justified additional nonredundant hypotheses with same-pass controls; collection alone is not evaluation. Screen the fixed48panel, confirm retained general methods on240. Preserve negative/unavailable findings and exact opportunities.
7. Complete required full-bank retained behavior confirmation where caches cannot prove equivalence; at least16balanced source-paced cases plus4event-sensitive repeats per retained condition/control; actual native name/direction/GUI events; two30minute host continuous correctness-scored sessions with drained consumers and bounded resources. These are distinct from the two15minute physical sessions. No oracle selected-person schedule.
8. Consolidate2–4 supported opt-in profiles only if justified. Preserve defaults; prepare pinned ARM64/CM5 workload/log retention without claiming desktop timing qualifies CM5. Update the complete handoff, including failures/unavailable branches. Preserve Revision20 and return only an insertion draft unless directly asked to edit Word. Stop at S6D.

The run's hard end remains2026-09-16T19:53:57Z; work cutoff with the45minute closeout reserve is19:08:57Z. If a mandatory branch is still blocked at a limit, preserve explicit incomplete status and a precise resume request. Never silently change denominators, drop conditions, relabel old evidence as new, or call this checkpoint completion.
''')
    for p in appdocs: copy(p, 'application/'+p.name, 'Application analysis and scope')
    for p in angledocs: copy(p, 'physical_angles/'+p.name, 'Physical and angle analysis and scope')
    copy(angledocs[0], 'ANGLE_ASSUMPTION_FINDINGS.md', 'Angle findings')
    copy(R/'listening/LISTENING_README.md','LISTENING_README.md','Listening commands')
    copy(R/'listening/COMPACT_LISTENING_INDEX.csv','COMPACT_LISTENING_INDEX.csv','240 playable pair pointers')
    copy(R/'pacing/PACING_AUDIT.json','PACING_AUDIT.json','Existing pacing audit')
    for name in ('STREAM_SUMMARY.csv','PAIR_SUMMARY.csv','ACQUISITION_SUMMARY.csv'):
        copy(R/'angles/eval_v1'/name,'metrics/ANGLE_'+name,'Full angle aggregate; evaluator-only')
    copy(R/'application/focus_replay_v1/AGGREGATES.csv','metrics/FOCUS_AGGREGATES.csv','All fixed focus policy aggregate conditions')
    copy(R/'application/ROOT_NATIVE_PILOT_COUNT_CORRECTION_V1.json','evidence/NATIVE_PAIR_COUNT_CORRECTION.json','13 not14 documentation correction')
    copy(R/'application/NATIVE_PILOT_FINDINGS_V2.md','NATIVE_PILOT_FINDINGS.md','Corrected native pilot findings')
    table(output/'NATIVE_PILOT_PAIRED.csv', [dict(left=p['left_job_id'],right=p['right_job_id'],comparison=p['comparison'],
        pairs=len(p['raw_final_rows']),raw_equal=p['all_raw_final_rows_equal'],publication_p50=p['additional_publication_delay']['p50'],
        publication_p95=p['additional_publication_delay']['p95'],publication_p99=p['additional_publication_delay']['p99'],
        consumer_p95=p['additional_consumer_delay']['p95']) for p in native['pairs']])
    predecl=read(R/'listening/HARDWARE_CASE_PREDECLARATION_V1.json')
    scan=set(predecl['P_SCAN6']['case_ids'])
    table(output/'CAPTURE_COVERAGE.csv',[dict(case_id=x['case_id'],required_MAIN=True,required_SCAN=x['case_id'] in scan,
        S6D_MAIN_captures=0,S6D_SCAN_captures=0,status='NOT_RUN_PREREQUISITES_PENDING',
        historical_input_ref='COMPACT_LISTENING_INDEX.csv; original historical captures are not new S6D evidence') for x in cases])
    physical=read(R/'physical_preparation_review_v2/CAPTURE_PLAN_PROPOSAL.json')
    save(output/'VERIFIED_STREAM_MAP.json',dict(status='PLANNED_SOURCE_CHECKED_NOT_PHYSICALLY_VERIFIED',actual_verified_S6D_routes=0,
        source_checked_route_contract=physical['route_contract'],physical_capture_count=0,
        distinction='MAIN and SCAN are separate passes sharing four processed streams. QA four-MIC echo is own-pass exact input evidence only.',
        actual_stream_identity_tail_qualification=None,proposal=note(R/'physical_preparation_review_v2/CAPTURE_PLAN_PROPOSAL.json','Withheld capture proposal')))
    eplan=read(R/'device_enrollment/DEVICE_ENROLLMENT_INPUT_PLAN_V1.json')
    table(output/'ENROLLMENT_DOMAIN_COMPARISON.csv',[dict(metadata_identity=x['metadata_identity'],roster=x['roster'],
        planned_device_passes=2,prepared_device_input_files=2,actual_device_passes=0,domain_comparison_status='NOT_RUN',
        identity_accuracy='',cpWER='',capture_gain_calibration='PENDING_C_ONLY_EVIDENCE') for x in eplan['people']])
    md('DISPLAY_AND_DIRECTION_MODES.md','''# Display/direction evidence

T0/T1/T2 fixed-prediction audits are executed but show the omissions/leakage limits in S6D_REPORT.md and application notes. V1–V3 historical association is unavailable because the independent current voice-to-direction support is missing. Zero arrows are not useful coverage. GUIv3 and beamv3 have accepted software/fixture scope only. No new native beam, physical, actual beam GUI, retained full-bank or CM5 performance is claimed.

Raw words remain preserved before optional punctuation/name/display filtering. Target selection must be by user-selected known identity, never reference geometry or oracle schedules. Current named identity, independent same-source voice support and direction validity need separate fresh evidence. Source/window identity, expiry, front/back ambiguity and at-most-two-person display limits remain explicit. See application notes and exact source manifests for commands and all pending native confirmation.
''')
    md('PER_BEAM_CAPABILITY_REPORT.md','''# Per-beam capability is unqualified

The opt-in beam engine implements one continuous auto-ASR decoder, shared serial model ownership and no more than two independent focused identity states. This is source/model-free evidence only. It does not splice ASR waveforms or instantiate six model stacks. C-only collection disables selectors; evaluation needs accepted capture provenance and calibrated thresholds. Duplicate resolution remains disabled without independent evidence. No scanning-beam, auto/focus/PP or dual-view quality/latency improvement has yet been measured in S6D.

VERIFIED_STREAM_MAP.json labels the planned source-checked routes as not physically verified. All planned actual comparisons are pending. The study has no new validated deployable beam profile.
''')
    md('BEAM_INTEGRATION_RESULTS.md','''# Beam integration results: NOT RUN

All BXR1–12 performance hypotheses remain untested. The implementation and synthetic tests do not fill the physical/model comparison matrix. At least three further nonredundant, recorded-data-motivated hypotheses remain to be declared and evaluated after capture; they must not be invented as completed experiments.

Required distinctions include same-pass auto controls, auto mono-ASR/beam identity, selected-beam association, duplicate ownership, complementary views, scanning subset, dynamic model compute, dedicated device E, gain/AGC, long state and fixed-mode controls. Build matched controls before observing outcomes. No new hypothesis wins, device-domain improvements or physical-state conclusions are claimed by this checkpoint.
''')
    md('CONTINUOUS_DSP_RESULTS.md','''# Continuous sessions: inputs prepared, experiments NOT RUN

Two exact900-second four-MIC inputs were built from36 full canonical45-second scenes plus4declared45-second zero blocks. Their output file hashes, headers and schedules were independently verified. This is input preparation, not continuous physical processing. No uninterrupted XVF session has run, and no reset-age/tail/adaptation/identity result exists.

The separate two30-minute HOST sessions are also outstanding. They require anonymous fallback and a naming/focus finalist, concatenated-reference correctness scoring, complete source consumption, drained event consumers, bounded queues and resource measurements. Concatenating historical device outputs cannot establish uninterrupted device adaptation. A source-paced pilot is not a30-minute session.
''')
    save(output/'TELEMETRY_OBSERVER_EFFECT.json',dict(status='PREDECLARED_NOT_MEASURED',observed_effect=None,
        design='Fixed expanded/fast-only/fast-only/expanded same-input MAIN repeats with identical DSP recipe/reset/guards',
        expanded_rates_hz=dict(fast=20,gain=2,slow=.2),standard_rates_hz=dict(fast=20,gain=0,slow=0),
        measured_comparisons=0,source=note(R/'physical_preparation_v2/QUALIFICATION_ANALYSIS_CONTRACT.json','Predeclared observer design'),
        no_equivalence_claim=True))
    md('RUNNER_AND_COSTS.md','''# Supervision and measured cost

The12-cell pilot used the exact original approved queue; completion, owner-lock closure and owned keep-awake restoration are preserved locally. Peak supervised RSS498827264bytes and USS435093504bytes are desktop observations, not a CM5 guarantee; PSS and user-plan/token percentages are unavailable.

Runner v3 was repaired and independently tested after a stop-file write-failure defect in an earlier epoch could release an unresolved hardware lock. It now durably guards hardware ownership before launch and requires actual matching restoration proof plus owner exit. Hardware owners are never force-killed. Exact width protocol21 tests and score protocol finalization/liveness checks are software evidence, not successful experiment outputs.

The code watcher uses bounded local observations and explicit action/command allowlists. Healthy unchanged state does not require repeated model interpretation. Automatic same-task model continuation was not qualified; manual RESUME_REQUEST fallback is explicit. Do not revive completed S6C monitoring or claim a scheduled model continuation was installed. Future full source consumption and event-consumer drainage must be checked semantically, not inferred from child exit.
''')
    save(output/'RUNTIME_AND_COMPLETENESS.json',dict(native_pilot_completed=12,native_pilot_comparisons=13,
        fullbank_retained_native_complete=False,balanced16_plus4_paced_complete=False,host30minute_sessions_complete=0,
        physical900second_sessions_complete=0,new_beam_native_jobs=0,default_promoted=False,CM5_tested=False,
        RSS_max_bytes=498827264,USS_max_bytes=435093504,PSS_bytes=None,account_token_usage=None,
        account_plan_percentage=None,automatic_model_continuation_qualified=False))
    copy(protocol_review,'evidence/INDEPENDENT_SCORE_PROTOCOL_REVIEW.json','Independent final scorer protocol source/synthetic review')
    for p,name in [(R/'runner/width_queue_v1/ROOT_QUEUE_REVIEW.json','WIDTH_QUEUE_REVIEW.json'),
        (R/'physical_preparation_review_v2/ROOT_PHYSICAL_SOURCE_REVIEW_V4.json','PHYSICAL_SOURCE_REVIEW.json'),
        (R/'device_enrollment/preparation_v1/ROOT_INPUT_REVIEW_V1.json','PREPARED_INPUT_REVIEW.json'),
        (R/'application/beam_native_interface_v3/ROOT_SOURCE_ACCEPTANCE.json','BEAM_SOURCE_REVIEW.json')]:
        copy(p,'evidence/'+name,'Source or preparation review; not physical efficacy')
    manifests={}
    for label,p in [('native_v3',R/'application/native_pilot_v3/MANIFEST.json'),
        ('beam_v3',R/'application/beam_native_interface_v3/MANIFEST.json'),
        ('gui_v3_review',R/'application/independent_direction_gui_v3/INDEPENDENT_DIRECTION_GUI_REVIEW_V3.json')]:
        manifests[label]=note(p,'Exact source epoch/profile/gallery manifest or review')
    save(output/'PROFILE_EPOCH_GALLERY_MANIFEST.json',dict(status='EXACT_SOURCE_POINTERS_NO_NEW_DEPLOYABLE_PROFILE_PROMOTION',
        epochs=manifests,original_controls=['B36 S6B epoch2','C065 N01','C067 N03','C088 original A15','C091 original B15'],
        actual_original_A15_count=15,actual_original_B15_count=15,
        later14person_gallery_substitution_forbidden=True,validated_new_deployment_profiles=[],
        capabilities=dict(beam_implemented=True,beam_model_free_tested=True,beam_native_tested=False,
                          beam_physical_tested=False,beam_GUI_tested=False,CM5_tested=False)))
    md('WORKBOOK_UPDATE.md','''# Revision20 insertion draft — S6D INCOMPLETE

Preserve XVF_Measurement_V20.docx unchanged. This is a suggested insertion, not an edited Word workbook. If applied later, insert under the S6D results area with light-yellow highlighting, preserving original styles, strikethroughs and user edits.

S6D checkpoint: all240 historical mono pairs are indexed; the5/2/0-degree evaluator sensitivity is complete and does not resolve the179stable-wrong selected-direction occurrences across124cases. Original manual±5-degree metadata remains unchanged. The operational2/5/10/20-degree tracker study is prepared but not executed.

The native diagnostic pilot completed12cells on two scenes;13verified comparisons/39paired final rows preserve raw words. An earlier count of14comparisons was a reporting error. The small C105 added-publication p95 of+0.398223seconds misses the+0.25second target; no broad latency or race-elimination claim is justified. Focus-policy omissions remain substantial. Historical voice-associated direction is unavailable, not successful zero-arrow suppression.

GUIv3, capture-ownerV4, runnerV3 and beam-interfaceV3 have source/model-free review.75additional microphone input files are prepared. Zero new S6D physical captures, zero new operational-width predictions and zero actual device-domain/continuous/beam integration results exist. Fresh analog-output setup confirmation and C>=50GiB are pending. Required full-bank/paced/host-long/physical/CM5 work and supported opt-in profiles remain outstanding; no default was promoted. See the current-state handoff and original S6D V2 contract before generating continuation prompts. Do not mark S6D complete.
''')
    copy(PACK/'Codex_S6D_Expanded_Beam_Capture_V2.md','source_contract/Codex_S6D_Expanded_Beam_Capture_V2.md','Original complete authorized execution scope')
    copy(PACK/'README_START_HERE.md','source_contract/README_START_HERE.md','Original pack interpretation and closure rules')
    copy(R/'runner/width_queue_v1/README_WIDTH_RUN.md','reproduction/README_WIDTH_RUN.md','Exact prepared width command; still storage-gated')
    copy(SIM/'scripts/README_S6D_CHECKPOINT_HANDOFF.md','reproduction/README_S6D_CHECKPOINT_HANDOFF.md','Package rebuild instructions')
    copy(R/'CONTINUE_S6D.md','CONTINUE_S6D.md','Latest detailed local checkpoint')
    for p,role in [(R/'application/native_pilot_analysis_v1/RESULT.json','All native pilot results'),
        (R/'angles/eval_v1/RESULT.json','Full angle sensitivity results'),
        (R/'application/focus_replay_v1/RESULT.json','Fixed focus evidence'),
        (R/'application/direction_replay_v1/RESULT.json','Unavailable historical V association evidence'),
        (G/'enrollment_continuous_inputs_v1/PREPARATION_RESULT.json','62prepared input provenance'),
        (R/'physical_preparation_v2/PREPARATION_RESULT.json','13qualification/C input provenance'),
        (R/'angles/width_scorer_plan_v2/ADAPTER_PLAN.json','Prepared unexecuted scorer matrix'),
        (R/'angles/operational_width_v1/PLAN.json','Prepared unexecuted operational-width matrix'),
        (Path('C:/Users/amiri/Downloads/XVF_Measurement_V20.docx'),'Current read-only master workbook'),
        (SIM/'listening/S45_all240_v1/index.html','Local listening player with transcripts/reference links')]:
        note(p,role)
    changed=[]
    for pattern in ('s6d*.py','README_S6D*.md','s6d_native/*.cs','s6d_native/*.ps1'):
        for p in sorted((SIM/'scripts').glob(pattern)):
            if p.is_file(): changed.append(dict(scope='Current maintained S6D helper; immutable execution epoch pointers are separate',**binding(p)))
    save(output/'CHANGED_CODE_INVENTORY.json',changed)
    save(output/'LOCAL_ARTIFACT_INDEX.json',index)
    files=sorted(p for p in output.rglob('*') if p.is_file())
    if len(files)+1>80:
        raise ValueError('Compact member ceiling exceeded')
    with (output/'CHECKSUMS_SHA256.txt').open('x',encoding='utf-8') as f:
        for p in files: f.write(binding(p)['sha256']+'  '+p.relative_to(output).as_posix()+'\n')
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(output).as_posix())
    if archive.stat().st_size>20*1024*1024:
        raise ValueError('Handoff exceeds20MiB; preserve artifact and revise curated contents')
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('ZIP CRC verification failed')
        if len(z.namelist())>80: raise ValueError('ZIP member count exceeded')
        for line in z.read('CHECKSUMS_SHA256.txt').decode().splitlines():
            sha,name=line.split('  ',1)
            if hashlib.sha256(z.read(name)).hexdigest()!=sha: raise ValueError('Member hash mismatch')
        for name in z.namelist():
            if name.endswith('.json'): json.loads(z.read(name))
        rows=list(csv.DictReader(z.read('CAPTURE_COVERAGE.csv').decode().splitlines()))
        if len(rows)!=240 or any(int(x['S6D_MAIN_captures']) for x in rows): raise ValueError('Capture denominator false')
        if len(list(csv.DictReader(z.read('NATIVE_PILOT_PAIRED.csv').decode().splitlines())))!=13: raise ValueError('Pilot pair count false')
    closure=dict(schema='s6d-checkpoint-external-delivery-closure.v1',status=status['status'],created_utc=now,
        zip=binding(archive),member_count=len(list(output.rglob('*')))-len([p for p in output.rglob('*') if p.is_dir()]),
        target10MiB_met=archive.stat().st_size<=10*1024*1024,CRC_and_member_hashes_verified=True,
        JSON_and_coverage_denominators_verified=True,whole_study_complete=False,
        physical_attempts=0,workbook_edited=False,raw_audio_included=False)
    save(archive.with_suffix('.DELIVERY.json'),closure)
    print(json.dumps(closure,indent=2))
    return closure

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--protocol-review',type=Path,required=True)
    a=p.parse_args();build(a.output,a.archive,a.protocol_review)
