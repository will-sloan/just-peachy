# Bounded S4.5 supervisor and closeout

The final package also indexes the post-supervisor audit fixtures at `staging/s45_final_audit_review/v1/FIXTURE_RECEIPT.json`. Run the final audit only after closure, using the inputs, outputs and PowerShell/Anaconda commands in `README_S45_FINAL_AUDIT.md`; the fixture receipt is not the actual audit result.

The initial S4.5 supervisor, `s45_execute.py` v1, launched on 2026-09-09 at 04:34:38 UTC and closed at 09:10:34 UTC with 232 canonical captures accepted. Its original code and blocked closeout evidence are preserved under `reports/S4_5/20260909T031300Z/checkpoint_232_20260909T091034Z`, indexed by `CHECKPOINT_RECEIPT.json`.

Incident02 occurred before playback for `S45_12_12`: the `GPO_PIN_PWM_DUTY` query timed out, followed by an `AEC_FIXEDBEAMSELEVATION_VALUES` restoration-readback timeout. The original failed restoration remains intact. The unchanged S4 restorer then verified exact exposed-state recovery at 09:12:44 UTC, without setting reapplication or audio playback. `INCIDENT_02_REVIEW.json` records the initial observation; `INCIDENT_02_CLOSURE_REVIEW.json` records the later recovery/closure review. They remain separate from the unchanged first-incident files.

The already-tested `s45_execute_v2.py` was first launched at 09:13:33 UTC to continue the same frozen bank and remaining eight canonical scenes. `RESUME_AFTER_INCIDENT_02.json` binds the original supervisor closure/checkpoint, recovery driver/receipt, v2 code and unchanged bank. Its capture-stage receipt is `supervisor/capture_20260909T091333_9e9dd0.json`.

Incident03 was the first failed **physical take**: `S45_12_16` reported `Finite capture timeout` despite retaining the full frame count and exact payload. It remains a failed, ineligible attempt; full payload does not override capture/telemetry acceptance gates. A restoration-readback timeout followed, and that v2 supervisor closed at 09:23:02 UTC with 235 accepted scenes and one failed physical attempt. The original take, failed restoration and `checkpoint_235_20260909T092302Z` remain preserved. Exact exposed-state recovery passed at 09:23:47 UTC, with only `PP_AGCGAIN` reapplied.

The same unchanged v2 supervisor resumed at 09:24:53 UTC. `RESUME_AFTER_INCIDENT_03.json` binds the second closure/checkpoint, recovery driver/receipt and unchanged v2/bank. Five intended scenes remained at that checkpoint, including the one allowed identical retry of `S45_12_16`; its resumed capture-stage receipt is `supervisor/capture_20260909T092453_f0a127.json`. `INCIDENT_03_REVIEW.json` and `INCIDENT_03_CLOSURE_REVIEW.json` preserve the initial and later evidence separately. Current acceptance, later stage receipts and final closure determine the eventual outcome. Neither resume resets the original deadline or global budgets. Do not launch another supervisor while the current resume or its owned children are active.

`HOST_STALL_OBSERVATIONS.json` records VSS/shadow-copy and Acronis-related activity around the two observed stall windows. This temporal association is correlation, not a demonstrated cause. Device/USB and other explanations remain unexcluded; these observations did not change services, backup settings, security configuration or the scientific policy.

Both versions start only after the real-noise scene bank has been frozen and independently validated. They run the canonical capture coordinator (then lower-priority optional references), offline capture analysis, frozen H2 dry plans, at most the accepted members of the predeclared 24 development sentinels on two outputs, and at most 24 dry controls. They verify restoration before releasing H2. No reserve task score, model selection, training or subsequent stage is started.

The supervisor launches only explicitly named Python children, redirects logs under `reports/S4_5/20260909T031300Z/supervisor`, prints a 20-second heartbeat and preserves the original eight-hour deadline. At the launch cutoff it requests finite cleanup; the capture owner and H2 runner enforce their own bounded stopping/cleanup. It never kills unrelated processes. Its own keep-awake request is scoped and restored. Closeout always attempts coverage, results and the failure-capable compact packager, recording errors instead of turning partial output into completion.

