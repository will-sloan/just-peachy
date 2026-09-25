# Regenerate the bank for the accepted sixteen-composition source

`prepare_v2.py` is a derivative of prepare.py. The original six-key adapter map
could not describe the new 16-entry catalog. V2 uses the composition builder's
strict inventory, verifies manifest hashes and all 16 A/D/E tuples, and binds
that inventory code. Its default source is the accepted N3-derived n4-catalog-v3.
Corpus verification, same-pass tap pairing, gain, truth separation, dependency
groups and deterministic paced-panel selection are unchanged.

Inputs: `--local` is the existing private campaign directory (default below),
`--source` is the fresh accepted-source derivative's prototype, and `--output`
is a fresh private preparation folder. Outputs are the 480-file audio-only bank,
24-file paced panel, eight regressions, private evaluator strata/provenance,
16-row implementation matrix and binding receipt. The matrix still records
zero completed integrated cells and 7,680 NOT_TESTED; implemented catalog entries
are not numerical compatibility or deployment qualification.

PowerShell, from the campaign worktree:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n4/prepare_v2.py --source G:/Just_Peachy_N1/20260924_campaign/local/releases/n4-catalog-v3/prototype --output G:/Just_Peachy_N1/20260924_campaign/local/n4/preparation-v2
```

CMD/Anaconda Prompt (no activation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/prepare_v2.py --source G:/Just_Peachy_N1/20260924_campaign/local/releases/n4-catalog-v3/prototype --output G:/Just_Peachy_N1/20260924_campaign/local/n4/preparation-v2
```

Keep the original preparation-v1 and all old releases intact. Repeated runs use
fresh output versions. This command performs file hashing and WAV-header checks,
not model inference, playback, capture, GUI launches or hardware contact. Run
hashing outside a candidate's timed/resource evaluation. The final check compares
all five data/provenance payloads byte-for-byte with preparation-v1 and verifies
16 populated unique matrix entries with zero execution credit.

Evaluator strata and provenance remain private because they contain source and
actor metadata. Never pass them into prediction or add them to Git. The audio-only
manifest exposes only the eight admitted audio fields to the predictor.
