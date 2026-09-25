# Native event-journal completeness review

`review_native_journal.py` reviews a closed native session's publication envelope
and event census without importing the application, loading models or reading
audio. The existing `AsyncText` uses a 1-MiB `RotatingText` sink with only two
backups. Terminal queue completion therefore does not guarantee that all event
records remain on disk. Lost prefixes must not become complete timing or content
evidence for N4.

Inputs to `inspect(session, job=audio_only_job, checkpoint=...)` are the expected
eight-field mono saved-audio job, native events.jsonl and contiguous numbered
rotations, s6d_consumer_closure.json and session_finalization_v3.json. The caller
must separately verify exact stopped process identity, production-plan inputs,
source bindings and the qualified application closure. This internal API cannot
admit a production run or accept an entire panel.

The reader binds rotations oldest first, rejects ambiguous/duplicate JSON,
non-finite numbers (including nested exponent overflow), internal sequence gaps,
duplicates, foreign sessions, inconsistent publication/write/source-cursor clocks,
and incomplete worker/handle closure. It compares retained serials with native
accepted/completed and consumed/coalesced counts. A retained tail is returned as
`INCOMPLETE_NATIVE_EVENT_JOURNAL`, with exact missing-prefix/suffix counts and
unavailable start/completion markers. `require_complete(review)` refuses it.
A complete synthetic or actual envelope has status
`PASS_COMPLETE_NATIVE_EVENT_ENVELOPE_ONLY`. This does not score semantic payloads,
raw/displayed words, identities, accuracy, visibility, latency or resource tiers.
Diagnostic event source times retain native padding overhang; the actual
publication source cursor must remain monotonic and within the expected audio.

Outputs are small private review dictionaries with exact evidence bindings,
serial/type census, source/completion clock facts and limitations. No transcript
strings or vectors are copied into these reports. Bounds are 256 MiB total input,
256 segments, 1 MiB per line and 500,000 records, with bounded streaming reads.
The reader does not prove physical playback/delivery and does not reconstruct
missing events. All N4 acceptance flags remain false and integrated count zero.

`probe_native_journal_review.py` runs 12 tests covering complete synthetic logs,
truncated tails/suffixes, clock/source/census corruption, malformed and oversized
records, file mutation, and nine saved N3 native sessions. Historical input is
read only. Synthetic fixtures and per-attempt source snapshots remain private.
It checks exact active D1 owners, all active/predecessor bindings, the helper lock,
CPU14 placement, 720-second limit, C:50/G:75 GiB floors and the shared 50-GiB
allowance including the conservative 6-GiB reserve. D1 keeps CPU4. The probe
launches no application, desktop, source, model, microphone or playback.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_native_journal_review.py" --output "$jpLocal\n4\native-journal-review-probe-v2"
```

Command Prompt and Anaconda Prompt (exact interpreter; no activation/install):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_native_journal_review.py" --output "%JP_LOCAL%\n4\native-journal-review-probe-v2"
```

Always use a fresh output. This admission is for the active D1 phase; if it has
finished, re-observe and version the probe admission. Successful qualification
is `PASS_NATIVE_JOURNAL_REVIEW_CHECKS_ONLY`; the public receipt binds reviewed
source and private results. Keep all raw journal content and audio private.

V1 is preserved with its failed log and exact source snapshots. One synthetic
foreign-session test accidentally used the same name for its fixture directory
and corrupted session ID. V2 fixes the fixture to use a different identity;
the journal reviewer itself is unchanged.

Before real N4 paced and continuity runs, create and qualify a fresh application
derivative with bounded complete event retention. Preserve its original async
worker/FIFO semantics and per-record/queue limits, and fail explicitly when the
complete-log budget is exhausted instead of deleting old events. Apply identical
instrumentation to every candidate and include its overhead in measurements.
Rebind/requalify affected source, application runner, planner and reviewer
contracts. Do not change the frozen catalog source or the active D1/ASR bindings.
This reader does not implement that retention repair and does not turn old
incomplete journals into complete records.
