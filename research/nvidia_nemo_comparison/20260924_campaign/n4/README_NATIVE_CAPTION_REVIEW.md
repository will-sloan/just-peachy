# Native caption and raw-word partitions

Purpose: `review_native_captions.py` joins native `s6d_display` records to the
reviewed raw ASR/text-publication stream. It checks caption revision identities,
raw text/finality/source support, causal publication order, display versions,
formatting provenance and exact word/character partitions across speaker
fragments. Stable token facts cannot change, and retired token IDs cannot
reappear. Speaker labels, known profile IDs, closed assignments and track zero
are retained as predictions; they are not interpreted as truth or confidence.

Inputs: a stopped native session, the verified eight-field audio-only job and
the exact complete native envelope from a separately reconstructed V2 cell.
The API reruns the qualified raw-text reader and native journal parser, then
verifies journal/terminal bindings and the segment set again. Its caller must
establish application ownership, qualified source lineage and full plan coverage.
No ground truth enters this layer.

Output: a private in-memory `PASS_NATIVE_CAPTION_RAW_PARTITIONS_ONLY` result
containing compact display/fragment histories, stable word facts, raw final text
and missing raw-revision IDs. Missing display revisions remain explicit and make
`raw_revision_caption_coverage_complete` false. Passing partition checks alone
does not establish complete caption coverage or successful inference. An empty
final is retained. Source windows remain ASR revision uncertainty, with no
invented acoustic alignment or timestamp clamping. These private text and label
records must never enter Git or public reports.

Limits: 32,768 display records, 8,192 unique word spans, 512 segments per display
and 8 MiB of cumulative raw/display text, in addition to the existing raw-text
and native-journal limits. Production callers must supply a bounded checkpoint
and enforce their output allowance. The API does not open any application, load
models, access devices or modify source. It does not yet connect native segments
to actual Controller/viewport strings or score naming, accuracy or latency.
All acceptance flags remain false; accepted integrated N4 cells remain zero.

The guarded probe uses CPU14/BelowNormal, one math thread, no GPU and the helper
lock. It verifies current D1 owners, heartbeats and protected code before and
after, with disk/private allowance and time bounds. Each fresh attempt records
its exact process owner and own source snapshots before prerequisite traversal;
failed attempts remain intact. Twelve tests cover rewrites, split identity
ownership, track zero, formatting, corrupt/missing partitions, retired/stable
spans, causes, versions, missing displays, empty finals and bounded accumulation.
Positive fixtures call the unchanged S6D/S7/N1 pure span-state modules from the
qualified derivative through an isolated package namespace; this avoids runtime
and model imports. Their inputs, event envelopes and clocks are synthetic.
No saved source, complete application, window, microphone or Pi runs in this test.

Attempt v1 preserved eleven passing tests and one fixture assertion failure:
deleting a segment also triggered the single-segment formatting guard before
the intended missing-tail guard. The v2 fixture keeps that remaining formatting
coherent so it exercises the omitted raw-text check. Production validation is
unchanged; v1 sources, admission, test log and failure remain private evidence.

Run only outside exclusive paced application measurements, using a fresh output.
PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_native_caption_review.py" --output "$jpLocal\n4\native-caption-review-probe-v2"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_native_caption_review.py" --output "%JP_LOCAL%\n4\native-caption-review-probe-v2"
```

Internal API after independent qualified cell/ownership reconstruction:

```python
from review_native_captions import review
private_captions = review(session, job=verified_audio_only_job,
    expected_envelope=joined_cell['transport']['native_envelope_review'],
    checkpoint=bounded_evaluator_guard)
```

These names stand for verified inputs. Preserve all earlier qualifications;
compose this new reader explicitly instead of changing a bound cell/panel reader.