Inputs: verified frozen scene/source/noise/RIR bindings, fresh recorded XVF analog-output isolation confirmation, final S4 policies, current lifecycle-fix receipts and the existing recorder/model runtimes. Outputs: all canonical/optional capture manifests, protected analysis, sentinel/dry receipts, supervisor logs/checkpoints and one compact ZIP. Raw audio remains on the verified G: payload SSD. `s45_package.py` can also package current partial evidence without starting hardware/models.

V2 changes step bookkeeping and bounded error cleanup only. Process creation, the first invocation/PID status writes, monitoring and final receipt export share one cleanup path. If the owned child exits, the failure receipt retains the original error and actual exit code and closes the active PID field. A failure before any child is returned records `FAILED_NO_CHILD`. An unconfirmed exit records `UNVERIFIED_ACTIVE_CHILD`, retains the PID and blocks follow-up work/completion. Only checkpoint packaging can run while that marker exists. Cleanup waits at most 300 seconds for this invocation's child, preserves additional cleanup errors and does not terminate unrelated processes. It never hashes a potentially still-changing log as complete. If storage itself remains unwritable, the original error still propagates; persisted closure cannot be assumed.

The exact historical v1 source, its original test/readme bytes, the two reproduced bookkeeping failures, the v2 diff and the fix receipt are under `simulation/staging/s45_supervisor_fix/v2`. The main stage ordering is unchanged. V2 passed the model-free fixtures before its actual resumes. Those two simulated v1 bookkeeping defects remain distinct from the observed pre-playback device-control timeouts, failed finite capture and recovered restoration-readback failures. See `README_S45_CLOSEOUT_TESTS.md` for the model-free tests and their limits.

If another compatible v2 resume is needed after the current supervisor and every owned child have ended with verified cleanup, PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' s45_execute_v2.py
```

For that same conditional resume, Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s45_execute_v2.py
```

These commands resume compatible completed work within this run's original time window; they do not reset budgets or repeat accepted captures. A stale/unresolved child marker requires explicit inspection of the indexed child receipts before a new supervisor is allowed to proceed; elapsed time alone does not prove child closure. After the deadline, a later authorized run needs an explicit new timing overlay while preserving all frozen input identities. To create an analysis-only checkpoint ZIP, substitute `s45_package.py` for `s45_execute_v2.py` in the commands above. Package inputs are current local receipts and compact exports; outputs are Markdown/JSON/checksums in the report folder and `simulation/handoffs/S4_5_CHATGPT_HANDOFF_20260909T031300Z.zip`.

Final handoff completion also requires current verified plot artifacts and a completed report review. `s45_package.py` reads `plots/FIGURE_INDEX.json` with schema `jp_s45_figures_v1`, one to four unique local PNG entries, `maximum_figures: 4` and `no_reserve_task_plots: true`. It verifies the index's exact current `summary_metrics.json`, current `s45_results.py`, `plotted_data.csv`, and each indexed PNG path/hash. It includes only those indexed files; unrelated PNGs found in the directory are never added. Missing, stale or tampered plot artifacts are excluded from checkpoint ZIPs and recorded as `PENDING_OR_STALE` in `status.json` and `START_HERE.md`.

The coordinator must inspect the freshly generated indexed figures and then update only the existing top-level QA value in that index to:

```json
"visual_QA": "PASS_TOOL_INSPECTION"
```

This is a recorded visual-inspection result, not a status set automatically by the packager. No additional QA object is required. Preserve all existing index entries and bindings. Re-generating plots or changing the summary/result code requires another integrity check and visual review. A generic `PASS`, a missing field or the renderer's `PENDING_HUMAN_OR_TOOL_INSPECTION` does not satisfy final review.

