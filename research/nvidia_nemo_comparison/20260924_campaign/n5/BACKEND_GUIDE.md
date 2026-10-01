# Backend availability and interpretation

Latest user authority (October1,18:14:20Z): restore NeMo TitaNet alongside ReDimNet using the previous implementation, expose each supported backend/embedding/mode combination through an idle desktop shortcut, and finish the existing delivery by October2,14:14:20Z (10:14:20 Toronto). Keep Sherpa ONNX ASR and Nemotron-3 diarizer. Earlier TitaNet retirement statements are historical; new integration remains OPEN until executed. Separate embedding/gallery namespaces are mandatory. See FINISH_CHECKLIST F06/F07/F12/F23 and DEADLINE_AUTHORITY_V3.json.

Current review: September 28, 2026, packaging reserve. N1 is complete within its
agreed offline scope. N2/N3 have accepted offline component handoffs. N4 has
7,680 reviewed main and 1,536 reviewed mode comparisons from offline journals.
Its actual 240-cell application panel has two collected pending acceptance, two
failed and 236 unattempted. There are **zero accepted new release profiles**;
N5 is partial. Component results do not establish integrated release acceptance.

PACKAGING_GUIDE_CHECK_20260928_V1.json binds the receipts used here and fresh
verification-only checks of both stable-input Windows preview routes. The latest
checks opened no GUI and ran no inference; they verify previously qualified
local files. No new performance or lifecycle pass is implied.

| Composition | What is available | Remaining boundary |
| --- | --- | --- |
| A0/D0/E0: Sherpa Giga, Pyannote, ReDimNet, final-only punctuation | Preserved N1 Windows baseline, Start-N5-BASELINE.cmd, N5 saved-file Windows lifecycle smoke and private ARM64 baseline bundle. Sherpa C-API now passes four-case Windows/ARM64 parity and eight malformed-WAV checks under Cortex-A76 emulation. | Full ARM64 Python/Tk, speaker, punctuation, GUI, installation and native CM5 remain pending. Old empty-output failures are historical. |
| A0/D1/E0: Sherpa ASR with Nemotron 3 diarization and ReDimNet | Accepted offline D1 evidence, reviewed modeled combinations and retained user priority. | Its actual N4 cell exceeded the speaker drain limit. The A2 preview does not qualify this route; no accepted dedicated release is established. |
| A2/D1/E0: Nemotron English 600M ASR, Nemotron 3 diarization, ReDimNet | Start-N5-NEMOTRON-REDIMNET.cmd uses the stable-input derivative. Paired one-file anonymous-conversation render/save/reopen/delete lifecycle passed with actual ReDimNet execution. | Workstation-specific engineering preview. Automatic personal naming, full-bank application, continuity/resources and ARM64 full stack remain unqualified. Retaining embeddings alone does not qualify naming. |
| A2/D1 with anonymous encoder bypass | Start-N5-NEMOTRON-ANONYMOUS.cmd uses the matching tested derivative. No external speaker-encoder load/calls occurred in this mode. | Anonymous slots only; no persistent personal-name recognition. Same release/target limits as the ReDimNet preview. Catalog-required model assets remain on disk. |
| A1/D0/E0: Parakeet realtime EOU 120M | Accepted N3 component scope, modeled comparisons and one actual application cell collected pending acceptance. | N3 limitations remain scoped to their receipts. No accepted portable application release or full per-build qualification. |
| A3/D1/E0: Nemotron 3.5 ASR alternative | Three N3 GUI cases with two CPU cores; one-core failure/fragmentation retained. Its separate 16-second emulated ARM64 native ASR protocol now passes. | Main-bank WER was worse than baseline; no selected release. Full-source ARM64 protocol, full stack and source-aligned word timing remain unverified. |

Further TitaNet/E1 work is retired at the user's request; historical results,
assets and model-specific namespaces remain. X1 multitalker and other matrix
compositions are comparators or deferred work, not shipped alternatives.
Never reinterpret a gallery vector in another encoder's space.

## Native ASR checks and exact limits

BASELINE_ARM64_CPU_RETEST_V2.json supersedes the baseline empty-text diagnosis.
Explicit Cortex-A76 passes empty, short-tail, full source and resident repeat
with unchanged binary/models/audio, matching Windows text and endpoint/reset
behavior. This is emulated C-API ASR parity, not full Pi software or target speed.

NATIVE_STREAM_SHORT_CHECK_V3.json independently verifies A2 and A3 on the exact
first 16 seconds: empty, one-sample, short-tail, full prefix, repeat and forced
endpoint. Both close normally and repeat final text/word objects. A3's raw final
word ends 160 ms beyond the source; no clamping or truth-aligned timing pass is
inferred. The 44.695-second A2 protocol still timed out during repetition; the
corresponding long A3 run was unattempted. A shorter pass cannot clear those
gaps. QEMU command duration includes several cases and loading, not native Pi RTF.

## Existing Windows preview commands

Purpose: saved mono 16-kHz PCM16 preview with the shared 480x800 frontend.
Inputs: qualified local derivatives, models/runtime and optional prepared O0 WAV
with gain already applied. Outputs: captions/preferences in separate campaign
preview stores. These are local-workstation tools, not portable installers.

PowerShell, verification only:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
.\Start-N5-NEMOTRON-REDIMNET.cmd --check-only
.\Start-N5-NEMOTRON-ANONYMOUS.cmd --check-only
```

CMD / Anaconda Prompt, no environment activation required:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
Start-N5-NEMOTRON-REDIMNET.cmd --check-only
Start-N5-NEMOTRON-ANONYMOUS.cmd --check-only
```

When the user later chooses to open a preview, omit --check-only for **one**
launcher and close it normally before starting the other. Both use two logical
CPUs total, one native thread per model and GPU off. They open idle unless a
prepared --wav is supplied. README_D1_ANONYMOUS_PREVIEW_V1.md gives exact stores,
inputs and file invocation. Older caption/speaker previews remain available,
with their own historical qualification, not replacements for this stable pair.

## Later Pi installation and real-world validation

PI_RECONNECT_QUICKSTART_V1.md gives the two-archive baseline transfer, trusted
hashes, actual-device preflight, staging, activation and rollback. The Pi has
not been contacted. Its 32-GB nominal eMMC is not measured free space; the baseline
2.80-GiB additional-space estimate excludes optional backends and working RAM.
No measured 2/4/8-GB deployment tier exists.

Keep the shared GUI and explicit backend choice. Add models only after their
software route and actual storage budget pass; reuse identical assets and load
only the selected backend. Report errors without silent fallback. Personal data
stays external; incompatible galleries must be refused.

COMPONENT_PERFORMANCE_REPORT_20260927.md gives accuracy and processing metrics.
CM5_PARALLEL_DIARIZATION_FEASIBILITY_20260928.md separates measured original
workload from estimated savings. The 34-method catalogue holds proposals;
six delivery-clock modes are implemented/tested as a model-free foundation,
without application integration. Parallel diarizers and silence skipping are
not qualified production optimizations. Preserve candidates for
realtime_validation_v1/REAL_WORLD_HOLDOUT_V1.md: matched ungated controls,
original pacing, dense/natural/quiet/short/overlap/noisy speech, actual costs and
backlog. Sparse synthetic savings do not establish conversational or Pi throughput.

Current complete profile map and deployment status: completion_20261001/BACKEND_COMBINATIONS.md (beside MODE_GUIDE.md in the completion pack).
