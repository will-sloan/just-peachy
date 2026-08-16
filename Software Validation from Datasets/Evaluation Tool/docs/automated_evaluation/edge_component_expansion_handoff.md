# Edge Component Expansion Handoff

Copy this document into a future ChatGPT/Codex conversation together with the current
`git status` and `git rev-parse HEAD` output.

## Current Git state

- Branch: `codex/edge-component-expansion`.
- Accepted baseline commit: `b78df94cf1b8c4c9a1ea684a0a64b7bd37020838`.
- Final implementation commit: use `git rev-parse HEAD` after handoff; the exact final
  commit is also reported in the completing Codex response.
- Long research campaigns were not started. Existing campaign roots and results were
  not modified. `Resumes/` remains local and ignored.

## What existed before

The repository already had frozen benchmark manifests, controlled/native augmentation
rules, deterministic scenarios, restart-safe campaign execution, checksummed artifacts,
resource telemetry, two-worker exchange, core and extended component screening, Stage 10
speaker protocols, Stage 11 diarization contracts, and Stage 12 analysis. Whisper Base
remains the reference ASR. Dining and Restaurant are the only executable exact RIRs;
Bedroom remains unresolved without substitution.

## What was added

- Native Moonshine English Tiny/Small/Medium streaming adapters and local assets.
- A distinct Sherpa-ONNX streaming Zipformer English 20M INT8 adapter and asset.
- FSMN-VAD in a NumPy-1.26-isolated environment.
- CAM++ and ERes2Net 512-dimensional speaker embeddings and Stage 10 policy support.
- Deterministic streaming replay, partial/final diagnostics, stability/churn/latency/RTF
  metrics, a v3 artifact contract, and an additive streaming metric registry.
- Three pinned profiles: `moonshine-edge`, `onnx`, and `edge-cpu`.
- Thirteen environment-homogeneous ASR campaign catalogs, two union research catalogs,
  eight opt-in large paths, and Stage 10 small/standard/large plans.
- A separate LibriSpeech+GigaSpeech Sherpa-ONNX 2023-06-21 component and opt-in
  32-scenario large ASR-isolation campaign, without changing historical catalogs.
- `prepare_edge_research.ps1`, `verify_edge_research.ps1`, and
  `run_edge_research.ps1` with global plan-only preflight and sequential execution.
- This handoff and `edge_research_quick_start.md`.

No source component YAML is modified at runtime. Model downloads are explicit prepare
actions; inference always has downloads disabled.

## Component table

| Component ID | Family | Profile | Code/model licence | Commercial disposition | Installed size | Parameters | CPU/GPU | Streaming | Status/evidence |
|---|---|---|---|---|---:|---:|---|---|---|
| `moonshine_streaming_tiny` | ASR | `moonshine-edge` | MIT / MIT | permissive | 51,441,771 B | 34M | CPU qualified; GPU unqualified | native | qualified; `runs/edge_backend_qualification/moonshine-edge.json` |
| `moonshine_streaming_small` | ASR | `moonshine-edge` | MIT / MIT | permissive | 165,489,086 B | 123M | CPU qualified; GPU unqualified | native | qualified; same evidence |
| `moonshine_streaming_medium` | ASR | `moonshine-edge` | MIT / MIT | permissive | 304,690,919 B | 245M | CPU qualified; GPU unqualified | native | qualified; same evidence |
| `sherpa_onnx_streaming_zipformer_20m_int8` | ASR | `onnx` | Apache-2.0 / Apache-2.0 | permissive | 136,398,588 B | 20M | CPU qualified; GPU not used | native | qualified; `runs/edge_backend_qualification/onnx-edge.json` |
| `sherpa_onnx_libri_giga_zipformer_2023_06_21` | ASR | `onnx` | Apache-2.0 weights/runtime | model license permissive; GigaSpeech provenance review required | 546,279,902 B cached tree; 190,180,941 B active | approximately 70,369,391 | CPU qualified | upstream native; campaign segment contract | qualified; `runs/edge_backend_qualification/onnx-libri-giga.json` |
| `fsmn_vad` | VAD | `edge-cpu` | MIT runtime / Apache-2.0 model | permissive | 515,999 B | not published locally | CPU qualified | incremental backend | qualified; `runs/edge_backend_qualification/edge-cpu.json` |
| `campplus_speaker_embedding` | embedding | `onnx` | Apache-2.0 / Apache-2.0 | permissive | 29,596,978 B | 7.18M | CPU qualified | no | qualified; `runs/edge_backend_qualification/onnx-edge.json`; Stage 10 `runs/edge_speaker_protocol_smoke/real_smoke_matrix.json` |
| `eres2net_base_speaker_embedding` | embedding | `onnx` | Apache-2.0 / Apache-2.0 | permissive | 39,593,761 B | 4.6M | CPU qualified | no | qualified; same evidence |

