# Integrated method bank with manifest-bound D1 clocks

Purpose: propagate the qualified native-clock review through the actual D1
publication boundary without changing immutable earlier code or evidence.
`component_d1_replay_v2.py` replaces only its event-scanner import with
`review_d1_frame_clock_v3`. `application_publication_v2.py` imports that replay
derivative. `integrated_bank_v2.py` imports those publication methods and
`integrated_bank_plan_v2.py`, whose code manifest includes both original and
derivative files. The planner also requires INTEGRATED_BANK_CLOCK_CHECK_V2.json.
The declared matrix, primary gallery/mode, source methods, modeled clocks,
prediction inputs, storage/CPU limits, failure preservation and acceptance
scope remain those in README_INTEGRATED_BANK.md. No inference or GUI is started.

The first derivative probe exposed one publication artifact above the original
32-MiB serialization cap. That failed attempt and its source snapshots remain
in `local/n4/integrated-bank-clock-v2-probe-v1`. `method_artifact_v2.py` uses the
same exclusive gzip writer and byte-for-byte round-trip verification with a
fixed 64-MiB expansion cap. Its reader enforces the declared/actual expansion,
compressed and expanded hashes and gzip CRC. No events or history are dropped.
The runner reserves a conservative 140-MiB cell peak instead of 70 MiB; total
bank allocation, free-space floors and shared allowance still apply. The source
publication and Controller history limits remain unchanged. Downstream scoring
must explicitly use this bounded reader in a qualified derivative; the original
32-MiB scorer must not be used for larger artifacts or silently loosened.

Inputs: complete passed ASR/D0 reviews and the passed D1 v3 review, all original
saved component files, immutable source/catalog/gallery, 480 audio-only jobs
and the unchanged 24-cell mode panel. Outputs: a fresh private 7,680-row main
plan, execution ADMISSION/PROGRESS/RESULT and lossless per-cell publication and
Controller artifacts, then a separate complete-bank review. The four additional
modes use a separate 1,536-row plan. Accepted integrated credit stays zero until
the required scoring, actual paced application/GUI/resource and acceptance work.

Tests retain the original full census, corrupted-parent, exact owner, actual
baseline/A3-D1-E1, empty hypothesis and resource/failure lifecycle cases. The
qualification also reruns both recorded clock-failure clips with E0 and E1
through the complete prediction boundary, saving full private outputs. Those
four boundary checks are development evidence, not main-matrix credit.

PowerShell (existing interpreter, no installation):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
Set-Location $jpCode
& $jpPython -B -c "from metric_process import pin; pin(); import unittest; unittest.main(module=None)" test_integrated_bank_v2 -v
& $jpPython -B "$jpCode\integrated_bank_plan_v2.py" --scope main --asr-review "$jpLocal\asr-full-bank-review-v1\REVIEW.json" --d0-review "$jpLocal\d0-bank-review-v1\REVIEW.json" --d1-review "$jpLocal\d1-full-bank-review-v3\REVIEW.json" --output "$jpLocal\integrated-main-plan-v2.json"
& $jpPython -B "$jpCode\integrated_bank_v2.py" run --plan "$jpLocal\integrated-main-plan-v2.json" --output "$jpLocal\integrated-main-v2" --allocation-gib 8
# Only after the exact runner exits:
& $jpPython -B "$jpCode\integrated_bank_v2.py" review --run "$jpLocal\integrated-main-v2" --output "$jpLocal\integrated-main-review-v2.json"
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
cd /d "%JP_CODE%"
"%JP_PY%" -B -c "from metric_process import pin; pin(); import unittest; unittest.main(module=None)" test_integrated_bank_v2 -v
"%JP_PY%" -B "%JP_CODE%\integrated_bank_plan_v2.py" --scope main --asr-review "%JP_LOCAL%\asr-full-bank-review-v1\REVIEW.json" --d0-review "%JP_LOCAL%\d0-bank-review-v1\REVIEW.json" --d1-review "%JP_LOCAL%\d1-full-bank-review-v3\REVIEW.json" --output "%JP_LOCAL%\integrated-main-plan-v2.json"
"%JP_PY%" -B "%JP_CODE%\integrated_bank_v2.py" run --plan "%JP_LOCAL%\integrated-main-plan-v2.json" --output "%JP_LOCAL%\integrated-main-v2" --allocation-gib 8
rem Wait for the exact runner to exit.
"%JP_PY%" -B "%JP_CODE%\integrated_bank_v2.py" review --run "%JP_LOCAL%\integrated-main-v2" --output "%JP_LOCAL%\integrated-main-review-v2.json"
```

Never duplicate an active runner. Automated starts use the existing supervisor
with an explicit argv/cwd worker JSON and a CPU14-pinned caller; its host and
child use CREATE_NO_WINDOW. Preserve the prior supervisor receipt before using
its `phase --phase replay --stage N4` and `start --spec` interfaces. Read the
new bank's own PROGRESS.json: shared panel_progress.json may describe an older
component bank. Do not mutate the shared ledger manually.

For the later mode panel, use `--scope modes-panel`, fresh
`integrated-modes-plan-v2.json` / `integrated-modes-v2`, initially 2 GiB and a
separate terminal review. Run one bank at a time; no overlap with controlled
paced/resource measurements. Keep private logs/transcripts/audio/models out of
Git, preserve both failed D1 reviews, and do not contact the powered-off Pi.
