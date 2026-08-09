# Stage 0 Readiness Freeze

## Outcome

Stage 0 establishes a versioned, evidence-backed inventory without implementing campaign execution. The core CPU environment is usable for contract work and six real component qualification paths pass. The immediate next gate is a separate pinned CUDA environment and real CUDA qualification. Large benchmarks, model selection, and concurrency testing are not authorized yet.

## Repository and environment identity

- repository: `C:\Users\amiri\Documents\GitHub\just-peachy`;
- speech pipeline location: inside `Software Validation from Datasets/Evaluation Tool` (not a second repository);
- branch: `handoff`;
- frozen observed commit: `e7e5516991b95f4e7c915e852fc0b4f5bae7cd11`;
- upstream divergence at inspection: `0 ahead / 0 behind`;
- Python: `3.12.7` in repository `.venv`;
- current Torch: `2.11.0+cpu`; CUDA unavailable to Torch;
- physical GPU: NVIDIA GeForce RTX 3080, 10240 MiB, driver `610.62`;
- dependency health: `pip check` passed;
- development verifier: 25/26 non-failing checks; only FFmpeg PATH discovery failed in the current process;
- FFmpeg: WinGet package `8.1.2` exists, but the current Codex process did not inherit its bin directory on PATH.

No installed direct-package version mismatch was found for the core/inference/development profile: the verifier reported the pinned versions and `pip check` found no broken requirements. The FFmpeg discovery issue is a system PATH mismatch, not a Python package mismatch. Optional-profile packages are absent by design and are recorded as unavailable rather than mismatched.

The repository contains no physical `AGENTS.md` at the root. The active workspace instruction supplied to Codex requires every new code area to include and maintain run instructions, purpose, inputs, and outputs; `docs/automated_evaluation/README.md` fulfills that requirement for Stage 0.

All six supported dataset families are locally visible in both expected forms: normalized Parquet metadata exists for AMI, CHiME-6, CMU Arctic, HiFiTTS, LibriSpeech, and VOiCES, and corresponding raw-data directories exist. This is an access/readiness observation, not a grant to redistribute dataset audio. Existing registry/path-rebase tests remain authoritative for resolving those sources.

## Git-state freeze and preserved user work

Stage 0 began from a dirty tree. Existing user-owned changes were preserved:

- staged `.gitignore` change and staged removal of the previously tracked resume copy;
- modified `Software Validation from Datasets/Final_Eval_Tool_Prep_and_Prompts.docx`;
- untracked real speaker-protocol artifacts under `Evaluation Tool/artifacts/speaker_protocol`.

The `Resumes/` folder was inspected once in the prior handoff, is ignored, and remains outside Git. Stage 0 did not inspect its contents again.

## Decision freeze

1. Whisper Base is the reference ASR used when VAD, segmentation, embedding, matching, or diarization components require a fixed ASR composition.
2. Whisper Tiny is the quick smoke model. Whisper Small is a required real candidate. Whisper Large, Medium, and Turbo variants are excluded.
3. Seed `3800` is the deterministic default for later benchmark selection and expansion.
4. CPU integration and contract qualification precede CUDA qualification. CUDA qualification is the next phase gate and must pass before standard/large benchmarks or performance-based selection.
5. One GPU-heavy scenario per machine is the default. Dual execution requires a controlled concurrency qualification later.
6. Unknown speaker labels are preserved as literal output and scored as predictions.
7. XVF3800 is excluded from current planning.
8. Existing Evaluation Tool reverberation simulation is reused without new RT60/EDT/C50/C80 analysis.
9. Only dining room, bedroom, and restaurant RIR environments are in current scope. Dining room is `h025_Diningroom_8txts.wav`; restaurant is `h093_Restaurant_2txts.wav`; the exact bedroom file remains a required explicit decision.
10. `h044_ParkingLot_4txts.wav` is a parking-lot response, not a kitchen response, and is excluded rather than substituted.
11. Optional backends do not block the core pipeline. They retain explicit unavailable/credential/asset/platform dispositions and cannot be advertised as current-ready.
12. Evaluation will use staged component screening and targeted combinations, not a full Cartesian product.

## Confirmed current qualification

The real CPU qualification report at `runs/component_qualification/cpu_contract_20260807.json` used CMU Arctic `arctic_b0476.wav` and produced 19 results with zero code failures:

