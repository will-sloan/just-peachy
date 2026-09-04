# Full-Pipeline Program Lock Validator

## Purpose

This package validates Prompt 0's authoritative Just-Peachy full streaming
speech-pipeline specification, Prompt 1's additive runtime completion state,
Prompt 2's common local demonstration layer, and Prompt 3's reproducible
full-pipeline evaluation infrastructure. At
`COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE`, it also validates Prompt 4's actual
all-18 development campaign, development-only challenger calibration,
qualification, frozen configurations, Tier-B predeclaration, and deterministic
report bundle.
It proves that the declared 2 ASR × 3 anonymous
diarization × 3 identity Cartesian product contains exactly 18 unique logical
pipelines, that every component/policy/environment/provenance reference resolves,
that the 15 common public contracts exist, and that the canonical program state
binds every declared canonical artifact—including Prompt-1 source, documentation,
tests, bounded result summaries, Prompt-2 demo artifacts, and Prompt-3 protocol,
schema, controller, monitor, scorer, wrapper, test, and synthetic-smoke
artifacts—by SHA-256. Contract checks also enforce
probability-safe raw-score semantics, exact enrollment-aggregation compatibility,
and biometric-sensitive enrollment artifact references.

At `COMPLETE_COMMON_DEMO`, validation additionally requires all 18 matrix presets,
the six ASR × frozen-anchor highlights, and bounded PASS evidence for AG-H5,
AG-H2, and AO-H4. The hashed smoke summary must prove local enrollment, file-mode
execution, labelled-transcript export, and model switching between immutable
sessions. It must explicitly record that no scientific campaign and no physical
microphone capture occurred.

At `COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE`, validation also requires
the prepared `full_speech_pipeline_v1` development/evaluation manifests. It
recomputes their ordered case counts and split identities, verifies the generated
protocol checksum map exactly, and checks source-audit/config identity. The
Prompt-3 smoke must contain a valid reusable perfect result, a valid but
non-reusable intentional failure, a successful retry, and checksum-bound result
documents. It must record zero model inference, zero evaluated pipelines, no
downloads, and no scientific campaign.

At `COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE`, validation retains every Prompt 0-3
invariant while moving stage-position checks to Prompt 4. It requires the exact
12-pipeline challenger registry, 18 PASS qualification records, four current
execution manifests, the checksum-bound inherited calibration manifest, 72
matched combined jobs over all 807 development cases, serial resource
measurements, 18 checksum-bound configurations, and the six unchanged H2/H4/H5
anchor decision hashes and settings. The completed recovery-v3 calibration is
accepted only through `frozen/policy_adoption_provenance.json`: its original
manifest, registry, and freeze bytes must remain unchanged, and the provenance
must record no repeated calibration inference, retuning, or evaluation-material
inspection. The raw calibration manifest keeps its pre-freeze registry fields
null; the separate freeze record binds the subsequently derived registry. The
recovery-v5 qualification/development/resource manifests must instead bind the
current comparator/restart-contract-corrected development package and that exact
adopted registry. The superseded v4 attempt is provenance only and is never an
accepted destination. The
validator deliberately does not reinterpret the historical v3 calibration with
newer code. The final report must contain one row per pipeline,
the mandatory six Tier-B anchors plus no more than two development-nondominated
challengers, an exact checksum map, and a byte-valid deterministic compact ZIP.
It may not use held-out outcomes or select a production winner.

The locked adoption reason is
`qualification_comparator_and_restart_contract_correction`. The validator pins
the complete handoff rather than trusting hashes declared by the provenance
file:

- v3 development package: `1ebb04143362d94f7987f142d3b7f139311ec37704f01d0bc41f30242e6bdde0`;
- unchanged evaluation package: `74551484a553edf74cdd3229c0b52cc75b01f26880cf277ece44aa9073799513`;
- unchanged streaming runtime package: `ce8a30253f8191c0ae58a4c0b8f3a30f5cb10416476887cfdd058e9a95fd622d`;
- v3 calibration manifest: `e4a0f7e33f2ec27ba2984f610f59c4f18e424e2d2ebdf3f774ca321bf3f7474e`;
- frozen registry file/identity: `f233a80b8d7dd39407987a1735f08c940cd0fab2591e7f1b1866159ffbbcb4f1` /
  `3b4f0bc674f0e1a27d7d60327c7c7cbe5532740369dae08c274cdedc3e977dda`;
- v3 calibration freeze: `10e071f9762b38ffd9462a6046e07bd22301e6f3aabbd39d57750ffa676e8c65`;
- v5 development package: `ff3f80fdcc55096366e148b7e8e82b9fcd06d77f0a9fc863a8dbce2e1606469a`;
- v5 adoption provenance file: `dc1ef272a5f8a7bbf963d4c71c4412cf5000d6e002bd60d053ceac59b87c1094`.

Prompt 4 validates prepared held-out manifest metadata, reference contracts,
and the held-out split identity only to preserve the already-frozen protocol
lock. In Prompt-4 state, `evaluation_material_inspected_by_prompt_4: false`
means no held-out audio, observations, scores, predictions, metrics, or results
were processed or inspected; it does not deny that protocol-lock metadata and
reference contracts were validated. The state records both facts separately.

The validator never imports or loads a speech model, runs inference, changes a
frozen result, downloads an asset, or starts a scientific campaign. The optional
asset check only reads and hashes already-local files.

## Inputs

