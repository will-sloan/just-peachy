# Edge research PowerShell controls

These scripts prepare isolated CPU environments, verify the pinned edge backends, and
operate deterministic campaigns without requiring manual environment activation.

Open Anaconda Prompt or PowerShell at the repository root and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare_edge_research.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify_edge_research.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Run
```

`prepare` installs the `edge-cpu`, `moonshine-edge`, and `onnx` pinned profiles and
downloads only explicitly approved assets. `verify` checks assets, packages, catalogs,
FFmpeg, real one-item inference, and Stage 10 adapter composition. `Plan` performs a
global dry-plan and never runs inference. `Run` materializes and executes only the three
default campaigns sequentially. Use `-CampaignId <id>` for one explicit job or
`-IncludeOptional` only after reviewing the large/combinatory counts.

Inputs are frozen manifests and scenario catalogs under the Evaluation Tool. Outputs are
campaign folders under `Software Validation from Datasets\Evaluation Tool\automated_runs`.
Use `-Action Status`, `-Action Stop`, and `-Action Resume` for safe operation after an
interruption or reboot. Successful scenarios are validated and retained.

## Frozen large five-ASR dry-plan

The opt-in five-model large study consists of 32 scenarios per campaign on the shared
frozen large manifest. It compares the original offline-contract `sherpa_onnx`,
`whisper_small`, `whisper_base`, `moonshine_streaming_medium`, and
`moonshine_streaming_small`. `sherpa_onnx` runs in the isolated `onnx` profile;
Whisper Small/Base run in `core-cpu`; Moonshine runs in `moonshine-edge`.

From Anaconda Prompt or PowerShell at the repository root, use the following input to
validate and dry-plan only those immutable catalogs. It prints five 32-scenario plans
and starts no inference or campaign state:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan -CampaignId campaign_edge_lg_shorig_v1,campaign_edge_lg_wsmall_v1,campaign_edge_lg_wbase_v1,campaign_edge_lg_mmed_v1,campaign_edge_lg_msmall_v1
```

The planned catalog inputs and their immutable SHA-256 values are recorded in
`Software Validation from Datasets\Evaluation Tool\benchmarks\edge_research\edge_research_queue.json`.
Only use a later, separately approved `-Action Run` with one explicit campaign ID; never
start these five long campaigns together.
