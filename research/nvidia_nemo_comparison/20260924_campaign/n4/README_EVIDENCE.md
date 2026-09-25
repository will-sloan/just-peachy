# Lossless evidence archive

`evidence_archive.py` packs a completed Controller cell's exact checkpoint-bound
JSON/JSONL evidence into a new ZIP. It rehashes every input, stores each distinct
content hash once, preserves original relative paths in a manifest, and reads
every archived byte back to verify hash and size. No source file is changed or
deleted. The archive can contain full transcripts and research voice vectors:
keep it private, outside Git and the public handoff ZIP.

Inputs: `--result` is an existing completed attempt's RESULT.json with an adjacent
parent CHECKPOINT.json; `--output` is a fresh private ZIP path. Outputs: the ZIP
and `.receipt.json` describing byte counts, ratio and verification. It uses CPU4/
BelowNormal. Only completed checked, hash-bound files inside the cell are admitted.

Choose a verified completed result path from its RESULT_INDEX (the example value
below is illustrative). PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\evidence_archive.py --result 'G:\path\to\completed\attempt\RESULT.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\storage\cell-v1.zip'
```

CMD/Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\evidence_archive.py --result G:\path\to\completed\attempt\RESULT.json --output G:\Just_Peachy_N1\20260924_campaign\local\n4\storage\cell-v1.zip
```

`verify_archive(path)` is the imported verifier. There is no prune command:
active N2/N3 evidence remains at its exact admitted paths. Before N4 full-bank
execution, integrate a verified bounded per-cell lifecycle in a new admission.
A successful compression probe alone does not make the full matrix's disk
budget feasible. Preserve 75 GiB free on G and 50 GiB on C, and the campaign's
80-GiB new allocation ceiling.

## Read and score archived evidence

`evidence_reader.py` provides `ControllerEvidence(result, archive_binding=None)`.
Inputs are a completed Controller result dictionary and optionally the archive's
exact path/SHA-256/byte binding. Outputs are verified bytes, decoded JSON and a
JSONL line iterator. With an archive, it validates every object and the original
RESULT.json, then reads the requested bound members directly without extracting
files. Original absolute paths must belong to the result's attempt directory.
Changed, duplicate, outside or unbound evidence is rejected. With no archive it
rehashes the original files. No model, audio device or inference is involved.

`score_controller.py --archive-index PATH` accepts a private JSON index:

```json
{
  "schema": "n4-archive-index-v1",
  "archives": {
    "ORIGINAL_RESULT_SHA256": {
      "execution_result": {"path": "ORIGINAL_RESULT_PATH", "sha256": "ORIGINAL_RESULT_SHA256", "bytes": 123},
      "archive": {"path": "VERIFIED_PRIVATE_ZIP_PATH", "sha256": "ZIP_SHA256", "bytes": 456}
    }
  }
}
```

Copy actual bindings from the archive receipt; placeholders above are schema
examples. Unlisted results use original files. Listed results must validate the
archive; an invalid archive never falls back silently. Keep RESULT_INDEX,
ADMISSION, RESULT.json and CHECKPOINT.json at their original paths. This reader
does not authorize deleting original evidence. Scorer outputs bind the archive
index, ZIPs, execution results and reader/metric source. Existing score semantics
and missing/failed counts are unchanged; see README_SCORING.md for all required
arguments.

`test_evidence_reader.py` tests exact prediction/metric equality after removing
only its temporary fixture files, overhang preservation, changed live/archived
bytes, a different execution result, duplicate and outside/unbound paths. Two
additional tests exercise the full scorer's archive index and reject a
misbound result. All 35 N4 tests passed. It
does not remove or modify campaign data. `check_archive_reader.py` performs the
same equality check against an existing real completed cell and its verified
archive, using the pinned metric environment. Inputs: archive receipt,
evaluator-only truth and a fresh output path. Output: a redacted JSON receipt
with hashes, equality flags and zero new inference/N4 execution credit. It reads
private evidence without printing transcripts, extracting the archive or
changing source files. Run the real check outside candidate resource tests.

PowerShell, from the worktree:

```powershell
$py='G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe'
& $py -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n4 -p 'test*.py'
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n4/check_archive_reader.py --receipt G:/Just_Peachy_N1/20260924_campaign/local/n4/storage/d1e0-first-cell-v1.receipt.json --truth G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/EVALUATOR_TRUTH.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/storage/reader-check-v1.json
```

CMD/Anaconda Prompt (no activation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe" -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n4 -p "test*.py"
"G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/check_archive_reader.py --receipt G:/Just_Peachy_N1/20260924_campaign/local/n4/storage/d1e0-first-cell-v1.receipt.json --truth G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/EVALUATOR_TRUTH.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/storage/reader-check-v1.json
```

Choose a fresh output version for a repeat. The historical compression receipt's
`portable_cache_reader_integrated=false` describes the earlier probe and remains
unchanged; the separate reader check records this later implementation.
ARCHIVE_READER_CHECK.json records the successful read-only real-cell check:
predictions and pinned metric outputs match exactly, with zero new model calls,
extraction, source modification/deletion or N4 integrated execution credit.
