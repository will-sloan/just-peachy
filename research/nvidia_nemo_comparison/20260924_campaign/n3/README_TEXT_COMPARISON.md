# Punctuation and text comparison

`compare_text.py` applies the exact baseline P0 model to identical lexical
hypotheses from each completed ASR and diagnostically to existing isolated-clip
reference words. P1 native A2/A3 formatting is preserved in inference; the P0
comparison is a separate diagnostic. It measures lexical insertions/removals,
punctuation boundaries, eligible isolated-clip punctuation F1 and ITN changes.
It makes no conversation-level reconstruction-F1 claim. Existing reference text
is evaluator data only and never enters ASR, decoder bias or identity inference.

Inputs: frozen prototype, existing model root, completed ASR directories, truth
and verified ITN artifact. Outputs: small aggregate JSON/Markdown and a private
prediction/trace JSONL. Only aggregates are eligible for the public handoff.

PowerShell (CMD/Anaconda omit the leading `&`):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n3/compare_text.py --prototype <FROZEN_PROTOTYPE> --models-root C:/Users/amiri/JustPeachy/shared/models --truth G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/EVALUATOR_TRUTH.json --grammar G:/Just_Peachy_N1/20260924_campaign/local/n3/itn/export/itn_subset.json --run <A0_RUN> --run <A1_RUN> --run <A2_RUN> --run <A3_RUN> --output <FRESH_PRIVATE_TEXT_OUTPUT>
```

Each `--run` is an explicit completed directory from the N3 plan. Run after
numerical ASR work, with one CPU owner. Synthetic text fixtures test protected
words, contextual WD-40 and similar names; they create no new audio or personal
preferences. P2 remains unavailable unless exact official checkpoint lineage and
weight terms are verified. All unconstrained sentence rewriting is deferred.
