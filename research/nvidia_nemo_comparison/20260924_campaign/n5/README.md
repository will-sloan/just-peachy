# N5 packaging tools

`CM5_PARALLEL_DIARIZATION_FEASIBILITY_20260928.md` reports the user's
caption-first/parallel-worker proposal and two new full-bank workload/support
analyses. `README_D1_WORKLOAD_V1.md` and `README_D1_CAUSAL_SUPPORT_V1.md`
document inputs, outputs, PowerShell/CMD/Anaconda commands and nine passing
checks. These reuse existing evidence; no optimized model or Pi runtime has
been validated and no production audio gate was deployed.

Latest checkpoint: V18. Baseline Sherpa C-API ASR now passes the four-case
Windows/ARM64 parity protocol under explicit Cortex-A76 emulation. See
`BASELINE_ARM64_CPU_RETEST_V2.json` and `BASELINE_ASR_CPU_FINDINGS_V5.md`.
Reproduction, inputs and outputs are documented in
`README_BASELINE_ARM64_CPU_V2.md`, `README_BASELINE_ARM64_CPU_REVIEW_V2.md`,
`README_BASELINE_ASR_CPU_V5.md` and `README_BASELINE_ASR_CPU_REVIEW_V5.md`.
The V4 preflight attempt remains preserved with its own README.
`README_CHECKPOINT_V5.md` packages the updated partial report.

`ASR_GUIDED_DIARIZATION_AND_FINETUNING_20260927.md`
reports ASR-assisted false-activity diagnostics, language support, current-bank
fine-tuning suitability and practical CPU backlog. Reproduce the two read-only
analyses using `README_ASR_ACTIVITY_SUPPORT_V1.md` and
`README_FINETUNING_ASSESSMENT_V1.md`. Further TitaNet work is retired.

`README_STABLE_ASR_CHUNKS_V1.md` documents the tested deterministic journal
input repair. `README_D1_ANONYMOUS_LIFECYCLE_V4.md` and
`README_D1_ANONYMOUS_REVIEW_V1.md` cover the successful actual Windows pair.
`README_D1_ANONYMOUS_PREVIEW_V1.md` describes the ReDimNet and encoder-free
launchers, both qualified for one saved-file anonymous-mode lifecycle only.
V1-V3 attempts and their READMEs are retained historical evidence; latest V4
passes all audio/activity/caption/coarse-timestamp and normal closure gates.
N4/N5 and ARM64 qualification remain partial. The Pi has not been contacted.

`NEMOTRON_UTILIZATION_AND_NAMING_20260927.md` audits native activity, optional
embeddings, manual/automatic naming, offline modes, optimization and future
fine-tuning. `README_D1_ANONYMOUS_V1.md` documents a fresh anonymous-mode
derivative with 50 model-free tests (49 pass, one skip); its original source was subsequently tested and its failed attempts retained.
The fresh stable-input derivatives now pass paired qualification as documented above.

`COMPONENT_PERFORMANCE_REPORT_20260927.md` gives the complete component and
combination comparison, with detailed Nemotron diarization accuracy and CPU/CUDA
processing measurements. `README_COMPONENT_PERFORMANCE_V1.md` documents the
read-only aggregate reproducer. The verified 960-cell CPU timing breakdown
identifies native diarizer calls as the dominant measured component cost.

Windows A2 now has verified one-file lifecycle checks in caption-only and
anonymous-speaker modes, with normal closure of all four private GUI processes.
`README_NEMOTRON_WINDOWS_PREVIEW_V1.md` documents the two user-invoked launchers,
inputs/outputs and PowerShell/CMD/Anaconda commands.
`README_NEMOTRON_WINDOWS_LIFECYCLE_V1.md` documents the bounded test/admission
code. `NEMO_RESULTS_AND_INSIGHTS_20260927.md` explains the accuracy, omission,
short-turn, noise and resource tradeoffs. That earlier checkpoint was V16. These are
working engineering previews, not completed N4/N5 release qualification.

Purpose: prepare verified offline baseline and native ARM64 artifacts while
upstream comparisons run. N5 is PARTIAL, not release acceptance or campaign
closure. START_HERE.md is the operating index. README_ARM64.md covers the build,
static ELF audit and no-model QEMU loader probes.

The paired baseline C-API probe is documented in
`README_BASELINE_ARM64_ASR_V1.md`. Its Windows reference passed, while both
emulated ARM64 full streams returned empty text and failed the strict gate.
`BASELINE_ARM64_ASR_CHECK_V1.json` and `BASELINE_ARM64_ASR_FINDINGS_V1.md`
preserve the audit and narrow investigation boundary; no complete ARM64 pass
is claimed. Bound V1 sources and failed private outputs remain unchanged.

`baseline_asr_diagnostic_v2/README.md` documents the subsequent paired C-API
investigation. V2 built on Windows but stopped before inference when CMake
selected a different installed compiler location. The owned compiler helper
was closed and all evidence retained. `README_BASELINE_ASR_DIAGNOSTIC_V3.md`
documents a fresh derivative that verifies and reuses that completed build,
then measures one full stream per platform. It records decoded sample identity
and effective runtime configuration. Measurement completion alone is not an
ASR parity pass or release acceptance; consult the newest stage receipt.

