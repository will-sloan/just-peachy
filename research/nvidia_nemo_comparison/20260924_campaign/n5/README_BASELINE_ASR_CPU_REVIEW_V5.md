# Independent Cortex-A76 diagnostic review

Purpose: verify the terminal V5 CPU-selection experiment against retained
V3 ARM64 and Windows evidence. This reviewer performs no model execution.
It checks all admission source/model/audio bindings, retained binary identity,
exact argv difference, complete decoded samples, Sherpa revision, output
fingerprint, final counts and resets, normal command closure and exact Windows
owners. A bounded hidden WSL command reads current Linux PID/start-ticks and
process groups; it does not contact the Pi or terminate any process.

Inputs: complete `local/n5/baseline-asr-cpu-v5` plus its hash-bound dependencies.
Outputs: a fresh private directory containing `LINUX_CLOSURE.json` and
`RESULT.json`, with an explicit nonempty-needs-retest or empty-persists status.
Both statuses are diagnostic and cannot accept the original ASR protocol or N5.
Raw transcripts remain in existing private evidence; the result exports only
counts, comparisons and hashes. CPU14 below normal, one thread, GPU off. Linux
identity inspection is capped at 20s. Code/README are bound in the audit.

Run only after the numerical host and supervisor have exited. PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B review_baseline_asr_cpu_v5.py --run G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-cpu-v5 --output G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-cpu-v5-audit
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B review_baseline_asr_cpu_v5.py --run G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-cpu-v5 --output G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-asr-cpu-v5-audit
```

An existing output is refused. Keep a failed audit and choose a fresh suffix if
further investigation is needed. A live owner or unexpected command/source
fails review; never bypass the check to manufacture closure or acceptance.
