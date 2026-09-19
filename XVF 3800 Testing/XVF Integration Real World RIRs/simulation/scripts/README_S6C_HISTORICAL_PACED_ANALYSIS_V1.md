# Closed historical paced analysis

`s6c_historical_paced_analysis_v1.py` converts **already completed** S6C-paced
B00, B01 and B36 control cells into source-bound observations and predictions.
It does not launch native workers, construct models, read model weights or PCM,
score predictions, change historical sources, or approve campaign completion.

Inputs are the exact reviewed historical manifests under
`G:\Just_Peachy_S6C\20260910T123540Z\paced_controls`, their launch/completion and
quiet-lease records, the sealed S6B epoch2 and original B00 source authorities,
and each worker's declared event, display, summary and process-sample files.
The pinned inventory V4 metadata API validates the original 16-case first pass
and four-case second pass, both taps, exact input/gain/profile/driver identities,
native PCM completion declarations and closed recorded process identities.
The adapter additionally verifies the exact consumed payload buffers. PCM and
model payloads remain transitively admitted by those completed authorities;
they are not independently rehashed here.

Outputs go to a fresh `reports\S6C\20260910T123540Z\historical_paced_analysis\NAME`:
`PLAN.json`, preserved metadata snapshots, per-cell measurement JSON, compressed
predictions, one prediction index per repetition and `RESULT.json`. A failed run
preserves completed outputs and writes `FAILURE.json`; it is never treated as an
empty prediction. Use a new name after a failed preparation or run. The adapter
does not resume partial analysis or alter a prior output namespace.

## Attribution and clock semantics

- Run B00 with `--generation baseline`, and B01/B36 with `--generation research`
  in separate fresh Python processes and namespaces. B00 uses the exact original
  `s6b_replay.historical` attribution body, with only its two file reads replaced
  by verified buffers. Its actual emitted decision windows come from the original
  `SpatialEvidence` support; one embedding per decision follows the frozen native
  code. Raw vectors, modeled feature availability and the common scheduler are
  unavailable. Those fields are null or explicitly unavailable, never invented.
- B01/B36 use the exact frozen S6B epoch2 `extract_events`, `scheduler_inputs` and
  `run_scheduler` bodies plus the original epoch2 tracker and scheduler classes.
  Actual independent ASR observations and finite native vectors are required.
  Decision sequence, shared transcript fields and final retained utterances must
  equal the same native run. Extra execution clock fields are excluded explicitly;
  causal modeled availability remains part of parity. No C-generation APP replaces
  these classes, and no C naming API is called on historical events.
  Semantic parity excludes only `policy_compute_sec`, `modeled_available_at_sec`,
  `compute_finished_elapsed_sec`, `release_watermark_lower_bound_sec` and
  `release_after_all_lanes_closed`. The two release diagnostics differ when native
  source-cursor watermarks seal later than replay's immediate modeled availability.
  Actual native values remain unchanged in the emission measurements. Causal
  `available_at_sec`, source support, label/text and all other shared fields remain
  exact. The source-only synthetic roundtrip proved this distinction without
  reading any actual paced cell or changing native behavior.
- Actual event-emission UTC is reported relative to that cell's `source_started`
  UTC and current source cursor. This is neither GUI latency nor phonetic latency.
  The original event serialization rounds the cursor to six decimals; only that
  same projection is applied when checking the separately bound display log.
  Native driver observation times remain in the source display file. Negative
  delays and backward UTC observations are retained and flagged, not corrected.
- Original source-cursor attribution for B00 and modeled support for B01/B36 stay
  separate from these actual-wall observations. There is no synthetic historical
  finalization timestamp or claim of current-speaker/name correctness.
- Trajectories report observed samples, gaps, missing LIVE/telemetry, observed
  backlog, RSS sum upper bound, USS private resident, Windows private commit and
  PSS separately. A sampler `tree_complete` flag cannot prove OS descendant
  enumeration: the original sampler can fall back to root-only after an error.
  No terminal sample or continuous maximum is fabricated. CPU totals sum each
  observed process's maximum lifetime counter and include its earlier work; they
  are not interval-only CPU. Native worker costs are separately retained, and
  inclusive/nested cost phases or concurrent lane times must not be added.
