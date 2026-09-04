# Bounded Prompt-5 Full-Pipeline Core Evaluation

## Purpose and evidence boundary

This additive package runs the untouched held-out core evaluation for all 18
frozen full speech pipelines under the user-authorized eight-day amendment:

- scope ID: `full_pipeline_prompts_4_8_eight_day_c_only.v1`;
- scope class: `BOUNDED_REDUCED`;
- original full scope complete: `false`;
- Prompt-5 wall-time budget: 60 hours;
- storage: C: only, with a 35-GiB free-space reserve.

It does not implement models or inference in the UI/orchestrator. It delegates
inference to `app.full_pipeline_evaluation` and the common Prompt-1 runtime. It
will not prepare or run until a byte-valid bounded Prompt-4 completion record,
all 18 frozen configurations, the challenger registry, `extended_set.yaml`, and
the development summary independently validate.

The package never retunes on held-out data. Selection uses only the already
prepared metadata/reference manifests, before predictions. Native AMI and
CHiME-6 are explicitly deferred to Prompt 6.

## Fixed reduced panel

The selection is immutable and identical for every pipeline:

| Stratum | Cases |
|---|---:|
| Common Voice 60+ (2 hash-ranked clips × 365 speakers) | 730 |
| Controlled V1 (all) | 360 |
| Product V2 (all primary-gallery + every full-gallery case) | 808 |
| CMU Arctic (3 clips per dataset/speaker group) | 54 |
| HiFiTTS | 30 |
| LibriSpeech | 219 |
| VOiCES ASR/acoustic | 39 |
| **Total** | **2,240** |

Selected case IDs, sorted and LF-terminated, have SHA-256
`0269ab1545cbd657732f88b73d75aeda734e4e3cdf72ac92af639633afaf82cd`.
The accuracy plan is 7 strata × 18 pipelines = 126 jobs, with at most two jobs
concurrent. The matched resource plan is one predeclared Product V2 case × 18
pipelines and always runs serially.

## Inputs

- `runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json`;
- `runs/full_pipeline_program/PROGRAM_STATE.json` at bounded Prompt 4;
- `runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json`, exact
  SHA-256 `f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4`;
- the Prompt-4 universal `completion_marker.json` supplied with
  `-Prompt4Marker`;
- Prompt-4's 18 `frozen_pipeline_configs/*.yaml` plus checksum document;
- Prompt-4's development-only `decision_policy_registry.json`;
- Prompt-4's `extended_set.yaml` and `development_summary.csv`;
- `benchmarks/full_pipeline/full_speech_pipeline_v1/evaluation/` metadata and
  references;
- local audio and model assets already bound by the frozen program.

No command downloads data or models. No input may resolve outside C:.
The deployment-steering path, hash, schema, ID, and status are included in the
immutable Prompt-5 authorization before held-out inference can start.

Under the automatic eight-day controller, the authoritative predecessor is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_development_prompt4_reduced_8day_v1_orchestrated\completion_marker.json
```

Prompt 5 independently verifies all 18 frozen YAML bytes and proves that their
result-affecting source files, matrix/runtime fields, model identities,
enrollment and decision policies, alignment/buffering policy, and UI policy
exactly match the live worker contract before preparing held-out cases. A
signed freeze that describes a different execution contract fails closed.

## Outputs

The restartable workspace defaults to:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_core_evaluation_reduced_8day_v1
```

Its `report` directory contains:

- `all18_finalist_summary.csv`;
- `all18_asr.csv`;
- `all18_diarization.csv`;
- `all18_identity.csv`;
- `all18_speaker_attributed_transcript.csv`;
- `all18_streaming.csv`;
- `all18_resources.csv`;
- `all18_deployment_evidence.json` (all 18 in exact matrix order, with every
  steering attribute represented by structured evidence);
- `all18_failures.csv` (one row for every terminal job, not failures only);
- `paired_comparisons.csv`;
- `bootstrap_intervals.csv`;
- `speaker_sufficient_statistics.jsonl.gz`;
- `evaluation_report.md` and `analysis.json`.

