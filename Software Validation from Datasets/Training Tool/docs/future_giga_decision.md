# Deferred Giga decision gate

Phase 5 performs no Giga training, adapter work, full fine-tuning, GigaSpeech
download, or legacy adapter implementation. Giga remains a frozen evaluation
baseline.

After Phase-7 evaluation and Phase-8 analysis, native Giga full fine-tuning may
be investigated only if the existing Giga baseline is materially stronger than
the best Original adapter on important product domains, if enough performance
headroom remains to justify a ceiling experiment, or if the product decision
requires an explicit AGE/ROBUST adaptation result from the strongest current
initialization.

If that gate is activated, begin with
`GIGA_NATIVE_FULL_FINETUNE_FEASIBILITY_CANARY` using the legacy
`pruned_transducer_stateless7_streaming_multi` checkpoint and `AGE_ROBUST`.
Verify RTX 3080 feasibility before considering only `G-AGE-ROBUST-FT` and,
optionally, `G-AGE-ROBUST-CMU-FT`. Do not create a custom legacy adapter.
