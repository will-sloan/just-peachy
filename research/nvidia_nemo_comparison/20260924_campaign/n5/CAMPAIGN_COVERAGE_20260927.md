# Campaign coverage at the September 27 packaging checkpoint

This is a partial checkpoint. Use the current status selected in
HANDOFF_SELECTION_V6.json and START_HERE.md for the newest receipts.
September 28 correction: WORKBOOK_UPDATE_20260928.md and BACKEND_GUIDE.md
supersede older current-state descriptions; TitaNet is retired from further work. N1 is
complete within agreed offline scope; N2/N3 have accepted offline component
handoffs. N4 has no accepted new release configuration, so N5 retains only the
baseline. Prepared or individually tested components do not form an accepted
new application composition.

## Notes and interpretation

The original 73-item ledger, ../NOTE_COVERAGE.csv, is preserved with its N1
scope: 55 ACTUALLY_RUN, 10 IMPLEMENTED, six NOT_TESTED and two UNAVAILABLE.
ACTUALLY_RUN means the linked test ran, not that every behavior passed on CM5.
TESTED below has that same evidence-specific meaning. The supplied summary
contained 13 sections; full original notes were unavailable, so paraphrases must
not be described as verbatim source notes. Later component results supplement
the ledger rather than retroactively changing what an earlier test established.

| Requirement or hypothesis | Classification | Evidence and remaining boundary |
|---|---|---|
| Common 480×800 UI, separate mode/backend/tap, bounded pending/Unknown, stable suffix/span ownership, rescue controls | IMPLEMENTED; TESTED in N1 scope | N1_HANDOFF.md, N1_METRICS.json and note ledger. Windows lifecycle smoke adds actual baseline rendering/persistence; no physical touch or scanout latency claim. |
| All accepted saved scenes and O0/O1 gain/provenance | TESTED | 240 pairs/480 prepared mono files; prepared O0 already has +3 dB, runtime unity. Same physical-pass pairing retained; no new bank or denoising. |
| D1 diarization and E1 model-specific gallery evaluation | TESTED offline components | N2 FINAL_REVIEW and accepted handoff; research E/C/Q remains isolated from personal enrollment. No cross-encoder vector comparison. |
| A1 export/state parity and A2/A3 native streaming geometry repairs | TESTED in accepted N3 scope | N3_ACCEPTANCE.json, REPORT_N3.md and SOURCE_DECISIONS.md supersede the failed earlier queues. These are not full release/CM5 results. |
| Integrated full-bank numerical comparison | TESTED, modeled | N4 main 7,680/7,680 and modes 1,536/1,536 independently reviewed. These combine offline journals; they do not measure visible application latency. |
| Actual source-paced application panel | FAILED/PARTIAL | V10: 240 required, four started, two collected pending review, two failed, 236 unattempted. Do not merge previous partial runs. Matching V10 semantic/timing acceptance remains incomplete. |
| Sustained continuity, paired restarts and resource acceptance for new compositions | DEFERRED/NOT_TESTED | Six 20-minute continuity and 12 paired restart requirements are not satisfied; no newly accepted profile or measured CM5 tier. |
| Baseline Windows process lifecycle | TESTED, smoke only | Two real processes, caption-only/fast, one saved source, 31 rendered segments from three saved utterances; save/reopen/delete and isolated people sentinel passed. See BASELINE_WINDOWS_LIFECYCLE_CHECK_V1.json. |
| Per-build import/export, all mode changes and live-source simulation | IMPLEMENTED or existing tests, incomplete N5 coverage | N1 test evidence is reusable only for its frozen baseline source. The new smoke does not establish these paths; optional builds have no per-build acceptance. |
| Baseline packaging, activation/rollback helpers and failure guards | TESTED at helper scope | TEST_RECEIPT.json records 22 Windows and 22 local Linux helper checks, 31 bundle member hashes and wrong-target refusal. Local Linux is not ARM64 GUI execution; no Pi was contacted. |
| Native ARM64 build/ABI and malformed-WAV checks | TESTED at build/emulator scope | Six native artifacts and static ELF audit; eight invalid-WAV checks. Long-source A2 timed out in repeat and long-source A3 was unattempted. The separate 16-second A2/A3 six-case protocol passes (NATIVE_STREAM_SHORT_CHECK_V3.json), with A3 raw word end 160 ms past EOF. No full-stack or target-speed claim. |
| Baseline Sherpa C-API paired ASR probe | TESTED, emulated component parity only (Sept 28) | BASELINE_ARM64_CPU_RETEST_V2.json: explicit Cortex-A76, four cases with exact Windows finals/endpoints/resets, including resident fresh-repeat; eight malformed-WAV refusals. Default-CPU failures remain historical. Does not establish ARM64 Python/GUI, speaker, punctuation, install or full-bank paths. |
| Baseline plus several portable backend releases | PARTIAL | Baseline archive prepared; zero accepted new alternatives. Optional model storage estimate is not a runtime or release acceptance. |
| CM5 2-GB RAM, latency, storage, power, thermal and hardware integration | DEFERRED | Actual target is off. 32-GB nominal eMMC and 2-GB total RAM are targets, not measured fit. No 4/8-GB tier has measured CPU performance. |
| Noisy naming and adaptation hypotheses | EXPLORATORY; some DEFERRED | N2 metrics separate evidence availability and speaker discrimination from downstream gating/tracking. N4 modeled label counts do not isolate the cause of a particular visible misname. Actual integration failures prevent a general noisy-naming or neural-accuracy claim. Closed-roster/seat labels cannot certify adaptation truth. |
| XVF/USB controls, camera, BMI270 and pins | DEFERRED/UNAVAILABLE | Disabled/null profile fields remain. Exact firmware ABI and ARM64 host-tool licensing/build audit still required; no hardware was accessed. |

