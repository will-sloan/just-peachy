# M1 Inference Pipeline Contracts

M1 defines model-free contracts for the future speech inference pipeline. These
objects describe how data moves between pipeline stages, but they do not load
models, run inference, read audio samples, require datasets, require a GPU, or
export to ExecuTorch.

## Contract Overview

- `EvaluationRecord` represents one selected metadata row passed by the
  Evaluation Tool runner. It preserves `recording_id`, `utt_id`, `start_sec`,
  `end_sec`, and `speaker_label`, and uses `record["inference_audio_path"]` as
  the primary audio path.
- `AudioSegment` represents model-ready audio metadata for a file or interval.
  Mono is the default path, with optional fields for channel index and channel
  count.
- `SpeechRegion` represents a VAD result with start/end times, confidence,
  channel, and label.
- `WordTiming` represents optional word-level ASR timing.
- `ASRTranscript` represents ASR output for a segment or speech region.
- `SpeakerEmbedding` represents speaker embedding metadata using a JSON-safe
  vector, without tensor libraries.
- `SpeakerDecision` represents speaker labeling or speaker matching output.
- `TranscriptItem` represents an assembled transcript span after optional VAD,
  ASR, and speaker processing.
- `RuntimeStats` records timing, device, model version, and counter metadata.
- `PipelineOutput` represents final output for one `EvaluationRecord` and maps
  back to the required `predictions/utterances.jsonl` fields.

## Runner Contract Preservation

The Evaluation Tool still owns dataset selection, augmentation, run folders,
scoring, plots, and reports. The runner contract remains:

```text
record["inference_audio_path"] -> future pipeline -> predictions/utterances.jsonl row
```

The required utterance prediction row remains exactly:

```json
{
  "recording_id": "string",
  "utt_id": "string",
  "start_sec": 0.0,
  "end_sec": 1.23,
  "speaker_label": "speaker-or-null",
  "text": "predicted transcript"
}
```

`recording_id` and `utt_id` must be preserved exactly because the scorer matches
predictions on `(recording_id, utt_id)`.

## Example

```python
from app.inference_pipeline.contracts import (
    ASRTranscript,
    EvaluationRecord,
    PipelineOutput,
    RuntimeStats,
    SpeakerDecision,
)

metadata_row = {
    "recording_id": "VOICES_example_recording",
    "utt_id": "utt-001",
    "inference_audio_path": "runs/tmp/augmented.wav",
    "start_sec": 0.0,
    "end_sec": 3.25,
    "speaker_label": "speaker-a",
}

record = EvaluationRecord.from_record(metadata_row)
transcript = ASRTranscript(text="hello from the future pipeline", confidence=0.91)
speaker = SpeakerDecision(speaker_label="speaker-a", confidence=0.88)
stats = RuntimeStats(total_sec=0.42, device="cpu")

output = PipelineOutput.from_record_and_transcript(
    record=record,
    transcript=transcript,
    speaker_decision=speaker,
    runtime_stats=stats,
)

utterance_row = output.to_utterance_prediction_row()
```

`utterance_row` is JSON-safe and contains only the fields required by
`predictions/utterances.jsonl`.

## Validation

The M1 contract tests check object creation, required-field validation,
identity preservation, JSON-safe serialization, mono defaults, time-ordering
validation, embedding dimension validation, and utterance row mapping.

