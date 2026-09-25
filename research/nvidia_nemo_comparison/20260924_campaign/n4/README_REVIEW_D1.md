# Review the D1 component smoke

`review_d1_components.py` reviews a terminal four-cell D1 collection after its
exact coordinator exits. Purpose: qualify the component protocol and evidence
integrity before a fresh full-bank admission. It does not perform neural
inference, accept N4, fit thresholds, qualify latency or integrate captions.

Inputs: `d1_bank_components.py`'s immutable admission, all four complete cell
receipts and gzip event streams, final encoder indexes, exact saved waveform
files, frozen application source, runtime/model bindings and numerical Python
versions. The source is imported only for its actual activity-window selector
and nominal profiles. The reviewer does not load native models or personal data.

Checks include exact source/asset/profile/cache/namespace bindings, CPU4 receipt,
full compressed and expanded hashes/CRC, forward 100-ms reads and exact tail,
one finish, full eight-channel probabilities and native endpoint overhang, all
exclusive windows derived again from the actual application selector, exact
waveform slices and finite unit vectors, every short-turn denominator, raw
native monotonic stamps and separately modeled compute times. E0/E1 must match
on all native frame semantics and selected query geometry. Different encoder
vectors are expected; they are not compared as if they shared a voice space.

Output: a new private `REVIEW.json`, status `PASS_D1_COMPONENT_SMOKE`, with four
component cells, two paired files, full source evidence bindings and hashes.
It explicitly records zero integrated N4 cells, full-bank admission false and
Controller/widget parity false. Prior reviews cannot be overwritten. Actual
smoke has not yet run merely because this reviewer exists or its tests pass.

Use the same application Python as the collector. The process pins CPU14 and
sets one thread through the collector imports. Do not launch a numerical model
while another worker owns the campaign slot.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B "$jpCode\review_d1_components.py" --run "$jpLocal\d1-smoke-v1" --output "$jpLocal\d1-smoke-review-v1"
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B "%JP_CODE%\review_d1_components.py" --run "%JP_LOCAL%\d1-smoke-v1" --output "%JP_LOCAL%\d1-smoke-review-v1"
```

`test_review_d1_components.py` builds full event fixtures with the actual frozen
application D1 loop and stub models, then injects corruption. It checks dropped
frames/final drain, false waveform/vector/namespace/clock claims, missing short
turns and summary/known-name forgery. Tests use no saved recordings or models.

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_review_d1_components.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_review_d1_components.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```