- All repeats are retained in separate complete indices. Repetition comparisons
  report words, labels, shared transcript sequence, journal digest and, when
  available, exact-window vector differences. Missing B00 vectors are unavailable.
  Repeated scenes are dependent observations and must not be pooled as new scenes.

## PowerShell

Use a fresh PowerShell process for each `run`. The explicit executable works
without activating an environment. No command below starts a native/model job.

```powershell
$simTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$pythonTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location -LiteralPath $simTask
& $pythonTask scripts/s6c_historical_paced_analysis_v1.py checks
& $pythonTask scripts/s6c_historical_paced_analysis_v1.py source-checks
```

Only **after the whole historical manifest and its owners are closed**, prepare
B00 from the 80-cell manifest. Copy its exact hash from the existing authoritative
manifest/admission receipt; do not use an unreviewed replacement path or hash.

```powershell
& $pythonTask scripts/s6c_historical_paced_analysis_v1.py prepare --manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_v1\MANIFEST.json' --manifest-sha256 EXACT_CLOSED_MANIFEST_SHA256 --generation baseline --name b00_first_v1
& $pythonTask scripts/s6c_historical_paced_analysis_v1.py run --plan 'reports\S6C\20260910T123540Z\historical_paced_analysis\b00_first_v1\PLAN.json' --plan-sha256 EXACT_PREPARED_PLAN_SHA256
```

For B01, repeat in another namespace (for example `b01_first_v1`) with
`--generation research` and the same controls manifest. For B36, use
`paced_controls\b36_v1\MANIFEST.json`, its own exact hash, `--generation research`
and a distinct name such as `b36_first_v1`. Each generation selects 40 logical
cells (32 first-pass + 8 repeat cells). Do not pass the continuous B36 or sentinel
manifest; those require their separate adapters. The shared active paced quiet
lease blocks `prepare` and `run`.

## Anaconda Prompt / Windows Command Prompt

The commands are identical in Anaconda Prompt and ordinary CMD; the exact EDGE
executable selects the preserved runtime without an environment-name assumption.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_HIST_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6C_HIST_PY%" scripts\s6c_historical_paced_analysis_v1.py checks
"%S6C_HIST_PY%" scripts\s6c_historical_paced_analysis_v1.py source-checks
"%S6C_HIST_PY%" scripts\s6c_historical_paced_analysis_v1.py prepare --manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_v1\MANIFEST.json" --manifest-sha256 EXACT_CLOSED_MANIFEST_SHA256 --generation baseline --name b00_first_v1
"%S6C_HIST_PY%" scripts\s6c_historical_paced_analysis_v1.py run --plan "reports\S6C\20260910T123540Z\historical_paced_analysis\b00_first_v1\PLAN.json" --plan-sha256 EXACT_PREPARED_PLAN_SHA256
```

`checks` exercises synthetic generation, span, buffer, display, clock, missingness
and closure-owner boundaries. `source-checks` admits only the two already prepared
manifest metadata trees and their original code, compares original attribution
AST and exercises synthetic baseline attribution. It does not read completed
cell payloads or assert native completion. Either supports `--output FRESH.json`
to publish a source-bound check receipt without overwriting existing evidence.
Empirical native/shared parity still gates every later research cell; pure/source
checks alone do not establish that actual paced outputs will pass.

The pre-repair helper, README and all prior source/check receipts are preserved
under `staging/s6c/20260910T123540Z/historical_paced_analysis/pre_release_diagnostics_v1`.
`independent_review/HISTORICAL_PACED_PRE_REPAIR_PRESERVATION_V1.json` maps the
original byte bindings to those copies. Only the two additional parity exclusions
changed executable behavior; original native/replay classes and output payloads
remain untouched. The separate maintained V2 independent roundtrip fixture tests
the corrected boundary and rejects changed causal availability, source support,
labels and words.
