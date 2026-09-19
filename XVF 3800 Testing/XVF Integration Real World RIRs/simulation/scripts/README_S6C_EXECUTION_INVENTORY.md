# S6C physical execution inventory

`s6c_execution_inventory.py` reads durable S6C receipts to produce a versioned
accounting snapshot for the handoff. It never loads models or opens waveform,
vector, compressed prediction or full event-log payloads. It does not modify
native evidence, historical controls, galleries or the working application.

## Inputs and authority

The fixed run is `20260910T123540Z`. The collector reads the S6C report directory
and `G:\Just_Peachy_S6C\20260910T123540Z`. It discovers epoch manifests,
`run_receipt.json` and `attempt_receipt.json`, current worker identities, native
coordinator completions/rows, prediction indexes, preserved failure resolvers,
the completed enrollment process, native-prefix receipts, and the separately
prepared historical paced-control manifest. Model/code/input hashes and payload
sizes come from these exact metadata authorities; they are not rehashed here.

Every consumed metadata file is read once per snapshot with bounded sharing and
concurrent-write retries. Its exact bytes are copied to a content-addressed local
`metadata_snapshots` directory. `METADATA_SOURCES.json` maps the original path and
hash to that preserved copy, so a later mutable attempt/status update does not
invalidate the earlier accounting. Unreadable or inconsistent metadata creates
an explicit flag and incomplete audit status. No partial JSON is accepted.

## Counting rules

- A physical epoch attempt uses PID, process creation time, start timestamp and
  exact job identity. The complete/attempt pair and copied views of that same
  attempt merge. Separate smoke, repeated or retried executions remain separate
  even when they have the same job key. Conflicting session identities reject.
- Completed actual native sessions are counted separately from STARTED/FAILED
  attempts with no recorded session. A missing native session is not proof that
  no model loaded. Current worker metadata can identify a still-running session.
  Inaccessible process inspection remains unknown, never falsely closed.
- Unique job keys and conservative inference-dependency groups are separate from
  physical execution counts. The grouping retains the exact epoch and keeps full
  profile/cue/gallery dependencies for state-driven dispatch. It is descriptive
  accounting, not a new cache admission mechanism or proof of numerical parity.
- Cumulative resident bundle counters are reduced by the maximum for each exact
  PID/creation-time identity. They are never summed across that worker's scenes.
  Actual gallery cache misses are deduplicated by worker and manifest. Repeated
  gallery `loaded_elapsed_sec` provenance is not charged as another load.
- Native coordinator row references, including explicit `COMPLETE_REUSED`, are
  separate from physical executions. Prediction indexes can reference the same
  output again or materialize another policy projection; neither is another
  neural execution. Model-free synthetic failure indexes are excluded explicitly.
- The actual enrollment process reports its 1,976 E/C embedding calls separately
  from full-pipeline sessions. Its cache hits are not new embeddings. The two real
  prefix sessions are separate empirical diagnostics; their common-clock replay
  and numerical fixtures are not extra native sessions.
- Historical paced controls are admitted only through their actual manifest and
  `WORKER_RESULT.json` schema. Prepared/not-launched cells stay explicit. Unknown
  native long-session results require the distinct `s6c_continuous_paced_native.v1`
  schema, matching owner/profile/composition and one closed session. Chronological
  model-free results are excluded. Unknown future HIL schemas or unmatched
  session directories are flagged for a later narrow adapter, never silently
  counted as completed work. A host concatenation is not continuous XVF state.

The collector reads bounded metadata during an interval, not an atomic global
snapshot. Work may finish after enumeration. Its status therefore cannot certify
the whole S6C study, broad accuracy coverage, paced acceptance, hardware behavior
or CM5 suitability. Resource maxima and latency are not reconstructed here.
Recorded operation counts are API/event counts, not hidden neural forward steps.
Nested admission costs and concurrent lanes must not be added to elapsed time.
Native-index references absent from the enumerated receipt set and later worker
observations are listed separately; their reference counts cannot be equated to
the physical completion denominator. An aggregate with no measured inputs is
null (empty in CSV), with its observed/unavailable row counts retained.
Owner closure combines native workers/coordinators, physical rows, enrollment,
prefix and any long/paced owners. It distinguishes ACTIVE, CLOSURE_UNVERIFIED and
CLOSED. Unknown-only inspection never becomes CLOSED. Orphan sessions or native
index references outside the receipt enumeration add explicit accounting flags,
so they cannot receive a completeness certification merely because workers closed.

## Outputs

Each new `--version` creates an immutable folder under
`simulation\reports\S6C\20260910T123540Z\execution_inventory`:

- `EXECUTION_INVENTORY.json`: compact branch totals, active/incomplete scope,
  worker/load counts, index-reference counts, failures and source bindings.
  Declared bytes are deduplicated within each representation role; overlapping
  roles must not be summed and are not a current whole-disk usage measurement.
- `EXECUTION_SUMMARY.csv`: small table grouped by branch/epoch/recipe/profile/taps
  and status, suitable for the compact handoff.
- `PHYSICAL_EXECUTIONS.csv` and `.json`: one row per physical attempt/session;
  detailed JSON includes exact source and payload bindings. Null/missing numeric
  values become empty CSV cells, not zero measurements.
- `DECLARED_ARTIFACT_BINDINGS.json`: deduplicated path/hash/size references to
  large evidence, model assets and source code, with the declaring receipt.
- `METADATA_SOURCES.json` plus `metadata_snapshots`: exact consumed metadata and
  immutable resolution of originally mutable paths. Keep these local/indexed;
  the final compact ZIP need not contain every receipt snapshot.
- `source_snapshots`: the exact collector/README that generated this inventory,
  retained before execution so later additive adapters cannot erase provenance.

The script refuses an existing version directory. Choose a new version for a
later snapshot; never overwrite a prior result. Do not run the collector during
a quiet paced/HIL measurement interval because its metadata reads add host I/O.

## PowerShell

```powershell
$jpRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$jpSim = Join-Path $jpRoot 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$jpTool = Join-Path $jpSim 'scripts\s6c_execution_inventory.py'
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpTool checks
# Use a new version name for each source-bound snapshot:
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpTool collect --version snapshot_v1
```

## Anaconda Prompt or CMD

No environment installation or activation is required. Use the existing native
Python executable explicitly; the collector uses its installed `psutil` only.

```bat
set "JP_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy"
set "JP_SIM=%JP_ROOT%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "JP_TOOL=%JP_SIM%\scripts\s6c_execution_inventory.py"
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_TOOL%" checks
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_TOOL%" collect --version snapshot_v1
```

`checks` uses temporary metadata and model-free negative fixtures for physical
identity, paired receipt deduplication, epoch/status admission, resident counters,
prediction classification, unknown process inspection and exact mutable-byte
preservation. No model inference or hardware call is involved.
