# Early Output Contract Notes for Later Evaluation

This file is not yet the final model-output contract. It is the initial planning note
for the later comparison tool.

## Later model output should include

### Minimum utterance-level output
Suggested file: `utterances.jsonl`

One row per predicted utterance:
- `recording_id`
- `utt_id`
- `start_sec`
- `end_sec`
- `speaker_label`
- `text`

### Optional word-level output
Suggested file: `words.jsonl`

One row per predicted word:
- `recording_id`
- `utt_id`
- `start_sec`
- `end_sec`
- `word`
- `speaker_label`
- `confidence`

### For VOiCES specifically

The simplest future comparison against VOiCES is:
- one distant/noisy input WAV
- one expected reference utterance transcript
- one file-level speaker label
- one room / distractor / microphone condition group

No turn-level diarization is required for this dataset.
