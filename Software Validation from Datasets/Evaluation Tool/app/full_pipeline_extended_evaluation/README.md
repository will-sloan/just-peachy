# Bounded Prompt 6 extended full-pipeline evaluation

## Purpose and scientific boundary

This additive package runs the eight-day amendment's reduced Prompt 6. It
loads the Prompt-4-frozen extended set through the universal Prompt-5
completion record, then exercises true streaming, online speaker behavior,
native/acoustic panels, long sessions, reliability faults, and serial resource
measurement. It does not modify or duplicate model inference in
`app/full_pipeline`, `app/full_pipeline_evaluation`, or
`app/full_pipeline_development`.

The terminal marker is:

```text
COMPLETE_EXTENDED_PIPELINE_EVALUATION_REDUCED_8DAY_V1
```

This marker is deliberately different from the original full Prompt-6 marker.
Every report declares `scope_class: BOUNDED_REDUCED` and
`original_full_scope_complete: false`. The package does not inspect Prompt-5
scientific outcome tables to choose pipelines or cases. It rehashes Prompt-5
artifacts, parses its authorization/frozen-input bindings and the one directly
manifested `all18_deployment_evidence.json` reporting artifact, and uses the
extended set that was frozen on development evidence in Prompt 4. Deployment
evidence is never a membership filter or retuning input.

## Fixed bounded inputs

Required inputs are:

- the orchestrator-supplied Prompt-5 `completion_marker.json` and exact SHA-256;
- the 18 immutable Prompt-4 pipeline configurations and checksum document;
- Prompt-4 `extended_set.yaml` (six mandatory anchors plus at most two
  predeclared challengers);
- the backend-specific frozen decision-policy registry;
- `full_speech_pipeline_v1` evaluation metadata/references and enrollment
  registry;
- the locked matrix/runtime configuration and local C:-resident model assets;
- the eight-day scope amendment and canonical `PROGRAM_STATE.json`.
- the C:-local authority
  `runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json`, fixed at
  SHA-256 `f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4`;
- exactly one checksum-bound Prompt-5 `all18_deployment_evidence.json` in the
  predecessor artifact manifest.

Prompt 6 fails closed if the predecessor, frozen set, policies, hashes, scope,
or program-state gate differs. Before every job claims work, it re-proves that
all 18 frozen YAMLs exactly match the live matrix, runtime configuration,
backend-specific policy, model-asset identities, alignment/UI contracts, and
result-affecting code hash. A checksum-valid but semantically drifted freeze is
rejected. All input, cache, temporary, log, result, report, package, and
checkpoint paths must resolve to drive C:. The controller preserves at least
35 GiB free and requests a restart-safe stop before that reserve is crossed.
The amendment's 30-hour value is a nominal planning/ETA target, not an elapsed-
time kill switch: the controller continues past it until completion unless the
operator stops it or the C: reserve guard fires.

There is intentionally no second CLI path for the Prompt-5 deployment report.
The wrapper/CLI binds the predecessor completion path and SHA-256; admission
then discovers exactly one required `all18_deployment_evidence.json` from that
completion's rehashed artifact manifest. This prevents a caller from swapping
in a convenient unmanifested copy.

## Raspberry Pi and Linux ARM64 evidence boundary

Raspberry Pi steering is additive decision context only. It does not change
the scientific method, cases, metrics, frozen policies, concurrency, or the
six-to-eight Prompt-4-predeclared pipelines. The generated
`extended_deployment_evidence.json` carries forward all 25 structured Prompt-5
deployment attributes and enriches only fields supported by Prompt-6's serial
Windows/x86-64 desktop resource run. Every value remains explicitly
`MEASURED`, `DERIVED`, `UNKNOWN`, or `UNSUPPORTED`.

The report includes the four declared 2-GiB feasibility classes and separately
the four Linux ARM64 portability classes: `LINUX_ARM64_READY`,
`LIKELY_PORTABLE`, `PORT_REQUIRES_WORK`, and `PLATFORM_BLOCKER`. Desktop RSS,
RTF, model bytes, and startup evidence are not ARM measurements or a final
Raspberry Pi ranking. Windows-specific assumptions, Debian/Pi OS ARM64
dependency support, required export/replacement work, and the seven future
Linux validation items remain explicit. A Raspberry Pi winner requires later
real ARM64 export, parity, memory, latency, thermal, and sustained-stream tests.

## Exact reduced panel

Selection is deterministic from metadata/references with seed 3800:

- 24 native stateful cases per two Sherpa ASR representatives;
- 24 online-speaker cases per unique frozen hybrid pair;
- 8 integrated cases per extended pipeline;
- 4 eligible AMI, 4 CHiME-6, and 24 VOiCES cases;
- 12 controlled noise/RIR and 12 speaker/gallery/overlap stress cases per
  pipeline;
- two true-incremental 30-minute streams per pipeline, selected from two
  provenance-distinct frozen audio sources and materialized/hash-bound
  separately at true 1.0x pacing;
- all 13 declared reliability contracts with 30–60-second bounded windows,
  using controlled prerecorded injection where a real hook exists and explicit
  `UNSUPPORTED` evidence where it does not;