`Collect` creates a checksum-bound compact copy and ZIP under:

```text
JustPeachyResearchSummaries\full_pipeline\heldout\full_speech_pipeline_v1_reduced_8day_v1
JustPeachyResearchSummaries\full_pipeline\heldout\full_speech_pipeline_v1_reduced_8day_v1.zip
```

The compact package excludes raw datasets, audio, model weights, enrollment
vectors, and raw prediction/event trees. The case/speaker sufficient statistics
are included because they are required to reproduce speaker-level intervals.
It includes the checksum-bound deployment steering and deployment-evidence
report in its protocol/checksum inventory.

`all18_deployment_evidence.json` is decision context, not a Raspberry Pi
benchmark or a pipeline filter. Windows/x86_64 serial resource measurements are
labelled as desktop evidence. Missing measurements use explicit `UNKNOWN` or
`UNSUPPORTED` cells. The report separately records one of the four 2-GiB design
classes and one of the four Linux ARM64 portability classes, Windows-specific
assumptions, dependency status, and required replacements. It cannot claim a
final Raspberry Pi winner, `LINUX_ARM64_READY`, or target-hardware performance
without later ARM64 Linux validation.

## PowerShell run sequence

Open PowerShell in the Evaluation Tool directory. Replace `$Prompt4` only if the
bounded Prompt-4 workspace uses a different absolute C: path.

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
$Prompt4 = "C:\ABSOLUTE\C-ONLY\PROMPT4\completion_marker.json"
$PiSteering = ".\runs\full_pipeline_program\RASPBERRY_PI_DEPLOYMENT_STEERING.json"
$Run = ".\scripts\run_full_pipeline_core_evaluation.ps1"

& $Run -Action ValidateFreeze -Prompt4Marker $Prompt4 -PiDeploymentSteeringPath $PiSteering
& $Run -Action PrepareReduced -Prompt4Marker $Prompt4
& $Run -Action RunAccuracy -Prompt4Marker $Prompt4 -ParallelJobs 2
& $Run -Action ValidateAccuracy -Prompt4Marker $Prompt4
& $Run -Action PrepareResources -Prompt4Marker $Prompt4
& $Run -Action RunResources -Prompt4Marker $Prompt4
& $Run -Action ValidateResources
& $Run -Action Analyze -Prompt4Marker $Prompt4
& $Run -Action Collect -Prompt4Marker $Prompt4
```

The eight-day orchestrator supplies `JP8_ADAPTER_ID`,
`JP8_ADAPTER_CONTRACT_SHA256`, `JP8_PREDECESSOR_COMPLETION_PATH`, and
`JP8_COMPLETION_RECORD`. To finalize manually:

```powershell
$env:JP8_ADAPTER_ID = "prompt5_core_evaluation_reduced_8day_v1"
$env:JP8_ADAPTER_CONTRACT_SHA256 = "<64-hex adapter contract SHA-256>"
& $Run -Action UpdateProgramState -Prompt4Marker $Prompt4 -PredecessorRecord $Prompt4
& $Run -Action ValidateCompletion
```

`UpdateProgramState` writes the universal completion marker
`COMPLETE_ALL18_CORE_EVALUATION_REDUCED_8DAY_V1`, three exact PASS gate records,
an artifact manifest, and then atomically advances `PROGRAM_STATE.json`. Gate
files are stored under `<WorkspaceRoot>\gate_records`.

For the eight-day controller, the single restart-safe stage command is:

```powershell
& $Run -Action RunAll -Prompt4Marker $Prompt4 -ParallelJobs 2
```

`RunAll` executes the same gated sequence shown above. Before final program-state
advancement, restarting it validates and reuses completed checksum-bound work;
it never widens the panel. After successful completion, use
`ValidateCompletion` rather than manually invoking `RunAll` again.
Every wrapper action uses the same authoritative steering default; an explicit
`-PiDeploymentSteeringPath` is accepted only to bind the same C:-local file.

The orchestrator's independent validation action is `ValidateCompletion`.
Overall percentage, phase, detail, and ETA are written every five seconds to
`$env:JP8_PROGRESS_RECORD` (or `<WorkspaceRoot>\program_progress.json`) using
schema `full-pipeline-core-progress.v1`. The eight-day controller captures the
stage process output in its configured `<WorkspaceRoot>\controller.log`.

## Live monitor and graceful stop

Open a second PowerShell window:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
while ($true) {
    Clear-Host
    .\scripts\run_full_pipeline_core_evaluation.ps1 -Action Status
    Start-Sleep -Seconds 30
}
```

