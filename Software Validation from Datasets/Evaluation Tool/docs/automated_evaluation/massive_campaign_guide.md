# Massive campaign guide

## Decision and scientific status

`campaign_05_massive_release` is a byte-frozen **candidate reference and
robustness campaign**, not yet the final multi-backend scientific campaign.
Its immutable scenarios all use Whisper Base on CPU with full-record input.
That is useful for a broad reference surface, but it cannot answer which VAD,
ASR, embedding, matcher, or diarization backend is best. The component canary,
small gate, standard gate, and screening-based finalist freeze must occur before
this candidate is authorized—or it must be regenerated with the approved
finalists. Current launch verdict: `NOT_READY_TO_LAUNCH`.

## Frozen identity and scale

| Contract | Value |
|---|---|
| Campaign | `campaign_05_massive_release` |
| Campaign manifest SHA-256 | `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4` |
| Scenario catalog SHA-256 | `24AD135F8F2F2450EED78D910727FC63B585958602D28429B3B46B5A1060367E` |
| Large benchmark SHA-256 | `BC207E61B82052F06CCB9FFFE038B6DFE7B1C65C21843D08905946114238DE88` |
| Speaker protocol SHA-256 | `A9B0B28F5C7FDEF51215069521215BB78598DB9497E40BDA6C893181F71288D4` |
| Tier / seed | `large` / 3800 |
| Scenarios | 41 |
| Scenario-item executions | 25,798 |
| Repeated audio | 33.720121 hours |
| Unique source rows / audio | 8,258 / 10.804780 hours |
| Repetition | 1 for every candidate scenario |
| Runtime | `core-cpu`, CPU, float32, batch 1, one thread, one scenario per machine |
| Scoring | `scoring-policy.v1`; missing/failed outputs remain visible |
| Downloads | `allow_model_downloads=false` |

## Research questions this candidate can answer

1. What is the fixed Whisper Base full-record ASR baseline across the large
   controlled, native, and speaker-protocol source selections?
2. How does that same pipeline's WER/CER and reliability change under approved
   white/pink noise, Dining RIR, Restaurant RIR, and selected interactions?
3. How do native AMI, VOiCES, and CHiME-6 results differ without synthetic
   augmentation?
4. What CPU time, RAM, disk, telemetry availability, and failure behavior occur
   across this fixed reference surface?

It cannot answer VAD, segmentation, speaker verification/open-set rejection,
embedding drift, diarization, backend superiority, CUDA performance, or
multi-backend Pareto questions because those components are disabled here.

## Scenario-family coverage

| Family | Candidate | Dataset/panel | Conditions | Scenarios | Item executions | Audio hours | Primary valid outputs | Purpose |
|---|---|---|---|---:|---:|---:|---|---|
| Controlled ASR | Whisper Base full-record | CMU Arctic, LibriSpeech clean, HiFiTTS clean / `controlled_clean` | clean, white 10/20 dB, pink 10/20 dB, Dining, Restaurant, selected RIR+pink 10 dB | 27 | 17,640 | 23.832780 | ASR/reliability/resources | Clean reference and controlled degradation |
| Native ASR | Same | AMI, VOiCES, CHiME-6 and approved native rows / `native_robustness` | native only | 5 | 6,298 | 8.156690 | ASR/reliability/resources grouped where metadata permits | Native far-field/meeting robustness without double augmentation |
| Speaker-source ASR | Same; no embeddings/matcher | Immutable enrollment/calibration/known/unknown source rows / `speaker_protocol` | clean/degraded manifest conditions | 9 | 1,860 | 1.730650 | ASR/reliability only | Preserve common source selection for later backend-specific speaker work; **not** speaker verification evidence |

Dataset scenario counts are CMU Arctic 18, LibriSpeech 10, HiFiTTS 10, AMI
1, VOiCES 1, and CHiME-6 1. Condition counts are clean 6, native 5, white
10 dB 5, white 20 dB 3, pink 10 dB 5, pink 20 dB 3, Dining 5,
Restaurant 3, Dining+pink 10 dB 3, and Restaurant+pink 10 dB 3.

