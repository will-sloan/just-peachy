# Frozen application D1 component capture

`d1_lane_components.py` captures the unchanged `N2Engine._speaker_loop` and
`_accept_activity` from the accepted `n4-catalog-v3` derivative. It is an
implementation building block, not a completed N4 result. It does not load a
model by itself or edit the frozen application. `d1_bank_components.py` adds a
separate supervised four-cell smoke admission, E0 then E1 on the same first
O0/O1 pair. Full-bank admission is deliberately unavailable pending actual smoke
evidence review; neither preparation nor smoke counts as an integrated cell.

Purpose: retain actual Nemotron activity and the application's exact exclusive
query windows for E0/E1 collection. D1 windows differ from D0's; never reuse D0
vectors for them. The existing model owner must acquire/reset one native stream
per independent scene. There is no reset at predicted turns or reference bounds.

Inputs to the API: one finite mono16k float32 saved waveform (gain already applied
once), a writable private JSONL stream, the admitted N2 resident owner, a unique
scene ID, and an encoder exposing `embed`, `namespace`, `last_embed_ms`. The real
application reads 100-ms chunks and the exact short tail, then drains once. Query
rereads are limited to audio already delivered. The native threshold .5, minimum
.5-second query, .5-second hop and maximum 2-second contiguous query come from
the unchanged application, without references, ASR, gallery or known names.

Outputs: all emitted native frames, overlap/silence, native endpoint overhang,
exclusive-run coverage, actual query events/vectors, anonymous decisions, real
call timing sidecars, exact float32 query hashes and complete source/closure
censuses. Raw native timestamps remain unchanged. The clock attribute used by
the application is explicitly replaced with a **modeled serial clock**:
`max(previous_ready, received_source) + actual_call_duration`. Each event marks
this substitution; it is not observed S7, Controller, first-visible or real-time
latency evidence. No caption widget or concurrent application worker is run.
Short exclusive turns and ambiguous/overlap support remain in the evidence.

The caller owns native lifetime and must close the resident even on failure.
The capture raises on native failure, nonunit/nonfinite vectors, mismatched query
bytes, future reads, duplicate acquisition or missing closure. Preserve the failed
attempt; a numerical retry requires a fresh derivative/admission.

API pattern, inside a separately admitted CPU-only worker after slot ownership
is checked (not a standalone launch instruction):

```python
from app.n2_pipeline import N2Engine, ActivityTimeline
from app.n2_identity import N2NameMap
from d1_lane_components import capture_type
Capture = capture_type(N2Engine, ActivityTimeline, N2NameMap)
capture = Capture(wave, private_log, resident, job_id)
summary = capture.run_capture(encoder)
```

`test_d1_lane_components.py` runs the actual frozen application methods with
synthetic arrays and stub models. It checks exact tail delivery, finished short
turns, overlap/silence/overhang retention, real window selection, independent
scene reset, failure paths and the modeled-clock distinction. It performs no
neural inference, saved-recording access, device enumeration or GUI action.
The default source is the verified campaign derivative. Set `JP_N4_SOURCE` only
to a separately verified equivalent source. Test outputs go to the console.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_d1_lane_components.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

Command Prompt / Anaconda Prompt (absolute interpreter, no environment change):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_d1_lane_components.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```

The runner verifies the frozen source, exact CPU1 native runtime, official Q8
model, accepted nominal 1.04-second input-buffer profile, both embedding assets,
full input manifest and numerical package versions. It reuses each resident
within its encoder and resets only at independent scenes. It runs no Pyannote,
ASR, gallery, enrollment, device or GUI acquisition. Model processes use CPU4;
their coordinator uses CPU14. No competing worker or waiter may be started.
Coordinator/child identities must match the exact supervisor PID and creation
times. The owner closes after success or failure; failed outputs are retained.

Private outputs include per-cell `RESULT.json` and full `D1_EVENTS.jsonl.gz`,
expanded/compressed SHA-256 and gzip CRC checks, per-encoder indexes and terminal
`SMOKE_COLLECTED_REQUIRES_REVIEW`. RSS samples and elapsed time are diagnostic;
the first cell includes native model load, while embedding load is recorded
separately. These are not whole-stack resource measurements.

Its 2-GiB cap and 32-MiB per-cell reserve are charged conservatively against the
shared 50-GiB allowance along with the existing D0 4-GiB and ASR 2-GiB reservations
and another 1 GiB contingency. It checks C:50/G:75 GiB floors and the packaging
reserve before each cell. No downloads or removal of prior evidence occur.

Preparation/check only (no model run; choose a fresh output if one exists):

```powershell
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\d1_bank_components.py" prepare --asr-admission "$jpLocal\n4\asr-smoke-v1\ADMISSION.json" --payload-inventory "$jpLocal\n4\payload-inventory-20260925T0224-v2.json" --output "$jpLocal\n4\d1-smoke-v1" --state "$jpLocal\supervision"
& $jpPython -B "$jpCode\d1_bank_components.py" check --admission "$jpLocal\n4\d1-smoke-v1\ADMISSION.json"
```

```bat
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\d1_bank_components.py" prepare --asr-admission "%JP_LOCAL%\n4\asr-smoke-v1\ADMISSION.json" --payload-inventory "%JP_LOCAL%\n4\payload-inventory-20260925T0224-v2.json" --output "%JP_LOCAL%\n4\d1-smoke-v1" --state "%JP_LOCAL%\supervision"
"%JP_PY%" -B "%JP_CODE%\d1_bank_components.py" check --admission "%JP_LOCAL%\n4\d1-smoke-v1\ADMISSION.json"
```

Only after prior numerical work finishes and is reviewed, and fresh PID/creation
identities establish that the slot is free, dispatch through the existing
supervisor. Preserve the ordering D0 full bank, ASR smoke, then D1 smoke. Verify
the exact supervisor host inherits CPU14; never broaden the admitted cores.

```powershell
& $jpPython -B "$jpCode\..\supervision\supervisor.py" phase --root "$jpLocal\supervision" --phase inference --stage N4
& $jpPython -B "$jpCode\..\supervision\supervisor.py" start --root "$jpLocal\supervision" --spec "$jpLocal\n4\d1-smoke-v1\worker.json"
```

```bat
"%JP_PY%" -B "%JP_CODE%\..\supervision\supervisor.py" phase --root "%JP_LOCAL%\supervision" --phase inference --stage N4
"%JP_PY%" -B "%JP_CODE%\..\supervision\supervisor.py" start --root "%JP_LOCAL%\supervision" --spec "%JP_LOCAL%\n4\d1-smoke-v1\worker.json"
```

Additional runner tests check cache invalidation, audio-only firewall, refusal
of an unreviewed full-bank scope, cutoff, floors and reservation guards. Run
the same unittest command above with pattern `test_d1_bank_components.py`.
Terminal evidence review, full-bank execution and application/presentation
parity remain required. See README_REVIEW_D1.md for the separate reviewer.
