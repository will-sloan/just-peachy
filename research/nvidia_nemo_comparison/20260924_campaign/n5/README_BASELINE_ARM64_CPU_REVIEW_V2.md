# Full ARM64 baseline retest review

Purpose: independently audit the completed Cortex-A76 full-protocol run. Inputs
are its ADMISSION/terminal/command/source records, exact original binary and
Windows reference, eight bound malformed-WAV fixtures and saved audio/models.
The unchanged strict baseline reader compares all four cases, final text,
source endpoint positions, reset counts, fresh-repeat state and closure.

Outputs: a fresh private `LINUX_CLOSURE.json` and `RESULT.json`, containing
counts and hash bindings rather than raw transcript text. The audit verifies
every admitted source, the sole CPU-argument difference, all ten command
closures, exact Windows owner absence, and a fresh hidden Linux PID/start-tick
and process-group census. The Linux check has a 20s cap; it neither terminates
processes nor runs models. Reviewer CPU14, one thread, below normal, GPU off.
No Pi, GUI, audio devices, downloads, new capture or training.

Only run after the supervisor has completed. PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B review_baseline_arm64_cpu_v2.py --run G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-arm64-cpu-v2 --output G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-arm64-cpu-v2-audit
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B review_baseline_arm64_cpu_v2.py --run G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-arm64-cpu-v2 --output G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-arm64-cpu-v2-audit
```

Fresh destinations are required. Audit failure is not permission to relax the
strict reader. Passing evidence qualifies only this emulated C-API baseline
ASR component condition; N4/N5, ARM64 Python/Tk/speaker/PnC and native CM5 tests
retain their separate acceptance requirements.