- `configs/automated_evaluation/full_pipeline_matrix.v1.yaml`
- `configs/automated_evaluation/schemas/full_pipeline_contracts.v1.schema.json`
- `runs/full_pipeline_program/PROGRAM_STATE.json`
- the Prompt-2 `common_demo_package`, `common_demo_targeted_tests`, and
  `prompt_2_common_demo_smoke` canonical-artifact bindings when the state is
  `COMPLETE_COMMON_DEMO`
- `configs/automated_evaluation/full_speech_pipeline_v1.yaml`
- `benchmarks/full_pipeline/full_speech_pipeline_v1/protocol_summary.json`,
  `source_audit.json`, `checksums.json`, and both split manifest/reference trees
- `configs/automated_evaluation/schemas/full_pipeline_evaluation_result.v1.schema.json`
- `app/full_pipeline_evaluation/`, the run/monitor wrappers, focused tests, and
  the checksum-bound Prompt-3 synthetic smoke when the state is
  `COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE`
- `automated_runs/full_pipeline_development_v1_prompt4_execution_recovery_v3/`
  immutable calibration manifest, decision-policy registry, and calibration
  freeze
- `automated_runs/full_pipeline_development_v1_prompt4_execution_recovery_v5_restart_contract_fix/`
  policy-adoption provenance, copied policy freeze, orchestration/current
  campaign manifests, qualification bundle, combined evidence, and 18 frozen
  configurations when the state is `COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE`
- `JustPeachyResearchSummaries/full_pipeline/development/full_speech_pipeline_v1/`
  development matrix/summary, extended set, report, metric/failure/resource
  tables, analysis, checksums, copied frozen configurations, and compact ZIP
- the component, model-asset, and environment registries referenced by the matrix
- the frozen diarization and hybrid selections referenced by the matrix
- the three scientific enrollment policies referenced by the matrix
- local model assets only when `--verify-assets` is supplied

## Outputs

The command writes nothing. It prints one validation summary and exits `0` on
success or prints all detected contract/resolution errors and exits `1`.
It accepts the locked Prompt-0 stage, the completed Prompt-1 stage, and the
completed Prompt-2, Prompt-3, and Prompt-4 stages; each later stage must retain
all earlier locks. Prompt-3/4 validation is read-only and does not prepare a
protocol, run inference, or create/rewrite scientific artifacts.

## PowerShell

From the repository root:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "..\..\.venv\Scripts\python.exe" -m app.full_pipeline_program validate --json
```

To also hash every locked local model file/tree without loading a model:

```powershell
& "..\..\.venv\Scripts\python.exe" -m app.full_pipeline_program validate --verify-assets --json
```

## Anaconda Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
call .venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python -m app.full_pipeline_program validate --json
python -m app.full_pipeline_program validate --verify-assets --json
```

The repository `.venv` is the validated control environment. Activating a base
Conda environment is not a substitute for the repository's pinned environment.

## Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool
..\..\.venv\Scripts\python.exe -m app.full_pipeline_program validate --json
```

## Targeted Tests

Run only the program-lock tests from the Evaluation Tool directory:

```powershell
& "..\..\.venv\Scripts\python.exe" -m pytest tests\automated_evaluation\test_full_pipeline_program_lock.py -q
```

These tests parse and validate declarations only. They do not run audio or
neural inference.

To inspect the currently recorded stage without changing it:

```powershell
Get-Content "runs\full_pipeline_program\PROGRAM_STATE.json" -Raw |
  ConvertFrom-Json |
  Select-Object status, current_prompt_index, remaining_prompt_indices
```

## Interpretation

A `PASS` always means that Prompt 0's specification remains internally consistent
and its current source anchors resolve. At Prompt 1 it also means the shared
runtime and bounded component/file/enrollment evidence are checksum-bound. At
Prompt 2 it additionally means the common demo exposes all 18 presets, highlights
the six ASR × H2/H4/H5 presets, and its required three-preset application smoke is
checksum-bound.

At Prompt 3, PASS additionally means the prepared protocol's exact generated
file set, case counts, split identities, and checksums resolve; all 18 logical
pipelines are recorded as planned; and the common result tree, scorers,
restart-safe controller, and measured monitor are checksum-bound. Its only run
evidence is the two-case model-free synthetic infrastructure smoke.

At Prompt 4, PASS additionally means all 18 pipelines have qualified and have
complete development-only accuracy/resource evidence, the 12 challengers use
independent frozen development calibrations, and the inherited v3 calibration
and copied v5 policy files are byte-identical and connected by explicit adoption
provenance. It also means every v5 execution manifest is bound to the corrected
current package rather than the historical calibration package. The six anchors
retain the frozen Hybrid Product-v2 selection SHA, and every published
configuration/report file is checksum- and ZIP-consistent. Tier A is
development-complete but held-out not run; Tier B is only predeclared; Tier C
and the production winner remain unselected.

Prompt-2 or Prompt-3 PASS is not evidence that the 18-pipeline scientific campaign ran, that
a physical microphone was tested, or that any model was scientifically ranked.
AG's frozen large-study segment identity remains unchanged while the runtime uses
a separately recorded native-streaming overlay; DE is not held out, C7–C9 remain
uncalibrated challengers, and Tier C is intentionally unselected. See
`app/full_pipeline/README.md` and `app/full_pipeline_demo/README.md` for runtime
and demo purpose, inputs, outputs, and exact execution commands.

Prompt-4 PASS is development evidence only. It is not held-out performance,
production selection, deployment clearance, or permission to tune from the
evaluation split.
