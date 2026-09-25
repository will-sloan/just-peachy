# Reviewed components to the complete N4 application-method bank

Purpose: `integrated_bank_plan.py` joins all 1,920 accepted ASR components and
960 components from each diarizer into the exact 16 x 480 matrix.
`integrated_bank.py` executes the unchanged publication and empty-safe Controller
methods using those sealed predictions, then reviews the complete lossless
outputs. Neither program loads a model or starts hardware, a GUI or the Pi.
Preparation, modeled method execution, scoring, paced application qualification
and stage acceptance remain separate statuses. No accepted integrated result
is claimed by this helper alone.

Before any bank result is examined, the primary 7,680-cell mode is fixed here as
`open_with_names`, using the existing primary 15-second open E rosters and
unchanged nominal configuration. This gives the full-caption open conversation
comparison across all compositions. The frozen 24-cell panel adds the other
four previously qualified modes: anonymous, enrolled names, selected plus
Unknown and selected closed (1,536 additional cases). The main mode's panel
cells already occur in the 7,680. No mode or gallery is selected from Q scores.
Forced labels and uncalibrated recognition remain explicitly unqualified.
Every D0/E1 row retains the failed C-scale qualification; nominal E1 remains an
engineering comparison and is not a calibrated accepted association profile.

Inputs: the passed terminal private full-bank ASR, D0 and D1 REVIEW.json files;
the immutable preparation-v2 audio-only manifest and 24-cell panel; frozen
16-entry application catalog and source receipt; original model-bound E gallery
bindings; actual N2/N3 runtime metadata; the 160-case publication and 38-case
empty-output qualification receipts. Each parent must be COMPLETE with the
exact source/audio/gain/profile/cache/runtime history contract. Terminal owners
must have exited. Queue READY_FOR_REVIEW is insufficient. Missing, duplicate,
foreign, failed or altered parents reject admission; they do not shrink the
required denominator. There is no fallback to historical smoke data in a plan.
The existing unavailable multitalker catalog placeholder is retained separately
with its reason and zero execution credit; it is outside the 16 core tuples.

The predictor receives only eight audio fields, a fixed mode/gallery and
verified component evidence. Reference words/activity, rooms and Q identities
are never predictor inputs. The runner reads full hash/CRC-verified gzip data,
uses actual D0 or D1 publication methods, and projects the resulting displays
through actual Controller methods. D1 waveform/query and native-slot checks
remain enforced. Independent scenes reset all method state. Successful empty
hypotheses remain successful; later scoring must count their missed words.

Outputs are private: immutable plan, ADMISSION.json with PID/creation identity,
per-cell full publication/projection gzip and Controller closure, per-cell
RESULT.json, atomic PROGRESS.json and a terminal RESULT.json. A failure preserves
all partial evidence and stops; remaining rows are NOT_TESTED. Resource stops
before a cell do not invent a failed prediction. A terminal reviewer requires
the exited exact owner, exact census and all result/expanded-artifact/closure
bindings. It writes PASS_REVIEWED_MODELED_METHOD_BANK_ONLY, with integrated
acceptance still zero. All transcripts, vectors and detailed events stay private.

The actual emit/consumer methods retain their prior scope: declared modeled
availability and 100-ms source cursor, with startup/model/journal/GUI paths
omitted. Full-session publication parity, actual first-visible timing, global
D0 speaker activity, scoring and complete-stack resources remain unqualified.
No modeled host timestamp can become a physical-latency or GUI metric.

Resource policy: CPU14 below normal, GPU disabled, one native math thread,
one OS-locked method-bank writer. At most 8 GiB per new bank and a conservative
70-MiB cell peak are admitted; all private campaign bytes plus the requested
allocation and 1-GiB contingency must fit the existing allowance (at most
50 GiB). Component banks must already be terminal and reviewed. C50/G75-GiB
free-space floors and the unchanged packaging cutoff apply before each cell.
The shared private inventory is rechecked every 128 completed cells against the
remaining admitted allocation and contingency. Prediction failures and stops
before prediction have separate failed/not-tested counts, covered by lifecycle
fixtures; failed evidence is never relabelled as an empty successful result.
The source, code, README and parent bindings are immutable once planned.
No deleting, overwriting, in-place resume, downloading or new inference occurs.
Preserve a stopped run and investigate before preparing a fresh derivative.

Tests (metadata fixtures cover the full 7,680/1,536 census; real saved evidence
covers all 960 D0 bindings, baseline, A3/D1/E1 and an empty-output prediction).
The fixture matrix is never admitted as production evidence. Outputs for the
small boundary tests are temporary private directories; no new audio is made.

PowerShell, using the existing interpreter:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpPrivate='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_integrated_bank.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
# Only after all three complete-bank reviews have passed:
& $jpPython -B "$jpCode\integrated_bank_plan.py" --scope main --asr-review "$jpPrivate\asr-full-bank-review-v1\REVIEW.json" --d0-review "$jpPrivate\d0-bank-review-v1\REVIEW.json" --d1-review "$jpPrivate\d1-full-bank-review-v1\REVIEW.json" --output "$jpPrivate\integrated-main-plan-v1.json"
& $jpPython -B "$jpCode\integrated_bank.py" run --plan "$jpPrivate\integrated-main-plan-v1.json" --output "$jpPrivate\integrated-main-v1" --allocation-gib 8
# After the exact runner process exits:
& $jpPython -B "$jpCode\integrated_bank.py" review --run "$jpPrivate\integrated-main-v1" --output "$jpPrivate\integrated-main-review-v1.json"
```

Command Prompt / Anaconda Prompt (same installed interpreter; no environment
installation or activation required):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_integrated_bank.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
rem Require all three passed full-bank reviews first.
"%JP_PY%" -B "%JP_CODE%\integrated_bank_plan.py" --scope main --asr-review "%JP_PRIVATE%\asr-full-bank-review-v1\REVIEW.json" --d0-review "%JP_PRIVATE%\d0-bank-review-v1\REVIEW.json" --d1-review "%JP_PRIVATE%\d1-full-bank-review-v1\REVIEW.json" --output "%JP_PRIVATE%\integrated-main-plan-v1.json"
"%JP_PY%" -B "%JP_CODE%\integrated_bank.py" run --plan "%JP_PRIVATE%\integrated-main-plan-v1.json" --output "%JP_PRIVATE%\integrated-main-v1" --allocation-gib 8
rem Wait for the exact runner to exit before reviewing.
"%JP_PY%" -B "%JP_CODE%\integrated_bank.py" review --run "%JP_PRIVATE%\integrated-main-v1" --output "%JP_PRIVATE%\integrated-main-review-v1.json"
```

For the separate four-mode panel, prepare with `--scope modes-panel` into a
fresh `integrated-modes-plan-v1.json`, run into `integrated-modes-v1` with a
separately admitted allocation (initially 2 GiB), and review to a new receipt.
Do not run both method banks concurrently or alongside controlled paced/resource
qualification. These shell examples run within their terminal; an automated
Windows launch must use the existing hidden-process mechanism and capture logs.
No visible terminal or app should be opened on the user's desktop.
