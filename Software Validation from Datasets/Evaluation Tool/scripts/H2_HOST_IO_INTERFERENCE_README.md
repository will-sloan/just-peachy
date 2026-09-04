# H2 Windows host-I/O interference receipt

## Purpose

`capture_h2_host_io_interference.ps1` preserves Windows host-I/O evidence that
overlaps the four Phase-1 medium H2 development runs. It verifies every declared
result checksum, summarizes per-case queue blocking, reads ESENT/VSS/storage
events for the exact job interval, and binds the evidence to the H2 protocol,
job manifest, and promotion decision.

The same collector also has a `SerialResource` evidence mode. In that mode it
requires manifest-declared serial resource jobs, classifies their exact
intervals as `SERIAL_RESOURCE_HOST_IO_CLEAR` or
`SERIAL_RESOURCE_HOST_IO_CONTAMINATED` (or
`SERIAL_RESOURCE_HOST_IO_UNVERIFIED` when an event-provider query genuinely
fails), and makes resource-comparison eligibility explicit.
`watch_h2_serial_resource_io.ps1` waits for the two
matched Phase-2 ReDim jobs and the three post-selection Phase-6 mode jobs, then
captures both receipts automatically. A transient collector or publication
failure is written to the watcher JSONL log and retried on the next interval;
it cannot silently terminate receipt collection.

The receipt is diagnostic and non-selection evidence. It does not change model
outputs, thresholds, promotion, the held-out firewall, or any frozen runtime
configuration. Accuracy metrics remain eligible when their result trees are
valid. Accuracy-run wall time, RTF, and queue blocking are declared unsuitable
for resource comparisons when host-I/O interference is present. Later serial
resource jobs must be checked independently and replayed if their intervals
overlap the same condition.

## Inputs

- `Workspace`: the active H2 controller workspace containing
  `program_state.json`, `job_manifest.json`, the Phase-1 promotion, and storage
  guardian log.
- `ResultsRoot`: the matching H2 result root containing the four complete medium
  candidate result trees.
- `CandidateJobIds`: optional explicit job IDs. The v16 Phase-1 medium IDs are
  the defaults in `Phase1AccuracyPromotion` mode. In `SerialResource` mode the
  collector discovers manifest-declared serial resource jobs unless explicit
  IDs are supplied.
- `EvidenceClass`: `Phase1AccuracyPromotion` (default) or `SerialResource`.
- `AllowNonidenticalReferences`: diagnostic escape hatch for unrelated serial
  jobs. Matched comparisons should retain the default fail-closed requirement.
- `OutputPath`: optional output path. It must remain inside the workspace.

The script is Windows-specific because it reads Windows Event Log and Windows
storage metadata. It performs no neural inference and does not require network
access.

Controller timestamps are normalized by instant before correlation. In
particular, PowerShell's `ConvertFrom-Json` may materialize an ISO-8601 value
with an explicit offset as a local `DateTime`; the collector converts that
local instant to UTC instead of relabelling its clock fields as UTC. This keeps
per-job Windows-event buckets correct on non-UTC hosts.

The Windows queries use a one-minute guard around the overall candidate window
so boundary events are not missed. Every timestamped event is then filtered
back to the exact union of candidate job execution intervals. An event found
only in guard padding or in a gap between serial jobs cannot contaminate a
resource measurement.

## Output

By default the script creates:

```text
<Workspace>\diagnostics\host_io_interference\windows_host_io_interference.json
```

The JSON contains:

- protocol, manifest, result-checksum, and promotion bindings;
- identical-reference verification across the four candidates;
- per-job and top per-case queue/backpressure evidence;
- ESENT hung-I/O events and parsed durations;
- temporally coincident Acronis VSS evidence without claiming sole causation;
- storage-guardian timing evidence from an independent process;
- C: disk/volume health reported by Windows;
- explicit eligibility decisions for accuracy, promotion, and resource use.

The automatic watcher creates:

```text
<Workspace>\diagnostics\host_io_interference\serial_resource_phase2_redim_host_io.json
<Workspace>\diagnostics\host_io_interference\serial_resource_phase6_modes_host_io.json
<Workspace>\logs\serial-resource-host-io-watcher.jsonl
```

The final augmented reproducibility package requires both serial receipts to be
present, checksum-bound to the current collector, and classified
`SERIAL_RESOURCE_HOST_IO_CLEAR`. Package construction fails closed when either
receipt is contaminated or unverified, so Phase-1 wall time or a compromised
serial run cannot silently enter the final resource comparison.

User paths in Windows event messages are replaced with stable placeholders.

## Run from PowerShell

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"

& ".\scripts\capture_h2_host_io_interference.ps1" `
  -Workspace ".\automated_runs\h2_complete_product_pipeline_v17" `
  -ResultsRoot ".\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17"
```

Run the automatic serial-resource watcher:

```powershell
& ".\scripts\watch_h2_serial_resource_io.ps1" `
  -Workspace ".\automated_runs\h2_complete_product_pipeline_v17" `
  -ResultsRoot ".\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17" `
  -IntervalSeconds 60
```

Run a one-time non-blocking status/capture pass:

```powershell
& ".\scripts\watch_h2_serial_resource_io.ps1" `
  -Workspace ".\automated_runs\h2_complete_product_pipeline_v17" `
  -ResultsRoot ".\JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17" `
  -Once
```

## Run from Anaconda Prompt

PowerShell owns the Windows Event Log query, so invoke it from Anaconda Prompt
as follows:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\capture_h2_host_io_interference.ps1" -Workspace "automated_runs\h2_complete_product_pipeline_v17" -ResultsRoot "JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17"
```

Automatic watcher from Anaconda Prompt:

```bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\watch_h2_serial_resource_io.ps1" -Workspace "automated_runs\h2_complete_product_pipeline_v17" -ResultsRoot "JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17" -IntervalSeconds 60
```

## Validation and interpretation

The command fails closed when a candidate is incomplete, a result hash fails,
the job manifest binding differs, references differ, held-out inspection is
claimed, or RTF entered promotion. Successful output prints the absolute receipt
path, SHA-256, status, ESENT event count, maximum reported OS I/O delay, and
maximum pipeline queue block.

For serial-resource receipts, any queried ESENT or storage warning/error in the
exact measurement interval makes wall-time, queue, RTF, CPU, and RAM evidence
ineligible. The receipt remains valid diagnostic evidence, and the affected
serial job must be replayed before final resource comparison. VSS coincidence
alone is recorded but is not treated as proof of causation. A Windows
`NoMatchingEventsFound` response is treated as a successful empty interval;
genuine provider-query or access failures remain explicit and prevent a final
"clear" package claim.

Do not interpret temporal coincidence with a backup/VSS event as proof of a
single root cause. The defensible conclusion is narrower: the host experienced
documented process-wide storage delays, so concurrent wall-time/resource
measurements are contaminated and need a clean serial measurement.
