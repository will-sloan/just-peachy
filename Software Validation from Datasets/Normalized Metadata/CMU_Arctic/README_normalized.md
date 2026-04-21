# CMU ARCTIC Normalized Metadata README

## Dataset
- **Name:** CMU Arctic
- **Dataset ID:** `cmu_arctic`
- **Raw dataset root:** `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- utterance-level transcription
- WER-style comparison
- speaker-group slicing by gender and accent

## Evaluation unit
- **Unit:** one utterance audio file
- **Key:** `(speaker_id, utterance_id)`

## Transcript source precedence
1. per-speaker `etc/txt.done.data`
2. optional fallback to global `cmuarctic_data.txt` if explicitly enabled

## Raw structure assumptions
Each speaker folder is expected to contain:
- `wav/`
- `etc/txt.done.data`

## Normalization decisions
- raw WAV files were not changed
- raw transcript files were not changed
- original transcript text is preserved
- normalized transcript text is stored separately
- speaker gender/accent metadata comes from `cmu_arctic_speaker_metadata.yaml`

## Output files
- `recordings.parquet`
- `utterances.parquet`
- `normalization_log.csv`

## Summary statistics
- total speaker folders found: `18`
- total transcript rows parsed: `15583`
- total normalized recordings emitted: `15583`
- total warnings/issues logged: `20`

## Known issues
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_bdl_arctic | utt=arctic_a0507 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_eey_arctic | utt=arctic_a0282 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0108 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0130 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0208 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0341 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0392 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0456 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0512 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0542 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0561 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0564 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0565 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0568 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0575 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0576 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_a0578 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_b0223 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_b0229 | details=WAV exists without per-speaker transcript row.
- [WARNING] missing_transcript_for_audio | speaker=cmu_us_jmk_arctic | utt=arctic_b0313 | details=WAV exists without per-speaker transcript row.
