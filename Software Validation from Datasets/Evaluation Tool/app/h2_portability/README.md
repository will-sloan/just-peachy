# H2 ONNX portability tooling

## Purpose

This package exports the exact local ReDimNet2-B2 and Pyannote Segmentation
3.0 checkpoints to FP32 ONNX, compares native PyTorch and ONNX Runtime under a
frozen numerical contract, and prepares (but does not qualify) an ARM64 Linux
deployment. It does not download models, retune thresholds, or change the H2
scientific configuration.

The future XVF hook uses `spatial-evidence-interface.v2`. It represents
timestamp/source-clock identity, AoA and confidence, speech energy/activity,
direction change, beamformer/channel state, availability, and quality flags.
The current `xvf3800-spatial-evidence.no-effect.v2` implementation records a
receipt only: supplied values, missing/default values, and every downstream
application flag are explicitly non-result-affecting. Legacy v1 field aliases
remain constructor-compatible and serialize to the canonical v2 schema.

Recorded predecessor Windows/x86-64 engineering result:

- ReDimNet2-B2: valid dynamic-time FP32 graph, SHA-256
  `5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609`;
- Pyannote Segmentation 3.0: valid fixed 10-second FP32 graph, SHA-256
  `b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a`;
- both bounded parity reports pass, including two real-speech engineering
  inputs, exact H2 identity/clustering decisions, and exact Pyannote
  speech/overlap boundaries;
- both preferred Dynamo attempts failed for concrete exporter limitations, so
  the successful graphs use the explicit `torch_onnx_legacy_v1` fallback. The
  failure reports are retained beside each graph;
- the separately versioned `H2_PORTABLE_ONNX_FP32` profile is wired into the
  common file and microphone factories while `H2_REFERENCE` stays the default;
- predecessor enrolled and empty-enrollment 10-second native-vs-ONNX runs pass
  their checksum-frozen full-pipeline contract. Transcript text/words, semantic
  events and their order, RTTM-equivalent turns, cluster coassignment, and
  identity states/labels match exactly after cluster-label permutation. The
  enrolled case exercised identity evidence and labels. Maximum identity-score
  delta was `1.7881393432617188e-07`; maximum boundary delta was
  `1.7763568394002505e-15` seconds.

This is bounded predecessor full-pipeline desktop parity for its recorded code
identity, not final v17 parity, a scientific accuracy campaign, ARM64 numerical
parity, or Raspberry Pi qualification. The v17 controller-managed
`H2_PORTABLE_ONNX_FP32_FROZEN_FIXTURE_PARITY` job is the only authority for the
current-runtime final claim.

## Inputs

- repository-local ReDimNet2 checkpoint and pinned official source;
- repository-local Pyannote Segmentation 3.0 snapshot;
- optional local WAVs for additional parity cases;
- the two isolated Python environments under `.stage8-envs`;
- an explicit destination for each ONNX graph/report.

## Outputs

- one self-contained FP32 `.onnx` graph per component;
- `.onnx.manifest.json` with hashes, exporter identity, environment, shapes,
  precision, and fallback evidence;
- exporter success/failure reports;
- frozen case manifests and per-component parity JSON;
- one controller-consumable E2E component-binding JSON;
- a pre-run full-pipeline tolerance/normalization freeze receipt plus enrolled
  and empty-enrollment semantic parity reports;
- ARM64 diagnostics and a two-GiB design budget.

The bounded evidence currently lives under
`JustPeachyResults/h2_product_program/portability_bounded_20260824`. Fresh
factory evidence lives under
`JustPeachyResults/h2_product_program/e2e_parity_current_20260824`. Its
`E2E_PARITY_SUMMARY.json` remains bound to its predecessor runtime source
hashes and is not substituted for the scheduled v17 receipt.

## Windows PowerShell / Anaconda Prompt

Run from `Software Validation from Datasets\Evaluation Tool`. The same
commands work in PowerShell launched from Anaconda Prompt.

```powershell
$Repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$Tool = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
$Out = Join-Path $Tool 'JustPeachyResults\h2_product_program\portability_bounded_20260824'
Set-Location $Tool

& "$Repo\.stage8-envs\redimnet2\Scripts\python.exe" -m app.h2_portability onnx-status `
  --component redimnet2_b2_speaker_embedding `
  --onnx-path "$Out\redimnet2_b2_fp32.onnx"

& "$Repo\.stage8-envs\redimnet2\Scripts\python.exe" -m app.h2_portability export `
  --component redimnet2_b2_speaker_embedding `
  --onnx-path "$Out\redimnet2_b2_fp32.onnx" `
  --exporter torch_onnx_legacy_v1 --replace

& "$Repo\.stage8-envs\credential-diarization\Scripts\python.exe" -m app.h2_portability export `
  --component pyannote_segmentation_3_0 `
  --onnx-path "$Out\pyannote_segmentation_3_0_fp32.onnx" `
  --exporter torch_onnx_legacy_v1 --replace

& "$Repo\.stage8-envs\redimnet2\Scripts\python.exe" -m app.h2_portability parity `
  --component redimnet2_b2_speaker_embedding `
  --onnx-path "$Out\redimnet2_b2_fp32.onnx" `
  --output-dir "$Out\parity"