The reference population stays explicit: 156 complete nonoverlap scenes,
47 overlap scenes, 26 incomplete ambient references and 11 empty controls.
Complete-reference error metrics and incomplete-reference diagnostic coverage
must be reported separately. The 240-scene denominator is not reduced because
a case is difficult. MAIN_MODELED_RESULTS_V1.md and MODES_MODELED_RESULTS_V1.md
give the reviewed numerical interpretation; N4_PARTIAL_REPORT_20260927.md gives
the actual application failure and exact continuation boundary.

## Models, terms and target blockers

LICENSE_LEDGER.md and the accepted N3 MODEL_REGISTRY.json retain revision/date,
weight/code/tokenizer terms and older-exception evidence. D1 and A3 use OpenMDW
1.1; A1/A2 use their pinned NVIDIA model terms; older E1 TitaNet uses CC BY 4.0.
Baseline assets remain unchanged. No new license acceptance, paid service or
public weight redistribution is inferred from this checkpoint. X1 and unverified
standalone punctuation remain deferred. Model assets, private transcripts and
personal profiles are excluded from Git and the compact handoff.

The baseline ARM64 bundle has verified CPython 3.11 aarch64 wheels, but the
emulator's existing host Python is x86-64 and cannot exercise those extensions.
The C-API probe avoids that interpreter for ASR only. A complete compatible
ARM64 Python/Tk/runtime stack and the other component models still need execution.
The A1 portable application route and D1/E1 full application binding likewise
remain unvalidated. No placeholder launcher is labelled Pi-ready.

## Later device checks and unchanged limits

After the user reconnects the Pi: verify the actual host/key and 64-bit OS;
run the read-only storage preflight; verify, stage, health-check and explicitly
activate the baseline; start idle; use saved mono audio for each installed
backend, persistence, mode changes, switching and rollback. Measure real total
system RAM, resources and sustained captions before assigning a target tier.
WHEN_HARDWARE_ARRIVES.md lists the later separately authorized microphone,
XVF, touch, camera, IMU and button checks. The personal store stays outside
replaceable releases. Never infer completion from storage metadata alone.

No denoising, new capture, playback, human enrollment, training, physical CM5
validation or GPIO assignment ran. Packaging reserve begins September 28 at
02:48:19 UTC and the deadline is 14:48:19 UTC. Hourly follow-up continues until
offline completion or that deadline. Complete compute and LLM totals are not
exposed and remain unknown; measured command durations retain their own scope.
