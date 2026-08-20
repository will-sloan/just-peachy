# Speaker Research Readiness Audit

Generated: 2026-08-20

Repository: `C:\Users\amiri\Documents\GitHub\just-peachy`

Branch: `codex/edge-component-expansion`
Audited implementation SHA: `38db58925d8fff46728caddfeb248faaeea142ec`

## Executive decision

**READY TO BEGIN SCIENTIFIC EXECUTION: YES**

The first authorized long stage is the ReDimNet2-B2 Stage 10 run described in Command Block 1. There are no installation, asset, credential, manifest, or smoke blockers to beginning that run.

The downstream stages are intentionally gated:

- ReDimNet Stage 10: `READY_WITH_WARNING`
- Six-model analysis: `READY_AFTER_UPSTREAM_ANALYSIS`
- Common Voice breadth: `READY_AFTER_FINALIST_SELECTION`
- Enrollment study: `READY_AFTER_BREADTH_FREEZE`
- Controlled diarization development: `READY_AFTER_FINALIST_SELECTION`
- Controlled diarization evaluation: `READY_AFTER_UPSTREAM_ANALYSIS`
- Pyannote credentials/models: `READY_NOW`

Important Stage 10 scope warning: the frozen Large manifest declares 960 protocol observations, while `speaker-protocol extract` emits the 510 unique clean-source embeddings used by each existing five-model run. All five historical results validate and each records `expected_items=960`, `observed_items=510`, and `successful_embeddings=510`. ReDimNet2 is ready for that same comparable 510-embedding scope. This audit does **not** claim that the direct CLI materializes the separate 450 degraded observations.

## Readiness matrix

| Stage | Tooling | Data/manifest | Environment | Smoke | Long run | Dependency | State |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ReDimNet Stage 10 | READY | READY | READY | PASS | READY with clean-source warning | none | `READY_WITH_WARNING` |
| Six-model speaker analysis | READY | ReDimNet result missing | n/a | n/a | WAIT | ReDimNet result + compact collection | `READY_AFTER_UPSTREAM_ANALYSIS` |
| Common Voice 60+ breadth | READY | READY | finalist-dependent | PASS | WAIT | six-model analysis selects top 2–3 | `READY_AFTER_FINALIST_SELECTION` |
| Enrollment/live-duration | READY | frozen implementation cohort is READY | READY | PASS | WAIT | breadth freezes primary/fallback | `READY_AFTER_BREADTH_FREEZE` |
| Controlled diarization development | READY | READY | five primary pipelines READY | PASS | WAIT | speaker shortlist + enrollment policy | `READY_AFTER_FINALIST_SELECTION` |
| Controlled diarization evaluation | READY | READY and locked | READY | PASS | WAIT | development analysis + frozen config | `READY_AFTER_UPSTREAM_ANALYSIS` |

## Scientific dependency graph

```text
READINESS VERIFIED
  -> REDIMNET2 STAGE 10 (comparable clean-source scope)
  -> COLLECT + ANALYZE ALL SIX SPEAKER MODELS
  -> FREEZE TOP 2-3 SPEAKER FINALISTS
  -> COMMON VOICE 60+ BREADTH
  -> BREADTH ANALYSIS
  -> FREEZE PRIMARY + FALLBACK SPEAKER BACKENDS
  -> ENROLLMENT / LIVE-DURATION STUDY
  -> ENROLLMENT ANALYSIS + PRODUCT POLICY FREEZE
  -> CONTROLLED DIARIZATION DEVELOPMENT
  -> DEVELOPMENT ANALYSIS + PIPELINE CONFIGURATION FREEZE
  -> CONTROLLED DIARIZATION EVALUATION
  -> DIARIZATION ANALYSIS

Future only:
  hybrid known/unknown attribution -> fine-tuning -> production integration
  -> XVF3800 integration -> target hardware
```

No command below automatically crosses an analysis/freeze gate.

## A. Sixth speaker model

The implementation exists and is runnable.

- Component: `redimnet2_b2_speaker_embedding`
- Family/checkpoint: PalabraAI ReDimNet2-B2 VoxCeleb2 large-margin, release `v1.0.0`
- Source revision: `cdc875670034dd7068013ca2ab21ec083a040ff8`
- Checkpoint: `C:\Users\amiri\Documents\GitHub\just-peachy\models\cache\redimnet2\b2-vox2-lm.pt`
- Checkpoint SHA-256: `0545B78B27D754C9B58EF7B12BC4CD0ED86ACD61EFDFF0F4A6BF4E50B0EEF77A`
- Environment: `redimnet2`
- Python: `C:\Users\amiri\Documents\GitHub\just-peachy\.stage8-envs\redimnet2\Scripts\python.exe`
- Embedding: 192 dimensions, 16 kHz, minimum 0.5 seconds
- Qualification: `qualified`; asset inventory verified
- Bounded load/extraction: PASS, including one exact Stage 10 Large enrollment item and an independent eight-item real-audio smoke
- License: MIT
- State: `READY_WITH_WARNING` because of the clean/degraded scope boundary described above

Implementation locations:

- Adapter: `app\inference_pipeline\speaker_embedding\redimnet2_adapter.py`
- Config: `configs\inference\components\speaker_embedding\redimnet2_b2.yaml`
- Registry/environment definitions: `configs\inference\component_registry.yaml`, `configs\models\model_asset_inventory.yaml`, `configs\inference\environment_profiles.yaml`
- Stage 10 entry point: `run_evaluation.py speaker-protocol`
- Tests: `tests\automated_evaluation\test_stage10_speaker_protocol.py`, `tests\inference_pipeline\test_modular_diarization.py`
- Documentation: `app\speaker_protocol\README.md`, `docs\automated_evaluation\speaker_protocol.md`

Minimal repair made during this audit: the Stage 10 smoke resolver now maps every non-core profile to `.stage8-envs\<profile>\Scripts\python.exe`, so `redimnet2` resolves. External result roots and paths containing spaces are now valid display/provenance paths. No scientific configuration changed.

## Speaker backend readiness matrix

| Component | Family/checkpoint | Profile / Python | Dim / rate | Qualification | Load / extract | Stage 10 | License |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `speechbrain_ecapa` | SpeechBrain ECAPA, `models\cache\speechbrain\spkrec-ecapa-voxceleb\embedding_model.ckpt`, SHA `0575CB012067A8D28FF7B9A15B13A13347D162E67531BA5184E6197435A126A2` | `core-cpu` / `.venv\Scripts\python.exe` | 192 / 16 kHz | qualified, asset verified | PASS / PASS | eligible | Apache-2.0 code; upstream checkpoint/local-cache redistribution review |
| `resemblyzer` | Resemblyzer d-vector, packaged `pretrained.pt`, SHA `39373BD76B4E021A4E8AC975DB346BCBA1D07EA297205A02C8A6841BA901134E` | `extended-local` / `.stage8-envs\extended-local\Scripts\python.exe` | 256 / 16 kHz | qualified, asset verified | PASS / PASS | eligible | Apache-2.0 code; packaged-weight provenance/redistribution review |
| `wespeaker` | ResNet221-LM `avg_model.pt`, SHA `47D762665D41658C27022622888A8C0FB3CCB21E3D1D06A9EE14B24D55B62EB5` | `wespeaker` / `.stage8-envs\wespeaker\Scripts\python.exe` | 256 / 16 kHz | qualified with warnings, asset verified | PASS / PASS | eligible with warnings | Apache-2.0 code; checkpoint CC BY 4.0 |
| `campplus_speaker_embedding` | CAM++ English VoxCeleb ONNX, SHA `357AB7F7C820CE741F540CA8AF02790EA89846E090EE1E0761E91EBF199F129B` | `onnx` / `.stage8-envs\onnx\Scripts\python.exe` | 512 / 16 kHz | qualified, asset verified | PASS / PASS | eligible | Apache-2.0 |
| `eres2net_base_speaker_embedding` | ERes2Net Base ONNX, SHA `1A331314E14A8BD1E23B78AEBFE433262C88BB20D5E006D239851601E8965E4B` | `onnx` / `.stage8-envs\onnx\Scripts\python.exe` | 512 / 16 kHz | qualified, asset verified | PASS / PASS | eligible | Apache-2.0 |
| `redimnet2_b2_speaker_embedding` | ReDimNet2-B2 Vox2-LM, SHA `0545B78B27D754C9B58EF7B12BC4CD0ED86ACD61EFDFF0F4A6BF4E50B0EEF77A` | `redimnet2` / `.stage8-envs\redimnet2\Scripts\python.exe` | 192 / 16 kHz | qualified, asset verified | PASS / PASS | eligible with scope warning | MIT |

