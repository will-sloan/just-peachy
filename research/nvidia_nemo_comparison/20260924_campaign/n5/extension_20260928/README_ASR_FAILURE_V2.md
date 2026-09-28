# Verify startup failure using the actual journal contract

Purpose: correct the V1 test's assumption that every session creates `audio_spool.pcm16`. This application's `PrototypeEngine._make_audio_journal` uses `MemoryJournal`. The failed V1 reached the intended missing-model error with zero model allocations and closed ownership, then failed because no spool file existed. It remains FAILED_PRESERVED, with its second fault and recovery unattempted.

V2 changes only evidence lookup: it identifies exactly one new finalized failed epoch per injected fault and checks its immutable `session_finalization_v3.json` and `session_summary.json`. Source/identity samples and ASR/speaker/source-time cursors must be zero; no live inference lane, open journal handle or finalization error is allowed. The independent reviewer rechecks those exact receipts. This strengthens the zero-audio assertion with the actual persisted counters rather than relying on the absence or size of an unused disk file.

Inputs, outputs, fault fields, recovery-prefix/baseline tests and resource/time bounds are otherwise unchanged from README_ASR_FAILURE_V1.md. Application source, native model/runtime files, inference/drain limits and prior evidence are unchanged. The builder creates fresh V2 child/harness/launcher/reviewer files and a parent/output SHA256 receipt. It syntax-checks generated code and refuses existing outputs. It performs no inference. A pass remains A2 Windows startup-failure/recovery scope only; N4/N5 and CM5 stay unaccepted.

PowerShell / Anaconda PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928'
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_asr_failure_v2.py
& $researchPython -B prepare_asr_failure_v2.py --name a2-asr-failure-v2 --backend nemotron_600m
# After terminal result and exact owner closure:
& $researchPython -B review_asr_failure_v2.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-asr-failure-v2' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-asr-failure-v2-REVIEW.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_asr_failure_v2.py
"%RESEARCH_PY%" -B prepare_asr_failure_v2.py --name a2-asr-failure-v2 --backend nemotron_600m
"%RESEARCH_PY%" -B review_asr_failure_v2.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-asr-failure-v2" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-asr-failure-v2-REVIEW.json"
```

Run the builder once. Use fresh names only for a justified later run. Saved audio, isolated application data and private desktop only; no target contact, capture, playback, training, enrollment or downloads.
