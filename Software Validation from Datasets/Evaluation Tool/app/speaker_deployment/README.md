# Speaker embedding deployment evaluation

## Purpose

This study compares WeSpeaker, ReDimNet2-B2, SpeechBrain ECAPA, and ERes2Net Base for a product that must name enrolled speakers and safely reject everyone else. It replays already-qualified frozen embeddings, so it does not download models, modify audio, or repeat inference.

The main panel is Common Voice 60+ (272 enrolled speakers, 93 held-out evaluation-unknown speakers). Clean CMU Arctic is an independent small-gallery read-speech panel. The known Stage-10 degraded-audio provenance problem is intentionally excluded from robustness claims.

The study keeps pairwise verification EER separate from deployment thresholding. Every operating threshold is fitted only on calibration probes against the full enrolled gallery. It jointly uses maximum score and the Top-1-minus-Top-2 margin, with unknown FPIR targets of 0.1%, 0.5%, 1%, 2%, and 5% and a 0.5% cap on known-speaker wrong-name assignments.

## Inputs

- Policy: `configs/automated_evaluation/speaker_embedding_deployment.v1.yaml`
- Frozen Common Voice speaker protocol and four existing observation bundles
- Frozen Stage-10 large CMU Arctic protocol and clean observation bundles
- No raw audio is read during replay

## Run from PowerShell or Anaconda Prompt

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_embedding_deployment.ps1" -Action Plan
powershell -NoProfile -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_embedding_deployment.ps1" -Action Validate
powershell -NoProfile -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_embedding_deployment.ps1" -Action Run -ParallelModels 2 -AutoExport
```

The same commands work inside an Anaconda Prompt; no `conda activate` is needed because the wrapper selects the repository environment explicitly. `-ParallelModels 2` is the recommended balance for this machine. Use `1` if memory pressure is visible.

Monitor from a second PowerShell or Anaconda Prompt:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\monitor_speaker_embedding_deployment.ps1"
```

Press `Ctrl+C` to stop only the monitor. A single snapshot is available with `-Once`.

## Outputs

Results are written under:

`Software Validation from Datasets/Evaluation Tool/JustPeachyResults/speaker_embedding_deployment/<study-id>/`

Each model receives:

- `gallery_operating_points.csv`: gallery size, calibration FPIR target, thresholds, DIR/FNIR, wrong-name and rejection rates;
- `enrollment_operating_modes.csv`: enrollment count and aggregation comparisons;
- `hubness.csv`: false-known assignments received by each enrolled identity;
- `subgroup_metrics.csv`: gender/accent slices with denominators;
- `session_accumulation.csv`: deterministic multi-turn accumulation simulation;
- `session_trajectories.csv`: first/stable correct turn, false-attribution latency, label flips, and a two-confirmation hysteresis replay;
- `summary.json` and live `progress.json`.

The combined `analysis/` directory contains the ranked model table, gallery/enrollment/session/hubness summaries, enrollment recommendations, a plain-language metric guide, and the detailed report. `-AutoExport` also creates a compact checksummed folder and ZIP under `JustPeachyResearchSummaries`. It includes no raw audio or model weights.

## Scientific boundaries

- Thresholds are model-, gallery-, enrollment-, and domain-specific. Never paste a threshold from one row into another deployment.
- Session accumulation is a replay of ordered independent utterances, not end-to-end diarization.
- Common Voice and CMU Arctic are prompted/read speech. Beaker far-field/channel, causal 0.5–5 second prefix, interruptions, and Speaker Label Error Rate require their dedicated frozen protocols before a release decision.
- Do not auto-adapt stored user templates from uncertain live predictions.
