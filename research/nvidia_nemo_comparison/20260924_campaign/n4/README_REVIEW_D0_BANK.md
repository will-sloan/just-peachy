# Verify the full-bank D0 collection

`review_d0_bank.py` checks the complete `d0_bank_components.py` v1 population:
480 saved mono scene/tap files with each of E0 and E1. It makes no model calls,
opens no audio devices, changes no producer file, and fits no parameters. It
rejects a running/incomplete collection or a still-live exact coordinator PID
and creation time. A successful queue alone is not acceptance.

Inputs are a terminal private run directory, its immutable admission, source
receipt, audio manifest, model/code/runtime bindings, encoder results and
indexes, 960 cell results and complete gzip logs. Audio is decoded only to
verify exact float32 window hashes. All these private inputs remain private.

The checker verifies every required cell and its component cache key, exact
source/reset/gain/profile/namespace, complete input census, partial tail, unit
192-dimensional vectors, exact short/mature geometry and clean support. It
reads gzip streams through EOF (CRC), verifies compressed and expanded hashes,
checks every 0.25-second embedding admission including rejections, every
0.5-second segmentation dispatch, source/availability ordering and full frame
arrays. Each recorded vector must equal its actual logged model observation
and its actual waveform slice. E0/E1 must have identical masks, gates, admission
semantics and waveform geometry. Compute times and embedding values can differ.
No model clock is reinterpreted as observed live latency.

Output is a **fresh** directory with `REVIEW.json` (private cell bindings and
details) and `REDACTED_REVIEW.json` (small aggregate receipt suitable for manual
review before Git). Output is created only after all checks pass; earlier
evidence is never replaced. The public receipt has zero integrated N4 cells,
no calibrated D0/E1 profile acceptance and no complete-stack/latency claim.
Empty admitted-window sets are retained and counted rather than discarded.

Run after the coordinator has exited. The command pins itself to admitted
CPU14 at below-normal priority, sets BLAS threads to one, and imports no neural
runtime to perform inference. Its pinned runtime-version check requires the
same application Python used by the collector. Do not run multiple numerical
workers or modify code/source bound to the collection while it runs.

PowerShell (use a new output suffix for a later independent review):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B "$jpCode\review_d0_bank.py" --run "$jpLocal\d0-bank-v1" --output "$jpLocal\d0-bank-review-v1"
```

Command Prompt / Anaconda Prompt (activation is unnecessary with the explicit
interpreter; do not substitute another Python):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B "%JP_CODE%\review_d0_bank.py" --run "%JP_LOCAL%\d0-bank-v1" --output "%JP_LOCAL%\d0-bank-review-v1"
```

`test_review_d0_bank.py` uses synthetic in-memory samples and temporary gzip
fixtures. It tests corrupted/truncated logs, altered vectors and waveforms,
missing/duplicate admissions, impossible clocks, invalid probability frames,
cache/index drift and exact process identity. It never loads saved audio,
models, profiles or personal data. Tests do not establish full-bank acceptance.

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_review_d0_bank.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_review_d0_bank.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```
