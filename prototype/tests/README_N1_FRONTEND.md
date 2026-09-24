# N1 frontend EVENT fixtures and isolated rendering

Purpose: verify the same portrait frontend independently of neural models,
audio, microphone/USB access, personal profiles and acoustic evaluation scenes.
These are source-only synthetic **EVENT** fixtures; they are not synthesized
conversations, benchmark inference, physical display tests or field accuracy.

Files:

- `test_backend_catalog.py`: canonical composition IDs, no unavailable fallback,
  common logical modes, and explicit spatial-telemetry requirement.
- `n1_event_fixtures.py`: fictional A/B/A spans, short interruption, concurrent
  event-window updates, late correction, scrolling and a 420-word paragraph.
- `test_n1_frontend.py`: a stub controller and withdrawn Tk root; full 480×800
  logical shell layout is allocated inside an unmapped root. It checks fixed
  active-pane position, independent history scrolling, retained row marks,
  unchanged inputs, full words, backend selection, bounded Unknown and explicit
  closed assumptions, and actual GUI-applied first-label receipts.
- `run_private_desktop.py`: Windows `CreateDesktopW` + `CreateProcessW` isolation.
  No `SwitchDesktop`, input injection, focus calls or user-screen capture. It
  verifies the input desktop remains unchanged and closes owned handles. Only
  its owned child is terminated on timeout. The launcher is for audited tests;
  `hardware_access:false` reflects this approved module set, not an OS sandbox.
- `test_n1_capture.py`: synthetic app is mapped only on that private desktop;
  `PrintWindow` renders its known client handle. PNG encoding uses the standard
  library. It refuses to run a mapped app outside a `codex-n1-*` desktop.

Inputs: source fixture rows, backend JSON, existing Tk/runtime, and a fresh
receipt directory. Outputs: `unittest.txt`, `tests.json`, `isolation.json`, and
for capture tests a `screenshots` directory with seven 480×800 PNGs, hashes and
GUI presentation receipts. No image contains the user's desktop or documents.
No real model, gallery, recording, playback endpoint or microphone is opened.

## Commands

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m prototype.tests.run_private_desktop --receipt-dir 'G:\Just_Peachy_N1\20260924_campaign\evidence\frontend\manual-run' prototype.tests.test_backend_catalog prototype.tests.test_n1_frontend prototype.tests.test_n1_capture prototype.tests.test_ui prototype.tests.test_caption_display
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m prototype.tests.run_private_desktop --receipt-dir "G:\Just_Peachy_N1\20260924_campaign\evidence\frontend\manual-run" prototype.tests.test_backend_catalog prototype.tests.test_n1_frontend prototype.tests.test_n1_capture prototype.tests.test_ui prototype.tests.test_caption_display
```

Use a different `--receipt-dir` each run to preserve prior failures. The default
240-second timeout can be changed with `--timeout-seconds 600`. Use only named,
audited nonhardware modules. Do not run the legacy Tk modules directly on the
user's desktop. The launcher adds the worktree's prototype and vendor import
paths; it never redirects imports to the original repository. Linux requires
a separately configured virtual display; this launcher does not claim Linux
support or install a display server.

## Shared controller/UI contract

`just-peachy.caption-event.v1` is the common frontend contract identifier.
Controller snapshots retain `mode`, `recipe`, `tap`, `selected_ids`, `strict`,
`rows` and separate backend metadata: `backend_id`, `backend`, `backends`.
Backend selection calls `select_backend(manifest_id)`. The controller validates
the immutable ID before state/model operations and gates Start on availability.

Rows retain stable `id`, `caption_key`, `raw_asr_text`, provisional/final display
text, identity label, profile/track IDs, `token_range`, `final`, selected/visible
state and assumption provenance. Timed ownership additionally exposes stable
`span_ids`, `source_start_sec`, `source_end_sec`, `timing_kind`, speaker revision,
first core-proposed label, committed label and speaker history. Coarse observed
revision spans are not phonetic timing. Paragraph grouping never rewrites span
identity. Coarse overlapping row windows group unfinished active panes as a UI
hint; they are not simultaneous-speech ground truth.

The fixed active pane shows the latest turn and concurrent unfinished windows.
The separate history widget retains all rows with active rows elided there, so
full archived text remains intact without duplicate visible captions. A partial
edit changes the active suffix and never scrolls history to its bottom. A newly
completed turn enters history; explicit history scrolling is preserved. Large
active paragraphs scroll in their own bounded pane. Back to live resumes both
panes. Font/theme/zoom apply to both.

`just-peachy.gui-presentation.v1` receipts are separate from core proposals.
They include exact applied label, stable spans, each span's first GUI label,
GUI label revision, applied monotonic time, backend, row, pane and Tk root state.
Grouped headings explicitly record suppression. The optional controller
`record_presentation(receipt)` callback can journal them. In-memory audit state
is bounded to 256 receipts and 8192 spans; the core journal is the durable
record. Scope is always **Tk text applied; viewport visibility and physical
scanout not measured**. Rendering/cosmetic delay does not change neural output
or establish live acoustic latency.
