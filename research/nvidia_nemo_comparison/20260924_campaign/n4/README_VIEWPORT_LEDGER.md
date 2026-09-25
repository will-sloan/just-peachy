# Bounded private viewport evidence

Purpose: retain actual sampled caption/name visibility for future application
runs without repeatedly copying long caption bodies into every span's memory
history. `viewport_ledger.py` consumes unchanged widget_visibility.snapshot
objects, stores changed rows once in a private JSONL file and keeps compact
references for each span's first visible, first final visible and latest state.
Unchanged observations still retain their exact observation timestamp. Removal,
resegmentation, strictly filtered/hidden text, heading changes and assumptions
remain explicit; no names, missing words or continuously visible intervals are
inferred. The observer does not mutate the application or its input observations.

It allows at most 512 rows, 8,192 lifetime spans and 16,384 active row-to-span
memberships, 8 MiB per record, 64 MiB per log and 8 MiB for a compact summary.
Overflow fails explicitly, preserves the successful prefix and rejects further
observations. It never silently evicts evidence to claim completion. All calls
belong to the original UI thread. References include byte offsets, lengths and
record hashes; truncated/corrupt records are rejected. Retirement has one
back-reference. Full observation clock metadata is retained, including samples
before the source clock becomes available. Later clock changes are rejected.

Outputs contain private captions and identity metadata: keep them outside Git.
`OBSERVATIONS.jsonl` is append-only within a fresh run directory. `SUMMARY.json`
contains compact state, bounds, failure status and its sealed log binding.
`expand_summary` is an evaluator-only compatibility view and must not run in
the measured application: expanding large histories deliberately reintroduces
caption duplication. Recorder elapsed time is accumulated separately; it is
not CPU time, memory usage or a deployment-fit measurement. Synchronous disk
cost and snapshot cost must be included in future whole-application resources.

## Qualification inputs and outputs

`probe_viewport_ledger.py` verifies WIDGET_VISIBILITY_CHECK_V2.json and its 160
saved private Tk observation pairs, then compares expanded ledger results exactly
against the previously saved VisibilityHistory summaries. It does not replay
audio or start Tk. Eight tests also cover final flags without a text rewrite,
name changes, retirement/resegmentation, corruption, source clocks, ownership,
disk/span limits and an 8,192-span long-text fixture. That fixture advances
synthetic observation timestamps; it is not the required actual 20-minute run.

The launcher uses CPU14, below-normal priority, one math thread and GPU off.
It checks shared payload accounting with 6 GiB of reservations, drive floors,
the packaging reserve and a 128-MiB probe output bound. It imports no application
model or GUI code and performs no new source, model, microphone, USB or playback
operation. It can accompany the sole component extraction owner; it makes no
controlled resource/timing claim. Outputs also include ADMISSION.json,
unittest.txt, CHECKS.json and RESULT.json. Deliberately invalid fixture ledgers
are retained, including one tampered negative-test log; they are not application
results. The 160 saved-case ledgers remain intact and hash-verifiable.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n4\probe_viewport_ledger.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\viewport-ledger-v1'
```

## CMD / Anaconda Prompt

Use the existing pinned interpreter; no conda environment change is needed.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_viewport_ledger.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\viewport-ledger-v1
```

After admission, preserve code and outputs. A repair needs a fresh derivative
and output directory. This helper earns no N4 integrated acceptance, continuous
wrong-name exposure, physical scanout, target-memory fit or source-paced latency
qualification. Join it to the later actual source/consumer/resource evidence.
