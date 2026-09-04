# Full-Pipeline Development Policy and Freeze

## Purpose

This package supports Prompt 4's development-only two-stage identity-policy
flow and immutable all-18 freeze. It does not run models, inspect held-out
evaluation data, or choose a production winner.

The flow is:

1. Run the deterministic calibration subset in raw-score/Unknown-only mode.
2. Preserve one score row per cumulative identity checkpoint, enriched with the
   exact pipeline, development role, truth state, realized gallery, overlap,
   evidence duration, consistency, and no-evaluation attestation.
3. `policies.py` retains the final valid non-overlap row per case/cluster,
calibrates each exact AO/AG pipeline separately by the frozen requested-gallery
bucket, and writes a registry.
4. The runtime loads the exact pipeline + requested-gallery policy, and the
   development campaign is replayed/rerun from shared caches.
5. `freeze.py` writes exactly 18 immutable configurations and predeclares the
   six mandatory Tier-B pipelines plus at most two development Pareto
   challengers.

H2, H4, and H5 are never recalibrated. They retain the frozen Product V2
BALANCED gallery-size-10 scalar threshold at every gallery size, target FPIR
`0.01`, margin `0.03`, evidence gate `2.0 s`, two confirmations, hysteresis
`0.02`, and expiry `120 s`. Their decision-policy SHA is the frozen selection
SHA `2e93bab8...`; it is not the enrollment-policy SHA.

## Inputs

- `full-pipeline-challenger-score-observation.v1` JSON-like rows from
  development only;
- the prepared `full_speech_pipeline_v1` development identity;
- the complete development result-set checksum for the final freeze;
- optional checksum-bound alignment/buffering policy (the baseline is supplied);
- a passing checksum-bound anchor runtime qualification attesting correct
  diarization/identity provenance, overlap exclusion, frozen consistency and
  hysteresis semantics, decision-policy hashing, and six integrated smokes;
- one complete development metric row for every pipeline when building the
  extended set.

Calibration rows must include `pipeline_id`, `hybrid_label`,
`identity_backend_id`, `case_id`, `anonymous_speaker_id`, `observation_id`,
`truth_state`, `calibration_role`, requested and realized gallery size,
Top-1/Top-2 raw cosine
scores and candidate identities, complete candidate count, gallery identity,
enrollment-policy identity, development-protocol identity, ALL_UNKNOWN overlay,
evidence duration, consistency, overlap state, source time, split, status, and
`evaluation_material_inspected: false`.

The full 807-case panel is not required to estimate thresholds. The calibration
stage needs only the deterministic 20% development calibration role among
identity-bearing controlled cases, with ALL_UNKNOWN coverage at every frozen
requested-gallery bucket (`1`, `2`, `5`, `10`, `20`, `50`, and `full`) that
will be used, plus the controlled-v1 `source_full` bucket. The `full` bucket
intentionally carries the development
calibration into a larger held-out full gallery without inspecting it, matching
Product V2; every observed realized size remains recorded. The complete
development panel is still
required after policy freeze for final metrics, qualification, and Tier-B
selection. Each calibration result records sample count, empirical FPIR step,
and whether the target FPIR is empirically resolvable.

Use the immutable upstream `source_case_id` when calling `development_role()`;
do not hash a newly generated full-pipeline wrapper ID. This reproduces the
Product V2 calibration/selection assignment instead of silently repartitioning
the speakers and cases.

## Outputs

- `full-pipeline-development-policy-registry.v1` JSON;
- `frozen_pipeline_configs/<pipeline_id>.yaml` for all 18 rows;
- `frozen_pipeline_configs/checksums.json`;
- an `extended_set.yaml`-ready mapping with the mandatory six and zero to two
  unweighted Pareto challengers.

No embedding vectors, model weights, audio, or evaluation observations are
written by this package.

## Shared accuracy execution

