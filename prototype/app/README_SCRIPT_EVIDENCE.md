# Optional script-aware enrollment — task09

Purpose: describe independently recognized paragraph speech and select a bounded
alternate AUDIO reference using the existing ReDimNet model. Text is not an input
to that model. This improves provenance and permits a diagnostic comparison;
the ordinary anchor remains the only reference used for identity decisions.

## Run and use

From `C:\Users\amiri\Documents\GitHub\just-peachy`, PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

1. Settings → Advanced → **Text-aware reference selection: On** (default Off).
2. People → Add person / Add reference → **Read paragraph → Done**. Edit the
   offered script if needed. The person participates and consents before capture.
3. Tap Done, wait for READY, then **Review paragraph coverage**. This shows
   intended/ordinary-ASR text, approximate agreement, uncertain words, unknown
   timing, rejected/unknown duration and original versus alternate duration.
   **Add correction / review note** uses the touch keyboard; notes are separate
   from raw ASR and do not rewrite timing or voice admission. Return and Save.
4. People → a person → **Review latest paragraph evidence** reads the saved
   sidecar. It is a review, not a new recording or inference request.
5. Start a name mode with a compatible tap. Advanced → **Compare base / alternate
   voice scores** shows the latest query and its age. Cosines are not probabilities.
   Turn the toggle Off, then Stop/Start, for an original-only comparison.

Toggle changes apply at the next enrollment / Start. Turning Off immediately hides
the score view but does not restart an active session. Existing free speech,
15/30/60-second enrollment, caption-only and spatial/seat modes remain available.
No new models, downloads or optional aligner setup are required. Windows is
checked; CM5 ARM64/resource qualification and fresh live participants are pending.

## Inputs, algorithm and outputs

`script_evidence.py` consumes unique captured mono16k float32 audio, the existing
quality result, unbiased Sherpa endpoint/token emissions, intended script, route
and frozen model hashes. It runs after capture/quality drainage, outside the
callback, using the same resident speaker model. `script_evidence_ui.py` supplies
the scrollable review/comparison pages; controller and store own persistence.

Sherpa1.13.4 token times are approximate transducer emissions, offset by the
recognizer's segment start. They are **not calibrated word confidence or phoneme
boundaries**. BPE fragments must reconstruct the independent ASR words. Unknown,
invalid and beyond-source decoder-flush emissions remain unsupported; valid
earlier words survive without clamping timestamps. `phone_boundaries=null` and
dictionary/pronunciation fields are unavailable. No canonical pronunciation is
imposed, no CTC model is loaded and no text is forced into ASR.

Selection uses contiguous admitted quality runs, nonoverlapping 2–4-second
contexts, at least two script-agreeing estimated words, and at most six contexts.
Greedy lexical diversity omits duplicate/no-new-word contexts. Quality remains
the existing RMS/clipping/speech/overlap/consistency gate, which cannot guarantee
only one person spoke. All audio in a selected context is recorded by its exact
sample bounds, including unindexed speech. Audio is never spliced to form a
reference, and repeated words do not multiply source duration. ReDimNet's existing
0.5-second minimum is exceeded by these contexts. Normalized context vectors are
equally averaged and normalized; per-person alternate centroids average compatible
reference alternates without a maximum-over-words advantage.

Output: original `.npy` anchor plus a versioned, hash-bound `<reference-UUID>.script.json`
in the external private `people/<person-UUID>` directory. The sidecar holds
source/tap/preprocessing/model bindings, transcript/script hashes and versions,
uncalibrated word spans, null phone boundaries, quality/coverage, unique context
IDs/bounds/vectors, retained duration, corrections and helper cost. Raw enrollment
audio is released after analysis; a sidecar does not let you reconstruct it.

The ordinary normalized centroid and existing S6/S7 decision thresholds do not
change. The optional extra matrix comparison returns diagnostic values only;
`PersonalGallery.score()` still returns the original scorer's result. **Matched-
content/phonetic identity support is unavailable**, because reliable query-content
confidence and validated acoustic boundaries are missing. No common content,
unknown timing, short/poor-quality audio or helper failure preserves base behavior.
Wrong intended text cannot discard otherwise admitted original speech.

## Bounds and storage compatibility

At most 180 seconds of temporary float32 source (11,520,000 bytes), with a temporary
concatenation copy up to another 11,520,000 bytes; no persistent raw WAV. Up to six
extra embeddings after Stop, no extra live ASR worker. Sidecars are limited to
256 KiB including their actual JSON formatting, with 16 notes of at most 500
characters. Oversized evidence fails the optional helper and keeps the original
reference available. A full note budget refuses the note before changing data.

Rename preserves UUIDs/vectors; delete removes declared sidecars too. Private
unencrypted profile export/import includes exact sidecars with checksums and the
existing 16 MiB archive limit. O0/O1 and gain/domain/preprocessing remain separate.
Damaged declared sidecars are rejected visibly, never silently accepted. For a
corrupt profile, restore a validated private export; switching Off is not an
integrity bypass. Import does not overwrite existing UUIDs.

Saving/importing evidence adds `script-evidence-v1` to external `DATA_SCHEMA.json`.
The updater refuses a release without this feature; the marker remains
conservatively even after deleting all sidecars. Do not remove it to force an old
reader. Original-only behavior is available by toggling Off in this source.
Task08's immutable ZIP is preserved; it does not contain this optional extension.
For source rollback and separate compatible data roots, follow
`../docs/UIITER2_09_HANDOFF.md`. Tests: `../tests/README_SCRIPT_EVIDENCE.md`;
actual audio checks: `../tools/README_SCRIPT_EVIDENCE.md`.

Task10: optional enhanced references retain the helper SHA in route/model provenance. Paragraph ASR follows its selected route; voice-context selection follows identity audio. These independent streams do not create validated matched-content timing. See README_NOISE.md.
