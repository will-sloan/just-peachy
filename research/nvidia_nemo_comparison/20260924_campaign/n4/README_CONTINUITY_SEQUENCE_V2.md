# Continuity assembly with a dedicated payload allowance

Use `continuity_sequence_v2.py` for actual preparation. V1's metadata and tiny
PCM tests passed, but its real assembly correctly stopped after 8.2 MiB because
the entry point reused an 8-MiB report-output guard. The failed V1 WAV prefix,
ADMISSION/PLAN/FAILED receipts and original code are preserved. Do not use that
prefix as a completed input or rerun the V1 entry point.

Purpose: retain V1's qualified selection, reference shifting, lossless PCM copy
and audio-only firewall while giving this audio artifact its own 64-MiB output
ceiling. The expected WAV is 38,616,902 bytes. A four-MiB metadata margin must fit
before writing. Guard checks retain C:50/G:75-GiB floors plus this allocation,
the shared 50-GiB limit plus six-GiB existing-worker reserve, 720-second helper
budget and the original packaging cutoff. No global policy or other guard is
changed. A new private output is mandatory; all failed attempts are preserved.

Inputs, selection rules, truthful eight-actor capacity, 27 whole sessions,
20:06.78 duration, fixed O0 tap, unmodified words/PCM and output files are described
in [README_CONTINUITY_SEQUENCE.md](README_CONTINUITY_SEQUENCE.md). The original
module remains imported unchanged; all its source/dependency bindings remain in
the V2 qualification. New outputs are private ADMISSION.json, PLAN.json,
CONTINUITY_O0.wav, INFERENCE_AUDIO_ONLY.json, EVALUATOR_TRUTH.json,
COPY_RECEIPT.json and RESULT.json or FAILED.json. The actual application receives
only the eight-field single-file job, never evaluator identities/text or joins.
No application, model inference, source execution, playback, microphone or Pi is
started. Successful input preparation is not a successful continuity run.

`probe_continuity_sequence_v2.py` reruns all ten V1 selection/reference/PCM checks
and four allocation regressions. These check acceptance of the legitimate WAV
size above the old report cap, rejection at 64 MiB, retained disk reserve,
deadline/time budget and whole-campaign allowance. The size/floor tests use
mocked observations and do not allocate dummy large files or alter the machine.
Outputs include immutable snapshots, ADMISSION.json, tests.txt, METADATA_PLAN.json
and RESULT.json/FAILED.json, binding the original failed assembly. Both helpers
use CPU14 and the existing helper lock; do not overlap controlled paced resource
measurements. Later candidate execution still needs the separate qualified
continuity runner, accepted shortlist and exclusive source/configuration review.

PowerShell probe, then actual preparation after qualification:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_continuity_sequence_v2.py" --output "$jpLocal\n4\continuity-sequence-probe-v2"
# Run only after CONTINUITY_SEQUENCE_CHECK_V2.json records the passed probe.
& $jpPython -B "$jpCode\continuity_sequence_v2.py" --output "$jpLocal\n4\continuity-sequence-v2"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_continuity_sequence_v2.py" --output "%JP_LOCAL%\n4\continuity-sequence-probe-v2"
rem Run only after CONTINUITY_SEQUENCE_CHECK_V2.json records the passed probe.
"%JP_PY%" -B "%JP_CODE%\continuity_sequence_v2.py" --output "%JP_LOCAL%\n4\continuity-sequence-v2"
```
