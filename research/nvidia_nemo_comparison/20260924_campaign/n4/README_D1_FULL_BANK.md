# Full-bank D1 components after reviewed smoke

`d1_full_bank.py` prepares 960 native D1 component cells: E0 and E1 separately,
each on all 480 admitted scene/tap files. It retains the unchanged N2Engine
speaker loop, ActivityTimeline queries, nominal low_latency CPU1 native runtime
and model-specific embedding namespaces from the reviewed four-cell smoke.
Every independent scene has one native stream reset, exact 100-ms source reads,
its actual tail and one final drain. It does not run ASR, Pyannote, a gallery,
enrollment or a Controller/widget. This supplies zero integrated N4 credit.

Inputs: passed D1 smoke review, bound full-bank ASR admission, the future ASR
full-bank review path, existing supervisor state, all 480 audio-only jobs and
their original waveform hashes, and a fresh private output directory. Preparation
rechecks the full smoke event/window evidence and every bank waveform. Source,
runtime, assets, numerical versions, exact profiles and executor code are bound.
References/names/turn boundaries never enter prediction. Smoke cells are
recollected as part of the full bank; no silent timing reuse occurs.

Preparation can finish during ASR inference. It starts no model or waiter.
Before loading any D1 model, both the coordinator and child require a passed
1,920-cell ASR full-bank review, an exited exact ASR coordinator, and unchanged
reviewer/source/result/event bindings. The accepted predecessor receipt is
sealed in the D1 run result. A missing or partial review leaves D1 prepared.
Use the sole existing supervisor after checking fresh PID creation identities.
Supervisor/coordinator use CPU14; the model uses CPU4, one library thread,
GPU disabled, hidden windows and below-normal priority. No desktop focus/input,
microphone/USB, capture, playback, training, Pi or new download is involved.

Outputs: private immutable admission/worker, all native frame/query events in
gzip, per-cell results, encoder indexes, progress and terminal result. Real
native monotonic stamps remain in the raw evidence; the application component
clock is explicitly modeled serial source plus actual call duration. It cannot
qualify observed S7 eligibility, live latency or widget timing. Short exclusive
turns, overlap, silence, endpoint overhang and no-query files remain counted.
RSS/load/elapsed samples are component diagnostics, not complete-stack resources.

Preparation inventories every current private campaign byte without deduplication
credit or reparse traversal. It adds this 2-GiB reservation, the active ASR run's
full 2-GiB reservation and 1 GiB contingency beneath the existing 50-GiB allowance.
This conservatively counts current ASR bytes plus its whole future reservation.
Each cell stops before 32 MiB expanded UTF-8 event text; serialized summary is
limited to 2 MiB, with 4 MiB margin reserved for summary/index updates. The run
checks its 2-GiB cap, C:50/G:75-GiB floors and the packaging cutoff before each
cell. Failure preserves the attempted cell and stops; no retry or deletion.

PowerShell preparation/check (no model launch):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\d1_full_bank.py" prepare --smoke-review "$jpLocal\n4\d1-smoke-review-v1\REVIEW.json" --asr-full-admission "$jpLocal\n4\asr-full-bank-v1\ADMISSION.json" --asr-full-review "$jpLocal\n4\asr-full-bank-review-v1\REVIEW.json" --output "$jpLocal\n4\d1-full-bank-v1" --state "$jpLocal\supervision"
& $jpPython -B "$jpCode\d1_full_bank.py" check --admission "$jpLocal\n4\d1-full-bank-v1\ADMISSION.json"
```

Command Prompt / Anaconda Prompt uses the exact existing interpreter:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\d1_full_bank.py" prepare --smoke-review "%JP_LOCAL%\n4\d1-smoke-review-v1\REVIEW.json" --asr-full-admission "%JP_LOCAL%\n4\asr-full-bank-v1\ADMISSION.json" --asr-full-review "%JP_LOCAL%\n4\asr-full-bank-review-v1\REVIEW.json" --output "%JP_LOCAL%\n4\d1-full-bank-v1" --state "%JP_LOCAL%\supervision"
"%JP_PY%" -B "%JP_CODE%\d1_full_bank.py" check --admission "%JP_LOCAL%\n4\d1-full-bank-v1\ADMISSION.json"
```

After ASR finishes and its strict full review passes, verify all numerical
ownership is free, then run the existing supervisor from a CPU14-pinned caller:

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "$jpCode\..\supervision\supervisor.py" phase --root "$jpLocal\supervision" --phase inference --stage N4
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "$jpCode\..\supervision\supervisor.py" start --root "$jpLocal\supervision" --spec "$jpLocal\n4\d1-full-bank-v1\worker.json"
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%JP_CODE%\..\supervision\supervisor.py" phase --root "%JP_LOCAL%\supervision" --phase inference --stage N4
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%JP_CODE%\..\supervision\supervisor.py" start --root "%JP_LOCAL%\supervision" --spec "%JP_LOCAL%\n4\d1-full-bank-v1\worker.json"
```

`review_d1_full_bank.py` requires terminal 960/960 coverage and an exited exact
coordinator. It verifies all bindings and complete gzip/expanded hashes, native
model/runtime, scene-specific track IDs, actual frames and query waveform bytes.
It reexecutes the frozen ActivityTimeline selection logic on every raw frame,
keeps short/no-query denominators and requires exact E0/E1 frame/query geometry.
Output: private full `REVIEW.json` and a small aggregate `REDACTED_REVIEW.json`.
`PASS_D1_FULL_BANK_COMPONENTS_ONLY` is not N4 integrated, naming, GUI, live
latency, whole-stack resource or physical CM5 acceptance.

```powershell
& $jpPython -B "$jpCode\review_d1_full_bank.py" --run "$jpLocal\n4\d1-full-bank-v1" --output "$jpLocal\n4\d1-full-bank-review-v1"
```

```bat
"%JP_PY%" -B "%JP_CODE%\review_d1_full_bank.py" --run "%JP_LOCAL%\n4\d1-full-bank-v1" --output "%JP_LOCAL%\n4\d1-full-bank-review-v1"
```

Tests exercise the real application loop with stub models and a bounded writer,
disk/cutoff guards, missing/partial smoke, a complete temporary 1,920-cell ASR
predecessor receipt, and a full temporary 960-cell paired D1 review. Missing
indexed cells and a live predecessor fail. These are unit fixtures with no
neural inference or private recordings. The D1 fixture uses float32 synthetic
test samples to preserve exact waveform hashes; actual bank admission separately
requires the saved PCM16 recordings. Tests print to the console and remove only
their own temporary fixtures.

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_*d1_full_bank.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_*d1_full_bank.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```
