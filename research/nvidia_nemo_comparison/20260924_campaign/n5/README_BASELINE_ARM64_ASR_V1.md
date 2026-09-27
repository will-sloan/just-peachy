# Baseline ASR: Windows versus emulated ARM64 component

Purpose: execute the retained Sherpa baseline ASR under QEMU using the C API
already included in the publisher-verified ARM64 core wheel. Compare it with
the same 1.13.4 Windows Python binding on exactly the same saved input. This
does not require a new download, model conversion, Python ARM64 installation,
microphone, playback or Pi connection.

The fixed configuration uses the existing INT8 encoder/joiner and FP32
decoder/tokens, mono 16 kHz, 80 features, greedy search, four active paths,
zero blank penalty, and endpoint thresholds 2.4/1.2/20 seconds. Pushes contain
1,600 samples (the baseline's 100-ms journal read), and final drain adds the
baseline's 0.66 seconds of zero padding. Both sides use one ASR thread for
the admitted resource budget. This is a declared component condition, not a
new selected application profile or an assertion that every recipe uses one
thread. The prepared O0 WAV already includes its gain; gain stays unity.

Cases are empty stream, the first 1,281 saved samples, full saved source, and
the same full source in a fresh stream on the resident recognizer. Compare
raw final text, endpoint positions in source samples, reset counts and final
flush. The second full stream must match the first. No punctuation, token
timestamps, speaker identity, GUI, CM5 resource tier or performance is inferred.

## Code and evidence

- `baseline_arm64_asr_v1.cpp`: bounded RIFF reader and actual Sherpa C-API
  recognizer/stream ownership. The RIFF helper is derived from the preserved
  native-stream harness. Eight malformed-WAV cases must reject before models
  are loaded. Source length is bounded to 1,281–960,000 frames.
- `baseline_asr_reference_v1.py`: same four cases through the Windows binding,
  saved PCM16 input only, no frontend or device imports. A registered owned
  child runs on a private desktop without displaying anything. Outputs are
  private events and a strict-reader result; startup errors have a separate
  preserved ERROR receipt.
- `baseline_arm64_asr_review_v1.py`: rejects truncated/extra/duplicate/nonfinite
  records, changed configuration, case order, incomplete delivery/closure,
  resident-state mismatch and cross-platform transcript/endpoint mismatch.
- `run_baseline_arm64_asr_v1.py`: verifies the pinned wheel and exact three
  members, extracts only two shared libraries and the C header, cross-compiles
  generic armv8-a, verifies ELF identity, runs eight input refusals, then runs
  QEMU and compares the complete outputs. Uses the existing pinned Arm GNU
  12.3.rel1 compiler/sysroot and QEMU. No package install or binfmt change.
- `run_baseline_arm64_asr_host_v1.py`: existing-supervisor child; owns the
  Windows reference job, waits for its normal closure, then starts hidden WSL.
  Exact PID/creation and Linux process/start-tick receipts preserve ownership.
- `test_baseline_arm64_asr_review_v1.py`: model-free refusal fixtures only;
  synthetic text is clearly a parser fixture, not measured ASR evidence.

Input CHECK JSON has scope `BASELINE_ASR_WINDOWS_ARM64_COMPONENT_PARITY_ONLY`,
fresh UTC admission/expiry (at most 1,800 seconds, before packaging reserve),
128-MiB allocation, full resource census, exact closed prior owners, every
source dependency, prepared WAV hash/frame count, four model bindings in
encoder/decoder/joiner/tokens order, pinned wheel/member hashes and previous
verified compiler/QEMU input receipt. Model records have `component_id` and
`asset` binding. Start within 120 seconds via the existing supervisor only.

Output is a fresh private `local/n5` run with immutable ADMISSION, Windows
REFERENCE_OWNER and job LIFETIME, reference events/result, LINUX_ADMISSION,
WSL_OWNER, Linux INPUTS, extracted private wheel members, executable, compiler
and malformed-input logs, model output, COMPONENT_REVIEW and terminal RESULT.
Every process exit is separate from component acceptance. Failures are retained.
The unchanged Windows application/release is neither edited nor replaced.

Windows coordination uses CPU14; reference uses CPU4 with Below Normal priority
and a 180-second owned-job timeout. It exits before Linux work begins. Linux
uses nice10 and one allowed CPU, one numerical thread and no GPU. Compilation
is limited to 120 seconds, each malformed case 15 seconds and the whole native
four-case run 1,200 seconds. A 1,450-second outer Linux timeout and 1,470-second
Windows wait bound contain failures. Cancellation requests target only the
owned process group/job. A terminated WSL launcher alone is never Linux closure
proof. C:50/G:75-GiB floors and the 128-MiB output cap remain monitored.
The 8-GiB QEMU address-space ceiling is containment, not a CM5 RAM measurement.

## PowerShell

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -m unittest test_baseline_arm64_asr_review_v1 -v
# Only after a fresh complete census and matching CHECK/worker spec:
& $py -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-arm64-asr-v1-worker.json
```

The worker spec argv is the absolute qualified Python, `-B`, absolute
`run_baseline_arm64_asr_host_v1.py`, `--precheck`, the fresh CHECK path,
`--output`, and the fresh run path. Its cwd is this N5 directory. Internal
reference/Linux entry points must receive the host's matching ADMISSION;
do not launch them alongside another allocation. Repeat in new versioned
paths with fresh admission; do not overwrite existing failed or passing runs.

## CMD / Anaconda Prompt

No activation is required; use the explicit interpreter.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_baseline_arm64_asr_review_v1 -v
rem Only after fresh admission:
"%JP_PY%" -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-arm64-asr-v1-worker.json
```

A passing result is **emulated ASR component parity only**. It does not close
N4/N5, create a new accepted backend, validate target installation/Python/Tk,
or establish physical audio/touch/RAM/latency. All such checks retain their
separate incomplete/deferred statuses. Keep events, models and libraries out
of Git; publish only small code, manifests and redacted status receipts.