`sherpa_onnx_speaker_embedding` uses the exact ERes2Net Base ONNX checkpoint and SHA above. It is an alias/control path, not a seventh independent speaker model.

## Environment verification

Every required interpreter exists, launches, imports its required packages, and sees its expected assets. No package was installed or upgraded.

| Profile | Python / pip | Important versions | Result |
| --- | --- | --- | --- |
| `core-cpu` | 3.12.7 / 26.2.1 | SpeechBrain 1.1.0; torch/torchaudio 2.11.0+cpu; NumPy 2.2.6; SoundFile 0.13.1 | PASS |
| `extended-local` | 3.12.7 / 24.2 | Resemblyzer 0.1.4; torch 2.11.0+cpu; NumPy 2.2.6; SoundFile 0.13.1 | PASS; deprecation warning only |
| `onnx` | 3.12.7 / 24.2 | sherpa-onnx 1.13.4; NumPy 2.2.6; SoundFile 0.13.1 | PASS |
| `wespeaker` | 3.12.7 / 24.2 | wespeaker 0.0.0; torch 2.11.0+cpu | PASS with recorded warnings |
| `redimnet2` | 3.12.7 / 24.2 | torch/torchaudio 2.11.0+cpu; NumPy 2.2.6; SciPy 1.15.3; scikit-learn 1.7.2 | PASS |
| `credential-diarization` | 3.12.7 / 24.2 | pyannote.audio 4.0.7; huggingface-hub 1.28.0; torch/torchaudio 2.11.0+cpu; torchcodec 0.16.0; sherpa-onnx 1.13.4 | PASS |

## Stage 10 Large integrity