| Family | Qualified now | Explicitly unavailable now |
|---|---|---|
| VAD/segmentation composition | Energy VAD + chunks + Whisper Base; Silero VAD + chunks + Whisper Base | Sherpa-ONNX VAD; WebRTC VAD |
| ASR | Whisper Tiny, Base, Small | Faster-Whisper; Sherpa-ONNX; Vosk; WeNet |
| Speaker embedding/matching | SpeechBrain ECAPA + cosine threshold | Resemblyzer; Sherpa-ONNX embedding; WeSpeaker |
| Diarization | no real backend qualified in this environment | NeMo; Falcon; Pyannote Community; Sherpa-ONNX |

No-op and deterministic fixed components are contract-test tools, not model qualification evidence.

## Environment/profile boundaries

`configs/automated_evaluation/environment_profiles.v1.yaml` defines seven separate profiles: core CPU development, core CUDA, extended local, ONNX, credential-gated diarization, Linux/CUDA NeMo, and test-only contracts. This prevents optional native/Git/CUDA stacks from silently destabilizing the qualified CPU core.

The CUDA profile intentionally does not invent an unverified wheel index. Before installation, the exact Python-3.12-compatible CUDA Torch 2.11.0 build and index must be selected from the official compatibility matrix and recorded. The CPU environment should remain intact for rollback/comparison.

## Credential and access actions

No API key is required for the qualified core CPU set. Optional components require user action:

- Pyannote Community: accept the gated model terms, obtain access, set `PYANNOTE_AUTH_TOKEN` only in the process environment, install the pinned package, acquire the local cache, then qualify.
- Picovoice Falcon: create/authorize a Picovoice account, set `PICOVOICE_ACCESS_KEY` only in the process environment, install the pinned package, then qualify.
- NeMo: use the isolated Linux/CUDA profile and acquire/checksum its diarization config/models.
- Other extended/ONNX components: install only their pinned profile and bootstrap checksum-verified local assets before qualification.

Credential values must never enter scenario files, manifests, worker assignments, logs, reports, shell history, or result handoffs.

## Model and RIR identity evidence

Exact Whisper and SpeechBrain filenames, byte sizes, SHA-256 hashes, package versions, and local terms gaps are recorded in `environment_profiles.v1.yaml`. Model cache directories do not carry all upstream license files, so the registry permits internal qualification but does not grant redistribution; upstream terms must be reviewed before distributing weights.

The RIR source is a flat directory of WAV files. The earlier planning text describing environment folders and naming `h044` as Kitchen conflicts with disk contents. Disk contents are authoritative. Stage 0 records hashes only; no acoustic characterization was performed or required.

## Conflicts resolved by code/evidence

| Conflict | Resolution |
|---|---|
| Earlier prompt described a separate speech repository. | The pipeline is inside the Evaluation Tool repository; component YAML is the source of truth. |
| Historical reports said several optional backends had run elsewhere. | Historical evidence is retained, but current readiness comes from the present environment and real report; absent backends are not current-qualified. |
| Qualifier chose Vosk, then Sherpa, then Tiny as its composition reference. | Readiness harness now requires Whisper Base, matching the approved decision. Normal inference behavior was not changed. |
| Earlier RIR list used folders and called `h044` Kitchen. | Actual source is flat WAV files and `h044_ParkingLot_4txts.wav`; no substitution is allowed. |
| Earlier planning required fifteen RIR classes and acoustic characterization. | Latest user decision limits current scope to dining room, bedroom, restaurant and no added acoustic analysis. |
| Earlier flow mentioned XVF3800. | Latest user decision excludes it. |
| Installed FFmpeg was expected to be ready. | Binary exists, but current process PATH is stale; restart/fix PATH and rerun verifier. |
| Benchmark manifest/scenario hash were to be frozen immediately. | Version identifiers and compatibility policy are reserved now; no implementation exists to freeze. Their wire shapes become public immutable contracts only after implementation and first validated release. |

## Stop conditions and next gate

Stage 0 is complete with two carried gates:

- an exact bedroom RIR must be chosen and hashed before any scenario manifest is generated;
- the CUDA environment must be pinned, built separately, and really qualified before any standard/large benchmark.

Optional credential/platform backends may remain unavailable without blocking the core benchmark. A later phase must not claim those backends are operational until its own real qualification artifact exists.
