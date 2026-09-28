# Baseline ARM64 protocol retest with Cortex-A76

Purpose: run the original four-case Windows/ARM64 component parity protocol
after the single-variable V5 diagnostic restored nonempty output with explicit
`-cpu cortex-a76`. This is emulated software validation; CM5 remains untested.

Inputs: original V1 failed protocol admission/command, exact retained V1 ARM64
executable and wheel libraries, original Windows reference events, four bound
model assets, same saved PCM16 WAV, eight retained invalid-WAV fixtures, fresh
complete guarded census, and a fresh scope
`BASELINE_ARM64_CORTEX_A76_FULL_PROTOCOL_V2` precheck. No rebuild or model
conversion. Only QEMU CPU selection changes for model execution. V1/V4/V5
attempts remain preserved. The corrected V5 CPU-help parser is reused.

Cases: empty stream, 1,281-sample tail, full 715,127-sample source, and full
source again using a fresh stream on the resident recognizer. The unchanged
strict `baseline_arm64_asr_review_v1.py` must verify source consumption, stream
closure, nonempty finals, exact raw text, endpoint sample positions/reset counts
and repeat parity against Windows. Eight malformed inputs must first reject
without loading models. Nonzero model exit remains a failure.

Outputs: fresh private ADMISSION/owners, CPU-help/malformed/model command
receipts, INPUTS binding the reused executable and exact argv difference,
COMPONENT_REVIEW and terminal RESULT. A passing component result does not
validate PnC, speakers, Python/Tk GUI, target RAM/thermals or N4/N5 completion.
Native Pi tests are deferred until reconnection.

The unchanged V5 host ownership pattern is retained with the original full-
protocol limits: 1,200s model, 1,450s outer Linux timeout, 1,470s host watch,
at most 1,800s fresh admission before 2026-09-28 02:48:19 UTC, 128MiB output,
C:50/G:75GiB free. CPU14 coordinator, one Linux CPU/nice10 and one math thread,
GPU off. Hidden WSL only. No download, device enumeration, playback or training.
Start only through the campaign supervisor after exact prior-owner closure.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -m unittest test_baseline_arm64_asr_review_v1 test_baseline_asr_cpu_v5 -v
& $py -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-arm64-cpu-v2-worker.json
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_baseline_arm64_asr_review_v1 test_baseline_asr_cpu_v5 -v
"%JP_PY%" -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-arm64-cpu-v2-worker.json
```

Worker argv uses pinned Python, `-B`, absolute `run_baseline_arm64_cpu_v2.py`,
`--precheck FRESH_CHECK --output FRESH_RUN`, cwd N5. Internal Linux admission
mode is host-owned and must not be started separately. Existing outputs are
refused. Do not weaken the original reader or substitute transcript similarity
for exact state/endpoint parity.