- Manifest root: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\stage10\large`
- Protocol ID: `speaker_protocol_8e3830b956dc`
- Manifest SHA-256: `313721A16B47BF298B756B4D60F1F2B7848F8A150ACE28BF4537107FA504358D`
- Core observations: 960; enrollment 60; calibration 340; known evaluation 360; unknown evaluation 200
- Clean probes: 450; degraded probes: 450
- PASS: enrollment/probe source disjointness
- PASS: calibration/evaluation source disjointness
- PASS: Unknown speakers never enrolled
- PASS: calibration/evaluation Unknown speakers disjoint
- PASS: clean/degraded variants stay in one split
- Frozen Stage 10 files changed by this audit: none

## B. Six-model analysis collection

State: `READY_AFTER_UPSTREAM_ANALYSIS`. The only missing input is the comparable full ReDimNet result.

- Historical five results: `C:\Users\amiri\JustPeachyResults\speaker_protocol\large_all5_4a170baf5d2a`
- Historical package: `C:\Users\amiri\JustPeachyResearchSummaries\speaker_stage10_large_all5_4a170baf5d2a`
- Planned ReDim backend root: `C:\Users\amiri\JustPeachyResults\speaker_protocol\large_redimnet_38db58925d8f\redimnet2_b2_speaker_embedding`
- Planned six-model package: `C:\Users\amiri\JustPeachyResearchSummaries\speaker_stage10_large_all6_38db58925d8f`

The supplied collector copies compact JSON/CSV evidence and the protocol manifest/config. It records each `observations.npz` path, byte count, and SHA-256 in `RESULT_FILE_INVENTORY.csv`; it does not copy those arrays.

## C. Common Voice breadth

State: `READY_AFTER_FINALIST_SELECTION`.

- Protocol ID: `commonvoice_60plus_v1_27e72793b4c0`
- Frozen protocol: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_breadth\commonvoice_60plus_v1`
- Raw source: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\Common Voice\cv-corpus-26.0-2026-06-12`
- Metadata: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\Common Voice\cv-corpus-26.0-2026-06-12\prepared\en\metadata\original\validated.tsv`
- Audio: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\Common Voice\cv-corpus-26.0-2026-06-12\prepared\en\clips`
- Raw audio files present: 101,411
- Selected source manifest SHA-256: `368EAD1AB9D7F5E11F6EDD3B840DE7602DF1524220EE238BB068479048D6BBC5`
- Cohort: 272 known, 48 calibration Unknown, 93 evaluation Unknown, 413 total
- Selected clips: 11,685; 18.126725 hours; missing clips: 0; selected audio hashes verified: 11,685
- Same-speaker transcript reuse across splits: 0
- Global cross-contributor sentence reuse diagnostic: 516; recorded as a diagnostic, not a speaker/source leakage violation
- Model-independent selection: yes
- Hard-coded finalists: no; `-Backends` is a runtime list
- Wrapper actions: `Prepare` (audit + freeze/reuse), `Plan`, `Validate`, `Run`, `Status`, `Collect`
- Full finalist run started: no

Implementation:

- `app\speaker_breadth\commonvoice.py`, `collection.py`, `cli.py`
- `configs\automated_evaluation\speaker_breadth_commonvoice_60plus.v1.yaml`
- `scripts\run_speaker_breadth_commonvoice.ps1`
- `tests\automated_evaluation\test_speaker_breadth_commonvoice.py`
- `docs\automated_evaluation\speaker_breadth_commonvoice_60plus.md`

The collector was verified to produce `RUN_SUMMARY.csv`, `RUN_PROVENANCE.txt`, `RESULT_FILE_INVENTORY.csv`, `PROTOCOL_SUMMARY.json`, `SPEAKER_COHORT_SUMMARY.csv`, `METADATA_COVERAGE.csv`, and compact per-backend identity/extraction/protocol evidence.

## D. Enrollment/live-duration study

State: `READY_AFTER_BREADTH_FREEZE`.

- Protocol ID: `speaker_enrollment_duration_v1_8ee8b2aa42d1`
- Source protocol ID: `commonvoice_60plus_v1_27e72793b4c0`
- Protocol: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_enrollment\speaker_enrollment_duration_v1`
- Config: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\configs\automated_evaluation\speaker_enrollment_duration.v1.yaml`
- Config SHA-256: `D27B89FAB02F0A664DA4B49F64D21BFCB74875ACC72582E53F22A3DD7528A013`
- Frozen paired cohort: 221 known, 47 calibration Unknown, 92 evaluation Unknown
- Slices: 20,574 from 2,848 unique source clips
- Frozen configurations before decision-dependent frontier: 90; plan count including the decision-dependent frontier: 97
- Enrollment utterance counts: 1, 2, 3, 5
- Enrollment duration budgets: 1, 2, 5, 10, 20 seconds
- Probe durations: 0.5, 0.75, 1, 1.5, 2, 3, 5 seconds; optional 10 seconds is excluded because paired feasibility is zero
- Aggregation: `normalized_mean`, `duration_weighted_mean`, `multi_template_mean_score`
- Calibration: every result-affecting configuration calibrates on the calibration partition and applies only its own threshold to held-out evaluation
- Cache identity: backend/model/config/preprocessing/protocol/Git identity plus slice ID, parent audio SHA-256, crop bounds, and duration policy. Aggregation is intentionally excluded so identical source embeddings are reused.
- Analysis: all requested configuration, speaker, curve, aggregation, frontier, reliability, manifest, and Markdown outputs are implemented
- Full run started: no

Implementation:

- `app\speaker_enrollment\`
- `configs\automated_evaluation\speaker_enrollment_duration.v1.yaml`
- `scripts\run_speaker_enrollment_study.ps1`
- `tests\automated_evaluation\test_speaker_enrollment_duration.py`
- `docs\automated_evaluation\speaker_enrollment_duration_study.md`

## E. Controlled diarization benchmark

Development state: `READY_AFTER_FINALIST_SELECTION`. Evaluation state: `READY_AFTER_UPSTREAM_ANALYSIS` because development analysis and an explicit frozen configuration/hash must exist first.

- Benchmark ID: `controlled_diarization_v1_acd5e6e431d8`
- Benchmark: `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\stage11\controlled_diarization_v1`
- Protocol-summary SHA-256: `FE2E644A3349B42D42C797E887FC2D0ECC42CC969434556C7854582643C81774`
- Generated audio: `C:\Users\amiri\JustPeachyGeneratedData\controlled_diarization_v1`
- Default results: `C:\Users\amiri\JustPeachyResults\diarization\controlled_diarization_v1`
- Smoke/development/evaluation cases: 8 / 60 / 120
- Smoke/development/evaluation speakers: 12 / 60 / 120; development ∩ evaluation = empty
- Factors: 1/2/3/5 speakers; relaxed/standard/rapid cadence; none/backchannel/moderate overlap
- Source isolation: 3,528 unique mixture clips; 960 separately reserved enrollment clips; 0 reused clips
- Generated evidence: 188 WAVs, 10,914.8575625 seconds total
- Validation: every factor balance, audio, hash, interval/RTTM, recurrence, speaker-count, overlap, source-integrity, and split-isolation check passes
- Evaluation assets: locked; evaluation `Run` refuses to proceed without `-FrozenPipelineConfig`
- Oracle diagnostic: `oracle_turn_campplus_diagnostic` is `DIAGNOSTIC_DEVELOPMENT_ONLY`, never primary
- Full development/evaluation started: no

Implementation:

- `app\controlled_diarization\`
- `configs\automated_evaluation\controlled_diarization_benchmark.v1.yaml`
- `scripts\run_controlled_diarization.ps1`
- `tests\automated_evaluation\test_controlled_diarization_benchmark.py`
- `docs\automated_evaluation\controlled_diarization_benchmark.md`
- Existing native Stage 11: `app\diarization_evaluation\`, `configs\automated_evaluation\diarization_evaluation.v1.yaml`, `benchmarks\stage11\small|standard|large`, `tests\automated_evaluation\test_stage11_diarization.py`, `docs\automated_evaluation\stage_11_diarization.md`

### Executable pipeline identities

| Pipeline | Segmentation | Embedding | Clustering | Profile | Config SHA-256 | State |
| --- | --- | --- | --- | --- | --- | --- |
| `modular_energy_campplus` | `lightweight_energy_vad_windows` | `campplus_speaker_embedding` | `agglomerative_cosine_engineering_v1` | `onnx` | `b41e303d471c5ea07df875d2ca1f3e231a63a0e086458147e29efe4bc507b3a4` | `READY_NOW` |
| `modular_pyannote_campplus` | `pyannote_segmentation_3_0` | `campplus_speaker_embedding` | `agglomerative_cosine_engineering_v1` | `credential-diarization` | `868a62321521779885d424f9a2dfce3ca8fa26b55d2d9a2874cde90140a8a2a1` | `READY_NOW` |
| `sherpa_onnx_diarization` | `sherpa_onnx_backend_internal` | `sherpa_onnx_speaker_embedding` | `sherpa_onnx_backend_internal` | `onnx` | `0eb3ea6bbaaddff025e7a3445819587ef9d3921b3afcce344a4d36c4fa05e60f` | `READY_NOW` |
| `modular_energy_wespeaker` | `lightweight_energy_vad_windows` | `wespeaker_resnet221_lm` | `agglomerative_cosine_engineering_v1` | `wespeaker` | `3862c42df5b0539d13bbae8a0fa102d3e4da93475a1ef815b1d5de0284518db7` | `READY_WITH_WARNING` |
| `pyannote_community1` | internal | internal | internal | `credential-diarization` | `7271bd37d8da2f8ee492ef8f10f13d51494c06424bbc24996031526bb07c0158` | `READY_WITH_WARNING`: off-the-shelf default comparison only |
| `oracle_turn_campplus_diagnostic` | oracle placement turns | `campplus_speaker_embedding` | `agglomerative_cosine_engineering_v1` | `onnx` | `274803d2dbe77483d61dc74da983c78d3a3c17fcdf54721ef2bb49ca9a582e04` | `READY_NOW`, DIAGNOSTIC NOT PRIMARY |

`modular_pyannote_selected_embedding` is `IMPLEMENTATION_INCOMPLETE` by design until the speaker-finalist decision supplies an embedding and clustering configuration. It is not executable and is not counted above as a primary candidate.

## F. Pyannote credentials/models

State: `READY_NOW`.

- Hugging Face authentication exists; account access was checked without reading or printing token material.
- `pyannote/segmentation-3.0` access resolves at revision `e66f3d3b9eb9cd362c3a8b4a9b8bd6b91656feaf`.
- `pyannote/speaker-diarization-community-1` access resolves at revision `3533c8cf5ed1c0b18fbb7644677b0872d60d01ef`.
- Credential-profile qualification and bounded model loading pass.
- No credential or access-terms blocker remains on this machine.

## G. Result collection

- Stage 10: Command Blocks 1 and 2 build metadata-only packages. The historical five package is not reused because it copied embeddings.
- Breadth: native `Collect` produces all requested protocol/cohort/coverage and backend evidence.
- Enrollment: native `Collect` includes all available analysis tables/report and compact backend evidence; embedding caches stay external.
- Controlled diarization: native `Collect` was tested on smoke output. It copied 48 compact artifacts and recorded eight external generated-audio references. It does not copy WAVs.

## H. Scientific dependency gates

Every next stage has a known command, environment, manifest, output root, validation, collection package, and stop point. Tooling readiness does not authorize crossing a scientific analysis gate. In particular:

- Do not run breadth until six-model analysis selects finalists.
- Do not run enrollment until breadth freezes primary and fallback.
- Enrollment phases A–C stop for analysis before probe-duration/frontier decisions.
- Do not run controlled development until the speaker shortlist/enrollment policy is frozen.
- Do not run controlled evaluation until development is fully valid, analyzed, and frozen to a configuration file containing exact pipeline hashes.

## Verification evidence and repairs

Bounded evidence performed:

- Stage 10 Large manifest validation: PASS
- Six-backend real-audio smoke: 6/6 PASS, eight items/backend
- ReDimNet exact Large start: 1/1 PASS
- Breadth Prepare/reuse, full hash Validate, and Plan: PASS; no inference
- Enrollment Audit, Prepare/reuse, Validate, and Plan: PASS; no inference
- Enrollment synthetic contract smoke: 6/6 PASS; no model inference
- Controlled Audit, Prepare/reuse, full source-hash Validate, and development Plan: PASS; no scientific inference
- Controlled Sherpa one-case smoke: PASS; second invocation REUSE; Analyze and Collect PASS
- Existing native Stage 11 Sherpa smoke: PASS
- Pyannote access/model-load checks: PASS
- Focused automated tests: `99 passed in 116.90s`

Focused test command:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider `
  tests\automated_evaluation\test_stage10_speaker_protocol.py `
  tests\automated_evaluation\test_speaker_breadth_commonvoice.py `
  tests\automated_evaluation\test_speaker_enrollment_duration.py `
  tests\automated_evaluation\test_controlled_diarization_benchmark.py `
  tests\automated_evaluation\test_stage11_diarization.py `
  tests\inference_pipeline\test_modular_diarization.py `
  tests\inference_pipeline\test_speaker_embedding_interface.py `
  tests\inference_pipeline\test_diarization_interface.py
```

