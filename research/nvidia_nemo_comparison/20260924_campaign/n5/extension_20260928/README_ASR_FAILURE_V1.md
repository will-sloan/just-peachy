# A2 native ASR startup failure and recovery

Purpose: test two previously untested native Nemotron ASR failures on the immutable `ui-error-v1` Windows application: a nonexistent A2 model path and a mismatched runtime dependency hash. Each changes exactly one field in an isolated copy of `n3_runtime.json`. Model files and bound application source remain unchanged. This extends the actual private-desktop startup checks; it does not rerun the D1 failure or UI mode matrix.

Inputs: accepted N3 lineage, reviewed A2/D1/E0 saved-file lifecycle, latest UI error-priority source receipt, original mono 16-kHz PCM16 saved audio, native CPU assets, fresh resource census and extension window. Setup uses the actual backend/Advanced/recipe controls, anonymous conversation, balanced recipe and one native thread per model. All work shares logical CPUs 4 and 14; the coordinator uses 14. No device enumeration, microphone, playback, visible window, Pi, training, enrollment or downloads.

For each fault, the check requires a visible GUI ERROR with the selected backend retained, zero successful ASR/speaker/stream allocations, no retained native recognizer, zero recorded source samples and joined owned workers. Immutable fault/configuration/closure receipts are retained. After restoring the pristine runtime configuration, an explicit new transcript processes at least eight seconds from the saved source and Stop drains every accepted sample through ASR and D1. E0 calls and caption rows must occur. Explicit baseline rollback, controller/thread/lock closure, empty process job and exact PID creation identities are checked. These are functionality checks, not accuracy or timing benchmarks.

Outputs: fresh private `local/n5/prepi-20260928/<name>` and `<name>-precheck`, worker spec, admission, application journals and independent `<name>-REVIEW.json`. The builder produces fresh harness/child/preparation/review Python files and a hash derivation receipt in this directory, rejecting existing output files. Existing failed attempts are never overwritten. A terminal success is not independent acceptance. The reviewer rechecks all bound files, each exact one-field fault, failure reasons, zero allocation/sample evidence, recovery and owner closure.

Bounds remain 600-second admission, 240-second child phase, 285-second process bound, original 90-second stop/60-second inference gates, 128-MiB run cap, combined 1-GiB extension output ceiling and original payload/reservations/free-space floors. The extension guard refuses competing work and expired authorization.

PowerShell or Anaconda PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928'
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_asr_failure_v1.py
& $researchPython -B prepare_asr_failure_v1.py --name a2-asr-failure-v1 --backend nemotron_600m
# After terminal result and supervisor/child closure:
& $researchPython -B review_asr_failure_v1.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-asr-failure-v1' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-asr-failure-v1-REVIEW.json'
```

CMD or Anaconda Prompt (uses the existing environment directly; no activation or installation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_asr_failure_v1.py
"%RESEARCH_PY%" -B prepare_asr_failure_v1.py --name a2-asr-failure-v1 --backend nemotron_600m
"%RESEARCH_PY%" -B review_asr_failure_v1.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-asr-failure-v1" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-asr-failure-v1-REVIEW.json"
```

Run the builder only once. A later authorized repeat must use fresh run/review names; never repeat solely to create progress. No pass completes N4/N5 or validates Raspberry Pi performance.