`shared_execution.py` provides the Prompt-4 evaluation worker with one
job-owned persistent-worker pool and an accuracy-only native ASR stream trace.
The trace identity includes the source-audio hash, normalization/frame policy,
exact decoder frame count/sample rate, duration-limited source-sample horizon,
exact ASR config/model asset, and runtime config. It records the
ordered `accept_audio`, `finalize`, and `reset` calls together with every native
partial/final row and its original source horizon and decode latency. A replay
therefore follows the same incremental coordinator path; it is not a batch
transcript substitution. Terminal publication is fail-closed: `input_finished`
only produces a reusable trace after accepted source frames contiguously cover
the identity's complete (or explicitly duration-limited) horizon. A stopped
prefix releases its per-key lock but is never published as reusable evidence.

Accuracy results expose `primary_computed` or `accuracy_replayed` in component
status. Resource measurement hard-refuses trace replay. Segmentation and
embedding adapters may start lazily during Prompt 4, so a checksum-validated
cache hit does not load or warm a model. The default demo, live, file, and
enrollment runtimes retain their original eager worker ownership.

Inputs are an immutable local audio file, the locked pipeline selection, and
the existing local content cache. Outputs are local checksum-bound JSON trace
entries below `_shared_cache/asr_stream_traces`; no data is uploaded.

## Run from Anaconda Prompt or PowerShell

From the repository root:

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
..\..\.venv\Scripts\python.exe -m pytest tests\full_pipeline_development -q
..\..\.venv\Scripts\python.exe -m ruff check app\full_pipeline_development tests\full_pipeline_development
```

Programmatic calibration:

```python
from app.full_pipeline_development.policies import (
    build_development_policy_registry,
    write_development_policy_registry,
)