Repairs were limited to implementation integration:

1. Generic isolated environment resolution for ReDimNet Stage 10 smoke.
2. External-path handling in Stage 10 smoke and Common Voice provenance.
3. Pyannote tests aligned with the documented in-memory waveform contract.

No data, cohort, split, duration setting, scoring policy, threshold policy, frozen protocol, or historical result was changed.

## Exact paths

| Purpose | Absolute path |
| --- | --- |
| Repository | `C:\Users\amiri\Documents\GitHub\just-peachy` |
| Evaluation tool | `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool` |
| Stage 10 Large manifest root | `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\stage10\large` |
| Common Voice raw data | `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\Common Voice\cv-corpus-26.0-2026-06-12` |
| Breadth frozen protocol | `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_breadth\commonvoice_60plus_v1` |
| Enrollment config | `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\configs\automated_evaluation\speaker_enrollment_duration.v1.yaml` |
| Enrollment protocol | `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_enrollment\speaker_enrollment_duration_v1` |
| Controlled benchmark | `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\stage11\controlled_diarization_v1` |
| Generated controlled data | `C:\Users\amiri\JustPeachyGeneratedData\controlled_diarization_v1` |
| Historical Stage 10 five results | `C:\Users\amiri\JustPeachyResults\speaker_protocol\large_all5_4a170baf5d2a` |
| Planned ReDim result base | `C:\Users\amiri\JustPeachyResults\speaker_protocol\large_redimnet_38db58925d8f` |
| Planned all-six package | `C:\Users\amiri\JustPeachyResearchSummaries\speaker_stage10_large_all6_38db58925d8f` |
| Breadth result base | `C:\Users\amiri\JustPeachyResults\speaker_breadth\commonvoice_60plus_v1` |
| Breadth package | `C:\Users\amiri\JustPeachyResearchSummaries\speaker_breadth_commonvoice_60plus_commonvoice_60plus_v1_27e72793b4c0` |
| Enrollment result base | `C:\Users\amiri\JustPeachyResults\speaker_enrollment\speaker_enrollment_duration_v1_8ee8b2aa42d1` |
| Enrollment package | `C:\Users\amiri\JustPeachyResearchSummaries\speaker_enrollment_duration_speaker_enrollment_duration_v1_8ee8b2aa42d1` |
| Controlled default results | `C:\Users\amiri\JustPeachyResults\diarization\controlled_diarization_v1` |
| Controlled default analysis | `C:\Users\amiri\JustPeachyResults\diarization\controlled_diarization_v1\analysis` |
| Controlled packages | `C:\Users\amiri\JustPeachyResearchSummaries\controlled_diarization_v1_<git12>` or the explicit roots below |

## Command Block 1 — run the sixth speaker model

