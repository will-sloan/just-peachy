# Sherpa LibriSpeech+GigaSpeech Zipformer 2023-06-21

## Purpose and immutable identity

This integration adds the English checkpoint
`csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-21` as the distinct Just-Peachy
component `sherpa_onnx_libri_giga_zipformer_2023_06_21`. It does not replace or alias
the Original Sherpa 2023-06-26 component or the Sherpa 20M component.

The upstream model is a streaming Zipformer Transducer converted from
`marcoyang/icefall-libri-giga-pruned-transducer-stateless7-streaming-2023-04-04` and was
trained on LibriSpeech plus GigaSpeech. It supports English only and has approximately
70,369,391 parameters. For comparison with the completed large study, the Just-Peachy
campaign uses the existing segment contract: upstream native streaming capability is
true, while campaign `streaming` is false.

## Inputs and outputs

The input archive is the official k2-fsa Sherpa-ONNX release:

`https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-en-2023-06-21.tar.bz2`

It is 506,956,414 bytes with SHA-256
`455f40e556aa2b20ac9d3bffd603b58002075c1193b4070938540c11efe0a4da`.
Bootstrap writes the ignored local output directory
`models/cache/sherpa_onnx/asr/sherpa-onnx-streaming-zipformer-en-2023-06-21`.
The cached extracted package is 546,279,902 bytes and its deterministic tree SHA-256 is
`8ad24aa63b28ffb15a5b91461e4d05b19e3237c3f5ca7a6d3557d0fac0a9dfdf`.

Result-affecting files are:

| File | Precision/purpose | Bytes | SHA-256 |
|---|---|---:|---|
| `encoder-epoch-99-avg-1.int8.onnx` | INT8 encoder | 187,823,992 | `32c98281c7bd8b63e3e142d007251b37f120572e8fdea9a4f5a79ce22b10ec4f` |
| `decoder-epoch-99-avg-1.onnx` | FP32 decoder | 2,092,566 | `9da02b77cb08826756ec6a88635f35a40374e4164e7c6359121a9145958a6ceb` |
| `joiner-epoch-99-avg-1.int8.onnx` | INT8 joiner | 259,335 | `831477d390e59a61f1b6a6f763b9903e6c6366ff6034f1ddba613be82637122f` |
| `tokens.txt` | token table | 5,048 | `49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb` |

The active files total 190,180,941 bytes. Runtime settings are CPU provider, two threads,
16 kHz audio, 80-dimensional features, `greedy_search`, four maximum active paths, and
0.66 seconds tail padding. Inference performs no network access.

## Setup and bounded qualification

Open Anaconda Prompt or PowerShell at the repository root. The existing pinned `onnx`
environment is reused; do not upgrade it for this model.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.stage8-envs\onnx\Scripts\python.exe scripts\bootstrap_models.py `
  --cache-root models\cache `
  --sherpa-libri-giga
```

The command verifies the archive and extracts the model. Its inputs are the official
archive URL and expected hash in `scripts/bootstrap_models.py`; its output is the local
cache directory above. Model binaries are ignored by Git.

To repeat only bounded qualification from the Evaluation Tool directory:

```powershell
Set-Location 'Software Validation from Datasets\Evaluation Tool'
..\..\.stage8-envs\onnx\Scripts\python.exe scripts\qualify_extended_backends.py `
  --profile onnx `
  --backend sherpa_onnx_libri_giga_zipformer_2023_06_21 `
  --audio '..\..\models\cache\sherpa_onnx\asr\sherpa-onnx-streaming-zipformer-en-2023-06-21\test_wavs\0.wav' `
  --output runs\edge_backend_qualification\onnx-libri-giga.json
```

The input is one known 6.625-second, 16 kHz mono WAV plus the qualifier's generated
one-second silence control. The output is schema-validated evidence containing two
repeated real transcripts, silence behavior, package/environment identity, exact config
identity, and asset hash observations. This is not the 32-scenario campaign.

## Campaign dry plan and status

From the repository root, dry-plan only the disabled-by-default campaign:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 `
  -Action Plan `
  -CampaignId campaign_edge_lg_shgiga_v1
```

The input catalog is
`Software Validation from Datasets/Evaluation Tool/benchmarks/edge_research/scenarios_edge_large_sherpa_libri_giga.jsonl`.
The output is a console-only dry plan of exactly 32 scenarios. No inference or campaign
state is started. Status is also read-only:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 `
  -Action Status `
  -CampaignId campaign_edge_lg_shgiga_v1
```

## Licensing and interpretation

- Model weights and source checkpoint publish Apache-2.0 license metadata.
- Sherpa-ONNX is Apache-2.0; ONNX Runtime is MIT.
- LibriSpeech is published through OpenSLR under CC BY 4.0.
- GigaSpeech access terms say SpeechColab does not own the source-audio copyrights and
  describe the database as non-commercial research/education use. Its dataset card also
  says trained models may potentially be eligible for commercial licensing/use subject
  to fair-use, underlying-rights, and use-specific review.

Accordingly, the registry records the model license as permissive and separately records
`commercial_deployment_review = required_due_to_gigaspeech_training_provenance`. It does
not label the model prohibited or commercially cleared. LibriSpeech is a known training-
domain overlap in this evaluation, so near/in-domain results must be separated in later
interpretation from genuinely unrelated datasets.

Source records are frozen in
`configs/automated_evaluation/model_asset_registry.v1.yaml`, including the exact model
and source-checkpoint revisions, official Sherpa archive, Sherpa/ONNX Runtime licenses,
OpenSLR LibriSpeech record, and current GigaSpeech dataset card/access notice.
