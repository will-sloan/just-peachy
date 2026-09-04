# Speaker enrollment and live identification v2

## Purpose

This additive study measures how WeSpeaker and ReDimNet2-B2 should be used for guided speaker enrollment and open-set live identification. It preserves the frozen v1 experiment and Common Voice source protocol. Pairwise EER remains a diagnostic; it is never used as the production identity threshold.

The v2 decision is calibrated only on calibration speakers. A probe is named only when its maximum gallery score reaches a score threshold and its Top-1 minus Top-2 margin reaches a margin threshold. The study fits independent policies for FPIR targets 0.1%, 0.5%, 1%, 2%, and 5%, then applies the frozen policies to held-out evaluation speakers.

## Inputs

- Frozen Common Voice 60+ protocol: `benchmarks/speaker_breadth/commonvoice_60plus_v1`.
- Policy: `configs/automated_evaluation/speaker_enrollment_live.v2.yaml`.
- Qualified local WeSpeaker and ReDimNet2-B2 environments and model assets.
- Raw audio resolved through the repository's portable logical-path resolver. No audio is copied into Git.

## Outputs

The immutable protocol is written to `benchmarks/speaker_enrollment/speaker_enrollment_live_v2`. Runtime results stay under `JustPeachyResults/speaker_enrollment/<protocol_id>/` inside the Evaluation Tool. Each configuration records calibration policies, open-set operating points, held-out decisions, speaker-level results, enrollment consistency, identity hubness, score trials, runtime/storage cost, and checksums.

After Phase D, analysis adds causal nested-prefix trajectories, raw and two-confirmation hysteresis results, first/stable correct-identification time, false-identification latency, identity flips, and estimated wrong-identity dwell. Common Voice has no independent session/device labels, so warm-session, channel, repeated-phrase, and real-device findings are explicitly simulation-only or unavailable.

## PowerShell

From the repository root:

```powershell
$Runner = "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_enrollment_live_v2.ps1"
powershell -ExecutionPolicy Bypass -File $Runner -Action Prepare
powershell -ExecutionPolicy Bypass -File $Runner -Action Validate
powershell -ExecutionPolicy Bypass -File $Runner -Action Plan
powershell -ExecutionPolicy Bypass -File $Runner -Action Start
```

Monitor once or continuously:

```powershell
$Monitor = "Software Validation from Datasets\Evaluation Tool\scripts\monitor_speaker_enrollment_live_v2.ps1"
powershell -ExecutionPolicy Bypass -File $Monitor
powershell -ExecutionPolicy Bypass -File $Monitor -Follow
```

The background controller extracts both finalists concurrently, reuses valid per-slice caches after a restart, and runs Phases A-D. It then writes an explicit, auditable Phase-E gate automatically. The gate selects two distinct enrollment modes using calibration known-correct acceptance, calibration wrong-name rate, calibration FPIR, and template storage only; held-out evaluation metrics are never used. Phase E crosses those two modes with all seven frozen causal durations, adding 14 joint-frontier configurations per backend before analysis and export.

SpeechBrain ECAPA and ERes2Net Base can run as an isolated reference-model add-on without changing or overwriting the primary finalist run:

```powershell
$Runner = "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_enrollment_live_v2.ps1"
powershell -ExecutionPolicy Bypass -File $Runner -Action Start -ControllerTag reference_models -BackendCsv "speechbrain_ecapa,eres2net_base_speaker_embedding"

$Monitor = "Software Validation from Datasets\Evaluation Tool\scripts\monitor_speaker_enrollment_live_v2.ps1"
powershell -ExecutionPolicy Bypass -File $Monitor -Follow -ControllerTag reference_models -BackendCsv "speechbrain_ecapa,eres2net_base_speaker_embedding"
```

The add-on uses the same frozen protocol but separate controller logs, analysis directory, and compact export. Backend result directories remain distinct, so no primary result or cache is replaced.

Monitor all four models together:

```powershell
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\monitor_speaker_enrollment_live_v2.ps1" -Follow -AllModels
```

The monitor prints separate extraction, evaluation, and weighted-overall percentage bars. The evaluation denominator is 156 configurations per backend: 142 from Phases A-D plus 14 automatically gated Phase-E configurations.

If extraction reaches 100% while evaluation is still 0%, inspect the controller state shown above the bars. A short pause is normal while the complete cache is summarized and runtime telemetry is written. A `FAILED` state requires a restart after correcting the reported cause. Valid cached `too_short` observations are expected scientific outcomes for slices below a backend's minimum duration; they count toward cache completeness and are retained as `TECHNICALLY_INVALID` during evaluation rather than being padded or discarded. Restarting the controller reuses these records and all successful embeddings.

If every probe at one frozen duration is below a backend's supported minimum,
the configuration is completed with `configuration_outcome=TECHNICALLY_INVALID`,
no fabricated threshold or margin, zero valid-probe coverage, and explicit
per-probe statuses. It still counts as a completed protocol condition so Phase E
and the final analysis can preserve the backend limitation. Windows artifact
publication uses bounded sharing-violation retries, and any extraction failure
now terminates the phase instead of silently advancing with missing results.
Before a failed controller is restarted, its state and logs are copied into a
timestamped `_controller*/attempts/` folder so the earlier failure evidence is
not overwritten by the resumed attempt.

The completed primary analysis is written to
`JustPeachyResults/speaker_enrollment/<protocol_id>/analysis/`; the reference
models use `analysis_reference_models/`. Compact exports are written under
`JustPeachyResearchSummaries/` with the protocol ID and controller tag.

## Anaconda Prompt or Command Prompt

The management environment can run the non-inference preparation and validation directly:

```bat
call .venv\Scripts\activate.bat
python "Software Validation from Datasets\Evaluation Tool\run_evaluation.py" speaker-enrollment prepare --config "Software Validation from Datasets\Evaluation Tool\configs\automated_evaluation\speaker_enrollment_live.v2.yaml" --source-protocol-root "Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_breadth\commonvoice_60plus_v1" --protocol-root "Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_enrollment\speaker_enrollment_live_v2"
python "Software Validation from Datasets\Evaluation Tool\run_evaluation.py" speaker-enrollment validate --source-protocol-root "Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_breadth\commonvoice_60plus_v1" --protocol-root "Software Validation from Datasets\Evaluation Tool\benchmarks\speaker_enrollment\speaker_enrollment_live_v2" --backend wespeaker --backend redimnet2_b2_speaker_embedding
```

Use the PowerShell controller for the full run because it safely launches the two isolated model environments in parallel and records restart-safe logs.

## Interpretation

- FPIR is the fraction of Unknown probes incorrectly assigned to any enrolled person.
- DIR/TPIR is the fraction of known probes correctly named and accepted.
- FNIR is one minus DIR: rejected known probes and wrong-known names both count as failures.
- Known-to-Unknown is the known rejection rate.
- Wrong-known-to-wrong-known is the rate at which a known person is confidently named as another enrollee.
- Unknown rejection is one minus FPIR.
- Hubness shows whether a few enrollment identities attract disproportionate stranger probes.
- Enrollment consistency flags unusual within-person templates for review; it does not prove a wrong speaker or bad recording.

No per-user fine-tuning, automatic template adaptation, or product threshold is selected by this run. Immediate ASR text and asynchronous identity labels remain separate product decisions.