This is a long scientific run. Do not run it until intentionally starting ReDimNet Stage 10. It requires the exact audited implementation SHA and preserves invalid/partial output before retrying.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\amiri\Documents\GitHub\just-peachy"
$Tool = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
$ExpectedImplementationSha = "38db58925d8fff46728caddfeb248faaeea142ec"
$ManifestRoot = "$Tool\benchmarks\stage10\large"
$Component = "redimnet2_b2_speaker_embedding"
$ManagementPython = "$Repo\.venv\Scripts\python.exe"
$BackendPython = "$Repo\.stage8-envs\redimnet2\Scripts\python.exe"
$Launcher = "$Tool\run_evaluation.py"
$GitSha = (git -C $Repo rev-parse HEAD).Trim()
git -C $Repo cat-file -e "$ExpectedImplementationSha^{commit}"
if ($LASTEXITCODE -ne 0) { throw "Audited implementation commit is unavailable: $ExpectedImplementationSha" }
$ResearchDelta = @(git -C $Repo diff --name-only "$ExpectedImplementationSha..HEAD" -- "Software Validation from Datasets/Evaluation Tool/app" "Software Validation from Datasets/Evaluation Tool/configs" "Software Validation from Datasets/Evaluation Tool/benchmarks")
if ($ResearchDelta.Count -ne 0) { throw "Research implementation changed after the audit. Re-audit before running.`n$($ResearchDelta -join "`n")" }
if (-not (Test-Path -LiteralPath $BackendPython -PathType Leaf)) { throw "Missing ReDimNet Python: $BackendPython" }
$DirtyCode = @(git -C $Repo status --porcelain -- "Software Validation from Datasets/Evaluation Tool/app" "Software Validation from Datasets/Evaluation Tool/configs" "Software Validation from Datasets/Evaluation Tool/benchmarks")
if ($DirtyCode.Count -ne 0) { throw "Research code/config/manifest paths are dirty. Commit or review them before scientific execution.`n$($DirtyCode -join "`n")" }
$GitShort = $ExpectedImplementationSha.Substring(0, 12)
$RunBase = "$env:USERPROFILE\JustPeachyResults\speaker_protocol\large_redimnet_$GitShort"
$BackendRoot = Join-Path $RunBase $Component
$ExtractionRoot = Join-Path $BackendRoot "extraction"
$ResultRoot = Join-Path $BackendRoot "evaluation"
$CollectRoot = "$env:USERPROFILE\JustPeachyResearchSummaries\speaker_stage10_large_redimnet_$GitShort"

Push-Location $Tool
try {
  & $BackendPython -c "import torch, torchaudio, numpy, scipy, sklearn, soundfile; print('redimnet2 environment: PASS')"
  if ($LASTEXITCODE -ne 0) { throw "ReDimNet environment verification failed" }
  & $ManagementPython $Launcher speaker-protocol validate --manifest-root $ManifestRoot
  if ($LASTEXITCODE -ne 0) { throw "Stage 10 Large manifest validation failed" }

  $Reuse = $false
  if (Test-Path -LiteralPath $ResultRoot -PathType Container) {
    & $ManagementPython $Launcher speaker-protocol validate --result-root $ResultRoot *> $null
    $Reuse = ($LASTEXITCODE -eq 0)
  }
  if ($Reuse) {
    Write-Output "[REUSE] Valid ReDimNet result: $ResultRoot"
  }
  else {
    if (Test-Path -LiteralPath $BackendRoot) {
      $Quarantine = "$BackendRoot.partial-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
      Move-Item -LiteralPath $BackendRoot -Destination $Quarantine
      Write-Output "[PRESERVE PARTIAL] $Quarantine"
    }
    New-Item -ItemType Directory -Force -Path $BackendRoot | Out-Null
    & $BackendPython $Launcher speaker-protocol extract --manifest-root $ManifestRoot --component $Component --output-root $ExtractionRoot
    if ($LASTEXITCODE -ne 0) { throw "ReDimNet extraction failed" }
    & $ManagementPython $Launcher speaker-protocol evaluate --manifest-root $ManifestRoot --observation-bundle (Join-Path $ExtractionRoot "observations.npz") --backend-identity (Join-Path $ExtractionRoot "backend_identity.json") --output-root $ResultRoot
    if ($LASTEXITCODE -ne 0) { throw "ReDimNet evaluation failed" }
  }

  $ValidationText = (& $ManagementPython $Launcher speaker-protocol validate --result-root $ResultRoot 2>&1 | Out-String)
  if ($LASTEXITCODE -ne 0) { throw "ReDimNet result validation failed: $ValidationText" }
  $ValidationText | Set-Content -LiteralPath (Join-Path $BackendRoot "validation.json") -Encoding utf8

  if (Test-Path -LiteralPath $CollectRoot) {
    $OldCollect = "$CollectRoot.previous-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Move-Item -LiteralPath $CollectRoot -Destination $OldCollect
  }
  New-Item -ItemType Directory -Force -Path "$CollectRoot\protocol", "$CollectRoot\backend" | Out-Null
  Copy-Item -LiteralPath "$ManifestRoot\speaker_protocol_manifest.json" -Destination "$CollectRoot\protocol\speaker_protocol_manifest.json"
  Copy-Item -LiteralPath "$Tool\configs\automated_evaluation\speaker_protocol.v1.yaml" -Destination "$CollectRoot\protocol\speaker_protocol.v1.yaml"
  $Copies = @(
    @{ From = "$ExtractionRoot\backend_identity.json"; To = "$CollectRoot\backend\backend_identity.json" },
    @{ From = "$ExtractionRoot\extraction_summary.json"; To = "$CollectRoot\backend\extraction_summary.json" },
    @{ From = "$ResultRoot\protocol_run.json"; To = "$CollectRoot\backend\protocol_run.json" },
    @{ From = "$ResultRoot\metrics\summary.json"; To = "$CollectRoot\backend\metrics_summary.json" },
    @{ From = "$BackendRoot\validation.json"; To = "$CollectRoot\backend\validation.json" }
  )
  foreach ($Copy in $Copies) {
    if (-not (Test-Path -LiteralPath $Copy.From -PathType Leaf)) { throw "Missing required result: $($Copy.From)" }
    Copy-Item -LiteralPath $Copy.From -Destination $Copy.To
  }
  $Extraction = Get-Content -LiteralPath "$ExtractionRoot\extraction_summary.json" -Raw | ConvertFrom-Json
  $ProtocolRun = Get-Content -LiteralPath "$ResultRoot\protocol_run.json" -Raw | ConvertFrom-Json
  [pscustomobject]@{
    backend = $Component
    protocol_id = $ProtocolRun.protocol_id
    expected_items = $ProtocolRun.expected_items
    observed_items = $ProtocolRun.observed_items
    successful_embeddings = $ProtocolRun.successful_embeddings
    failed_items = $Extraction.failed_items
    validation = "PASS"
    git_sha = $GitSha
    result_root = $ResultRoot
  } | Export-Csv -LiteralPath "$CollectRoot\RUN_SUMMARY.csv" -NoTypeInformation -Encoding utf8
  @(
    "SCHEMA_VERSION=stage10-redimnet-collection.v1"
    "GIT_SHA=$GitSha"
    "PROTOCOL_ID=$($ProtocolRun.protocol_id)"
    "PROTOCOL_MANIFEST=$ManifestRoot\speaker_protocol_manifest.json"
    "BACKEND=$Component"
    "RESULT_ROOT=$ResultRoot"
    "OBSERVATIONS_COPIED=NO"
    "SCOPE=historical-five-comparable-clean-source-extraction"
  ) | Set-Content -LiteralPath "$CollectRoot\RUN_PROVENANCE.txt" -Encoding utf8
  $Inventory = @(Get-ChildItem -LiteralPath $CollectRoot -Recurse -File | Where-Object Name -ne "RESULT_FILE_INVENTORY.csv" | ForEach-Object {
    [pscustomobject]@{ area = "package"; path = $_.FullName; bytes = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash; copied = $true }
  })
  $ObservationPath = Join-Path $ExtractionRoot "observations.npz"
  $Inventory += [pscustomobject]@{ area = "external_observation_bundle"; path = $ObservationPath; bytes = (Get-Item -LiteralPath $ObservationPath).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ObservationPath).Hash; copied = $false }
  $Inventory | Export-Csv -LiteralPath "$CollectRoot\RESULT_FILE_INVENTORY.csv" -NoTypeInformation -Encoding utf8
  Write-Output "UPLOAD PACKAGE: $CollectRoot"
}
finally {
  Pop-Location
}
```

## Command Block 2 — collect all six speaker models

Run after Block 1 succeeds. This creates one compact metadata-only package.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\amiri\Documents\GitHub\just-peachy"
$Tool = "$Repo\Software Validation from Datasets\Evaluation Tool"
$ExpectedImplementationSha = "38db58925d8fff46728caddfeb248faaeea142ec"
$GitSha = (git -C $Repo rev-parse HEAD).Trim()
git -C $Repo cat-file -e "$ExpectedImplementationSha^{commit}"
if ($LASTEXITCODE -ne 0) { throw "Audited implementation commit is unavailable: $ExpectedImplementationSha" }
$ResearchDelta = @(git -C $Repo diff --name-only "$ExpectedImplementationSha..HEAD" -- "Software Validation from Datasets/Evaluation Tool/app" "Software Validation from Datasets/Evaluation Tool/configs" "Software Validation from Datasets/Evaluation Tool/benchmarks")
if ($ResearchDelta.Count -ne 0) { throw "Research implementation changed after the audit. Re-audit before collecting.`n$($ResearchDelta -join "`n")" }
$GitShort = $ExpectedImplementationSha.Substring(0, 12)
$Python = "$Repo\.venv\Scripts\python.exe"
$Launcher = "$Tool\run_evaluation.py"
$ManifestRoot = "$Tool\benchmarks\stage10\large"
$ExistingFiveBase = "$env:USERPROFILE\JustPeachyResults\speaker_protocol\large_all5_4a170baf5d2a"
$ReDimRoot = "$env:USERPROFILE\JustPeachyResults\speaker_protocol\large_redimnet_$GitShort\redimnet2_b2_speaker_embedding"
$CollectRoot = "$env:USERPROFILE\JustPeachyResearchSummaries\speaker_stage10_large_all6_$GitShort"
$Sources = [ordered]@{
  speechbrain_ecapa = "$ExistingFiveBase\speechbrain_ecapa"
  resemblyzer = "$ExistingFiveBase\resemblyzer"
  wespeaker = "$ExistingFiveBase\wespeaker"
  campplus_speaker_embedding = "$ExistingFiveBase\campplus_speaker_embedding"
  eres2net_base_speaker_embedding = "$ExistingFiveBase\eres2net_base_speaker_embedding"
  redimnet2_b2_speaker_embedding = $ReDimRoot
}
if (Test-Path -LiteralPath $CollectRoot) {
  Move-Item -LiteralPath $CollectRoot -Destination "$CollectRoot.previous-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
}
New-Item -ItemType Directory -Force -Path "$CollectRoot\protocol" | Out-Null
Copy-Item -LiteralPath "$ManifestRoot\speaker_protocol_manifest.json" -Destination "$CollectRoot\protocol\speaker_protocol_manifest.json"
Copy-Item -LiteralPath "$Tool\configs\automated_evaluation\speaker_protocol.v1.yaml" -Destination "$CollectRoot\protocol\speaker_protocol.v1.yaml"
$Rows = @()
$External = @()
Push-Location $Tool
try {
  foreach ($Entry in $Sources.GetEnumerator()) {
    $Backend = $Entry.Key
    $Source = $Entry.Value
    $Extraction = Join-Path $Source "extraction"
    $Evaluation = Join-Path $Source "evaluation"
    if (-not (Test-Path -LiteralPath $Evaluation -PathType Container)) { throw "Missing result for ${Backend}: $Evaluation" }
    $Validation = (& $Python $Launcher speaker-protocol validate --result-root $Evaluation 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "Invalid result for ${Backend}: $Validation" }
    $Destination = Join-Path "$CollectRoot\backends" $Backend
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $Files = @{
      "$Extraction\backend_identity.json" = "$Destination\backend_identity.json"
      "$Extraction\extraction_summary.json" = "$Destination\extraction_summary.json"
      "$Evaluation\protocol_run.json" = "$Destination\protocol_run.json"
      "$Evaluation\metrics\summary.json" = "$Destination\metrics_summary.json"
    }
    foreach ($Pair in $Files.GetEnumerator()) {
      if (-not (Test-Path -LiteralPath $Pair.Key -PathType Leaf)) { throw "Missing required file: $($Pair.Key)" }
      Copy-Item -LiteralPath $Pair.Key -Destination $Pair.Value
    }
    $Validation | Set-Content -LiteralPath "$Destination\validation.json" -Encoding utf8
    $ExtractSummary = Get-Content -LiteralPath "$Extraction\extraction_summary.json" -Raw | ConvertFrom-Json
    $ProtocolRun = Get-Content -LiteralPath "$Evaluation\protocol_run.json" -Raw | ConvertFrom-Json
    if ($ProtocolRun.protocol_id -ne "speaker_protocol_8e3830b956dc") { throw "Protocol mismatch for $Backend" }
    $Rows += [pscustomobject]@{
      backend = $Backend
      protocol_id = $ProtocolRun.protocol_id
      expected_items = $ProtocolRun.expected_items
      observed_items = $ProtocolRun.observed_items
      successful_embeddings = $ProtocolRun.successful_embeddings
      failed_items = $ExtractSummary.failed_items
      validation = "PASS"
      result_root = $Evaluation
    }
    $Observation = Join-Path $Extraction "observations.npz"
    $External += [pscustomobject]@{ area = "external_observation_bundle"; backend = $Backend; path = $Observation; bytes = (Get-Item -LiteralPath $Observation).Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Observation).Hash; copied = $false }
  }
}
finally {
  Pop-Location
}
$Rows | Export-Csv -LiteralPath "$CollectRoot\RUN_SUMMARY.csv" -NoTypeInformation -Encoding utf8
@(
  "SCHEMA_VERSION=stage10-six-model-collection.v1"
  "COLLECTION_GIT_SHA=$GitSha"
  "PROTOCOL_ID=speaker_protocol_8e3830b956dc"
  "HISTORICAL_FIVE_EXECUTION_SHA=4a170baf5d2a"
  "REDIMNET_EXECUTION_SHA=$GitSha"
  "HISTORICAL_FIVE_ROOT=$ExistingFiveBase"
  "REDIMNET_ROOT=$ReDimRoot"
  "OBSERVATIONS_COPIED=NO"
) | Set-Content -LiteralPath "$CollectRoot\RUN_PROVENANCE.txt" -Encoding utf8
$Inventory = @(Get-ChildItem -LiteralPath $CollectRoot -Recurse -File | Where-Object Name -ne "RESULT_FILE_INVENTORY.csv" | ForEach-Object {
  [pscustomobject]@{ area = "package"; backend = ""; path = $_.FullName; bytes = $_.Length; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash; copied = $true }
})
$Inventory += $External
$Inventory | Export-Csv -LiteralPath "$CollectRoot\RESULT_FILE_INVENTORY.csv" -NoTypeInformation -Encoding utf8
Write-Output "UPLOAD PACKAGE: $CollectRoot"
```

## Command Block 3 — Common Voice breadth

**DO NOT RUN UNTIL SIX-MODEL ANALYSIS SELECTS FINALISTS.** `Prepare` is the repository's combined source Audit + deterministic freeze/reuse action. There is no separate breadth `Analyze`; upload the collected package to ChatGPT for the analysis gate.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\amiri\Documents\GitHub\just-peachy"
$Tool = "$Repo\Software Validation from Datasets\Evaluation Tool"
$Wrapper = "$Tool\scripts\run_speaker_breadth_commonvoice.ps1"
$ProtocolRoot = "$Tool\benchmarks\speaker_breadth\commonvoice_60plus_v1"
$ResultBase = "$env:USERPROFILE\JustPeachyResults\speaker_breadth\commonvoice_60plus_v1"
$CollectRoot = "$env:USERPROFILE\JustPeachyResearchSummaries\speaker_breadth_commonvoice_60plus_commonvoice_60plus_v1_27e72793b4c0"
$Backends = @(
  "FINALIST_1",
  "FINALIST_2"
)
if ($Backends | Where-Object { $_ -like "FINALIST_*" }) { throw "Replace FINALIST_1/FINALIST_2 using the six-model analysis decision." }
& $Wrapper -Action Prepare -ProtocolRoot $ProtocolRoot
& $Wrapper -Action Validate -ProtocolRoot $ProtocolRoot
& $Wrapper -Action Plan -ProtocolRoot $ProtocolRoot -Backends $Backends
& $Wrapper -Action Run -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -Backends $Backends
& $Wrapper -Action Status -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -Backends $Backends
& $Wrapper -Action Collect -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -CollectRoot $CollectRoot -Backends $Backends
Write-Output "STOP HERE — UPLOAD FOR BREADTH ANALYSIS: $CollectRoot"
```

