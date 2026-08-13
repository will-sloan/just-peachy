# Just-Peachy Handoff

Read this first when continuing work in a new Codex account.

## Goal

The repository is an automated, reproducible speech-pipeline evaluation tool. The
current work adds qualified edge components, deterministic edge-research scenario
catalogs, and operator scripts while reusing the existing dataset, augmentation,
scoring, reporting, campaign-state, and artifact-validation systems.

The intended research order is component isolation first, targeted combinations
second, and only then larger robustness, speaker, or distributed campaigns. The
current implementation is ready for the first one-scenario integration run; it is
not a claim that any added backend is the best model.

## Current Git state

- Repository: `C:\Users\amiri\Documents\GitHub\just-peachy`
- Branch: `codex/edge-component-expansion`
- Current implementation commit: `94151fc9a068b7438a62c9eb6f3256afa86b746e`
- Accepted baseline: `b78df94cf1b8c4c9a1ea684a0a64b7bd37020838`
- The edge expansion is committed locally and was not pushed.
- No long research campaign has been run. Preserve all existing campaign results.
- `Resumes/` is intentionally local and ignored by Git.
- At handoff, `HANDOFF.md` is the only untracked file. It is documentation only.

Confirm before changing anything:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
```

If the commit, branch, or working tree differs, inspect that difference before
using frozen catalogs or comparing results. Do not reset, rebase, or delete
campaign folders to make the repository look clean.

## Decisions that remain in force

- Whisper Base is the reference ASR; do not evaluate Whisper Large.
- Models must be acquired explicitly. Inference and qualification never download
  models implicitly.
- Keep dependency stacks isolated: `edge-cpu`, `moonshine-edge`, `onnx`, and
  existing `core-cpu`. Do not combine them in one Windows Python process.
- Default execution is sequential. CUDA and GPU-concurrency qualification are not
  complete.
- Dining Room and Restaurant are the executable exact RIRs. Bedroom is unresolved;
  do not substitute ParkingLot, Kitchen, or another RIR.
- Preserve `Unknown` speaker labels. Do not use reference speaker or transcript
  fallbacks in predictions.
- Do not start optional combinations, large campaigns, Stage 10 campaigns, or
  multi-day research until the initial small screen is reviewed.

## Architecture and ownership map

```text
Frozen benchmark manifests + normalized metadata
  -> deterministic edge scenario catalogs
  -> campaign planner/state/artifact contracts
  -> selected isolated Python profile
  -> configured pipeline (VAD -> segmentation -> ASR -> optional embedding)
  -> standardized predictions + optional streaming diagnostics
  -> existing scoring, telemetry, plots, reports, and analysis
```

Do not replace the middle or final Evaluation Tool layers when extending a
component. Add a component YAML and adapter, register its identity/assets/profile,
then let the configured runner and campaign executor handle it.

The important implementation boundaries are:

- `app/inference_pipeline/` - adapters, interfaces, pipeline composition, and
  component registry.
- `app/model_runner/configured.py` - resolved-pipeline execution into existing
  normalized prediction outputs.
- `app/campaign_executor/` - immutable scenarios, state, retries, artifact
  validation, and resume behavior.
- `app/edge_research/` - deterministic catalog/queue generation and preflight;
  it does not duplicate evaluator logic.
- `app/speaker_protocol/` - backend-bound Stage 10 enrollment/probe contracts.

## Qualified additions

| Component | Profile | Status |
|---|---|---|
| Moonshine Streaming English Tiny, Small, Medium | `moonshine-edge` | CPU-qualified |
| Sherpa-ONNX Streaming Zipformer English 20M INT8 | `onnx` | CPU-qualified |
| FSMN-VAD | `edge-cpu` | CPU-qualified |
| CAM++ and ERes2Net Base speaker embeddings | `onnx` | CPU-qualified; Stage 10 smoke passed |

Evidence and exact asset hashes/licenses are in
[edge_component_expansion_handoff.md](<Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/edge_component_expansion_handoff.md>).

The main evidence files are:

- `Software Validation from Datasets/Evaluation Tool/runs/edge_backend_qualification/edge-cpu.json`
- `Software Validation from Datasets/Evaluation Tool/runs/edge_backend_qualification/moonshine-edge.json`
- `Software Validation from Datasets/Evaluation Tool/runs/edge_backend_qualification/onnx-edge.json`
- `Software Validation from Datasets/Evaluation Tool/runs/edge_speaker_protocol_smoke/real_smoke_matrix.json`

## Research catalogs

Default campaigns: 84 scenarios total.

| Campaign | Profile | Scenarios |
|---|---|---:|
| `campaign_edge_screen_v1` | `edge-cpu` | 36 |
| `campaign_edge_stream_moon_v1` | `moonshine-edge` | 36 |
| `campaign_edge_stream_onnx_v1` | `onnx` | 12 |

There are 532 frozen ASR scenarios in ten catalogs, including optional combination
and large campaigns. Catalogs, queue, and plan are under
`Software Validation from Datasets/Evaluation Tool/benchmarks/edge_research/`.

Optional, disabled campaigns are `campaign_edge_combo_moon_v1` (216),
`campaign_edge_combo_onnx_v1` (72), and five `campaign_edge_lg_*_v1` catalogs
(32 each). Stage 10 plans are also disabled:
`campaign_spk10_edge_sm_v1` (63 clean items/backend),
`campaign_spk10_edge_std_v1` (240), and `campaign_spk10_edge_lg_v1` (510).

Union catalogs are design/analysis inputs only; they must not be run as a single
process because their scenarios require different environment profiles.

## Important files

- [Edge plan](<Software Validation from Datasets/Evaluation Tool/app/edge_research/plan.py>) - deterministic catalog generation and preflight.
- [Operator quick start](<Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/edge_research_quick_start.md>) - full run guidance.
- [Detailed edge handoff](<Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/edge_component_expansion_handoff.md>) - component table, asset hashes, evidence, and limits.
- [Script README](scripts/EDGE_RESEARCH_README.md) - PowerShell script inputs and outputs.
- `scripts/prepare_edge_research.ps1` - install/refresh isolated profiles and acquire approved assets.
- `scripts/verify_edge_research.ps1` - preflight packages, assets, source rows, catalogs, and bounded smokes.
- `scripts/run_edge_research.ps1` - plan, run, status, stop, and resume.
- `Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/model_asset_registry.v1.yaml`
  - declared model identity, hashes, licensing, and acquisition requirements.
- `Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/artifact_registry.v3.yaml`
  - required/conditional scenario artifacts, including streaming diagnostics.
- `Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/streaming_metric_registry.v1.yaml`
  - streaming diagnostic metrics and definitions.

## Verification already completed

- Seven added backends passed repeated real qualification.
- CAM++ and ERes2Net Stage 10 smoke passed for both backends with `Unknown`
  preserved.
- All 10 catalogs and 532 scenario identities validate.
- Source preflight checked 8,663 frozen manifest rows with zero missing inputs.
- Default dry-plan passed: 36 + 36 + 12 scenarios.
- Focused tests passed (118 passed, 2 skipped; final Stage 10 file: 16 passed),
  plus Ruff, compilation, and Git whitespace checks.

The focused test command used for the expansion was:

```powershell
Set-Location 'Software Validation from Datasets\Evaluation Tool'
..\..\.venv\Scripts\python.exe -m pytest test_stage1 test_stage3 test_stage5 test_stage6 test_stage8 test_stage10 test_edge_research test_campaign_runtime_publication
```

Do not rerun broad campaigns merely to revalidate the repository. Run targeted
tests only if you change their covered behavior.

## Exact next steps

From the repository root:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
git switch codex/edge-component-expansion

powershell -ExecutionPolicy Bypass -File scripts\prepare_edge_research.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify_edge_research.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan

# First and only recommended real run at this point:
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Run -CampaignId campaign_edge_screen_v1 -MaxScenarios 1
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Status -CampaignId campaign_edge_screen_v1
```

