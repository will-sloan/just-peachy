# Application source-delivery integration

Purpose: `paced_application_cell_v2.py` is an explicit application cell variant
that collects the qualified saved-source delivery trace. `application_delivery.py`
owns the fresh-source launch hook and independently joins the completed trace
to the retained engine and consumer-source clock. Existing source, original
ApplicationCell and runner/planner files remain unchanged.

Inputs: the same admitted eight-field saved-audio job, backend/mode contract,
source, runtimes and fixed research gallery as the original ApplicationCell.
The real runner must enforce source/audio hashes, a qualified shortlist, exact
private process ownership and the exclusive resource slot. There is no direct
application launch CLI here. SourceLaunchCapture is installed inside the child
only after the run admission callback passes and before Controller.start_file.
It wraps FileSource.start in that isolated process; no source file is patched.

At the seam it requires the Controller command thread, saved-file STARTING
state, exact path/tap/mode, adaptation off, expected engine, bound callback
owner, and the same actual bypass input/ASR/identity MemoryJournal. One start is
allowed. Rejected/duplicate starts cannot launch a source. For the admitted
start it installs SourceDelivery and calls the original start method once,
preserving its return/exception. The class hook is restored after run_source,
including errors. Foreign hooks are preserved and cause a failed receipt.

The original engine/archive/consumer/viewport closure remains required. After
Controller cleanup and SOURCE_CLOCK.json persistence, delivery extraction writes
`delivery/OBSERVATION.json`, `TRACE.bin` and `CAPTURE.json`. It runs before the
resource observer closes, so collection cost remains in the observed process
lifetime. The inherited phase at extraction is closed/draining, separate from
running inference. No observer cost is subtracted. Each source is limited to an
hour; the binary is bounded at 5,220,000 bytes plus small metadata. Partial or
failed attempts retain their evidence and fail application collection.

The independent reader requires these exact local filenames, caller-bound
application source files and unchanged hashes. It rejects reparse paths and
checks file sizes before hashing/loading (128 KiB capture/observation, 1 MiB
engine/clock records, and 5,220,000-byte trace). It re-parses every trace record
and checks the entire source sample count, origin, source/consumer session,
engine identity, stopped source thread, restored hook, clean observer and fixed
job/contract. It rejects test-seam flags. Its result is only
PASS_APPLICATION_DELIVERY_SOURCE_CLOCK_JOIN_ONLY. Full engine/archive closure
must pass separately; this does not establish timing thresholds, physical
callback latency, word/paint latency, accuracy, resource tier or continuity.

The new successful cell status is
CELL_WITH_SOURCE_DELIVERY_CLOSED_REQUIRES_REVIEW, and RESULT.json binds the
capture and independent join. The old runner does not accept this new status
and does not import this variant. A new explicit child/runner/planner/reviewer
binding is still required, followed by actual private GUI prestart qualification
and controlled full source runs. No existing production admission is bypassed.
The original 3,500-second cell execution bound is retained; a 20-minute test
fits, but a future full one-hour run needs an explicitly reviewed lifetime policy.
Functional stop/restart across real Controller sessions also remains separate.

Development probe inputs are qualified source/observer/closure bindings and a
fresh private output directory. It checks D1 exact ownership/heartbeat/bindings,
CPU14 BelowNormal with one math thread and GPU off, helper lock, disk/private
allowance, 12-minute lifetime and 8-MiB output cap. The five new source files are
snapshotted before tests. It checks original FileSource/MemoryJournal/Pacer bodies
using RAM-only fixtures. The actual new cell methods run with mocked Controller,
UI, resources and engine/archive closure. Positive pure-join fixture copies have
explicitly normalized test flags; original captured fixture files keep their
flags, and tests prove those originals cannot pass production validation.

Sixteen checks cover launch order and exact owner rejection, duplicate starts,
exception identity, foreign hooks, no-start closure, partial capture, source/
consumer joins, changed origin/session/counters/contracts, fixture rejection,
bound file paths and positive synthetic file-reader composition, pre-hash byte
limits, source extraction before resource closure, refusal of success
when delivery review fails, and admission rejection before hook/source start.
They establish development wiring only. No WAV, model, actual Controller/GUI,
private desktop or device is started by this probe.

PowerShell (choose a fresh output suffix for every attempt):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_delivery.py" --output "$jpLocal\n4\application-delivery-probe-v2"
```

Command Prompt and Anaconda Prompt (direct pinned interpreter):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_delivery.py" --output "%JP_LOCAL%\n4\application-delivery-probe-v2"
```

Private outputs: PROBE_OWNER.json, source snapshots, ADMISSION.json, tests.txt,
per-case synthetic capture/trace/cell records, SYNTHETIC_JOIN.json, SYNTHETIC_FILE_JOIN.json,
SYNTHETIC_CELL_WIRING.json and RESULT.json or FAILED.json. Keep failed attempts
and all actual source paths/trace evidence private. Only reviewed code,
documentation and redacted qualification/hash records belong in GitHub.