## Components and acoustic policy

The only active model component is `whisper_base` through
`WhisperBaseASRAdapter` / `WhisperASR`. VAD, segmentation, speaker embedding,
speaker matching, and diarization are explicit disabled no-ops. Whisper Base
uses English, beam size 1, 16 kHz audio, CPU/float32, and the exact 145,262,807
byte model with SHA-256
`ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E`.

Only controlled-clean sources receive simulation. Native rows are `native_only`.
The two executable RIR identities are:

- `dining_room_h025` — `h025_Diningroom_8txts.wav`, SHA-256
  `940D761A280DCD8FAAB077074E02BADE649E64E47461D80A4F927A01ABBEF5E2`;
- `restaurant_h093` — `h093_Restaurant_2txts.wav`, SHA-256
  `C2CA8A07002943409D31A2C6D6D07BA826AA428FE6EF6CECF2C4FF33D7D4A8A8`.

Bedroom is unresolved and has no scenario. ParkingLot is never substituted for
Bedroom or Kitchen. No XVF3800 processing or extra RIR characterization is in
scope.

## Metrics, telemetry, plots, and reports

Each ASR scenario is expected to retain standardized predictions, diagnostics,
failures, item/grouped metrics, summary, telemetry samples, component spans,
resource summary, logs, checksums, and scenario reports. Valid campaign-level
analysis includes WER/error counts, reliability/completion, available CPU/RAM/
disk/GPU-null telemetry, condition/dataset groups, coverage, and eligibility-
gated plots. CER, latency, RTF, throughput, sensor values, and subgroup plots
are emitted only when their required artifacts exist. Speaker/diarization
metrics are not supported by this candidate and must be reported unavailable,
not zero.

## Excluded or blocked coverage

| Component family | Status in candidate | Reason |
|---|---|---|
| Whisper Tiny/Small and extended ASR | Excluded pending screening | No final non-dominated shortlist/gate evidence |
| Energy/Silero/WebRTC/Sherpa VAD and VADChunker | Excluded pending screening | Candidate is full-record reference only |
| ECAPA/Resemblyzer/WeSpeaker/Sherpa embeddings and cosine matching | Excluded | Backend-specific speaker protocol is a separate scientific run |
| Sherpa diarization | Excluded pending native-panel selection | No diarization scenarios in candidate |
| Pyannote/Falcon | Blocked/optional | Owner licence/credentials absent |
| NeMo | Blocked/optional | Linux/CUDA and active checkpoints unresolved |
| WeNet | Blocked/optional | Runtime-required `final.zip` unavailable |
| Bedroom RIR | Blocked/excluded | Unresolved; no substitution allowed |
| CUDA and dual-job GPU concurrency | Deferred | Candidate is CPU; concurrency unqualified |

Machine-readable coverage is
`configs/automated_evaluation/launch_coverage.v1.json`.

## Worker split, runtime, and storage

Machine A provisionally owns 20 scenarios, 12,368 item executions, and
16.882998 hours; estimate 4.08 hours (3.46–6.24), with 2.15 GiB artifacts.
Machine B provisionally owns 21, 13,430, and 16.837123 hours; estimate 4.07
hours (3.45–6.24), with 2.30 GiB artifacts. B's estimate reuses A's measured
CPU rate and is not hardware evidence. Both assignments have global IDs, no
overlap, and complete 41-scenario union.

Run one scenario at a time. Status may be checked at any time. A controlled stop
preserves partial work; resume through the worker wrapper with `-ResumeStopped`.
Export only after all assigned scenarios validate, or after a planned periodic
checkpoint clearly labelled partial and not eligible for final merge. Contact
the coordinator for repeated deterministic failures, checksum mismatch,
unexpected model identity, output disk below reserve, or any pressure to change
a result-affecting setting under the same scenario ID.

Final completion means both complete transfer manifests validate, merge reports
41/41 with no conflicts/missing work, analysis reconciles all planned IDs, and
the standard-gate prerequisite is passed. Operational commands are in
[the launch control sheet](launch_control_sheet.md) and
[the two-machine runbook](two_machine_launch_runbook.md).