## Command Block 4 — enrollment study

**DO NOT RUN UNTIL SPEAKER-BREADTH ANALYSIS IS COMPLETE.** The default phase list deliberately runs only phases A–C. Analyze those results and select the reference enrollment configuration before running `ProbeDuration`; then make a separate decision before `JointFrontier`.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\amiri\Documents\GitHub\just-peachy"
$Tool = "$Repo\Software Validation from Datasets\Evaluation Tool"
$Wrapper = "$Tool\scripts\run_speaker_enrollment_study.ps1"
$SourceProtocolRoot = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_breadth\commonvoice_60plus_v1"
$ProtocolRoot = "$Tool\benchmarks\speaker_enrollment\speaker_enrollment_duration_v1"
$ResultBase = "$env:USERPROFILE\JustPeachyResults\speaker_enrollment"
$AnalysisRoot = "$ResultBase\speaker_enrollment_duration_v1_8ee8b2aa42d1\analysis"
$CollectRoot = "$env:USERPROFILE\JustPeachyResearchSummaries\speaker_enrollment_duration_speaker_enrollment_duration_v1_8ee8b2aa42d1"
$Backends = @(
  "PRIMARY_BACKEND",
  "FALLBACK_BACKEND"
)
$Phases = @("EnrollmentCount", "EnrollmentDuration", "Aggregation")
if ($Backends | Where-Object { $_ -in @("PRIMARY_BACKEND", "FALLBACK_BACKEND") }) { throw "Replace the backend placeholders using the breadth-analysis freeze." }
if (-not (Test-Path -LiteralPath "$SourceProtocolRoot\protocol_summary.json" -PathType Leaf)) { throw "Frozen breadth source protocol is missing: $SourceProtocolRoot" }
& $Wrapper -Action Audit -SourceProtocolRoot $SourceProtocolRoot
& $Wrapper -Action Prepare -SourceProtocolRoot $SourceProtocolRoot -ProtocolRoot $ProtocolRoot
& $Wrapper -Action Validate -SourceProtocolRoot $SourceProtocolRoot -ProtocolRoot $ProtocolRoot -Backends $Backends
& $Wrapper -Action Plan -Phase All -SourceProtocolRoot $SourceProtocolRoot -ProtocolRoot $ProtocolRoot -Backends $Backends
foreach ($Phase in $Phases) {
  & $Wrapper -Action Run -Phase $Phase -SourceProtocolRoot $SourceProtocolRoot -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -Backends $Backends
  & $Wrapper -Action Status -SourceProtocolRoot $SourceProtocolRoot -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -Backends $Backends
}
& $Wrapper -Action Analyze -SourceProtocolRoot $SourceProtocolRoot -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -AnalysisRoot $AnalysisRoot -Backends $Backends
& $Wrapper -Action Collect -SourceProtocolRoot $SourceProtocolRoot -ProtocolRoot $ProtocolRoot -ResultBase $ResultBase -AnalysisRoot $AnalysisRoot -CollectRoot $CollectRoot -Backends $Backends
Write-Output "STOP HERE — ANALYZE PHASES A-C AND SELECT ReferenceEnrollmentConfigId BEFORE ProbeDuration/JointFrontier."
Write-Output "UPLOAD PACKAGE: $CollectRoot"
```

## Command Block 5 — safe diarization smoke

This block runs one native Sherpa smoke item and at most one controlled smoke case per selected executable primary pipeline. It does not run development or evaluation.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\amiri\Documents\GitHub\just-peachy"
$Tool = "$Repo\Software Validation from Datasets\Evaluation Tool"
$Python = "$Repo\.venv\Scripts\python.exe"
$OnnxPython = "$Repo\.stage8-envs\onnx\Scripts\python.exe"
$Launcher = "$Tool\run_evaluation.py"
$Wrapper = "$Tool\scripts\run_controlled_diarization.ps1"
$GitShort = (git -C $Repo rev-parse --short=12 HEAD).Trim()
$NativeSmokeRoot = "$env:USERPROFILE\JustPeachyResults\diarization\readiness_native_sherpa_$GitShort"
$ControlledSmokeRoot = "$env:USERPROFILE\JustPeachyResults\diarization\controlled_smoke_$GitShort"
$ControlledAnalysisRoot = "$ControlledSmokeRoot\analysis"
$ControlledCollectRoot = "$env:USERPROFILE\JustPeachyResearchSummaries\controlled_diarization_smoke_$GitShort"
$Pipelines = @(
  "sherpa_onnx_diarization",
  "modular_energy_campplus",
  "modular_pyannote_campplus",
  "modular_energy_wespeaker",
  "pyannote_community1"
)
Push-Location $Tool
try {
  & $Python $Launcher diarization-benchmark pipeline-status
  if ($LASTEXITCODE -ne 0) { throw "Pipeline/model-load readiness check failed" }
  & $Python $Launcher diarization validate --manifest-root "$Tool\benchmarks\stage11\small"
  if ($LASTEXITCODE -ne 0) { throw "Native Stage 11 manifest validation failed" }
  & $OnnxPython $Launcher diarization smoke --manifest-root "$Tool\benchmarks\stage11\small" --output-root $NativeSmokeRoot
  if ($LASTEXITCODE -ne 0) { throw "Native Sherpa smoke failed" }
}
finally {
  Pop-Location
}
& $Wrapper -Action Audit
& $Wrapper -Action Prepare
& $Wrapper -Action Validate
& $Wrapper -Action Plan -Tier smoke -Pipelines $Pipelines
& $Wrapper -Action Smoke -Tier smoke -MaxCases 1 -ResultRoot $ControlledSmokeRoot -Pipelines $Pipelines
& $Wrapper -Action Status -Tier smoke -ResultRoot $ControlledSmokeRoot -Pipelines $Pipelines
& $Wrapper -Action Analyze -Tier smoke -ResultRoot $ControlledSmokeRoot -AnalysisRoot $ControlledAnalysisRoot -Pipelines $Pipelines
& $Wrapper -Action Collect -Tier smoke -ResultRoot $ControlledSmokeRoot -AnalysisRoot $ControlledAnalysisRoot -CollectRoot $ControlledCollectRoot -Pipelines $Pipelines
Write-Output "SAFE SMOKE PACKAGE: $ControlledCollectRoot"
```

