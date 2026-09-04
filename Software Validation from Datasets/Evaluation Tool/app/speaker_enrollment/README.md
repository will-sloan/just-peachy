# Speaker enrollment and live-duration study

The recommendation-driven open-set successor is documented in `LIVE_V2_README.md`. It is additive: the frozen v1 protocol and its pairwise-EER behavior remain available for reproducibility.

## Purpose

This package implements the additive `speaker_enrollment_duration_v1` experiment. It measures enrollment utterance count, accumulated enrollment audio, enrollment representation, and nested live/probe duration after a speaker backend has been selected. It preserves the frozen Stage 10 calibration/evaluation boundary, recalibrates a backend-specific threshold for every configuration, evaluates held-out known and Unknown speakers, caches every immutable audio-slice embedding once, and produces speaker-cluster-bootstrap analysis.

It does not select the winning speaker model, modify Stage 10, modify the Common Voice speaker-breadth package, run diarization, train a model, pad short audio, or make an automatic product decision.

## Inputs

- Source protocol supplied with `-SourceProtocolRoot`; the default is `benchmarks/speaker_breadth/commonvoice_60plus_v1`.
- Study policy: `configs/automated_evaluation/speaker_enrollment_duration.v1.yaml`.
- Source audio resolved from each frozen logical path through `JP_DATA_ROOT`.
- One primary and one fallback backend ID selected after the earlier six-model and breadth analyses.
- Existing local qualified environments and model assets. Inference never downloads a model.
- Phase D: an explicit completed enrollment configuration ID selected after reviewing Phases A-C.
- Phase E: an explicit YAML decision gate selected after reviewing the Phase D duration curves.

Common Voice is prompted/read speech. Durations are available waveform durations from the source-file start, not exact voiced-speech durations. The source does not provide reliable session/device identity, so session diversity is recorded as unavailable.

## Outputs

The frozen protocol is under:

```text
benchmarks/speaker_enrollment/speaker_enrollment_duration_v1/
```

It contains feasibility evidence, cohort and probe-parent selections, immutable audio slices, nested probe variants, enrollment selections, configurations, phase templates, provenance, and checksums. It contains no audio or embeddings.

Runtime results default to:

```text
<Evaluation Tool>/JustPeachyResults/speaker_enrollment/<protocol_id>/<backend>/
├── embeddings/                         # backend-specific per-slice cache
├── phase_a_enrollment_count/
├── phase_b_enrollment_duration/
├── phase_c_aggregation/
├── phase_d_probe_duration/
├── phase_e_joint_frontier/
└── plans/
```

Combined analysis is written to `<protocol result root>/analysis/` and includes:

```text
analysis_manifest.json
configuration_results.csv
speaker_results.csv
duration_curve.csv
enrollment_curve.csv
aggregation_comparison.csv
joint_frontier.csv
reliability_summary.csv
quality_loss_vs_reference.csv
marginal_gain.csv
speaker_diagnostics.csv
enrollment_selection_variance.csv
subgroup_results.csv
report.md
plots/
```

`Collect` creates a compact package under `<Evaluation Tool>/JustPeachyResearchSummaries/`. It copies the frozen manifests and compact analysis, but references rather than duplicates large biometric-sensitive embedding caches.

## Anaconda Prompt / Command Prompt

Open Anaconda Prompt or Command Prompt and run:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"

powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_enrollment_study.ps1" -Action Audit
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_enrollment_study.ps1" -Action Prepare
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_enrollment_study.ps1" -Action Validate
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_enrollment_study.ps1" -Action Plan -Phase EnrollmentCount
```

The safe bounded synthetic contract smoke is:

```bat
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_enrollment_study.ps1" -Action Smoke
```

It uses two known speakers, one calibration Unknown speaker, one evaluation Unknown speaker, enrollment counts 1 and 2, probe durations 0.75 and 3 seconds, and normalized plus duration-weighted aggregation. It runs no model and is labeled `NON-SCIENTIFIC`.

## PowerShell scientific workflow

After finalist selection, replace only the backend placeholders:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy"

$Wrapper = "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_enrollment_study.ps1"
$Backends = @(
    "PLACEHOLDER_PRIMARY"
    "PLACEHOLDER_FALLBACK"
)

& $Wrapper -Action Validate -Backends $Backends
& $Wrapper -Action Run -Phase EnrollmentCount -Backends $Backends
& $Wrapper -Action Run -Phase EnrollmentDuration -Backends $Backends
& $Wrapper -Action Run -Phase Aggregation -Backends $Backends
& $Wrapper -Action Status -Backends $Backends
& $Wrapper -Action Analyze -Backends $Backends
```

Choose one completed reference configuration from the earlier results; do not let the tool choose it from evaluation accuracy:

```powershell
$ReferenceEnrollmentConfigId = "cfg_REPLACE_AFTER_PHASES_A_TO_C"
& $Wrapper -Action Run -Phase ProbeDuration -Backends $Backends `
    -ReferenceEnrollmentConfigId $ReferenceEnrollmentConfigId
& $Wrapper -Action Analyze -Backends $Backends
```

After reviewing the observed curves, create a gate outside the frozen protocol, for example:

```yaml
schema_version: speaker-enrollment-joint-decision.v1
enrollment_configuration_ids:
  - cfg_REPLACE_WITH_SELECTED_POINT_1
  - cfg_REPLACE_WITH_SELECTED_POINT_2
probe_durations_sec:
  - 0.75
  - 1.50
  - 3.00
```

Then run only the selected joint frontier:

```powershell
$DecisionGate = "C:\path\to\speaker_enrollment_joint_decision.yaml"
& $Wrapper -Action Run -Phase JointFrontier -Backends $Backends `
    -DecisionGate $DecisionGate
& $Wrapper -Action Analyze -Backends $Backends
& $Wrapper -Action Collect -Backends $Backends
```

The runner emits `[REUSE EMBEDDING]`, `[EXTRACT]`, `[CALIBRATE]`, `[EVALUATE]`, `[VALIDATE]`, and `[PASS]`. Valid cache items and completed configurations are reused. Invalid partial results are preserved under timestamped names.

## Tests

From Anaconda Prompt, Command Prompt, or PowerShell:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest `
    tests\automated_evaluation\test_speaker_enrollment_duration.py -q `
    --basetemp=.pytest-speaker-enrollment
```

These focused tests do not load a speaker model. The runner Plan and Validate checks resolve local source paths but perform no inference.
