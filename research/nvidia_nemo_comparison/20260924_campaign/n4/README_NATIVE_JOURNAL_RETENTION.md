# Complete native event retention derivative

The research application needs its full native event history for N4 content and
timing review. Its original event sink keeps only a rotating tail. This derivative
changes event retention identically for every backend while preserving the shared
frontend, prediction algorithms, asynchronous queue and worker drain behavior.

`native_complete_text.py` supplies `CompleteText`, a fresh-file-only UTF-8 sink
with a 256-MiB total budget and 1-MiB per-record limit. It never deletes or rotates
the prefix. Exhaustion raises an error through the existing `AsyncText` worker;
normal closure then fails explicitly. It adds no second event queue or model.
Other native transcript/readable journals keep their original rotating behavior.
This is research instrumentation whose I/O/storage overhead must be included in
all paired resource measurements. It is not a default production promotion.

`probe_native_journal_retention.py` binds the current immutable catalog source,
copies only its verified source/auxiliary inventory into a fresh derivative,
adds `app/native_complete_text.py` and this README, and makes two precise edits:
`AsyncText` accepts an optional sink factory; `PrototypeEngine._open_journal_text`
selects the complete sink for events.jsonl. All other source files and the common
frontend are rehashed unchanged. The original component source is never edited.

Inputs are the qualified source parent, existing active D1 supervision and fresh
private output/release paths. Outputs are an immutable derivative SOURCE_RECEIPT,
per-attempt source snapshots, synthetic writer fixtures, test log and private
RESULT.json (or preserved FAILED.json). Source copy is capped at 32 MiB. The
CPU14 helper enforces its existing lock, 720-second limit, 8-MiB test-output bound,
C:50/G:75 GiB floors and shared 50-GiB payload allowance including a 6-GiB reserve.
The numerical owner remains on CPU4; no audio, models, UI or desktop is opened.

Eight checks use the actual copied AsyncText and an isolated AST of the actual
factory method. They verify preservation beyond the old three-MiB rotating
window, exact FIFO bytes/counts, Unicode byte accounting, budget failure,
existing-file protection, record limits, unchanged ordinary rotation, closed
writes and normal/failed worker shutdown. Factory isolation avoids importing
the neural runtime and does not establish that the complete application ran.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_native_journal_retention.py" --output "$jpLocal\n4\native-journal-retention-probe-v1" --derivative "$jpLocal\releases\n4-complete-journal-v1"
```

Command Prompt and Anaconda Prompt (no activation or installation required):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_native_journal_retention.py" --output "%JP_LOCAL%\n4\native-journal-retention-probe-v1" --derivative "%JP_LOCAL%\releases\n4-complete-journal-v1"
```

Both paths must be new. This guarded builder is phase-specific to active D1;
re-observe and version its admission after that phase. Keep all fixtures and
full native logs private. Publish only reviewed code and redacted receipts.

The derivative status is `IMPLEMENTED_NOT_APPLICATION_ADMITTED`; passing writer
checks are `PASS_NATIVE_JOURNAL_RETENTION_CHECKS_ONLY`. Before using it, version
and requalify the application preparation, runner, planner and review bindings,
then reconfirm actual native source/GUI/worker closure for paired candidates.
Never substitute this receipt into an older qualified plan. Future native
envelopes must pass the completeness reader as well as semantic and viewport
reviews. No existing missing prefix is repaired. Continuity may still hit the
finite budget; that is an explicit failed/incomplete cell, not permission to
discard events or raise limits mid-run. N4 acceptance remains pending.
