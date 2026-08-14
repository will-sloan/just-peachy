# Edge research planner

This additive package resolves already-registered components into deterministic,
environment-isolated scenario catalogs. It does not run inference or download models.

From an Anaconda Prompt or PowerShell opened at the repository root:

```powershell
..\..\.venv\Scripts\python.exe -m app.edge_research.cli plan
..\..\.venv\Scripts\python.exe -m app.edge_research.cli verify
```

Run those commands from `Software Validation from Datasets\Evaluation Tool`, or use
the repository-level PowerShell wrappers documented in
`docs/automated_evaluation/edge_research_quick_start.md`.

Inputs are the frozen `benchmarks/v1` manifests, component/model registries, existing
inference YAML fragments, approved condition sets, and Stage 10 manifests. Outputs are
written under `benchmarks/edge_research`: the plan, queue, per-environment JSONL scenario
catalogs, hashes, and Stage 10 execution-plan metadata. Source audio is never copied.

## Frozen large five-ASR study

The opt-in large ASR-isolation catalog set uses the frozen large manifest
`manifest_bc207e61b820` (`BC207E61B82052F06CCB9FFFE038B6DFE7B1C65C21843D08905946114238DE88`,
8,258 rows). Every catalog has 32 scenarios with `no_op_vad`, `no_op_segmentation`,
`no_op_speaker_embedding`, `no_op_speaker_matching`, and `no_op_diarization`.

| Campaign | ASR component | Environment | Native streaming diagnostics |
|---|---|---|---|
| `campaign_edge_lg_shorig_v1` | `sherpa_onnx` | `onnx` | no; the existing offline-segment adapter contract is preserved |
| `campaign_edge_lg_wsmall_v1` | `whisper_small` | `core-cpu` | no |
| `campaign_edge_lg_wbase_v1` | `whisper_base` | `core-cpu` | no |
| `campaign_edge_lg_mmed_v1` | `moonshine_streaming_medium` | `moonshine-edge` | yes |
| `campaign_edge_lg_msmall_v1` | `moonshine_streaming_small` | `moonshine-edge` | yes |

`sherpa_onnx` is the prior `sherpa-onnx-streaming-zipformer-en-2023-06-26` checkpoint
behind `SherpaOnnxASRAdapter`; it is distinct from
`sherpa_onnx_streaming_zipformer_20m_int8`. `whisper_small` is the local OpenAI Whisper
`small.pt` checkpoint. All model downloads remain disabled during planning and inference.

From an Anaconda Prompt or PowerShell at the repository root, regenerate and validate
the frozen definitions, then dry-plan only the five selected campaigns:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan -CampaignId campaign_edge_lg_shorig_v1,campaign_edge_lg_wsmall_v1,campaign_edge_lg_wbase_v1,campaign_edge_lg_mmed_v1,campaign_edge_lg_msmall_v1
```

This command reads frozen manifests/catalogs and writes no campaign artifacts; its output
is one 32-scenario dry-plan per campaign. Do not use `-Action Run` until an operator has
reviewed the frozen catalog identities and the planned queue.
