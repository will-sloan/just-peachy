# Run actual N3 ASR cells

`run_asr.py` loads one admitted model once and creates fresh recurrent state for
each independent saved file. Inputs: immutable prototype, strict audio-only
manifest, model roots/binding and runtime selection. Outputs: private complete
partial/final JSONL, per-cell JSON, a full source/config lock and aggregate result.
No truth, speaker boundaries, names or expected text enter the inference process.

PowerShell baseline command, from the campaign worktree:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py research/nvidia_nemo_comparison/20260924_campaign/n3/run_asr.py --prototype G:/Just_Peachy_N1/20260924_campaign/local/releases/n3-common-v2/prototype --audio-manifest G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/AUDIO_ONLY.json --models-root C:/Users/amiri/JustPeachy/shared/models --output G:/Just_Peachy_N1/20260924_campaign/local/n3/screen/A0 --variant A0 --runtime sherpa --cpu 4
```

CMD or Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research/nvidia_nemo_comparison/20260924_campaign/n3/run_asr.py --prototype G:/Just_Peachy_N1/20260924_campaign/local/releases/n3-common-v2/prototype --audio-manifest G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/AUDIO_ONLY.json --models-root C:/Users/amiri/JustPeachy/shared/models --output G:/Just_Peachy_N1/20260924_campaign/local/n3/screen/A0 --variant A0 --runtime sherpa --cpu 4
```

Native: set `--variant A2` or `A3`, `--runtime native`, and `--binding` to the
verified native JSON. Reference: use the isolated NeMo Python in README_REFERENCE,
`--runtime reference --reference-model <exact.nemo> --reference-source <pinned NeMo>`.
These argument substitutions are identical in PowerShell and Anaconda Prompt.
Use a fresh output directory for each model/runtime/profile/source/delivery mode.
Add `--paced` for an independent real-time producer with a bounded 120-second
journal. Otherwise this is accelerated causal inference and cannot establish
live latency. `--job-id` (repeatable) and `--limit` select explicit smoke panels.

Do not run these commands against a live mutable source tree. The example
release is created only after checks; its absence means it is not admitted yet.
Do not launch while N2 owns both numerical slots. Only one GPU owner may run.
Resume accepts only complete cells with the same full contract and unchanged
event hashes. Failed/partial cells are preserved and require a fresh run path.
No original audio is copied, deleted or played. Keep output transcripts private.
