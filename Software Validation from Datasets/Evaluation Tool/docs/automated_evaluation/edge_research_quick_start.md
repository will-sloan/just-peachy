# Edge Research Quick Start

## What this adds

Just-Peachy is a reproducible laboratory for comparing speech pipelines on fixed audio.
This extension adds three Moonshine English streaming ASRs, a distinct Sherpa-ONNX
20M INT8 streaming ASR, FSMN-VAD, CAM++, and ERes2Net. It preserves the existing
dataset loaders, augmentation, scoring, plots, reports, restart safety, and immutable
scenario hashes. It does not make Raspberry Pi performance claims and it does not
enable parallel model jobs.

The first-time path is: **prepare -> verify -> plan -> run one scenario -> resume**.
The first three steps run no campaign inference.

## Vocabulary in plain English

- A **dataset** is a source collection of audio and reference metadata.
- A **benchmark manifest** is the frozen, versioned list of source utterances selected
  from those datasets. The same manifest is reused for every comparable pipeline.
- A **condition** is clean, approved noise, an exact approved RIR, or native audio.
  Native robustness audio is never synthetically augmented.
- A **component** is one VAD, segmenter, ASR, embedding model, matcher, or diarizer.
- A **pipeline** is a compatible composition of components and runtime settings.
- A **scenario** is one immutable benchmark slice, condition, pipeline, model identity,
  seed, and runtime policy. Its global ID is derived from canonical content.
- A **scenario catalog** is a deterministic JSONL list of scenarios.
- A **campaign** is the restart-safe execution state and artifacts for one catalog.
- **Qualification** proves that a pinned backend loads local assets and emits a valid
  real output. It is a contract smoke, not evidence that the model is scientifically best.

Environments are isolated because Moonshine bundles a native ONNX Runtime, Sherpa uses
a newer ONNX Runtime API, and FunASR/FSMN requires NumPy 1.26. Loading those stacks in
one Python process is unsafe on Windows. The wrapper chooses the correct interpreter;
you do not activate environments manually.

## Stages

- Stage 9 screens one component family at a time and then targeted interactions.
- Stage 10 handles backend-bound enrollment, verification, identification, and Unknown.
- Stage 11 handles diarization only when RTTM/timebase references are compatible.
- Stage 12 validates completed results and creates comparisons, plots, and reports.
- This edge extension adds deterministic native streaming replay, partial/final update
  diagnostics, isolated edge profiles, bounded ASR/VAD catalogs, and opt-in large paths.

New target-domain audio can be added later by creating a new versioned benchmark
manifest and new scenarios. Never edit a frozen manifest or reuse an old scenario ID.

## 1. Prepare once

Open Anaconda Prompt or PowerShell at the repository root:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
powershell -ExecutionPolicy Bypass -File scripts\prepare_edge_research.ps1
```

This installs or refreshes `edge-cpu`, `moonshine-edge`, and `onnx`, explicitly acquires
the approved pinned assets, and checks package consistency. It does not create or run a
campaign. Use `-Recreate` only when you intentionally want fresh isolated environments.

## 2. Verify before research

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_edge_research.ps1
```

This checks FFmpeg, all three interpreters, packages, model hashes, frozen source audio,
catalogs, exact scenario counts, and real bounded backend smokes. It also proves CAM++
and ERes2Net can pass the backend-specific Stage 10 contract. Secret values are never
written, and no implicit model download is allowed. `-SkipSmoke` is available only for
a repeat check after the real smoke evidence already exists.

## 3. Dry-plan the default queue

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan
```

Expected output is exactly:

- `campaign_edge_screen_v1`: 36 scenarios (`edge-cpu`);
- `campaign_edge_stream_moon_v1`: 36 scenarios (`moonshine-edge`);
- `campaign_edge_stream_onnx_v1`: 12 scenarios (`onnx`);
- default total: 84 scenarios.

Every selected job must pass global preflight before any one of them may run.

## 4. Recommended first real run

Run only one FSMN isolation scenario first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 `
  -Action Run `
  -CampaignId campaign_edge_screen_v1 `
  -MaxScenarios 1
```

Inspect status, then resume the same immutable campaign:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 `
  -Action Status `
  -CampaignId campaign_edge_screen_v1

powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 `
  -Action Resume `
  -CampaignId campaign_edge_screen_v1
```