Exact asset hashes:

| Asset | SHA-256 scope | SHA-256 |
|---|---|---|
| Moonshine Tiny | installed tree | `285467a3d614f5bfdc98660ff40a0b95ba005dac26f8ef4b9046c44a9d43911c` |
| Moonshine Small | installed tree | `56ab2918138d593ef6caae027e7987c64023893bcde2409e7dc3b6907e9e811c` |
| Moonshine Medium | installed tree | `d697b820001e512f82cd0b6b476ae5bbc551250ea5bf73b8ceb60039b167bc3a` |
| Sherpa20 INT8 | installed tree | `f8edd2bfe4ba76b9fdac18f09740bb3dc4eb9c87acc3ca3d6c604e9b26bb36d5` |
| Sherpa Libri+Giga 2023-06-21 | installed tree | `8ad24aa63b28ffb15a5b91461e4d05b19e3237c3f5ca7a6d3557d0fac0a9dfdf` |
| CAM++ | installed file | `357a834f702b80161e5b981182c038e18553c1f2ca752ed6cec2052365d4129b` |
| ERes2Net Base | installed file | `1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b` |
| FSMN-VAD | installed tree | `42a97051d20b99486fbc4f583316eeba7d4f0ea499fee664dc49068861a08e42` |

## Scenario and campaign table

| Catalog/campaign | Purpose | Scenarios | Profile | Default |
|---|---|---:|---|---|
| `campaign_edge_screen_v1` | Whisper Base control vs FSMN observe/chunk | 36 | `edge-cpu` | yes |
| `campaign_edge_stream_moon_v1` | Moonshine Tiny/Small/Medium native streaming | 36 | `moonshine-edge` | yes |
| `campaign_edge_stream_onnx_v1` | Sherpa20 native streaming | 12 | `onnx` | yes |
| `campaign_edge_combo_moon_v1` | bounded Moonshine x VAD/segmentation | 216 | `moonshine-edge` | no |
| `campaign_edge_combo_onnx_v1` | bounded Sherpa20 x VAD/segmentation | 72 | `onnx` | no |
| `campaign_edge_lg_mtiny_v1` | large robustness | 32 | `moonshine-edge` | no |
| `campaign_edge_lg_msmall_v1` | large robustness | 32 | `moonshine-edge` | no |
| `campaign_edge_lg_mmed_v1` | large robustness | 32 | `moonshine-edge` | no |
| `campaign_edge_lg_sh20_v1` | large robustness | 32 | `onnx` | no |
| `campaign_edge_lg_wbase_v1` | large reference | 32 | `core-cpu` | no |
| `campaign_edge_lg_shorig_v1` | original Sherpa-ONNX ASR isolation | 32 | `onnx` | no |
| `campaign_edge_lg_wsmall_v1` | Whisper Small ASR isolation | 32 | `core-cpu` | no |
| `campaign_edge_lg_shgiga_v1` | Sherpa Libri+Giga ASR isolation | 32 | `onnx` | no |

