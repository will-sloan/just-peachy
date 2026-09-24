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

`verify_archive(path)` is the imported verifier. There is deliberately no prune
command: active N2/N3 evidence remains at its exact admitted paths. Before N4
full-bank execution, integrate archive-aware readers and a verified bounded
per-cell lifecycle in a new admission. A successful compression probe alone
does not make the full matrix's disk budget feasible. Preserve 75 GiB free on G
and 50 GiB on C, and the campaign's 80-GiB new allocation ceiling.