& "$Repo\.stage8-envs\credential-diarization\Scripts\python.exe" -m app.h2_portability parity `
  --component pyannote_segmentation_3_0 `
  --onnx-path "$Out\pyannote_segmentation_3_0_fp32.onnx" `
  --output-dir "$Out\parity"

& "$Repo\.stage8-envs\redimnet2\Scripts\python.exe" -m app.h2_portability e2e-hook `
  --report "$Out\parity\redimnet2_b2_speaker_embedding.parity.json" `
  --report "$Out\parity\pyannote_segmentation_3_0.parity.json" `
  --output "$Out\parity\h2_e2e_parity_hook.json"
```

Freeze the full-pipeline comparison before running a fresh pair. The example
assumes the bounded enrollment command has created
`$E2E\enrollment\protected_store`.

```powershell
$CorePy = Join-Path $Repo '.venv\Scripts\python.exe'
$E2E = Join-Path $Tool 'JustPeachyResults\h2_product_program\e2e_manual'
$Audio = Join-Path $Tool 'artifacts\realtime_test_audio\aew_rxr_eey_arctic_a0301_concat.wav'

& $CorePy -m app.full_pipeline enrollment-smoke `
  --backend redimnet2_b2_speaker_embedding --input $Audio `
  --output-root "$E2E\enrollment"

& $CorePy -m app.h2_portability e2e-freeze `
  --output "$E2E\protocol_freeze.json"

& $CorePy -m app.h2_portability e2e-run `
  --input $Audio --duration-sec 10 `
  --enrollment-root "$E2E\enrollment\protected_store" `
  --output-root "$E2E\case_enrolled" `
  --freeze-receipt "$E2E\protocol_freeze.json" `
  --redim-onnx "$Out\redimnet2_b2_fp32.onnx" `
  --redim-sha256 5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609 `
  --segmentation-onnx "$Out\pyannote_segmentation_3_0_fp32.onnx" `
  --segmentation-sha256 b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a
```

Run the portable profile directly through the common factory file path:

```powershell
& $CorePy -m app.h2_portability runtime-file `
  --input $Audio --duration-sec 10 `
  --output-root "$E2E\portable_file_demo" `
  --enrollment-root "$E2E\enrollment\protected_store" `
  --redim-onnx "$Out\redimnet2_b2_fp32.onnx" `
  --redim-sha256 5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609 `
  --segmentation-onnx "$Out\pyannote_segmentation_3_0_fp32.onnx" `
  --segmentation-sha256 b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a
```

To add a real local WAV to a parity run, repeat `--audio C:\path\case.wav`.
The samples after deterministic mono/resample/pad processing are hashed. The
WAV itself is not copied into the report.

The toolchain pins were installed only into the scoped environments:

```powershell
& "$Repo\.stage8-envs\redimnet2\Scripts\python.exe" -m pip install `
  onnx==1.22.0 onnxruntime==1.29.0 onnxscript==0.7.1
& "$Repo\.stage8-envs\credential-diarization\Scripts\python.exe" -m pip install `
  onnx==1.22.0 onnxruntime==1.29.0 onnxscript==0.7.1
```

## Controller-callable Python API

```python
from app.h2_portability.controller_adapter import execute_portability_job
from app.h2_portability.onnx_tooling import export_component
from app.h2_portability.parity import run_component_parity, build_e2e_parity_hook
from app.h2_portability.platform_support import arm64_diagnostic
from app.h2_portability.runtime import H2OnnxRuntimeBundle
```

The autonomous H2 controller calls:

```python
execute_portability_job(paths, job, state, jobs)
```

for `onnx_export`, `onnx_parity`, and `linux_portability`. It returns the
controller-standard `state`, `result_path`, `result_sha256`, and `error`
fields. Every successful result is bound to the final
`selected_runtime_snapshot`. Export graphs and detailed parity evidence are
stored under `paths.results_root/portability_artifacts`, outside the compact
ZIP; the small job receipt remains checksum-bound. The parity job requires both
component reports plus fresh enrolled and empty-enrollment full-pipeline
reports. The Linux job requires all of that evidence but completes only the
package-preparation scope and always reports `PORT_REQUIRES_WORK` until an
actual ARM64 Linux target passes the documented hardware gates.

Every completed portability receipt also references a checksum-complete
`artifact_manifest.json`. Dependency loading and `ExportPortable` revalidate
every listed file; deleting or changing a graph, manifest, component report,
full-pipeline report, enrollment receipt, or package file makes the scheduled
receipt invalid. The parity job declares only its two frozen fixture case IDs;
it does not claim to execute the ordinary 36-case development panel.

The controller adapter tries the preferred Dynamo exporter first. If that
exporter fails, the failure JSON and logs are retained before a separately
named `torch_onnx_legacy_v1` worker is invoked. No fallback occurs inside
`export_component` and no exporter change is silent.

`export_component` never changes exporter automatically. A caller must request
`torch_onnx_legacy_v1` explicitly after retaining a failed Dynamo report.
`run_component_parity` has no tolerance arguments: it uses and hashes the
predeclared code contract.

## Tests

```powershell
& "$Repo\.venv\Scripts\python.exe" -m pytest tests\h2_portability -q
```

Model-free tests cover contracts, platform classification, no-effect XVF,
asset validation, deterministic case manifests, cluster-permutation-aware
semantic comparison, forbidden text/boundary drift, and the E2E gate. Actual
model export/parity is the bounded evidence run above, not part of ordinary
unit tests.

## ARM64

See `deployment/h2_arm64/README.md`. The current candidate classification is
`PORT_REQUIRES_WORK`: the common factory and headless service launch now
consume the explicit ONNX profile, but the exact Raspberry Pi must still pass
wheel, audio, ARM64 numerical, resource, restart, GUI, and sustained-streaming
validation. The two-GiB allocation is a design budget, not a measurement.