`README_REVIEWED_HANDOFF_V2.md` covers the current compact handoff builder,
its explicit selection, current status input and fresh private ZIP/receipt.
It verifies every selected byte against the remotely backed-up Git commit and
reads back every ZIP member. `CAMPAIGN_COVERAGE_20260927.md` records scoped
coverage, and `RELEASE_MAPPING_20260927.md` distinguishes immutable software
from later validation evidence. These are partial checkpoint artifacts.

`README_BASELINE_WINDOWS_LIFECYCLE_V1.md` documents the new saved-file Windows
smoke, inputs/outputs, resource admission and PowerShell/CMD/Anaconda commands.
`BASELINE_WINDOWS_LIFECYCLE_CHECK_V1.json` records two passing real GUI process
phases with saved transcript persistence and isolated deletion. It is baseline
smoke evidence only. The separate ARM64 partial result and timeout are recorded
in `NATIVE_STREAM_MODELS_PARTIAL_V1.md`; neither result completes N5.

`pi_storage_preflight_v1.py` provides a separate read-only companion for the
preserved baseline ZIP. It takes the archive plus trusted SHA256 and explicit
space budgets, and writes a fresh JSON inventory/space report. Later on Linux
ARM64 it can also observe prerequisite metadata and actual install/data-root
free space, without creating those roots or installing anything. Purpose,
inputs/outputs and PowerShell, CMD/Anaconda and later Pi commands are in
`README_PI_STORAGE_PREFLIGHT_V1.md`. Its 11-test and real-bundle verification
receipt is `PI_STORAGE_PREFLIGHT_CHECK_V1.json`. It does not qualify ARM64 model
execution or change the immutable release. START_HERE.md and INSTALL_CM5.md now
include this step; inspect report statuses rather than relying on exit code.

`package_baseline.py` takes the existing N1 release receipt/archive, the original
hash-addressed model root, pinned ARM64 wheelhouse and publisher receipt. It
creates a fresh private ZIP plus a SHA-256/member receipt. It verifies all eight
models and 13 wheels before packaging and reads back every member. No original
file or personal store changes. The bundle is local-only because it contains
model weights. `verify_bundle.py` checks extracted member paths, sizes and hashes
before installation. `install-offline.sh` invokes the existing non-root ARM64
installer, using external data, versioned code/runtime and shared hashed models.

PowerShell from this campaign worktree:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py research/nvidia_nemo_comparison/20260924_campaign/n5/package_baseline.py --models C:/Users/amiri/JustPeachy/shared/models --wheelhouse 'G:/Just_Peachy_PROTO1/arm64 cp311 wheels' --wheel-receipt research/nvidia_nemo_comparison/20260924_campaign/n5/ARM64_WHEEL_PUBLISHER.json --output G:/Just_Peachy_N1/20260924_campaign/local/n5/releases/just-peachy-baseline-cm5-offline-v2.zip
& $py -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n5 -p test_n5.py -v
& $py prototype/release_tools/run_checks.py --output G:/Just_Peachy_N1/20260924_campaign/local/n5/release-tests-v3 --wsl
```

CMD/Anaconda Prompt, without activation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" research\nvidia_nemo_comparison\20260924_campaign\n5\package_baseline.py --models C:/Users/amiri/JustPeachy/shared/models --wheelhouse "G:/Just_Peachy_PROTO1/arm64 cp311 wheels" --wheel-receipt research/nvidia_nemo_comparison/20260924_campaign/n5/ARM64_WHEEL_PUBLISHER.json --output G:/Just_Peachy_N1/20260924_campaign/local/n5/releases/just-peachy-baseline-cm5-offline-v2.zip
"%JP_PY%" -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n5 -p test_n5.py -v
"%JP_PY%" prototype\release_tools\run_checks.py --output G:/Just_Peachy_N1/20260924_campaign/local/n5/release-tests-v3 --wsl
```

Actual baseline bundle is v1. Use a new filename for a repeat; do not overwrite
versioned evidence. The package verifier can be run as `PYTHON verify_bundle.py
--root EXTRACTED_BUNDLE`. The tests use temporary artificial byte fixtures,
including corruption, path traversal, duplicate paths and incompatible ELF;
they contain no audio. Install commands are in INSTALL_CM5.md.

`Start-N5-BASELINE.cmd` is a thin shortcut to ../Start-N1.ps1. From PowerShell,
run `& .\research\nvidia_nemo_comparison\20260924_campaign\n5\Start-N5-BASELINE.cmd`;
from CMD use the same path without `&`. It uses the earlier immutable installed
baseline and isolated manual-baseline data. Optional arguments are the existing
Start-N1.ps1 parameters. The output is an idle GUI and external user-selected
session data; do not run inference concurrently with admitted campaign jobs.

`package_checkpoint.py` is historical and contains early stage counts. Do not
rerun it for a current handoff. Its earlier archive and receipts remain preserved.
Use `package_reviewed_handoff_v2.py` with the explicitly selected current status;
the complete PowerShell/CMD/Anaconda commands, inputs and outputs are in
`README_REVIEWED_HANDOFF_V2.md`. Neither builder establishes stage acceptance.