If that scenario validates, continue the same immutable campaign:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Resume -CampaignId campaign_edge_screen_v1
```

To stop safely:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Stop -CampaignId campaign_edge_screen_v1
```

After a completed campaign, analyze with the core environment:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
..\..\.venv\Scripts\python.exe run_evaluation.py analysis run --campaign-root automated_runs\campaign_edge_screen_v1
```

### Operator command semantics

- `prepare_edge_research.ps1` installs/refreshes the three isolated profiles and
  downloads only approved explicit assets. Use `-Recreate` only when deliberately
  rebuilding those environments.
- `verify_edge_research.ps1` checks FFmpeg, interpreters, packages, assets, frozen
  source inputs, catalogs, and real bounded smokes. Its default smoke mode rewrites
  the qualification-evidence files; use `-SkipSmoke` for a non-invasive repeat
  preflight after evidence is already trusted.
- `run_edge_research.ps1 -Action Plan` regenerates the deterministic plan/catalogs
  and dry-plans every selected campaign, but starts no inference.
- `Run`, `Resume`, `Status`, and `Stop` accept `-CampaignId`; `Run` may also use
  `-MaxScenarios 1` for a bounded smoke. `-IncludeOptional` is deliberately not
  part of the immediate next step.

Results are written beneath:

```text
Software Validation from Datasets/Evaluation Tool/automated_runs/<campaign_id>/scenarios/<scenario_id>/
```

For each scenario, inspect `resolved_scenario.json`, `status.json`, standardized
`predictions/utterances.jsonl`, `metrics/`, `resource_logs/`, `logs/`,
`report/`, and `checksums.json`. Streaming scenarios additionally require
`predictions/streaming_diagnostics.jsonl`. Use campaign validation rather than
judging completion from a folder's presence.

## Known blockers and deferred work

- TitaNet is optional and not integrated.
- Bedroom RIR has no approved replacement.
- Degraded Stage 10 probes require the approved augmentation execution path.
- CUDA/GPU, GPU concurrency, and Raspberry Pi performance are unqualified.
- Stage 11 diarization remains gated by installed/licensed backends and valid timebase
  references.

## Rules for the next Codex account

1. Read this file, then the detailed edge handoff and quick-start guide.
2. Re-run the three Git commands above and report deviations before editing anything.
3. Treat benchmark manifests, scenario schemas/hashes, catalog identities, and source
   component YAML as versioned contracts. A result-affecting change creates a new
   scenario identity; never reuse an old scenario ID.
4. Keep the active work narrowly scoped. Do not refactor dataset loading, augmentation,
   scoring, plotting, reporting, GUI behavior, or existing runners merely to support a
   new backend.
5. Preserve per-item failures, `Unknown`, identifiers, timestamps, and original
   artifact/checksum evidence. Never silently fill predictions from references.
6. Before asking the operator to run a larger campaign, provide the exact selected
   campaign IDs, profile, count, prerequisites, expected output path, and stop/resume
   command.

The next recommended experiment is the single `campaign_edge_screen_v1` scenario above,
followed by review of its predictions, telemetry, checksums, and report before any
broader campaign is started.
