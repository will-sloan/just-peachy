# Bounded Prompt-7 Production-Candidate Selection and Hardening

## Purpose and scientific scope

This additive package implements Prompt 7 for the C:-only eight-day amendment. It
consumes the checksum-bound bounded Prompt-5 core results and bounded Prompt-6
extended results, applies the selection priorities frozen before evaluation, and
hardens up to three complete speech pipelines. It does not modify the frozen full
pipeline matrix, runtime, scientific thresholds, model code, Prompt-5/6 evidence,
or common demo inference logic.

The bounded completion marker is
`COMPLETE_PRODUCTION_CANDIDATE_HARDENING_REDUCED_8DAY_V1`. It is explicitly not
the original full-scope Prompt-7 claim. Technical, user-safety, resource, and
licensing evidence remain separate; no weighted composite score is used.

Prompt 7 also creates a separate two-to-four pipeline Raspberry Pi research
shortlist. This is not a new desktop role ranking and does not select a Pi
winner. It is restricted to the Prompt-4 frozen extended set, always retains the
unchanged desktop PRIMARY, retains a safety-nondominated efficiency candidate
when supported, and then preserves H2/H5, WeSpeaker, and AO/AG ASR diversity
categorically within the four-candidate cap. A Pi-only research candidate need
not be desktop software-ready and receives no acceptance tasks or bundle. The
2-GiB class is recorded, never used as a hard filter.

The controller examines the six frozen anchors (AO/AG with H2, H4, and H5) plus
zero to two challengers frozen in Prompt 4. H2 same-model simplicity is reported
only from measured worker count, startup, RTF, RAM, and model bytes. Missing
measurements are labelled partial or unsupported and never treated as a benefit.
All candidates remain visible in the technical/licensing reports. A challenger
is nevertheless excluded from a software-ready role unless its exact frozen
registry, YAML, requested-gallery, and realized-gallery binding can be supplied
to the common runtime. The current common demo cannot supply that complete
challenger binding, so only the six exact frozen anchors are role-eligible and an
unresolved Unknown-only fallback is never run as production acceptance.

## Inputs

- Prompt-5 universal completion record and all checksum-bound required reports.
- Prompt-5 `all18_deployment_evidence.json`, discovered only through its
  checksum-bound universal artifact manifest.
- Prompt-6 universal completion record and all checksum-bound required reports.
- Prompt-6 `extended_deployment_evidence.json`, likewise manifest-discovered and
  bound back to Prompt 5.
- Prompt-6 `hardening_input_manifest.json`. Its paths and WAV hashes are frozen
  independently of Prompt-6 outcomes and cover 5-minute replay, 10-minute
  deterministic virtual-live input, 2-minute repeated sessions, a
  60-minute soak, and at least three enrollment samples.
- Prompt-5 frozen 18-pipeline configs and predeclared extended set.
- `PROGRAM_STATE.json`, `EIGHT_DAY_SCOPE_AMENDMENT.json`, and the
  `EIGHT_DAY_EXECUTION_POLICY_ADDENDUM.json` advisory-timing audit record, plus
  the authoritative matrix/runtime, selection priorities, and
  license/provenance inventory.
- `RASPBERRY_PI_DEPLOYMENT_STEERING.json`, schema
  `full-pipeline-deployment-steering.v1`, frozen at SHA-256
  `f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4`.
- Existing model assets and isolated environments referenced by the frozen
  configs. Downloads are not permitted during hardening.

The prerequisite gate independently decodes every input WAV and requires mono,
16-kHz, 16-bit uncompressed PCM with the declared duration matching the frame
count. It also rehashes every selected model tree/file and environment
interpreter, validates the exact 18-YAML checksum map and internal freeze hashes,
and binds anchor policy/model/runtime identities before any acceptance task.

All material paths must be on drive C:. The controller checks a 35 GiB free-space
reserve before and periodically during execution.

## Outputs