Write nonempty UTF-8 `ANALYSIS_FINDINGS.md` and `WORKBOOK_FINDINGS.md` in the current report directory after reviewing fresh metrics. Their contents are inserted into the main report and proposed workbook update. The automatic package produced before these reviews remains a checkpoint even when capture/model counts are complete. After visual review and both findings files are ready, run only the packager again; this starts no hardware or models:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' s45_package.py
```

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s45_package.py
```

Check `status.json` fields `plot_artifact_validation`, `findings_validation` and `final_report_review_ready`, plus `HANDOFF_RECEIPT.json`, before final delivery. The original native H2/provenance, exact count, reserve and restoration requirements still apply. The report review is an additional completion condition, not a substitute for execution evidence.

The prior packager/README/test bytes, exact diffs and dated test receipt for these reporting-only gates are preserved under `simulation/staging/s45_package_review/v1`. All 31 closeout tests passed on 2026-09-09 in 1.536 seconds, using temporary files and fake children only; the packager was not executed against the active report during this change. See `README_S45_CLOSEOUT_TESTS.md` for test commands and scope.

The local artifact index also includes `staging/s45_package_review/v1/TEST_RECEIPT.json` and the report's `SPATIAL_INTERPRETATION_REVIEW.md` when present. The test receipt is embedded in the component test bundle; the spatial interpretation review is indexed locally only. This later index-only update has its own preserved before/diff and compile verification under `staging/s45_package_review/v1/index_only_followup`; it does not rewrite the earlier 31-test receipt or claim those tests were rerun.

## Packaged test provenance

The handoff's existing test_receipt.json now includes exact receipt bindings for the source, noise, H2 runner and reporting review, plus versioned reporting-readiness runs. Earlier pre-freeze tests are explicitly historical and do not claim later code bytes were identical. Model-free tests do not establish physical capture or model completion.

