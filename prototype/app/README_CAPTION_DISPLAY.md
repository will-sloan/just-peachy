# Caption presentation (task 02)

`caption_display.py` supplies GUI-only identity labels and supported same-turn
grouping to `ui.py`. Inputs are detached controller rows with stable S7 segment,
utterance, token-range and track metadata. Outputs are caption header strings
and grouping decisions. It neither changes rows/events nor loads models, reads
audio, creates enrollments or writes personal data.

Default: Compact 21px captions, immediate text, generic Unknown, optional spatial
panel off. Saved display preferences still override defaults. Settings offers
150/300ms fixed-deadline batching; it keeps only the latest snapshot and cannot
renew its deadline on every partial. The existing 80ms GUI poll and OS scheduling
are additional. Final text uses the same bounded optional display path; endpoint
rules and all native journals stay unchanged. No GUI timer is a hard real-time
guarantee on an overloaded desktop.

Pending identity has a 1.2s deadline from first visible utterance evidence; it
resolves at the next applied display update. The 80ms poll, selected 0/150/300ms
batching and OS scheduling can add to that visible interval. A changed native
segment ID cannot renew the deadline.
Names/advanced numbered labels require 200ms of unchanged display evidence.
A contradicted name is immediately removed on the next applied snapshot; the
old name is never carried forward to hide uncertainty. A stable late name can
still replace Unknown. Explicit unavailable/invalidated voice evidence shows
`Unknown · voice unavailable`; unresolved evidence shows dots then Unknown.
Historical supported labels annotate historical words, not current localization.

Selected closed-group mode is an explicit exception: a controller-validated
selected display name is shown immediately, including **Name · assumed** when
voice evidence is missing. Its separate display UUID/provenance does not replace
raw acoustic identity or add a confidence score. The pending/Unknown timer still
applies to the other modes. See README_ROSTER.md for the bounded fallback order.

Advanced retains the native numbered anonymous labels. Ordinary Unknown rows
remain separate. Grouping only suppresses a repeated heading for contiguous,
supported same-track tokens inside one native utterance, with compatible UUIDs;
all segment IDs and raw rows remain separate. A handoff or Unknown breaks it.
The Tk renderer edits changed ranges and retains surviving marks even when S7
replaces an active segment. It does not rebuild the full history on partials.

N1 adds a fixed 184px active caption pane below independently scrollable history.
The latest turn and concurrent unfinished source windows occupy the active pane;
history retains those rows with their active copies visually elided. Source
window overlap is a display hint, not phonetic/simultaneous-speech truth. Long
paragraphs scroll inside the active pane, all words remain accessible, and
partial revisions never force history to its bottom. Back to live resumes both
views. Separate bounded GUI presentation receipts retain the first applied
label per stable span and later label revisions; they do not claim physical
scanout or actual user visibility. See `../tests/README_N1_FRONTEND.md` for the
safe private-desktop test/capture commands, inputs, outputs and event contract.

The visible Backend selector and model-only manifest registry are documented
in `README_BACKENDS.md`. Every backend preserves the same logical mode list;
unimplemented candidates show an explicit reason and cannot start inference.

Launch from the repository root in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

Inputs for the full app are consented XVF speech or an explicitly selected,
prepared mono16k WAV. Outputs are the existing captions and private session
journals. The UI opens idle. Model/profile locations remain unchanged. See
`../docs/UI_ITERATION.md`, `../tests/README_CAPTION_DISPLAY.md` and the task 02
handoff for checks, exact rollback, screenshots and limitations.
