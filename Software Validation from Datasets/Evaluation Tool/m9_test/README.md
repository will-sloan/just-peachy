# M9 Speaker Embedding Test Folder

This folder is a local workspace for testing the M9 speaker embedding component without writing outputs to `/private/tmp`.

## Contents

- `audio/` contains sample WAV files for smoke checks.
- `labels.csv` maps each sample file to a speaker label for same-speaker vs different-speaker similarity reporting.
- `fake_embeddings.jsonl` is produced by the deterministic fake backend smoke command.
- `fake_embedding_quality.md` is produced by the deterministic fake backend smoke command.
- `speechbrain_embeddings.jsonl` is the recommended output path for a real SpeechBrain ECAPA run.
- `speechbrain_embedding_quality.md` is the recommended report path for a real SpeechBrain ECAPA run.

## Labels CSV Format

`labels.csv` uses this format:

```csv
file_name,speaker_label
a1.wav,a
a2.wav,a
b1.wav,b
```

The embedding script can run without labels, but labels are needed for the similarity distribution section of the report.

## Deterministic Fake Backend Smoke Check

Run this command from `Evaluation Tool` folder.

Use this first to confirm the script, serialization, labels, and report generation work:

```bash
python scripts/embed_speaker_folder.py \
  m9_test/audio \
  --backend fake \
  --output m9_test/fake_embeddings.jsonl \
  --report m9_test/fake_embedding_quality.md \
  --labels-csv m9_test/labels.csv \
  --dimension 8 \
  --min-duration-sec 0.1 \
  --run-id m9_fake_local
```

Expected result:

- The command exits with status `0`.
- `m9_test/fake_embeddings.jsonl` contains one JSONL row per audio file.
- Each successful row has `"status": "ok"`, `"dimension": 8`, and a normalized vector.
- `m9_test/fake_embedding_quality.md` includes the similarity distribution.

## Real SpeechBrain ECAPA Smoke Check

Use this after `speechbrain` is installed in the repository `.venv`:

```bash
python scripts/embed_speaker_folder.py \
  m9_test/audio \
  --backend speechbrain \
  --allow-model-downloads \
  --output m9_test/speechbrain_embeddings.jsonl \
  --report m9_test/speechbrain_embedding_quality.md \
  --labels-csv m9_test/labels.csv \
  --min-duration-sec 0.1 \
  --run-id m9_speechbrain_local
```

Expected result:

- The command exits with status `0`.
- `m9_test/speechbrain_embeddings.jsonl` contains rows with `"status": "ok"`.
- Successful rows should have `"dimension": 192`.
- Vectors should have L2 norm near `1.0`.
- `m9_test/speechbrain_embedding_quality.md` includes runtime, memory, short-segment, and similarity summaries.

If you do not want downloads, remove `--allow-model-downloads`. The command will only work if SpeechBrain ECAPA assets are already available locally at the configured cache path.

## Quick Inspection Commands

```bash
head -n 1 m9_test/fake_embeddings.jsonl
head -n 1 m9_test/speechbrain_embeddings.jsonl
sed -n '1,160p' m9_test/fake_embedding_quality.md
sed -n '1,160p' m9_test/speechbrain_embedding_quality.md
```

## Run Registered Smoke Checks

The centralized smoke runner copies the existing smoke commands into one registry without removing them from their original report or source locations. Run these commands from the `Evaluation Tool` folder.

List every registered smoke check:

```bash
python tests/run_smoke_tests.py --list
```

Run the default short set:

```bash
python tests/run_smoke_tests.py
```

Run checks by group:

```bash
python tests/run_smoke_tests.py --group quick
python tests/run_smoke_tests.py --group dataset
python tests/run_smoke_tests.py --group model
python tests/run_smoke_tests.py --group gui
python tests/run_smoke_tests.py --group all
```

Run one smoke check by name:

```bash
python tests/run_smoke_tests.py --only m6-segmentation-direct
python tests/run_smoke_tests.py --only m7-asr-fixed-direct
python tests/run_smoke_tests.py --only m9-fake
python tests/run_smoke_tests.py --only m9-speechbrain-cached
```

The default set currently includes direct M6 segmentation, direct M7 ASR, deterministic M9 fake embedding, and cached M9 SpeechBrain embedding smoke checks. Dataset, model, and GUI checks can take longer or require local datasets/model assets. Missing optional assets are reported as skipped instead of pretending the smoke ran.

The SpeechBrain smoke uses `models/cache/speechbrain/spkrec-ecapa-voxceleb` and does not pass `--allow-model-downloads`. If the cache is missing, the runner reports the check as skipped.

## Notes

This folder is for local validation artifacts. It does not change the Evaluation Tool runner contract or `predictions/utterances.jsonl`.