- one serial resource job per pipeline: cold start, 60-second warmup, and
  300-second measured interval.

Accuracy concurrency is at most two. Resource jobs are always serial. Every
reliability row is evidence-backed as `PASS`, `FAIL`, or `UNSUPPORTED`; a normal
runtime completion without the named injection/assertion can never become a
pass. Hardware faults without a deterministic controlled hook (for example a
physical device disconnect) remain explicit `UNSUPPORTED`. CHiME WER, native
known-speaker identity without leakage-safe enrollment, VOiCES diarization/
identity, energy, and Beaker power remain explicitly unsupported. Any
accidentally computed value in those disallowed native scopes is suppressed
before export, and completion rechecks that no such value remains. AMI ASR,
cpWER, and diarization metrics are retained only where every selected case has
the corresponding complete frozen reference declaration.
The serial resource result separates startup and warmup from its 300-second
comparison interval and records total/component RTF, CPU, RAM, model/cache
bytes, cache growth, queue depth/drops, deadline-counter support, and
temperature/runtime drift only when the installed telemetry can measure it.
Component RTF is computed only from measured component `processing_sec` /
`audio_duration_sec` pairs in the post-warmup window; otherwise its support
status is explicit and its numeric value is empty.

For the stateful online panels, checksum-bound common-runtime event logs add
explicit engineering rows for segmentation lookahead and compute latency,
boundary commitment, cluster creation/revision, first generic/tentative/
confirmed label times, evidence duration, identity flips, warm reacquisition,
short-turn inheritance, Unknown_N allocation, and capture-to-event latency.
These rows remain separate from reference-dependent scientific metrics.

## Environment setup

The wrapper uses the repository-managed Python at
`C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe`.
It does not create a second environment or download models.

From **Anaconda Prompt**:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
call ".venv\Scripts\activate.bat"
cd /d "Software Validation from Datasets\Evaluation Tool"
python -m app.full_pipeline_extended_evaluation --help
```

From **PowerShell** or Windows Terminal:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
& '..\..\.venv\Scripts\python.exe' -m app.full_pipeline_extended_evaluation --help
```

No command in this README installs or downloads model assets. Complete Prompt-5
first; do not substitute a locally rediscovered predecessor after orchestration
has bound a path/hash.

## Automatic eight-day launch

The program controller supplies these environment variables:

```text
JP8_PREDECESSOR_COMPLETION_PATH
JP8_PREDECESSOR_COMPLETION_SHA256
JP8_ADAPTER_ID
JP8_ADAPTER_CONTRACT_SHA256
JP8_COMPLETION_RECORD
JP8_PI_DEPLOYMENT_STEERING_PATH
JP8_PI_DEPLOYMENT_STEERING_SHA256
```

Its Prompt-6 start, stop, and validator commands are:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_extended_evaluation.ps1' -Action RunAll

& 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_extended_evaluation.ps1' -Action Stop

& 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_extended_evaluation.ps1' -Action ValidateCompletion
```

`RunAll` is idempotent: it prepares immutable selection/input bindings, resumes
unfinished accuracy work, runs serial resources, analyzes, collects, finalizes,
and independently validates an existing completed stage. Explicit failed jobs
remain in the evidence and do not silently disappear.

## Complete manual PowerShell command

Use the exact adapter ID/hash supplied by the eight-day controller. This example
computes only the predecessor file hash for an explicit manual invocation; it
does not search for or replace the predecessor file.

```powershell
$Tool = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Workspace = Join-Path $Tool 'automated_runs\full_pipeline_extended_evaluation_reduced_8day_v1'
$P5 = Join-Path $Tool 'automated_runs\full_pipeline_core_evaluation_reduced_8day_v1\completion_marker.json'
$P5Sha = (Get-FileHash -LiteralPath $P5 -Algorithm SHA256).Hash.ToLowerInvariant()
$PiSteering = Join-Path $Tool 'runs\full_pipeline_program\RASPBERRY_PI_DEPLOYMENT_STEERING.json'
$PiSteeringSha = 'f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4'

$env:JP8_PREDECESSOR_COMPLETION_PATH = $P5
$env:JP8_PREDECESSOR_COMPLETION_SHA256 = $P5Sha
$env:JP8_ADAPTER_ID = '<exact Prompt-6 adapter ID from EIGHT_DAY_ADAPTERS.json>'
$env:JP8_ADAPTER_CONTRACT_SHA256 = '<exact 64-character adapter contract SHA-256>'
$env:JP8_COMPLETION_RECORD = Join-Path $Workspace 'completion_marker.json'
$env:JP8_PI_DEPLOYMENT_STEERING_PATH = $PiSteering
$env:JP8_PI_DEPLOYMENT_STEERING_SHA256 = $PiSteeringSha

& (Join-Path $Tool 'scripts\run_full_pipeline_extended_evaluation.ps1') `
  -Action RunAll `
  -WorkspaceRoot $Workspace `
  -PredecessorRecord $P5 `
  -PredecessorSha256 $P5Sha `
  -PiDeploymentSteeringPath $PiSteering `
  -PiDeploymentSteeringSha256 $PiSteeringSha `
  -ParallelJobs 2 `
  -AdapterId $env:JP8_ADAPTER_ID `
  -AdapterContractSha256 $env:JP8_ADAPTER_CONTRACT_SHA256 `
  -CompletionRecord $env:JP8_COMPLETION_RECORD
