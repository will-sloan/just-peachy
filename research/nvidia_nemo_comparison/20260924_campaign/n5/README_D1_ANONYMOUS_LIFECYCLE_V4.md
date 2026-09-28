# Stable-input Windows paired lifecycle qualification

Purpose: compare the fresh stable-ASR-input parent with its anonymous encoder
bypass counterpart using exactly CPUs 4 and 14, one numerical thread per model,
GPU off. README_STABLE_ASR_CHUNKS_V1.md documents the source repair and tests.
V3 completed all samples with identical activity/display/words and zero encoder
calls, but failed exact coarse timestamp parity by 20-80 ms; it stays failed.
V4 keeps the exact timestamp gate and fixes input fragmentation in both arms.

Inputs: accepted N3 ancestry, the two fresh derivative receipts, unchanged A2/D1
CPU model/runtime bindings and the original saved O0 WAV. First run parent;
candidate requires its passing result. Outputs: fresh precheck/admission,
private Tk inference/save/reopen/delete evidence, semantic fingerprints, exact
process lifetimes and result receipts. Actual inference uses a private Windows
desktop with unchanged user input desktop. No visible launch, audio device,
capture/playback, training, enrollment, personal store or Pi connection occurs.

Each arm retains 600-second/128-MiB limits, C50/G75 GiB reserves, fresh full
resource census and existing supervisor. CPU14 coordination shares the two-CPU
allowance. The application's 60-second drain, 240-second phase timeout,
sample completeness, native activity and exact caption/timestamp parity,
normal closure and save/reopen/delete checks are unchanged. A pass establishes
one-file engineering qualification, not N4 acceptance or sustained real time.

PowerShell from this n5 directory, after preparing and testing both derivatives:

```powershell
$d1Py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $d1Py -B -m unittest test_d1_anonymous_lifecycle_v4 -v
& $d1Py -B prepare_d1_anonymous_lifecycle_v4.py --name d1-anonymous-lifecycle-parent-v4 --arm parent
# Only after parent RESULT passes and its exact owners are absent:
& $d1Py -B prepare_d1_anonymous_lifecycle_v4.py --name d1-anonymous-lifecycle-candidate-v4 --arm candidate --reference-result 'G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-anonymous-lifecycle-parent-v4\RESULT.json'
```

CMD / Anaconda Prompt (existing environment, no installation or activation):

```bat
set "D1_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%D1_PY%" -B -m unittest test_d1_anonymous_lifecycle_v4 -v
"%D1_PY%" -B prepare_d1_anonymous_lifecycle_v4.py --name d1-anonymous-lifecycle-parent-v4 --arm parent
rem Only after parent completion and exact owner closure:
"%D1_PY%" -B prepare_d1_anonymous_lifecycle_v4.py --name d1-anonymous-lifecycle-candidate-v4 --arm candidate --reference-result "G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-anonymous-lifecycle-parent-v4\RESULT.json"
```

Every name must be fresh. Do not run the arms concurrently or modify bound
source. Thirteen refusal/accounting tests plus three fragmentation tests in
each derivative precede actual execution. Independent review is required after
both arms finish. Failed attempts remain intact; there is no relaxed tolerance.
