# CHiME-6 Normalized Metadata README

## Dataset
- **Name:** CHiME-6
- **Dataset ID:** `chime6`
- **Raw dataset root:** `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CHiME 6`

## Included splits
- `train`
- `dev`
- `eval`

## Normalization decisions
- raw WAV files were not changed
- raw JSON files were not changed
- original transcript text is preserved
- normalized transcript text is stored separately
- `text_norm` removes bracketed events such as `[laughs]`, `[noise]`, and `[inaudible ...]`
- `text_norm` also lowercases text, removes punctuation, and collapses whitespace
- overlap is preserved
- train JSON does not include `ref` / `location`, so those fields are left empty there
- dev/eval `ref` and `location` are preserved when present
- bracketed event tags are kept in `text_original` and removed from `text_norm`

## Output files
- `recordings.parquet`
- `utterances.parquet`
- `segments.parquet`
- `normalization_log.csv`

## Summary statistics
- total included splits found: `3`
- total normalized audio streams indexed: `540`
- total transcript segments emitted: `98432`
- total warnings/issues logged: `0`

## Known issues
- none