From the scripts directory above, run current bank, capture-acceptance, protected-analysis, coverage and closeout fixtures in PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest -v test_s45_bank test_s45_campaign test_s45_capture_analysis test_s45_coverage test_s45_closeout
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" -m unittest -v test_s45_bank test_s45_campaign test_s45_capture_analysis test_s45_coverage test_s45_closeout
```

These use temporary fixture outputs and print results/exit status; they do not open audio endpoints or run models. The recorded 2026-09-09T05:05:19Z readiness invocation passed 47 tests, with exact source hashes and stdout retained in reports/S4_5/20260909T031300Z/tests/reporting_readiness_20260909T050519Z. Results aggregation has its separate 17-test review receipt in staging/s45_results_review/v1. Future test runs should retain a new dated receipt rather than replacing these observations.

The local artifact index also binds the read-only 121-WAV/Word/S4 preservation checkpoint, measured resource forecast, reporting review and final resource/restoration receipt when available. A checkpoint is an observation at its recorded time, not a claim that capture or analysis had finished.

Pre-playback device-control interruptions are distinct from failed audio takes. Packaging inventories every hardware batch summary, reports recorded batch errors separately in the count table, and embeds the bound EXECUTION_INCIDENTS.json when present. A recovered setup failure remains disclosed even when all eventual capture receipts pass.

`FIX_RECEIPTS.json` includes every `RESUME_AFTER_INCIDENT_nn.json` in the current report, both known v2 resumes, their checkpoint/recovery bindings and corresponding initial/closure reviews. `HOST_STALL_OBSERVATIONS.json` is indexed locally, with its observation/inference limits summarized in the existing fix bundle. The historical first-incident files and earlier review stages are not rewritten. Batch-error and failed-take totals remain computed from actual hardware summaries and capture manifests: the incident03 checkpoint follows three interrupted batches and one failed physical take, while later totals must come from current receipts. The compact file-count cap is unchanged because these references enter existing bundles rather than new top-level packet files.

The prior packager and README bytes, exact reporting diff and dated compile-only receipt for this history/index update are preserved under `staging/s45_package_review/v2_execution_history`. No packager, hardware or model was run to apply this update; execution/scoring and completion-gate logic were unchanged. The maintained commands above still require verified closure before any additional supervisor launch.

The subsequent multi-resume/incident03 extension preserves its own four prior reporting files, exact diff and compile receipt under `staging/s45_package_review/v3_multiple_resumes`. It changes history, uncertainty wording and metadata indexing only. It does not replay a capture, rerun a model, rewrite the failed take or change any completion/acceptance rule.

The final review-index follow-up preserves the packager and this README, its exact diff and a dated compile/AST receipt under `staging/s45_package_review/v4_final_reviews`. `LOCAL_ARTIFACT_INDEX.json` binds `FINAL_SOURCE_COVERAGE_REVIEW.json`, `FINAL_SPATIAL_AND_TRANSPORT_REVIEW.json`, `H2_FIRST_NATIVE_REVIEW.json` and `H2_FINAL_NATIVE_REVIEW.json` only when each exists. Their full contents stay local; they are not added as separate ZIP members. An anticipated final native review is optional for this index and does not introduce a new completion gate. The first-native-job review alone does not establish all-job completion. The original count, provenance, restoration and final-review gates remain unchanged.

The source review retains the fourth CV reserve contributor's QC gap, limited short-clip and isolated-development support, partner/role coverage and the distinction between prepared and captured optional references. CMU ARCTIC `arctic_a/bNNNN` basenames can repeat across voices with different transcripts; normalized transcript prompt groups, not bare recording basenames, determine lexical split independence. These source limitations remain applicable even after all canonical captures are accepted.

For syntax verification only, from the scripts directory shown above, PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -c "from pathlib import Path; p=Path('s45_package.py'); compile(p.read_text(encoding='utf-8'), str(p), 'exec'); print('PASS: syntax compiled; packager not executed')"
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" -c "from pathlib import Path; p=Path('s45_package.py'); compile(p.read_text(encoding='utf-8'), str(p), 'exec'); print('PASS: syntax compiled; packager not executed')"
```

This reads only the packager source and prints its syntax result; it creates no bytecode cache or handoff and starts no hardware or model process. The recorded follow-up also compares protected completion, ZIP membership and scientific/execution-code identities against the preserved version. It does not relabel earlier fixture runs as tests of these later reporting bytes.

After 240 canonical captures, 48 output jobs and 24 dry controls complete with exposed-state restoration PASS, no mandatory execution resume is needed. The supervisor commands above and in `NEXT_PHASE_INPUTS.md` apply only to compatible incomplete checkpoints after verified closure. The 34 prepared optional references were deliberately skipped to preserve analysis time; they are not unfinished mandatory work or an instruction to launch another capture. Later reference work requires a separately authorized stage. Final audit, findings and plot review still govern handoff completion.

The local index also binds the verified native-review implementation and README plus `staging/s45_native_review/v2/TEST_RECEIPT.json` when present. These remain local references, without additional ZIP members or completion rules. This last resume-scope/index follow-up preserves its before files, exact diff and compile/AST receipt under `staging/s45_package_review/v5_final_resume_scope`. Use the syntax-only commands immediately above to verify the packager without running it.


Final closeout also indexes BANK_SIZE_REVIEW.json, the layout-only results revision receipts, and the storage-provider audit revision receipts when present. These local bindings preserve provenance without adding ZIP members or changing completion gates. The before/diff/compile observation is retained under staging/s45_package_review/v6_final_storage_and_plots. Main execution and analysis commands remain as documented above.

The local index also retains PID_REUSE_OBSERVATION.json and the strict service/timestamp audit revision receipts. This preserves the original blocked audit observation and distinguishes a later Windows service reusing a former model PID from a live campaign owner. See staging/s45_package_review/v7_pid_audit_history for the metadata-only index diff/compile receipt. Completion gates and commands are unchanged.
