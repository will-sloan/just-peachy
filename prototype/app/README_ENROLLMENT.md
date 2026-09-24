# Paragraph enrollment and progress (task 06)

Purpose: `enrollment_quality.py` preserves the existing audio quality/embedding
calculation. `enrollment_progress.py` provides an optional ordinary-ASR text
estimate and display interpolation. `controller.py`, `people.py` and `ui.py`
connect these to the existing microphone, private UUID store and touch screen.

## Run (from repository root)

PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

Inputs: existing pinned local models/runtime; configured XVF O0/O1 route; the
participating person's consent and speech; name or existing UUID; 15/30/60 target
or Read paragraph → Done. The offered paragraph stays editable (max 4096 chars).
No new dependency, model download, pronunciation dictionary or aligner is used.

Outputs: private profile vector, unique source spans/hash, duration, quality,
route and capture-integrity receipt. Paragraph mode also stores offered text/hash
explicitly marked **reference only**, ordinary raw ASR endpoint segments with
source-sample bounds, and estimated word coverage/agreement. No raw reference
WAV is retained. These are not phoneme/word alignments or a verified transcript.
Timed enrollment does not store the offered paragraph or run this extra ASR
stream. Existing profiles default to timed validation without migration.

## Invariants and limitations

- `target_sec=None` explicitly means paragraph mode. Its minimum is one admitted
  8000-sample / 0.5-second window, matching the installed speaker adapter. This
  technical minimum is not a recommendation for reliable identity. Under 15s is
  labelled limited evidence using the existing shortest timed option as a UI
  reference, not a newly tuned accuracy threshold.
- Preserve disjoint 10s segmentation blocks, zero context only for the final
  partial block, 0.5s embedding windows, RMS gate from config, speech ≥0.6,
  overlap ≤0.2, clipping ≤0.005, and centroid consistency ≥0.3. Padded samples
  never count as support. Input must be finite, source contiguous and gap-free.
- `process(..., source_start=offset)` is idempotent for an identical already
  submitted block. Conflicting/overlapping/gapped support fails. Identical words
  newly spoken at distinct source times remain legitimate separate support;
  source identity is not an acoustic replay detector. Reusing a saved exact
  source for the same UUID is rejected by the existing store.
- Quality publishes scalar verified support after each existing 0.5s window,
  never by re-running inference. UI interpolation uses the existing 80ms poll
  and cannot exceed the latest verified count. Measured level activity is not
  speech; quality backlog is captured minus analyzed source time.
- In paragraph mode a separate *stream*, sharing the existing resident Sherpa
  recognizer/punctuator, runs on the same worker after each unchanged quality
  block. If this is the first ASR use it loads that existing model once. There
  is no second capture, concurrent decoder owner, script hotwording or forced
  decoding. First estimates may take 10s of captured audio; Stop processes the
  remainder immediately. Quality and ASR backlog are shown separately.
- Ordered case-folded word matching (standard-library SequenceMatcher) gives
  coverage = matched reference words / offered words, agreement = 2×matches /
  total offered+recognized words. It can regress after ASR revisions. Empty
  script has no coverage percentage. Names, skips, substitutions and paraphrases
  affect only this estimate. Optional ASR failure shows unavailable and does not
  invalidate an otherwise sound voice reference.
- Done/Stop exposes DRAINING → ANALYZING → READY. Save requires READY, quiet
  workers, capture integrity and the actual quality gate. Cancel, failures and
  Save release temporary audio, per-window vectors and the enrollment ASR
  stream. Resident models and previously saved people remain.
- Maximum capture remains 180s, one bounded queue of 20 blocks, one quality
  worker. No inference, USB, disk or UI work is added to the audio callback.
  Profile metadata retains its existing size bounds; an excessive metadata
  payload is rejected visibly, not silently truncated into a saved reference.

The installed ReDimNet ONNX input is `waveform: float32[1,num_samples]`; it has
no transcript input. Knowing the script does not improve its vector or fine-tune
it. See [upstream audio interface](https://github.com/PalabraAI/redimnet2).
The [CMU dictionary license](https://github.com/cmusphinx/cmudict/blob/master/LICENSE)
was reviewed as a reference only; nothing was installed or redistributed from
it. Existing code/weights/data licensing remains separate; task 06's no-addition
ledger is `docs/UIITER2_06_DEPENDENCIES.json`.

See `../docs/ENROLLMENT_GUIDE.md` for human use and
`../tests/README_ENROLLMENT.md` / `../tools/README_ENROLLMENT.md` for checks.

Task10 routes paragraph ASR and reference-quality audio independently according to Advanced noise selection. Enhanced references bind the helper hash and are incompatible with original-domain queries. The unchanged quality gate is measured, not recalibrated. See README_NOISE.md.
