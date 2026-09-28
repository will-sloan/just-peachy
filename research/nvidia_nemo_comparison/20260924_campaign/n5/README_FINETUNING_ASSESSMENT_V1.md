# Saved-corpus fine-tuning suitability audit

Purpose: assess the existing S4.5 synthetic-scenario/physical-capture bank for
possible future Nemotron diarization fine-tuning, without training or changing
the campaign's comparison. It counts scenario diversity, annotation readiness
and reuse of source clips, speaker keys and text across scenes and historical
partitions. Connected scene groups expose leakage in a naive random split.

Inputs: DATA_AUDIT_SUMMARY.json and CORPUS_CATALOGUE_240.csv plus the two private
hash-bound corpus/transcript audits. No waveform is decoded, no model loaded,
no data downloaded, no scene generated and no personal profile accessed.
The code reads on CPU14 below normal. It verifies the audit bindings; it does
not redundantly rehash the original 480 WAVs or rerun the accepted data audit.

Output: one aggregate JSON with counts, lineage grouping sizes and caveats,
without text, individual speaker IDs, voiceprints or audio. It is an assessment,
not a training manifest, accepted split, optimization result or trained model.
All original files remain unchanged; use a fresh output for changed inputs.

PowerShell:

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B assess_finetuning_data_v1.py --output FINETUNING_DATA_ASSESSMENT_V1.json
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B assess_finetuning_data_v1.py --output FINETUNING_DATA_ASSESSMENT_V1.json
```

The existing interpreter needs no activation/install. Study the resulting
groups before any future speaker/source-disjoint split; no automated split is
invented when reuse joins large parts of the bank. Source provenance and data
rights need separate review before any training job. Existing no-training,
saved-audio-only and powered-off-Pi constraints remain in force.