## Command Block 6 — controlled diarization development

Run only after the speaker shortlist and enrollment/live-identification policy are frozen. Edit the list to the intentionally selected development candidates. This block stops after development collection.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\amiri\Documents\GitHub\just-peachy"
$Tool = "$Repo\Software Validation from Datasets\Evaluation Tool"
$Wrapper = "$Tool\scripts\run_controlled_diarization.ps1"
$GitShort = (git -C $Repo rev-parse --short=12 HEAD).Trim()
$ResultRoot = "$env:USERPROFILE\JustPeachyResults\diarization\controlled_diarization_v1\development_$GitShort"
$AnalysisRoot = "$ResultRoot\analysis"
$CollectRoot = "$env:USERPROFILE\JustPeachyResearchSummaries\controlled_diarization_development_$GitShort"
$Pipelines = @(
  "PIPELINE_1",
  "PIPELINE_2"
)
if ($Pipelines | Where-Object { $_ -like "PIPELINE_*" }) { throw "Replace PIPELINE_1/PIPELINE_2 using the speaker/enrollment decision." }
& $Wrapper -Action Audit
& $Wrapper -Action Prepare
& $Wrapper -Action Validate
& $Wrapper -Action Plan -Tier development -Pipelines $Pipelines
& $Wrapper -Action Run -Tier development -ResultRoot $ResultRoot -Pipelines $Pipelines
& $Wrapper -Action Status -Tier development -ResultRoot $ResultRoot -Pipelines $Pipelines
& $Wrapper -Action Analyze -Tier development -ResultRoot $ResultRoot -AnalysisRoot $AnalysisRoot -Pipelines $Pipelines
& $Wrapper -Action Collect -Tier development -ResultRoot $ResultRoot -AnalysisRoot $AnalysisRoot -CollectRoot $CollectRoot -Pipelines $Pipelines
Write-Output "STOP HERE — ANALYZE DEVELOPMENT BEFORE EVALUATION"
Write-Output "UPLOAD PACKAGE: $CollectRoot"
```

After analyzing development, create the freeze separately and document the decision:

```powershell
$Pipelines = @("SELECTED_PIPELINE_1", "SELECTED_PIPELINE_2")
$DecisionNote = "REPLACE_WITH_THE_REVIEWED_DEVELOPMENT_DECISION"
$FrozenPipelineConfig = "$ResultRoot\frozen_pipeline_configuration.json"
& $Wrapper -Action Freeze -Tier development -ResultRoot $ResultRoot -AnalysisRoot $AnalysisRoot -FrozenPipelineConfig $FrozenPipelineConfig -DecisionNote $DecisionNote -Pipelines $Pipelines
Get-FileHash -Algorithm SHA256 -LiteralPath $FrozenPipelineConfig
```

## Command Block 7 — frozen controlled diarization evaluation

This block refuses to continue unless the frozen file has the exact freeze schema, benchmark identity, frozen decision state, evaluation-tuning prohibition, nonempty analysis hash, and per-pipeline configuration hashes. The runner independently rechecks benchmark and current pipeline hashes.

```powershell
$ErrorActionPreference = "Stop"
$Repo = "C:\Users\amiri\Documents\GitHub\just-peachy"
$Tool = "$Repo\Software Validation from Datasets\Evaluation Tool"
$Wrapper = "$Tool\scripts\run_controlled_diarization.ps1"
$GitShort = (git -C $Repo rev-parse --short=12 HEAD).Trim()
$FrozenPipelineConfig = "C:\REPLACE_WITH_REVIEWED_DEVELOPMENT_RESULT\frozen_pipeline_configuration.json"
if (-not (Test-Path -LiteralPath $FrozenPipelineConfig -PathType Leaf)) { throw "Frozen pipeline configuration is required." }
$Frozen = Get-Content -LiteralPath $FrozenPipelineConfig -Raw | ConvertFrom-Json
if ($Frozen.schema_version -ne "controlled-diarization-frozen-pipelines.v1") { throw "Unexpected frozen configuration schema." }
if ($Frozen.benchmark_id -ne "controlled_diarization_v1_acd5e6e431d8") { throw "Frozen benchmark identity mismatch." }
if ($Frozen.development_decision_status -ne "frozen" -or $Frozen.evaluation_tuning_prohibited -ne $true) { throw "Development decision is not frozen." }
if (-not $Frozen.analysis_manifest_sha256 -or -not $Frozen.pipelines -or $Frozen.pipelines.Count -eq 0) { throw "Frozen analysis/pipeline hashes are missing." }
if ($Frozen.pipelines | Where-Object { -not $_.pipeline_id -or -not $_.configuration_sha256 }) { throw "A frozen pipeline identity/hash is incomplete." }
$Pipelines = @($Frozen.pipelines | ForEach-Object { $_.pipeline_id })
$FrozenFileSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $FrozenPipelineConfig).Hash
Write-Output "Frozen configuration SHA-256: $FrozenFileSha256"
$ResultRoot = "$env:USERPROFILE\JustPeachyResults\diarization\controlled_diarization_v1\evaluation_$GitShort"
$AnalysisRoot = "$ResultRoot\analysis"
$CollectRoot = "$env:USERPROFILE\JustPeachyResearchSummaries\controlled_diarization_evaluation_$GitShort"
& $Wrapper -Action Validate
& $Wrapper -Action Plan -Tier evaluation -Pipelines $Pipelines
& $Wrapper -Action Run -Tier evaluation -ResultRoot $ResultRoot -FrozenPipelineConfig $FrozenPipelineConfig -Pipelines $Pipelines
& $Wrapper -Action Status -Tier evaluation -ResultRoot $ResultRoot -Pipelines $Pipelines
& $Wrapper -Action Analyze -Tier evaluation -ResultRoot $ResultRoot -AnalysisRoot $AnalysisRoot -Pipelines $Pipelines
& $Wrapper -Action Collect -Tier evaluation -ResultRoot $ResultRoot -AnalysisRoot $AnalysisRoot -CollectRoot $CollectRoot -Pipelines $Pipelines
Copy-Item -LiteralPath $FrozenPipelineConfig -Destination "$CollectRoot\frozen_pipeline_configuration.json"
Set-Content -LiteralPath "$CollectRoot\FROZEN_PIPELINE_FILE_SHA256.txt" -Value $FrozenFileSha256 -Encoding utf8
Write-Output "UPLOAD PACKAGE: $CollectRoot"
```

## What to upload after each stage

| Stage | Upload package and required contents |
| --- | --- |
| ReDimNet / six-model Stage 10 | Upload `C:\Users\amiri\JustPeachyResearchSummaries\speaker_stage10_large_all6_38db58925d8f`: `RUN_SUMMARY.csv`, `RUN_PROVENANCE.txt`, `RESULT_FILE_INVENTORY.csv`, all six `protocol_run.json`, `backend_identity.json`, `extraction_summary.json`, validation files, and protocol manifest/config. |
| Common Voice breadth | Upload `C:\Users\amiri\JustPeachyResearchSummaries\speaker_breadth_commonvoice_60plus_commonvoice_60plus_v1_27e72793b4c0`: `RUN_SUMMARY.csv`, `RUN_PROVENANCE.txt`, `RESULT_FILE_INVENTORY.csv`, `PROTOCOL_SUMMARY.json`, `SPEAKER_COHORT_SUMMARY.csv`, `METADATA_COVERAGE.csv`, each finalist `protocol_run.json`, identity/extraction summaries, and any analysis produced outside the runner. |
| Enrollment | Upload `C:\Users\amiri\JustPeachyResearchSummaries\speaker_enrollment_duration_speaker_enrollment_duration_v1_8ee8b2aa42d1`: `configuration_results.csv`, `speaker_results.csv`, `enrollment_curve.csv`, `duration_curve.csv`, `aggregation_comparison.csv`, `joint_frontier.csv` when available, `reliability_summary.csv`, `analysis_manifest.json`, `report.md`, `RUN_PROVENANCE.txt`, and `RESULT_FILE_INVENTORY.csv`. |
| Diarization development | Upload the explicit development `CollectRoot`: `overall_results.csv`, `recording_results.csv`, `factor_results.csv`, `speaker_count_results.csv`, `overlap_results.csv`, `turn_cadence_results.csv`, `fragmentation_results.csv`, `reentry_results.csv`, `resource_results.csv`, `reliability_summary.csv`, `analysis_manifest.json`, `report.md`, pipeline identities/configurations, and inventory/provenance. |
| Diarization evaluation | Upload the explicit evaluation `CollectRoot`: the same science package plus `frozen_pipeline_configuration.json`, `FROZEN_PIPELINE_FILE_SHA256.txt`, benchmark identity/hash, prediction RTTMs, and scoring summaries. |

## Manual next-action checklist

1. Run ReDimNet Stage 10 Large using Command Block 1 and retain the clean-source scope warning.
2. Collect all six Stage 10 results using Command Block 2.
3. Upload the compact six-model package to ChatGPT.
4. Do not run breadth yet.
5. Analyze the six models and freeze the top 2–3.
6. Run Common Voice breadth only on those finalists.
7. Upload the breadth package to ChatGPT.
8. Analyze breadth and freeze the primary and fallback speaker backends.
9. Run enrollment phases A–C on the primary and fallback.
10. Upload the enrollment package to ChatGPT.
11. Analyze, run only the explicitly selected later phases, and freeze the enrollment/live-ID policy.
12. Select diarization development pipelines using the speaker results.
13. Run only the controlled diarization development panel.
14. Upload the development package.
15. Analyze development, choose pipelines/parameters, and create the frozen configuration/hash.
16. Run the controlled diarization evaluation panel with that frozen file.
17. Upload the evaluation package.
18. Analyze and select the final diarization architecture(s).

Do not automatically continue past any analysis gate.

## Git and contamination check

- Frozen Stage 10, breadth, enrollment, and controlled diarization protocol diffs: none.
- Raw files tracked under `Raw Datasets (Not formatted)`: 0.
- Breadth selection is model-independent.
- Enrollment outputs do not alter breadth artifacts.
- Development and evaluation diarization speakers are disjoint.
- Known-speaker labels do not alter primary anonymous DER scoring.
- Smoke outputs are outside scientific development/evaluation roots.
- Existing user scientific/qualification evidence and untracked research queue logs were preserved.
