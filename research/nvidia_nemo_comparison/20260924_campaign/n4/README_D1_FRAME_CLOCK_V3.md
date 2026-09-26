# D1 native frame and query event-clock review

Purpose: review the completed 960-cell D1 bank with the exact native frame
interval declared by its recorded runtime manifest. The frozen runtime emits
`frame_end * seconds_per_frame` and passes the same interval to ActivityTimeline.
Its float32 representation of 10 ms is 0.009999999776482582 seconds. The original
reviewer substituted decimal 0.01; accumulated endpoint error exceeded its
unchanged one-microsecond comparison tolerance on longer scenes.

`review_d1_frame_clock_v3.py` is a derivative of the original event scanner.
It admits only exact decimal 0.01 or its IEEE float32 representation, requires
every frame interval to equal the manifest, and uses that value for native
endpoints, overhang and the actual frozen ActivityTimeline. Other clock
tolerances, query waveform hashes, sample counts, probability/vector checks,
short-turn denominators and pairing requirements are unchanged. No source
events, predictions, model settings, historical reviewer or failed evidence
are edited. This is a reviewer correction, not new neural inference.

The v2 full review also exposed a distinct event-clock assumption: the actual
application emits an embedding event at its native window end, while its
payload records the rounded half-open waveform samples. V3 preserves both:
call/research event clocks match the reconstructed native window end; payload
support, clean intervals and waveform hashes still match exact integer samples.
The same one-microsecond tolerance is retained, and the research event clock is
now checked independently. Failed original and v2 attempts remain preserved.
The v2 qualification established its tested scope; it did not pass production.

`review_d1_full_bank_v3.py` retains the original full-bank admission, source,
runtime, cache and exact exited-owner checks. It records and rechecks both
original and derivative code bindings. Inputs: terminal `d1-full-bank-v1`,
saved mono audio, complete native logs and unchanged source/model receipts.
Outputs: a new private REVIEW.json and aggregate REDACTED_REVIEW.json with
PASS_D1_FULL_BANK_COMPONENTS_ONLY, 960 components, 480 paired files and zero
integrated acceptance. Preserve the failed execution in
`local/n4/d1-full-bank-review-execution-v1` and `-v2`, and choose a fresh output directory.

The tests use the actual frozen D1 application loop with stub models, including
a 55-second float32 interval fixture and a 65-second late-speech query fixture reproducing the original failure. They
reject manifest/interval drift, endpoint/overhang/source-clock corruption and
retain the original event-integrity and complete-bank census tests. Synthetic
fixtures are not production evidence. No devices, model inference or GUI start.

PowerShell (existing environment, no installation):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
Set-Location $jpCode
$env:JP_N4_SOURCE='G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-complete-journal-v1\prototype'
& $jpPython -B -c "from metric_process import pin; pin(); import unittest; unittest.main(module=None)" test_d1_frame_clock_v3 test_review_d1_full_bank_v3 -v
& $jpPython -B "$jpCode\review_d1_full_bank_v3.py" --run "$jpLocal\d1-full-bank-v1" --output "$jpLocal\d1-full-bank-review-v3"
```

Command Prompt / Anaconda Prompt (same installed interpreter):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
cd /d "%JP_CODE%"
set "JP_N4_SOURCE=G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-complete-journal-v1\prototype"
"%JP_PY%" -B -c "from metric_process import pin; pin(); import unittest; unittest.main(module=None)" test_d1_frame_clock_v3 test_review_d1_full_bank_v3 -v
"%JP_PY%" -B "%JP_CODE%\review_d1_full_bank_v3.py" --run "%JP_LOCAL%\d1-full-bank-v1" --output "%JP_LOCAL%\d1-full-bank-review-v3"
```

Wait for the exact reviewer owner to exit before downstream admission. Supply
the passed v3 REVIEW.json as `--d1-review` to the unchanged integrated-bank
planner documented in README_INTEGRATED_BANK.md. Neither a test pass nor a
component review establishes N4 stage, GUI, latency, naming or CM5 acceptance.