```

Direct Python equivalent, after setting the same variables:

```powershell
Set-Location $Tool
& '..\..\.venv\Scripts\python.exe' -m app.full_pipeline_extended_evaluation run-all `
  --workspace-root $Workspace `
  --predecessor-record $P5 `
  --predecessor-sha256 $P5Sha `
  --pi-deployment-steering-path $PiSteering `
  --pi-deployment-steering-sha256 $PiSteeringSha `
  --parallel-jobs 2
```

## Monitor with a percentage bar

Open a second PowerShell window. This refreshes every 10 seconds and does not
touch scientific results:

```powershell
$Tool = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Runner = Join-Path $Tool 'scripts\run_full_pipeline_extended_evaluation.ps1'
while ($true) {
    $Status = (& $Runner -Action Status | ConvertFrom-Json)
    $Progress = $Status.progress
    $Eta = if ($null -eq $Progress.eta_seconds) { 'calculating' } else { [TimeSpan]::FromSeconds($Progress.eta_seconds).ToString() }
    Write-Progress -Activity 'Prompt 6 bounded extended evaluation' `
      -Status "$($Progress.phase): $($Progress.detail) ETA $Eta" `
      -PercentComplete ([double]$Progress.overall_percentage)
    if ($Progress.phase -eq 'complete') { break }
    Start-Sleep -Seconds 10
}
```

Machine-readable live files are:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_extended_evaluation_reduced_8day_v1\program_progress.json
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_extended_evaluation_reduced_8day_v1\controller_state.json
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_extended_evaluation_reduced_8day_v1\logs\controller.log
```

## Stop and resume

Stop is cooperative and restart-safe:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_extended_evaluation.ps1' -Action Stop
```

After running workers have shut down, repeat the full `RunAll` command with the
same predecessor, adapter, workspace, and environment. Completed checksum-bound
results and explicit failures are retained. Do not delete the SQLite queue or
workspace to resume.

## Outputs

Workspace:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_extended_evaluation_reduced_8day_v1
```

Canonical compact report:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\full_pipeline\extended\full_speech_pipeline_v1_reduced_8day_v1
```

Requested report files:

```text
extended_summary.csv
true_streaming_asr.csv
online_diarization.csv
online_identity.csv
ux_latency.csv
label_revision.csv
native_results.csv
long_session_results.csv
reliability_results.csv
serial_resources.csv
extended_deployment_evidence.json
failure_analysis.md
extended_report.md
```

Additional integrity/handoff files include `failure_inventory.csv`,
`licensing_provenance.json`, `analysis.json`, `checksums.json`, the compact ZIP,
three universal gate records, `artifact_manifest.json`, and
`completion_marker.json`.

`hardening_input_manifest.json` is outcome-independent and binds absolute C:
WAV paths/hashes for deterministic replay (at least 5 minutes), controlled
loopback (at least 10 minutes), repeated sessions, a true 60-minute soak input,
two provenance-distinct 30-minute Prompt-6 long-stream inputs, and at least
three distinct enrollment samples. The large WAVs remain in the stage workspace
and are intentionally excluded from the compact report ZIP.

## Inputs and outputs of each action

| Action | Input | Output |
|---|---|---|
| `ValidatePrerequisite` | Prompt-5 completion path/hash, state, amendment, Pi steering path/hash | fail-closed authorization including the exact manifested Prompt-5 deployment report; no inference |
| `Prepare` | frozen metadata, extended set, enrollment references, deployment bindings | immutable plan, selection/exclusion inventory, hardening WAV/manifest, SQLite queue |
| `RunAccuracy` | prepared accuracy queue | restart-safe scored/online/native/reliability/long-stream results, max two workers |
| `RunResources` | prepared resource queue | serial cold/warm/measured resource result per pipeline |
| `ValidateTerminal` | queue and result checksums | explicit complete/failed inventory |
| `Analyze` | terminal results and bound Prompt-5 deployment evidence | requested reports plus serially enriched deployment evidence |
| `Collect` | compact reports and protocol bindings | canonical report tree and deterministic ZIP |
| `Finalize` | collected evidence plus adapter/predecessor contract | gates, artifact manifest, universal completion, updated program state |
| `Status` | workspace only | progress/ETA/storage JSON |
| `Stop` | workspace only | cooperative stop request |

## Reliability and safety behavior

- Model workers never run in the UI/controller process by custom inference
  logic; the controller delegates to the common runtime and Prompt-3 worker.
- Stop requests are forwarded to active stateful runtimes and queued work is
  marked restartable.
- A complete job requires a checksum document; a failed job requires an
  explicit error.
- Native applicability declarations are exported beside computed metrics.
- Raw datasets, model weights, biometric embeddings, and raw event trees are
  excluded from the compact ZIP.
- A bounded result is never relabeled as completion of the original full
  Prompt-6 campaign.