registry = build_development_policy_registry(
    observations,
    protocol_id=protocol_id,
    development_identity_sha256=development_identity_sha256,
)
write_development_policy_registry(output_path, registry)
```

Use the supported Prompt-4 controller/wrapper for the actual campaign. Do not
manually apply a challenger threshold, do not share an AO policy with AG, and do
not run held-out evaluation during Prompt 4.

## Prompt-4 staged controller

`orchestration.py` is the only Prompt-4 campaign entry point. It hard-rejects
held-out cases and creates separate immutable roots below
`automated_runs/full_pipeline_development_v1`:

```text
calibration/             56 ALL_UNKNOWN development cases, 12 challengers
frozen/                  immutable challenger decision-policy registry
qualification_cold/      one short mixed case, all 18, isolated cold execution
qualification_shared/    the same case/all 18 through shared accuracy execution
development_accuracy/    the complete 807-case development panel, all 18
resource_spots/          one controlled + one product spot, all 18, serial
```

The qualification case is
`fspcase_5b4c2ffbe73bc0c7da24`. It contains both Known and Unknown speakers,
uses requested gallery size 10, and is above every backend technical minimum.
Cold and shared results remain separate so the qualification builder can compare
semantic transcript/event identities without treating a cached replay as a cold
execution. The comparison preserves scientific event order, scores, decisions,
source-audio positions, and all stable enrollment metadata. Run-local capture
clocks and causal IDs are normalized; each run's aggregate profile hash is first
validated against its selected profile artifacts and then rebound to a common
semantic profile-set identity. Resource runs use an attempt-local component
cache and concurrency 1.

PowerShell sequence from the repository root (each run action is restart-safe):

```powershell
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action Plan
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action PrepareCalibration
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action RunCalibration
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action FreezePolicies
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action PrepareQualification
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action RunQualification
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action PrepareDevelopment
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action RunDevelopment
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action PrepareResources
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action RunResources
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action CombineEvidence
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action FreezeDevelopment
```

`RunQualification` automatically performs the six unique component restart
checks and seals `qualification/qualification.json`. If a machine interruption
occurs between those steps, rerun the action or invoke `QualifyRestarts` and
`FinalizeQualification` separately. `CombineEvidence` calls the standard
analysis controller for both complete campaigns, verifies every result checksum,
and creates one development-only manifest/analysis without rerunning a model.
`FreezeDevelopment` consumes that result-set identity and the passing anchor
qualification to write exactly 18 immutable configurations.

The qualification contract records the actual segmentation runtime/model asset
(`pyannote_segmentation_3_0`) separately from its cross-job cache contract
(`pyannote_segmentation_3_0_shared_cache`). Restart evidence is keyed by the
runtime component ID; the cache namespace is never treated as a model worker.

Monitor or request a graceful stop from another PowerShell window:

```powershell
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action Status
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" -Action Stop
```

From Anaconda Prompt or `cmd.exe`, use the same commands prefixed by
`powershell.exe`; no Conda environment activation is required because the
wrapper invokes the repository `.venv` explicitly. Inputs are the already
prepared `full_speech_pipeline_v1` protocol, locked matrix/model assets, and
local enrollment material. Outputs are campaign manifests, restart databases,
checksum-bound result trees, raw challenger diagnostics, the frozen registry,
and resource telemetry. This controller has no held-out evaluation command.

## All-18 qualification and development report

`qualification.py` creates a deterministic plan for exactly the 18 locked
matrix rows and validates runtime-produced evidence. It never runs a model. One
qualification record per pipeline must checksum-bind exact assets and
environments, backend minimum duration, native streaming ASR, segmentation,
diarization embedding, clustering, identity, enrollment, known/unknown decision,
labelled transcript, event log, restart, clean shutdown, and cold-versus-shared
semantic equivalence. The `0.50 s` technical checkpoint may correctly report
`TECHNICALLY_INVALID_BELOW_BACKEND_MINIMUM` for a `0.75 s` backend without
invalidating the complete pipeline; the actual integrated smoke must still use
audio at or above the documented minimum.

`reporting.py` accepts only the complete development job set from the frozen
campaign manifest, a file-verified passing qualification bundle, and exactly 18
checksum-valid frozen configurations. It rejects any held-out row. The report
has no weighted score and selects no production winner. Tier B always contains
AO/AG crossed with H2/H4/H5, plus no more than two challengers that are
non-dominated on development evidence.

Inputs:

- `campaign_manifest.json` and development-only `analysis/analysis.json` from
  the full-pipeline evaluation controller;
- `qualification_plan.json`, `qualification.json`, and their referenced smoke
  evidence files;
- `frozen_pipeline_configs/` containing exactly 18 YAML files and its checksum
  manifest.

Outputs:

```text
development_matrix.csv
development_summary.csv
frozen_pipeline_configs/
extended_set.yaml
development_report.md
metric_guide.md
failure_inventory.csv
resource_spot_checks.csv
development_analysis.json
checksums.json
full_pipeline_development_compact.zip
```

The compact ZIP is deterministic and excludes raw audio, model assets, caches,
and biometric vectors.

PowerShell from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" `
  -Action PlanQualification

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" `
  -Action ValidateQualification

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" `
  -Action Analyze

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_development.ps1" `
  -Action Collect
```

Anaconda Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
call .venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python -m app.full_pipeline_development.cli plan-qualification --plan-path automated_runs\full_speech_pipeline_v1\development\qualification_plan.json
python -m app.full_pipeline_development.cli validate-qualification --plan-path automated_runs\full_speech_pipeline_v1\development\qualification_plan.json --qualification-path automated_runs\full_speech_pipeline_v1\development\qualification.json
python -m app.full_pipeline_development.cli analyze --plan-path automated_runs\full_speech_pipeline_v1\development\qualification_plan.json --qualification-path automated_runs\full_speech_pipeline_v1\development\qualification.json --analysis-path automated_runs\full_speech_pipeline_v1\analysis\analysis.json --campaign-manifest automated_runs\full_speech_pipeline_v1\campaign_manifest.json --frozen-config-root automated_runs\full_speech_pipeline_v1\frozen_pipeline_configs --output-root JustPeachyResearchSummaries\full_pipeline\development\full_speech_pipeline_v1
```
