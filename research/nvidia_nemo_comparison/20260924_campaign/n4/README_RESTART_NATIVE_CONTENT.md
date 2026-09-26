# Released native caption and retained widget content

`review_restart_native_content.py` interprets a stopped session's raw ASR,
text publication, formatting and caption/word-fragment history using the existing
qualified pure parsers. It reconstructs the explicit released-session envelope
first. The full planned job is never shortened to make a prefix look complete.
The first session can end at its actual mid-file delivery count; diagnostic ASR
support beyond that delivery remains overhang, and partial-only utterances stay
unfinished. Missing caption revisions remain explicit denominators.

For the second viewport, both sessions' independently reconstructed native
histories are indexed together. Applied caption text and row metadata must have
compatible preceding native publications in the matching session. This allows
retained old captions without attributing their words or times to the restarted
source. Recorded state arithmetic uses each caption's original source origin.
Ambiguous predecessors remain ambiguous; first/final/latest states and native
spans never observed in the widget stay in the result.

## Inputs and outputs

`review_native(session, job=..., delivered_frames=..., intent=...,
expected_envelope=..., checkpoint=...)` takes the unchanged full audio-only job,
the independently joined delivery count/intent and exact reviewed native
envelope. It returns `PASS_RELEASED_NATIVE_TEXT_AND_CAPTION_LINEAGE_ONLY`, the
raw and caption parser results, full-job hash, actual delivery scope and bindings.

`review_widget(sources, job=..., index=..., viewport_summary=...,
source_receipt=..., people=..., mode=..., checkpoint=...)` takes exactly two ordered
source descriptors, each containing `session`, `delivered_frames`, `intent` and
`envelope`. These must come from the qualified pair reader. `index` is 0 or 1;
the first ledger cannot borrow future-session caption history. People contain
only the admitted display IDs/spellings, never evaluator truth. Only the primary
`open_with_names` mode is supported by this content check.

The result includes full private native text lineage, matched widget states,
original per-caption source clocks, missing/unobserved spans, ambiguous native
predecessors, evidence hashes and false acceptance fields. These dictionaries
must be persisted privately by the guarded caller, never to GitHub.

This is a content component. The caller must independently admit the selected
plan/population, transport, exact owners, pair lifecycle/delivery and fixed display
roster before calling it. The earlier complete selected-run reviewer is immutable
and does not yet invoke this component. Integration with those joins, timing and
functional restart acceptance remains separate. It proves neither actual word
visibility, exact consumed-event attribution, phonetic alignment, physical screen
latency, naming accuracy, controlled hardware fit nor N4/N5 acceptance.

## Development probe

`probe_restart_native_content.py` runs 23 checks: twelve original native-caption
adversarial cases against a real explicit-prefix reader, three additional
released-content cases and eight two-history widget cases. It calls the original
pure span-state/casing code and the real native/viewport parsers. No native reader
is mocked. Source clocks and widget geometry are synthetic fixtures; there is no
model, audio source or GUI execution and no actual production pair qualification.

The probe requires the current healthy D1 worker and a fresh private `--output`.
It pins the helper to CPU14/BelowNormal/one math thread, uses the existing writer
lock, and checks time, C:/G: floors and the shared private allowance. Outputs are
PROBE_OWNER, ADMISSION, exact source snapshots, all fixture files, tests.txt and
RESULT or FAILED. Preserve failures and choose a new suffix for another attempt.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\probe_restart_native_content.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-native-content-probe-v1'
```

CMD:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_native_content.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-native-content-probe-v1"
```

Anaconda Prompt: use the same CMD commands and explicit admitted interpreter.
Do not install packages or change the campaign environment. Direct unittest
execution is unsupported because the probe supplies verified source paths and
private fixture roots. The production functions are internal APIs, not standalone
admission commands. No frozen release or running source is changed. The Pi remains
off; live device integration is deferred until the user reconnects it.
