# AMI Normalized Metadata README

## Dataset
- **Name:** AMI Meeting Corpus
- **Dataset ID:** `ami`
- **Raw dataset root:** `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\AMI Meeting Corpus`
- **Annotation root used:** `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\AMI Meeting Corpus\ami_manual_1.6.1`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- speaker-attributed transcription
- WER-style comparison
- segmentation / utterance-level comparison
- close-talk vs far-field comparison
- meeting-level and stream-level analysis

## Evaluation units
- **Words:** XML word tokens from `words/*.words.xml`
- **Utterances/segments:** XML segments from `segments/*.segments.xml`
- **Recordings:** headset streams and `Array1-*` meeting-level streams

## Streams included
- individual headset channels
- `Array1-01` through `Array1-08` where present

## Normalization decisions
- raw WAV files were not changed
- raw XML annotations were not changed
- original transcript text is preserved
- normalized transcript text is stored separately
- `meetings.xml` is used for agent-to-channel mapping
- `participants.xml` is used for speaker metadata where available
- segment text is reconstructed from inclusive word-ID ranges in the corresponding words XML

## Output files
- `recordings.parquet`
- `utterances.parquet`
- `words.parquet`
- `segments.parquet`
- `meetings.parquet`
- `participants.parquet`
- `normalization_log.csv`

## Summary statistics
- total meetings parsed: `171`
- total recording streams emitted: `2034`
- total segment/utterance rows emitted: `834429`
- total word rows emitted: `1207406`
- total warnings/issues logged: `16`

## Known issues
- [WARNING] missing_audio_stream | meeting=IS1003b | agent= | stream=array:Array1-01 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1003b | agent= | stream=array:Array1-02 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1003b | agent= | stream=array:Array1-03 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1003b | agent= | stream=array:Array1-04 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1003b | agent= | stream=array:Array1-05 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1003b | agent= | stream=array:Array1-06 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1003b | agent= | stream=array:Array1-07 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1003b | agent= | stream=array:Array1-08 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1007d | agent= | stream=array:Array1-01 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1007d | agent= | stream=array:Array1-02 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1007d | agent= | stream=array:Array1-03 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1007d | agent= | stream=array:Array1-04 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1007d | agent= | stream=array:Array1-05 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1007d | agent= | stream=array:Array1-06 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1007d | agent= | stream=array:Array1-07 | details=Expected audio stream file not found.
- [WARNING] missing_audio_stream | meeting=IS1007d | agent= | stream=array:Array1-08 | details=Expected audio stream file not found.
