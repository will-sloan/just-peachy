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

For AMI, diarization output is strongly recommended.

## For AMI specifically

The simplest first comparison modes are:
1. close-talk headset stream vs reference segments for the matching speaker
2. far-field Array1 stream vs projected reference segments for all speakers in the meeting
