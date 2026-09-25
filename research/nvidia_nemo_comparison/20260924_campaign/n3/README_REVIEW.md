# Verify and summarize completed N3 evidence

`review_completed.py` reads the exact completed A1 nominal and Controller plans,
the v4 native/reference results, the passing A2 final-state GUI panel and the
separate A3 two-core panel. It verifies plan/result hashes, required job statuses,
per-cell result hashes, complete/matched screen denominators, exact sample
accounting, regression/paced counts, GUI archive/closure checks, A1 service parity
and the final source suite. It does not run a model, open a device, alter evidence
or decide stage acceptance. Run after the final A3 plan has finished.

Inputs: `--local` is this campaign's private n3 directory. The versioned plan
names are explicit in the script; later derivatives require a new reviewed
script rather than silently following a different result. `--output` is a fresh
JSON file. Output contains numerical aggregates, hash/path references and
limitations, never raw captions, audio, vectors or weights. Do not overwrite a
previous review. EVIDENCE_REVIEW_COMPLETE describes these checks; final stage
acceptance additionally requires the human-readable report, source/configuration
freeze, limitations, handoff and verified Git backup.

The primary WER is summed word errors divided by summed reference words across
complete nonoverlap cases. Both tap rows and other reference classes remain
separate. The lexical scorer lowercases and removes ASCII punctuation; this is
not case/punctuation-sensitive verbatim WER. Controls retain false-word counts,
and overlap keeps only its explicitly labelled one-hypothesis diagnostic.
Raw private predictions remain available in the original bound artifacts.

The A1 paced coordinator has one preserved bookkeeping failure: its expected
count was four, while its frozen command and hash-bound manifest specified eight
files. The runner exited zero and completed all eight. The review admits this
specific discrepancy only after checking the exact original failure reason,
plan/result/event hashes, manifest binding, all eight job IDs, waveform hashes,
sample counts, gain/reset and paced delivery. It records a separate eight-file
acceptance receipt without changing the original FAILED coordinator record.
This is not a general failed-job override or new inference credit.

Resource summaries distinguish the CPU A0/A1 screens from native CUDA A2/A3
screens and keep native CPU panels separate. RSS is sampled process memory,
not full-stack or 2-GB system memory. First text is measured from source start,
including initial silence. For source-paced cases the review reports completion
time minus audio duration. It separately labels the original last-final-event
offset: a negative value means speech ended before trailing audio, not negative
flush latency. Actual A1 paced coverage is eight files; the inherited A0/A2/A3
paced panels each contain four. No expected words are removed for absent output.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n3/review_completed.py --local G:/Just_Peachy_N1/20260924_campaign/local/n3 --output G:/Just_Peachy_N1/20260924_campaign/local/n3/final-review-v1.json
```

CMD/Anaconda Prompt (no activation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/review_completed.py --local G:/Just_Peachy_N1/20260924_campaign/local/n3 --output G:/Just_Peachy_N1/20260924_campaign/local/n3/final-review-v1.json
```

Verification reads small result receipts and reports, not model payloads or full
event logs. Earlier executed scoring/GUI verifiers bind those larger artifacts.
The report retains those upstream receipts instead of inventing a new inference
or integrity pass. Private file paths in the report are references, not uploads.

`test_review_completed.py` runs six model-free checks of ratio-of-sums scoring,
overlap exclusion, missing/duplicate/unmatched cases, incomplete sample support,
changed evidence, false completed counts, exact eight-file manifest evidence and
negative endpoint interpretation.
From PowerShell use the same interpreter above with `-B
research/nvidia_nemo_comparison/20260924_campaign/n3/test_review_completed.py`.
The identical arguments work in CMD/Anaconda Prompt after the quoted interpreter
path. These tests use temporary JSON fixtures and launch no model or GUI.