Press `Ctrl+C` to close only the monitor. To request a restart-safe campaign
stop from another window:

```powershell
.\scripts\run_full_pipeline_core_evaluation.ps1 -Action Stop
```

Completed checksum-bound jobs are reused on the next `RunAccuracy` or
`RunResources`; they are not rerun.

## Anaconda Prompt

The repository `.venv` is authoritative even when launching from Anaconda
Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
call .venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
set PROMPT4=C:\ABSOLUTE\C-ONLY\PROMPT4\completion_marker.json
set PI_STEERING=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\runs\full_pipeline_program\RASPBERRY_PI_DEPLOYMENT_STEERING.json
python -m app.full_pipeline_core_evaluation validate-freeze --prompt4-marker "%PROMPT4%" --pi-deployment-steering-path "%PI_STEERING%"
python -m app.full_pipeline_core_evaluation prepare-reduced --prompt4-marker "%PROMPT4%"
python -m app.full_pipeline_core_evaluation run-accuracy --prompt4-marker "%PROMPT4%" --parallel-jobs 2
python -m app.full_pipeline_core_evaluation validate-accuracy --prompt4-marker "%PROMPT4%"
python -m app.full_pipeline_core_evaluation prepare-resources --prompt4-marker "%PROMPT4%"
python -m app.full_pipeline_core_evaluation run-resources --prompt4-marker "%PROMPT4%"
python -m app.full_pipeline_core_evaluation validate-resources
python -m app.full_pipeline_core_evaluation analyze --prompt4-marker "%PROMPT4%"
python -m app.full_pipeline_core_evaluation collect --prompt4-marker "%PROMPT4%"
```

## Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool
set PROMPT4=C:\ABSOLUTE\C-ONLY\PROMPT4\completion_marker.json
..\..\.venv\Scripts\python.exe -m app.full_pipeline_core_evaluation status
..\..\.venv\Scripts\python.exe -m app.full_pipeline_core_evaluation validate-freeze --prompt4-marker "%PROMPT4%"
```

## Scientific aggregation

CSV tables retain computed/unsupported/undefined status and aggregation method
beside every metric. Ratio metrics use pooled sufficient numerators and
denominators; additive durations/counts are summed only across disjoint jobs;
other scalars use an explicit case-count-weighted mean.

Every required category CSV contains exactly one row for each of the 18
pipelines, including all-failure and no-supported-metric cases. Scientific
metric values are labelled as conditional on checksum-complete job outputs.
Separate `end_to_end_*` planned-job, planned-case, completion, noncompletion,
and failure-rate fields use all planned terminal jobs, so failures remain in
the end-to-end denominator without fabricating WER, DER, or identity scores for
missing output.

Confidence intervals use 2,000 deterministic speaker-cluster resamples. All
probes for one reference speaker share a resampling weight. A multi-speaker
mixture contributes fractionally to each participating speaker so it is not
counted in full once per person. Paired comparisons use identical speaker draws
and report speakers absent from either side. Clips are never treated as
independent speakers.

## Developer validation

These tests use synthetic metadata/results only; they do not open held-out
predictions or run neural inference:

```powershell
& "..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline_core_evaluation -q
& "..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline_deployment_evidence -q
```

Static import/compile check:

```powershell
& "..\..\.venv\Scripts\python.exe" -m compileall -q `
  app\full_pipeline_core_evaluation app\full_pipeline_deployment_evidence
```