After that passes, start the two streaming screens one at a time:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Run -CampaignId campaign_edge_stream_moon_v1
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Run -CampaignId campaign_edge_stream_onnx_v1
```

`-Action Run` without `-CampaignId` executes only the three default campaigns,
sequentially. Do not add `-IncludeOptional` until the default screens are analyzed.

## Stop and restart safely

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Stop -CampaignId campaign_edge_screen_v1
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Resume -CampaignId campaign_edge_screen_v1
```

After a reboot, rerun the same Resume command. Do not delete the campaign folder or
database. Valid successes are skipped; incomplete or corrupt work remains visible.

## Optional catalogs

These are frozen and dry-plan successfully but are disabled by default:

| Campaign | Scenarios | Purpose |
|---|---:|---|
| `campaign_edge_combo_moon_v1` | 216 | Three Moonshine ASRs x Energy/Silero/WebRTC observe/chunk strategies |
| `campaign_edge_combo_onnx_v1` | 72 | Sherpa20 x Energy/Silero/Sherpa-VAD observe/chunk strategies |
| `campaign_edge_lg_mtiny_v1` | 32 | Moonshine Tiny large controlled/native robustness |
| `campaign_edge_lg_msmall_v1` | 32 | Moonshine Small large controlled/native robustness |
| `campaign_edge_lg_mmed_v1` | 32 | Moonshine Medium large controlled/native robustness |
| `campaign_edge_lg_sh20_v1` | 32 | Sherpa20 large controlled/native robustness |
| `campaign_edge_lg_wbase_v1` | 32 | Whisper Base large reference |
| `campaign_edge_lg_shorig_v1` | 32 | Original Sherpa-ONNX offline-contract large ASR isolation (`onnx`) |
| `campaign_edge_lg_wsmall_v1` | 32 | Whisper Small large ASR isolation (`core-cpu`) |

Select one explicitly, for example:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan -CampaignId campaign_edge_combo_moon_v1
```

For the frozen five-ASR large study, plan only—do not run—these exact campaigns:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan -CampaignId campaign_edge_lg_shorig_v1,campaign_edge_lg_wsmall_v1,campaign_edge_lg_wbase_v1,campaign_edge_lg_mmed_v1,campaign_edge_lg_msmall_v1
```

All five use the same 8,258-row large manifest and 32-scenario ASR-isolation design.
Original `sherpa_onnx` is deliberately non-native-streaming in this catalog because its
existing adapter preserves the offline segment contract; it is not the distinct native
`sherpa_onnx_streaming_zipformer_20m_int8` component.

## Stage 10 plans

The queue records immutable small, standard, and large plans for CAM++ and ERes2Net:

- `campaign_spk10_edge_sm_v1`: 63 clean extraction items per backend;
- `campaign_spk10_edge_std_v1`: 240 per backend;
- `campaign_spk10_edge_lg_v1`: 510 per backend.

Direct Stage 10 extraction deliberately accepts clean source rows only. Degraded probes
must pass through the approved campaign augmentation path; the high-level ASR wrapper
does not pretend clean embeddings are degraded results. Run the small Stage 10 contract
smoke with:

```powershell
Set-Location 'Software Validation from Datasets\Evaluation Tool'
..\..\.stage8-envs\onnx\Scripts\python.exe run_evaluation.py speaker-protocol smoke `
  --backend campplus_speaker_embedding `
  --backend eres2net_base_speaker_embedding `
  --output-root runs\edge_speaker_protocol_smoke
```

## Results and analysis

Scenario artifacts live at:

```text
Software Validation from Datasets/Evaluation Tool/automated_runs/<campaign_id>/scenarios/<scenario_id>/
```

Each streaming scenario includes `predictions/streaming_diagnostics.jsonl` in addition
to standardized predictions, metrics, telemetry, logs, checksums, and reports. After a
campaign is complete:

```powershell
Set-Location 'Software Validation from Datasets\Evaluation Tool'
..\..\.venv\Scripts\python.exe run_evaluation.py analysis run `
  --campaign-root automated_runs\campaign_edge_screen_v1
```

The Stage 12 report is under `automated_runs/<campaign_id>/analysis/report/`. Hardware,
environment, chunk policy, and endpoint policy remain comparison covariates.

## Adding a second computer later

First clone the same commit and prepare the same profile on the second machine. Use the
existing `campaign assign`, `run-assignment`, `export-results`, `validate-transfer`, and
`merge-results` commands. Assign complete scenario IDs without overlap; never share a
live SQLite database over a network drive. See `two_machine_launch_runbook.md`.
