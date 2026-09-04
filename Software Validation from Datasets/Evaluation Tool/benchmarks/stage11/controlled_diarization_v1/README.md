# Controlled diarization v1 frozen package

This directory contains the small, versioned metadata needed to reproduce and
score the controlled anonymous-speaker benchmark. Rendered WAV files are not
stored in Git. Their default physical root is
`<Evaluation Tool>\JustPeachyGeneratedData\controlled_diarization_v1`; set
`JP_GENERATED_DATA_ROOT` to relocate that base.

The implemented panel contains 8 non-scientific smoke recordings, 60
development recordings, and 120 evaluation recordings. Development and
evaluation speakers are disjoint. Every evaluation speaker, source clip, and
mixture is marked as protected holdout evidence. Five independent source clips
per selected speaker are reserved for later identity-overlay enrollment.

Rapid cases target 48 seconds because the frozen older-adult Common Voice pool
has relatively few naturally short utterances. Standard and relaxed cases
target 60 seconds. Every case must remain within 45–75 seconds, uses complete
utterances after conservative boundary-only trimming, and prohibits exact clip
reuse within or across tiers.

The `backchannel` design factor is realized and reported as `short_overlap`;
the generator does not inspect or publish transcript text and therefore makes
no semantic backchannel claim.

Prepare or validate from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File `
  "Software Validation from Datasets\Evaluation Tool\scripts\run_controlled_diarization.ps1" `
  -Action Prepare

powershell -ExecutionPolicy Bypass -File `
  "Software Validation from Datasets\Evaluation Tool\scripts\run_controlled_diarization.ps1" `
  -Action Validate
```

See `app/controlled_diarization/README.md` and
`docs/automated_evaluation/controlled_diarization_benchmark.md` for inputs,
outputs, Anaconda Prompt, Command Prompt, PowerShell, pipeline IDs, analysis,
and restart behavior.
