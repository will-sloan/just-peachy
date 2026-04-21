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

### Optional diarization output
Suggested file: `segments.rttm`

This is not necessary for CMU ARCTIC itself, but is necessary for AMI and CHiME-6.

## For CMU ARCTIC specifically

The simplest future comparison against CMU ARCTIC is:
- one input WAV
- one expected reference utterance
- one predicted utterance transcript

No diarization is required for this dataset.