The thirteen executable catalogs contain 628 scenario rows in total; the default queue is 84.
The union catalogs are analysis/design aids and are not executable as one process because
their environment profiles differ.

`campaign_edge_lg_shorig_v1` preserves the existing `sherpa_onnx` offline-segment adapter
contract and its `sherpa-onnx-streaming-zipformer-en-2023-06-26` checkpoint. It is distinct
from the native-stateful `sherpa_onnx_streaming_zipformer_20m_int8` campaign.
`campaign_edge_lg_wsmall_v1` uses the existing local `whisper_small` / OpenAI Whisper
`small.pt` checkpoint. The additive Libri+Giga catalog and the prior two additions use
the exact no-op ASR-isolation components and frozen 8,258-row large manifest used by the
existing large catalogs. The LibriSpeech evaluation overlap is explicitly recorded.

Stage 10 plans are `campaign_spk10_edge_sm_v1` (63 clean items/backend),
`campaign_spk10_edge_std_v1` (240), and `campaign_spk10_edge_lg_v1` (510). They are
disabled by default. Existing enrollment/calibration/evaluation split identities remain
unchanged. Degraded probes still require the approved augmentation execution path.

## Exact operator commands

```powershell
# Prepare
powershell -ExecutionPolicy Bypass -File scripts\prepare_edge_research.ps1

# Verify, including real bounded smokes
powershell -ExecutionPolicy Bypass -File scripts\verify_edge_research.ps1

# Dry-plan defaults; no inference
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan

# Recommended first one-scenario run
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Run -CampaignId campaign_edge_screen_v1 -MaxScenarios 1

# Status / stop / resume
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Status -CampaignId campaign_edge_screen_v1
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Stop -CampaignId campaign_edge_screen_v1
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Resume -CampaignId campaign_edge_screen_v1

# Analyze only after completion
Set-Location 'Software Validation from Datasets\Evaluation Tool'
..\..\.venv\Scripts\python.exe run_evaluation.py analysis run --campaign-root automated_runs\campaign_edge_screen_v1
```

## What was actually tested

- Profile-specific repeated real qualification passed for the seven prior additions and
  the additive Libri+Giga Sherpa backend.
- Every streaming ASR consumed deterministic 100 ms chunks with backend state retained,
  emitted a final transcript, and produced `streaming-diagnostics.v1` without downloads.
- CAM++ and ERes2Net produced finite, normalized, repeatable 512-dimensional vectors.
- Stage 10 selected-backend smoke passed 8/8 items for each backend, preserved `Unknown`,
  and kept calibration/evaluation separate.
- All 13 catalogs validate; all 628 scenario identities validate.
- Complete dry-plan passed for all 13 campaigns. The default PowerShell plan passed at
  exact counts 36 + 36 + 12.
- Source preflight checked 8,663 frozen manifest rows with zero missing audio.
- Focused automated tests and final static checks are recorded in the completing Codex
  response because that response is produced after this file is finalized.

## What was not run

No small, standard, large, combination, multi-day, or release research campaign was
executed. No GPU concurrency test was run. No Raspberry Pi benchmark was inferred.

## Blocked or deferred

- TitaNet remains optional and was not added; it is nonblocking.
- No ambiguous commercial licence was accepted. ERes2Net and FSMN were integrated only
  after exact Apache-2.0 model evidence was recorded.
- Full Stage 10 degraded-probe execution remains on the approved campaign augmentation
  path; direct extraction continues to reject degraded rows.
- Bedroom RIR remains unresolved and excluded without replacement.
- Existing optional credential/platform backends and Stage 11 diarization remain governed
  by their existing qualification gates.
- Windows workstation results must not be reported as Raspberry Pi results.

## Next recommended experiment

Run exactly one scenario from `campaign_edge_screen_v1`, validate its predictions,
telemetry, checksums, and report, then resume the remaining 35 scenarios. Analyze that
FSMN/Whisper Base isolation campaign before starting either streaming campaign. Only
after the small screens should one of the 216/72 targeted combination catalogs advance.
