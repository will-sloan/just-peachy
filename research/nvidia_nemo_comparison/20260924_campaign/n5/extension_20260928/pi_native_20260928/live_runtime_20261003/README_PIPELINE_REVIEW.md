# Closed pipeline allocation and private WER review

`review_pipeline_allocation.py` reads one explicitly identified, complete PC mirror. It performs no native work, SSH, model loading, audio playback, database writes or broad recording search. Before project imports/reads it sets CPU14 and durably registers its actual owner in a fresh private output directory.

Inputs are `--mirror` (contains MIRROR_COMPLETE/MIRROR_MANIFEST and closed-output), `--session` exact ID, `--reference` the existing SHA/provenance-pinned38-word matched reference receipt, and `--output-root` private audit preparation. It requires exact owner+cgroup closure, manifest digest, selected evidence file readback, source/identity sample coverage and matching source WAV SHA. It opens SQLite with `mode=ro&immutable=1`, validates complete compact-event recovery, and reads final labelled rows without printing transcript text.

Output `REVIEW.json` contains actual writer totals, physical SQLite size/logical allocation ledger, event type counts/sizes, compaction integrity, sample/closure evidence, model-load RSS/PSS/VM and health/thermal ten-second bins. Linear hourly projections are explicitly estimates, not native performance or storage qualification. They include short-run fixed overhead and do not predict every future caption/raw/event distribution.

WER uses the receipt's exact lowercase/remove ASCII punctuation/collapse whitespace normalization, with no number/contraction expansion, full ordered final captions and the complete38-word reference. Only normalization, word/error counts and WER are public; no transcript/reference words are printed. Equal edit paths prefer substitution, then deletion, then insertion. This is one matched-input text result; it does not measure DER or establish multi-speaker quality.

PowerShell:

```powershell
& $PY -B "$N/review_pipeline_allocation.py" --mirror "$Q/pipeline-qualification-04-monitor-01" --session 18e940c490514718ba05f24a8dfe88db --reference "$Q/audit-preparation/matched-reference-0776a5e2f07a4ce487a413902f182c41/REFERENCE.json" --output-root "$Q/audit-preparation"
```

CMD or Anaconda Prompt:

```bat
"%PY%" -B "%N%\review_pipeline_allocation.py" --mirror "%Q%\pipeline-qualification-04-monitor-01" --session 18e940c490514718ba05f24a8dfe88db --reference "%Q%\audit-preparation\matched-reference-0776a5e2f07a4ce487a413902f182c41\REFERENCE.json" --output-root "%Q%\audit-preparation"
```

Use `PY=C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe`; `N` is this source directory and `Q` is the private `B/live-runtime-20261003`. No package/environment installation is required. Each invocation creates fresh evidence and leaves all prior sources/results unchanged. Native full-app-hour review may use a separately reviewed labeled repeated-reference protocol; this short-input reviewer does not silently repeat the38-word reference.
