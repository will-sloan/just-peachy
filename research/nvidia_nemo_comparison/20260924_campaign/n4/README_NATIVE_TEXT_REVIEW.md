# Native raw-text publication review

Purpose: `review_native_text.py` reconstructs raw ASR revisions from a complete
native event journal, checks one matching independent text publication per
revision, and attaches punctuation to its exact final raw utterance. It never
uses punctuation or rendered captions as the raw ASR hypothesis. Interleaved
speaker/display events are allowed. Untimed token identities and ASR source
windows do not become phonetic word alignments. Diagnostic padding overhang is
retained without clamping. Partial-only utterances remain explicit; they are not
silently finalized or dropped from an accuracy denominator.

Inputs: a stopped native session, its eight-field audio-only job, and the exact
complete envelope review reconstructed by the qualified native reader. The
reader rechecks the complete journal, terminal bindings and envelope fingerprint
before interpretation and verifies raw bindings again afterwards. The caller
must separately establish application ownership, qualified source lineage and
complete V2 plan coverage. No models, references or microphone APIs are imported.

Output: a private in-memory `PASS_NATIVE_RAW_TEXT_PUBLICATION_LINEAGE_ONLY`
record with all raw revisions, publication joins, final revision IDs, unfinished
utterances, raw final text and separate formatting. Limits: 32,768 revisions,
4,096 utterances, 64-KiB individual strings and 8-MiB cumulative raw/display text
across relevant events, in addition to the native journal reader's limits.
The record contains private transcripts and must not enter Git. This does not
review all semantic event types, pane captions, names, visibility, accuracy,
latency, source inference completeness, continuity or deployment acceptance.
An empty event population is represented explicitly; it is not proof that an
ASR model was run. Partial-only output requires a separate completeness decision
before a final-only metric. Accepted integrated N4 cells remain zero.

The development probe uses CPU14, BelowNormal priority, one math thread, no GPU
and the existing helper lock. It verifies the exact active D1 identities and
source hashes before/after and enforces time, disk and private allowance limits.
It records its owner and own source snapshots before prerequisite traversal and
preserves every failed attempt. It exercises synthetic native publications and
the real journal/terminal reader, including cross-stream corruption, incomplete
history, formatting isolation, partial/empty cases, clocks, bounds and mutation.
Nine historical truncated journals must still be refused. Synthetic fixtures
never establish a newly run source/application or complete production plan.
Attempt v1 passed its initial twelve tests and its exact sources/results remain
preserved privately. Before qualification, an audit added strict JSON-type
equality and the same-clock requirement that text readiness follows its raw
observation publication. Fresh attempt v2 includes those additional corruption
cases in the twelve-test suite. Neither attempt starts application/model work.

Use a new private output directory per attempt. Do not run this probe during
exclusive application measurements. PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_native_text_review.py" --output "$jpLocal\n4\native-text-review-probe-v2"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_native_text_review.py" --output "%JP_LOCAL%\n4\native-text-review-probe-v2"
```

Internal API, after a qualified V2 cell review has established the expected
session/job and reconstructed native envelope:

```python
from review_native_text import review
private_text = review(session, job=verified_audio_only_job,
    expected_envelope=joined_cell['transport']['native_envelope_review'],
    checkpoint=bounded_evaluator_guard)
```

These names represent verified inputs, not runnable placeholders. This API does
not launch an application or change immutable source/runner qualifications.
