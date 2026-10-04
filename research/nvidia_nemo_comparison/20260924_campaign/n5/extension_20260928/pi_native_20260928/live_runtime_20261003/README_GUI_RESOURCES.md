# Review resources from a closed GUI workflow

`review_gui_resources.py` reads one explicitly named complete GUI mirror. It
checks actual natural job/worker/source closure, manifest hashes of selected
metadata and immutable read-only SQLite, then reports both sessions' sample
counts, numeric health/backlog ranges, minute bins, ledger use and retained work
bytes. It separately summarizes the external whole-unit sampled-memory trace.
No waveform, transcript, model or native process is opened or displayed.

For exactly one closed saved-input qualification worker, add `--pipeline-only`
and pass its full mirror instead. The same bounded health/closure review applies;
it does not infer GUI actions or fabricate a missing GUI result.

Inputs: complete `--mirror` with `MIRROR_COMPLETE.json`, selected worker metadata,
closed `history.sqlite3` and `SAMPLED_MEMORY.jsonl`; a private `--output-root`.
Outputs: a fresh CPU14 numeric owner receipt and bounded private `REVIEW.json`.
The aggregate trace is explicitly partial/late-start, not a continuous or full
live-phase peak. A discarded replay may retain less metadata than the kept live
recording; absence of its summary does not create a claimed final telemetry row.
Speech/identity accuracy and hour-long stability are not inferred.

Set N, Q and PY to the paths in `README_PACKAGE.md`. PowerShell:

```powershell
& $PY -B "$N/review_gui_resources.py" --mirror "$Q/gui-qualification-02-monitor-01" --output-root "$Q/audit-preparation"
```

CMD or Anaconda Prompt:

```bat
"%PY%" -B "%N%\review_gui_resources.py" --mirror "%Q%\gui-qualification-02-monitor-01" --output-root "%Q%\audit-preparation"
```

The program registers actual CPU14 ownership before project reads/imports. It
never invokes SSH or starts native work, and refuses incomplete/tampered selected
evidence. Existing mirrors and immutable packages remain unchanged.
