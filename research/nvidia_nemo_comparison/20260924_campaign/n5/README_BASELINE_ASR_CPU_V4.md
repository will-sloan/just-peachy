# Baseline ARM64 CPU-feature diagnostic V4

Purpose: isolate whether explicitly selecting QEMU's Cortex-A76 changes the
empty-output failure seen in the retained V3 baseline recognizer. This is
emulated software diagnosis, not CM5 execution or performance qualification.
The Pi stays off. There is no build, model download, device access or training.

Inputs: fresh guarded_execution_v1.snapshot census and precheck, retained V3
ADMISSION, Linux model command and binary receipt, original Linux tool/runtime
inputs, Windows reference events, four model assets and the saved mono 16kHz
WAV. All are hash-bound. Reuse the exact ARM64 executable; the only inference
argv change is insertion of `-cpu cortex-a76`. Before inference, the pinned
QEMU must advertise that CPU. Source/sample fingerprint and nonempty output
are compared with the retained Windows reference. No precision, gain, model,
endpoint or decoder setting changes. No acceptance is inferred from completion.

Outputs: fresh private ADMISSION, host/WSL/Linux ownership records, CPU-help
and model command receipts, decoded-input/nonempty REVIEW and terminal RESULT.
The existing command helper enforces Linux process-group closure and preserves
timeouts. The host uses hidden WSL, not a visible console. Coordinator CPU14,
one Linux CPU/nice10, one numerical thread, GPU off; Windows reference is reused
without another model run. Caps: 600s model, 650s outer Linux timeout, 680s host
watch, 900s admission, 128MiB output, C:50/G:75GiB reserves. Expiry must precede
the unchanged 2026-09-28 02:48:19 UTC packaging reserve.

Only the existing campaign supervisor starts the host. Prepare a fresh
`BASELINE_C_API_CPU_CONTRAST_V4` CHECK and matching worker specification after
complete resource census and exact prior-owner closure. The CHECK binds this
driver/README/tests and every retained dependency; it fixes `qemu_cpu` to
`cortex-a76`. Do not reuse expired prechecks or manually mutate shared ledgers.

PowerShell (from N5):

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -m unittest test_baseline_asr_cpu_v4 -v
& $py -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-cpu-v4-worker.json
```

CMD / Anaconda Prompt (same explicitly pinned interpreter):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_baseline_asr_cpu_v4 -v
"%JP_PY%" -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-cpu-v4-worker.json
```

Worker argv: pinned Python, `-B`, absolute `run_baseline_asr_cpu_v4.py`,
`--precheck FRESH_CHECK --output FRESH_RUN`; cwd is N5. The internal Linux
`--admission` role must not be launched separately. The two model-free tests
check exact one-variable insertion and refuse altered CPU/ambiguous commands.
If output changes, repeat/state/nonempty and integrated checks are still needed
before qualification. If it stays empty, retain the result and stop this
CPU-selection hypothesis rather than retrying unchanged.
