# Actual application ASR component collection

`asr_bank_components.py` prepares and supervises an initial eight-cell smoke:
the first two already-admitted full-bank scene/tap files, with A0, A1, A2 and A3
sequentially. A separate model process uses CPU4 for each variant; supervisor
and coordinator use CPU14. The smoke must be reviewed before a fresh full-bank
admission. The `full` preparation option currently refuses dispatch deliberately;
no complete 1,920-component or 7,680-integrated-cell run is claimed by this code.

`asr_lane_components.py` wraps the **unchanged frozen application's** A0
`PipelineEngine._asr_loop`, A1/A2/A3 `StreamingASRLane._asr_loop`, `_publish_final`
and `_transcript_event`. These methods determine actual chunk size, partial
throttling, endpoint/reset, raw event support and tail flush. In this source the
profile reads 100-ms chunks, distinct from the earlier N3 screen's external
80-ms chunks. A1 retains its internal 80-ms stateful service buffering. A2/A3
retain the fixed native geometry in the accepted source. No prior screen is
silently substituted for this different application-level collection contract.

The collector passes exactly once-gained prepared samples through forward-only
journal reads. Streams reset at independent scenes only, with no evaluator turn,
text or identity input. One ASR owner is reused across scenes and released before
the next variant. A0 is the retained Sherpa model; A1 is the qualified ONNX/P0
owner; A2/A3 use their qualified native CPU owners with native punctuation.
There is no diarizer, embedding model, gallery, tracking, GUI or audio device.

The production loops submit final raw text before their separate punctuation
worker completes. Here those same final-only `asr.punctuate` calls are queued
in order and executed after isolated ASR closure, producing a separate component
event. The original raw observations never change. Each formatting call retains
actual compute stamps and an explicitly **modeled** FIFO availability based on
its ASR submission. This is reusable text evidence, not the production worker's
observed schedule, caption latency, first-visible output or S7 Controller parity.
Do not promote these modeled clocks to measured real-time results.

Inputs: the verified D0 admission's frozen accepted-source derivative and full
audio manifest, exact accepted N3 runtime, all existing model/bundle/DLL assets,
prior conservative payload inventory, supervision state and a fresh output
directory. Preparation verifies N3 acceptance/config bindings and the actual
16-entry catalog runtime. It hashes assets but does not load inference models.
The predictor receives only the eight audio-only fields. All dependency/source/
Python/package versions and nominal profiles are frozen in `ADMISSION.json`.

Outputs: per-variant indexes; per-cell `RESULT.json`, complete UTF-8
`ASR_EVENTS.jsonl.gz` and expanded/compressed hashes; private raw partial/final
text and actual P0/P1 formatting; and a terminal coordinator result requiring
review. Every gzip is read through EOF for CRC verification. Failure stops the
run and preserves failed/partial evidence; no in-place retry. The component
cache key binds the full source/model/runtime/code/profile, waveform and state
contract. Matching keys alone never authorize unverified reuse.

The allocation is capped at 2 GiB with 32 MiB per-clip reserve, charged against
the shared 50-GiB allowance **in addition to** the existing 4-GiB D0 reservation
and another 1-GiB contingency. C:50/G:75 GiB floors and the packaging cutoff are
checked before each scene. This is a cooperative limit, not an OS quota or a
whole-stack memory qualification. No assets are downloaded or original files
removed. The Pi stays off and no desktop input/focus is taken.

PowerShell preparation/check (safe while another model worker runs; no model
inference starts). Use a fresh output name if this admission already exists:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\n4\asr_bank_components.py" prepare --scope smoke --d0-admission "$jpLocal\n4\d0-bank-v1\ADMISSION.json" --n3-runtime "$jpLocal\n3\runtime\a1controllerv2\cpu\n3_runtime.json" --payload-inventory "$jpLocal\n4\payload-inventory-20260925T0224-v2.json" --output "$jpLocal\n4\asr-smoke-v1" --state "$jpLocal\supervision"
& $jpPython -B "$jpCode\n4\asr_bank_components.py" check --admission "$jpLocal\n4\asr-smoke-v1\ADMISSION.json"
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\n4\asr_bank_components.py" prepare --scope smoke --d0-admission "%JP_LOCAL%\n4\d0-bank-v1\ADMISSION.json" --n3-runtime "%JP_LOCAL%\n3\runtime\a1controllerv2\cpu\n3_runtime.json" --payload-inventory "%JP_LOCAL%\n4\payload-inventory-20260925T0224-v2.json" --output "%JP_LOCAL%\n4\asr-smoke-v1" --state "%JP_LOCAL%\supervision"
"%JP_PY%" -B "%JP_CODE%\n4\asr_bank_components.py" check --admission "%JP_LOCAL%\n4\asr-smoke-v1\ADMISSION.json"
```

Only after inspecting fresh exact worker PID/creation identities and verifying
the numerical slot is free, dispatch via the existing supervisor. Do not launch
`run`/`extract` directly or start a second waiter while the D0 bank is active:

```powershell
& $jpPython -B "$jpCode\supervision\supervisor.py" phase --root "$jpLocal\supervision" --phase inference --stage N4
& $jpPython -B "$jpCode\supervision\supervisor.py" start --root "$jpLocal\supervision" --spec "$jpLocal\n4\asr-smoke-v1\worker.json"
```

```bat
"%JP_PY%" -B "%JP_CODE%\supervision\supervisor.py" phase --root "%JP_LOCAL%\supervision" --phase inference --stage N4
"%JP_PY%" -B "%JP_CODE%\supervision\supervisor.py" start --root "%JP_LOCAL%\supervision" --spec "%JP_LOCAL%\n4\asr-smoke-v1\worker.json"
```

Verify the owned supervisor host inherits only admitted CPUs and pin that exact
host to CPU14 if needed. The coordinator and model child verify their exact
supervisor/parent creation identities before inference; every child pins CPU4.
Terminal `SMOKE_COLLECTED_REQUIRES_REVIEW` does not mean N4 acceptance.

`test_asr_lane_components.py` executes the actual frozen application loops with
stub models and synthetic arrays, checking exact tail samples, multiple finals,
source spans, endpoint reset, raw-text/formatting separation, error/close paths,
scene reset, cache invalidation, ownership and disk/cutoff guards. No neural
model, device or saved recording is loaded. It uses the frozen source path above;
set `JP_N4_SOURCE` only to an explicitly verified equivalent derivative.

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_asr_lane_components.py','-v']; runpy.run_module('unittest',run_name='__main__')" "$jpCode\n4"
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_asr_lane_components.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%\n4"
```
