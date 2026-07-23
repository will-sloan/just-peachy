# Inference Pipeline Notes

This file summarizes the newer code under `app/inference_pipeline` and how it
connects to the Evaluation Tool GUI and CLI.

## Purpose

The inference pipeline is the replaceable model side of the Evaluation Tool. It
loads selected audio, optionally detects speech regions, splits audio into
segments, runs ASR, optionally labels speakers, assembles a transcript, and
returns the standardized prediction rows that the evaluator scores.

## Main Entry Points

- GUI: `app/gui/main.py`
- CLI: `run_evaluation.py` and `app/cli/main.py`
- Model runner bridge: `app/model_runner/external_stub.py`
- Modular pipeline: `app/inference_pipeline/pipeline.py`
- Default external-runner config: `configs/inference/e2e_named_transcript.yaml`

In the GUI, choose **External stub / real runner hook** to use
`ExternalStubRunner`, which calls the modular `PipelineRunner`.

## Current Default Behavior

The default external config runs a real pipeline shell, but not a real ASR or
diarization model:

- audio loading: enabled
- VAD: `energy_vad`
- segmentation: `vad_chunks`
- ASR: `no_op_asr` with `dummy pipeline transcript`
- diarization: disabled
- speaker embedding/matching: no-op diagnostics

This is useful for verifying the pipeline and evaluator wiring. It is not yet a
Whisper or pyannote run unless you edit the config and install the optional
model dependencies/assets.

## Install And Run

From Anaconda Prompt:

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
pip install -r requirements.txt
python run_evaluation.py list-datasets
python run_evaluation.py gui
```

If `python` is not on PATH, use the verified interpreter directly:

```powershell
& "C:\Users\amiri\anaconda3\python.exe" run_evaluation.py list-datasets
& "C:\Users\amiri\anaconda3\python.exe" run_evaluation.py gui
```

One-record external pipeline smoke:

```powershell
& "C:\Users\amiri\anaconda3\python.exe" run_evaluation.py full --dataset cmu_arctic --max-recordings 1 --runner external-stub --run-name external_pipeline_smoke
```

Inputs: normalized metadata, selected raw audio, and the inference config.

Outputs: a timestamped folder under `runs/` with predictions, diagnostics,
metrics, plots, logs, and a Markdown report.

## Component Layout

- `audio_io/`: loads and validates WAV/FLAC audio.
- `vad/`: energy and Silero VAD adapters.
- `segmentation/`: turns speech regions into ASR chunks.
- `asr/`: no-op, fixed, Whisper, and faster-whisper adapter boundaries.
- `diarization/`: pyannote adapter boundary and diarization contracts.
- `speaker_embedding/`: no-op, fake, and SpeechBrain ECAPA adapter boundary.
- `speaker_matching/`: cosine-threshold speaker matching and calibration.
- `transcript/`: combines segment transcripts into one prediction.
- `runtime/`: runtime stats, GPU helpers, and job scheduling.
- `reporting/` and `metrics/`: component-level reports and metric helpers.

## Enabling Real Models

Example component configs live under `configs/inference/components/`.

- Whisper: `components/asr/whisper_tiny.yaml` or `whisper_base.yaml`
- pyannote: `components/diarization/pyannote_community.yaml`
- SpeechBrain: `components/speaker_embedding/speechbrain_ecapa.yaml`

Downloads are disabled in these configs by default. To use real models, install
the relevant optional package, provide local model assets or tokens, and point
the external runner at a config that enables those components.