The canonical workspace is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_production_candidate_hardening_reduced_8day_v1
```

Important outputs are:

- `program_progress.json` — percentage, ETA, phase, detail, and task counts;
- `controller.log` — restart/audit events;
- `selection/selection.json` and `report/h2_simplicity_measurement.csv`;
- `acceptance_plan.json` and checksum-bound evidence for every task;
- `report/production_candidate_catalog.yaml`;
- `report/production_candidate_summary.csv`;
- `report/technical_ranking.csv`, `licensing_ranking.csv`, and
  `pareto_frontier.csv`;
- `report/licensing_provenance.json` and `failure_inventory.csv`;
- `report/PRIMARY_PIPELINE.md`, `FALLBACK_PIPELINE.md`, and
  `ALTERNATIVE_PIPELINE.md` (an optional unfilled role is documented);
- `report/DEMO_RUNBOOK.md`, `TROUBLESHOOTING.md`, and
  `VALIDATION_CHECKLIST.md`;
- `report/common_demo_production_catalog.yaml`, a checksum-bound overlay that the
  common demo consumes and uses to select the PRIMARY role by default;
- `report/raspberry_pi_candidate_shortlist.json`, the sole Prompt-7 Pi
  membership authority consumed by Prompt 8. It binds the frozen Prompt-4
  `extended_set.yaml`, unchanged desktop catalog, Prompt-5/6 deployment
  evidence, exact model identities, explicit UNKNOWN/UNSUPPORTED cells, four
  2-GiB and four Linux ARM64 classes, and all 14 hardware plus 7 Linux tests;
- `report/report_checksums.json`, including the exact Pi shortlist hash;
- `candidate_bundles/<role>/` with immutable config, asset/environment manifest,
  launch/validate/health scripts, demo preset, baseline, limitations, and hashes;
- `packages/full_pipeline_production_candidates_reduced_8day_v1.zip`;
- `artifact_manifest.json`, exactly three universal gate records, and
  `completion_marker.json`.

The compact ZIP excludes audio, model binaries, credentials, raw datasets,
biometric vectors, and large caches.

## Acceptance workload

Every selected candidate must pass 17 tasks:

1. two identical deterministic five-minute replays;
2. one ten-minute 1.0x deterministic WAV-backed virtual live-session run through
   `DemoSessionManager.start_microphone`;
3. enrollment/import, profile binding, and export;
4. five repeated two-minute sessions;
5. one 60-minute 1.0x soak;
6. six recovery faults (no profiles, invalid profile, operator stop, worker
   failure/restart, slow consumer/queue pressure, and unsupported input);
7. one startup asset/worker self-test.

The virtual-live harness injects a frozen WAV through the common live-session API.
It is explicitly distinct from file simulation, but it does not claim an OS
loopback device or physical-microphone performance. Actual hardening is serial and
restart-safe. Passed task attempts are checksum/task/plan-bound and reused after a
restart, including recovery from a crash between result publication and the
`latest.json` pointer. Failed attempts remain preserved for diagnosis. The
12-hour value is an advisory planning/ETA target only: there is no elapsed-time
kill switch. Execution continues to a terminal result unless the operator stops
it, a worker health timeout fires, or the C: reserve is violated.

## Run from Anaconda Prompt

Open **Anaconda Prompt**, then run:

```powershell
conda activate base
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
".venv\Scripts\python.exe" -m pip check
powershell -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1" -Action Status
```

The repository `.venv` is the coordinator environment. Model workers continue
to use the isolated environment profiles recorded by the matrix; do not install
all model stacks into the coordinator environment.

## Run automatically after Prompt 6

Normally the eight-day orchestrator supplies all `JP8_*` variables. For a direct
authorized run, substitute the real Prompt-6 record and adapter identity:

```powershell
$env:JP8_PREDECESSOR_COMPLETION_PATH = "C:\absolute\prompt6\completion_marker.json"
$env:JP8_ADAPTER_ID = "<adapter-id-from-eight-day-controller>"
$env:JP8_ADAPTER_CONTRACT_SHA256 = "<64-lowercase-hex-contract-hash>"
$env:JP8_COMPLETION_RECORD = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_production_candidate_hardening_reduced_8day_v1\completion_marker.json"
& ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1" -Action RunAll
```

`RunAll` is `RERUN_IDEMPOTENT`. It validates both upstream stages before opening
selection evidence, runs the serial acceptance campaign, packages successful
candidates, publishes the universal envelope, and independently validates it.
The nominal planning target is 12 hours, not a deadline. Actual time depends on
one to three selected candidates and hardware. The mandatory real-time inputs
contribute about 70 minutes per candidate before startup/compute overhead, and the
displayed ETA may exceed 12 hours without stopping the campaign.

## Run actions one at a time

```powershell
$runner = ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1"
& $runner -Action ValidatePrerequisites -Prompt6Marker $env:JP8_PREDECESSOR_COMPLETION_PATH
& $runner -Action Select -Prompt6Marker $env:JP8_PREDECESSOR_COMPLETION_PATH
& $runner -Action PrepareHardening -Prompt6Marker $env:JP8_PREDECESSOR_COMPLETION_PATH
& $runner -Action RunHardening -Prompt6Marker $env:JP8_PREDECESSOR_COMPLETION_PATH
& $runner -Action ValidateHardening -Prompt6Marker $env:JP8_PREDECESSOR_COMPLETION_PATH
& $runner -Action Package -Prompt6Marker $env:JP8_PREDECESSOR_COMPLETION_PATH
& $runner -Action UpdateProgramState -PredecessorRecord $env:JP8_PREDECESSOR_COMPLETION_PATH -AdapterId $env:JP8_ADAPTER_ID -AdapterContractSha256 $env:JP8_ADAPTER_CONTRACT_SHA256
& $runner -Action ValidateCompletion
```

To name the deployment authority explicitly, add the following parameter to any
action. The file bytes must still match the frozen SHA-256:

```powershell
-PiDeploymentSteeringPath "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\runs\full_pipeline_program\RASPBERRY_PI_DEPLOYMENT_STEERING.json"
```

## Monitor, stop, and resume

One-time status:

```powershell
& ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1" -Action Status
```

Refreshing percentage screen:

```powershell
$progress = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_production_candidate_hardening_reduced_8day_v1\program_progress.json"
while ($true) {
    Clear-Host
    if (Test-Path -LiteralPath $progress) {
        $p = Get-Content -LiteralPath $progress -Raw | ConvertFrom-Json
        $width = 40
        $filled = [Math]::Floor($width * [double]$p.overall_percentage / 100)
        $bar = ('#' * $filled).PadRight($width, '-')
        "[{0}] {1,6:N2}%  phase={2}  eta={3}s" -f $bar,$p.overall_percentage,$p.phase,$p.eta_seconds
        $p.detail
    } else { "Waiting for Prompt-7 progress record..." }
    Start-Sleep -Seconds 10
}
```

Request a graceful stop, then rerun `RunAll` to resume:

```powershell
& ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1" -Action Stop
& ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1" -Action RunAll
```

## Candidate launch, validation, and health

After completion, each role bundle contains `launch.ps1`, `validate.ps1`, and
`health.ps1`. Direct controller examples are:

```powershell
& ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1" -Action ValidateCandidate -CandidateRole primary
& ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1" -Action Health -CandidateRole primary
& ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_production_hardening.ps1" -Action ServeHealth -Bind 127.0.0.1 -Port 8767
Invoke-RestMethod http://127.0.0.1:8767/health
```

The local health endpoint is state-derived. It reports `DEGRADED` while absent,
not started, incomplete, stopped, or stale; `UNHEALTHY` for failed/tampered
evidence; and `HEALTHY` only after universal completion, all acceptance evidence,
candidate bundles, compact ZIP, frozen identities, external assets, and
environments revalidate. Non-healthy HTTP responses use status 503. These checks
perform no model inference and make no physical-microphone health claim.

## Direct Python command line

From the Evaluation Tool directory:

```powershell
& "..\..\.venv\Scripts\python.exe" -m app.full_pipeline_production_hardening --help
& "..\..\.venv\Scripts\python.exe" -m app.full_pipeline_production_hardening material-paths
```

`MaterialPaths` reports the exact nine adapter classes: inputs, workspaces,
caches, temporary, logs, results, reports, packages, and checkpoints. The only
stage workspace is the canonical Prompt-7 root; the shared cache is
`JustPeachyResults\full_pipeline\_shared_cache`; checkpoint entries are the
exact frozen configs and selected `models\cache` assets. The mutable Evaluation
Tool root is never reported as a stage workspace.

## Static verification without inference

From the repository root in Anaconda Prompt or PowerShell:

```powershell
conda activate base
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
$env:PYTHONPATH = "Software Validation from Datasets\Evaluation Tool"
& ".venv\Scripts\python.exe" -m pytest -q "Software Validation from Datasets\Evaluation Tool\tests\full_pipeline_production_hardening"
```

These tests validate exact nested model identity, source/hash binding,
manifest/package requirements, frozen-order membership, Pi-only candidate
handling, and tamper/firewall failures. They do not load models or run audio
inference.

## Safety and failure semantics

- `Stop` is a cooperative request. The active child receives an interrupt and
  incomplete evidence is not accepted.
- Any selected candidate failure blocks completion and remains visible in
  `failure_inventory.csv`; failures are never silently dropped.
- No threshold, margin, enrollment, identity, alignment, buffering, or label
  policy is retuned.
- Desktop roles, their exact 17 acceptance tasks per selected candidate, and
  their bundles are unchanged by the Pi shortlist. Desktop x86 measurements are
  never relabelled as Linux ARM64 measurements, and no final ARM preference is
  claimed before real target-hardware validation.
- The common demo verifies the additive overlay hash, exposes the selected roles,
  and defaults UI/CLI commands to PRIMARY without duplicating model logic.
- Normal sessions require complete exports, exact runtime/frozen identities,
  offline/no-download flags, clean shutdown, and zero orphan child processes.
- XVF and fine-tuning hooks remain disabled.
- This package remains `NOT_READY`/infrastructure-only until the validated
  Prompt-5/6 predecessor chain authorizes `RunAll`; this implementation task ran
  static/unit tests only and did not launch inference or inspect unavailable
  Prompt-5/6 outcomes.
