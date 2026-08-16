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

## Additive Libri+Giga Sherpa dry-plan

The separate `sherpa_onnx_libri_giga_zipformer_2023_06_21` component uses the existing
`.stage8-envs\onnx` interpreter, local hash-pinned assets, greedy search, two CPU threads,
and the non-streaming segment contract used by Original Sherpa. Its only campaign is
`campaign_edge_lg_shgiga_v1`; it is opt-in and has 32 scenarios.

From Anaconda Prompt or PowerShell at the repository root, the setup input is:

```powershell
.\.stage8-envs\onnx\Scripts\python.exe scripts\bootstrap_models.py --cache-root models\cache --sherpa-libri-giga
```

This reads the official cached/downloaded Sherpa archive, verifies its SHA-256, and
writes the extracted model beneath `models\cache\sherpa_onnx\asr`. Model binaries remain
ignored by Git. To perform only a dry plan, with no inference or campaign state:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan -CampaignId campaign_edge_lg_shgiga_v1
```

The input is the frozen catalog in
`Software Validation from Datasets\Evaluation Tool\benchmarks\edge_research`; output is
a console line reporting exactly 32 scenarios. Qualification evidence is written to
`runs\edge_backend_qualification\onnx-libri-giga.json`. See the dedicated model runbook
in `docs\automated_evaluation\sherpa_libri_giga_zipformer_2023_06_21.md`.
