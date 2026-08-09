# CMU Arctic speaker protocol: seed 3800, version 1

## Purpose

This folder freezes a deterministic, leakage-controlled selection of real CMU Arctic audio for speaker enrollment, known-speaker probes, and unknown-speaker rejection. It references the existing dataset audio in place; it does not copy or alter source audio.

The selection is a prepared data artifact, not evidence that speaker recognition has passed CPU or CUDA qualification.

## Inputs

- `Software Validation from Datasets/Normalized Metadata/CMU_Arctic/utterances.parquet`
- CMU Arctic WAV files under `Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic/`
- deterministic seed `3800`

Only utterances at least 1.0 second long with non-empty normalized text are eligible. Speakers are split deterministically and stratified by accent group. Utterances are ordered using SHA-256 identities derived from the seed, speaker ID, and utterance ID.

## Outputs

- `selection_manifest.json`: protocol identity, source metadata checksum, split policy, known and unknown speakers, counts, and the checksum of `items.jsonl`.
- `items.jsonl`: 60 clean enrollment items, 120 known-speaker clean probes, and 60 held-out-speaker clean probes. Every row includes its source-relative path and source-audio SHA-256.
- `enrollment_db_speechbrain_ecapa.json`: an `m10.enrollment_db.v1` database containing 12 known speakers, five real 192-dimensional SpeechBrain ECAPA exemplars per speaker, and no probe or held-out-speaker audio.
- `enrollment_reports/`: the existing enrollment workflow's validation report for each enrolled speaker.

Known speakers have five enrollment utterances and ten disjoint probe utterances. Held-out speakers have ten probes and no enrollment utterances. Later noisy or reverberant probes must reuse these exact probe identities. The literal prediction label `Unknown` must be retained and scored.

## Validation

From an Anaconda Prompt or PowerShell opened at the repository root:

```powershell
.\.venv\Scripts\python.exe -c "import hashlib,json,pathlib; p=pathlib.Path(r'Software Validation from Datasets/Evaluation Tool/artifacts/speaker_protocol/cmu_arctic_seed3800_v1'); m=json.loads((p/'selection_manifest.json').read_text(encoding='utf-8')); b=(p/'items.jsonl').read_bytes(); rows=[json.loads(x) for x in b.splitlines()]; assert hashlib.sha256(b).hexdigest()==m['items_sha256']; assert len(rows)==240; assert sum(x['role']=='enrollment' for x in rows)==60; assert sum(x['role']=='probe' and x['speaker_partition']=='known' for x in rows)==120; assert sum(x['role']=='probe' and x['speaker_partition']=='unknown' for x in rows)==60; print('speaker protocol selection: PASS')"
```

Expected result:

```text
speaker protocol selection: PASS
```

The existing enrollment workflow created the database from only the 60 enrollment rows using runtime model ID `speechbrain_ecapa`. Artifact validation passed with 12 speakers, 60 exemplars, one consistent model ID, and 192-dimensional embeddings. Probe rows must never be added to that database.
