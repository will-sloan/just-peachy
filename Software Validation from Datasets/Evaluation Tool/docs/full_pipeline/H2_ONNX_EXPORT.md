# H2 FP32 ONNX export and parity

## Purpose and result

This document records deterministic FP32 ONNX export for the exact local H2
ReDimNet2-B2 and Pyannote Segmentation 3.0 assets. It also records component
and bounded full-pipeline desktop parity. It does not authorize threshold
retuning, implicit downloads, ARM64 readiness, or a scientific accuracy claim.

### Evidence status for the v17 autonomous program

The two exported graphs below remain present and match their recorded SHA-256
identities. Earlier full-pipeline comparisons are retained as bounded
predecessor engineering evidence, not as final parity proof for v17. The v17
controller must complete its predeclared
`H2_PORTABLE_ONNX_FP32_FROZEN_FIXTURE_PARITY` job after development selection
and bind fresh enrolled and empty-enrollment comparisons to the exact
`selected_runtime_snapshot`. The final package may report ONNX parity complete
only when that checksum-bound receipt validates. Until then, current v17
end-to-end ONNX parity is **PENDING**, while the historical bounded result
remains **PASS only for its recorded code identity**.

| Component | ONNX SHA-256 | Bytes | Input/output | Result |
|---|---|---:|---|---|
| ReDimNet2-B2 | `5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609` | 16,025,408 | `[1, dynamic samples] -> [1, 192]` | PASS |
| Pyannote Segmentation 3.0 | `b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a` | 5,925,265 | `[1, 1, 160000] -> [1, 589, 7]` | PASS |

Both use opset 18 and FP32. ONNX checker validation passes. Regeneration
produced stable graph hashes.

## Exact native inputs

- ReDimNet2 checkpoint SHA-256:
  `0545a29679a87fe1c662d2bbd05e3b3fe0d1b392832729abaa135e4079a2f77a`
- pinned ReDimNet hub source SHA-256:
  `325d5dfa4db8377ca76d71ecf4b652a2ebf54e77179c7ce50f77759b32de6ddd`
- pinned ReDimNet model source SHA-256:
  `3b6bb2b9e8a5766d1286ea18b76f94cfacdd6e895cf4b996efbaf5c5f146dc5b`
- Pyannote config SHA-256:
  `fa65a47a751602f04cc570135007d76859b69e8f9f1bfdf5878a5145980d4263`
- Pyannote weights SHA-256:
  `da85c29829d4002daedd676e012936488234d9255e65e86dfab9bec6b1729298`

Inference never downloads replacements. Export dependencies were installed
only into `.stage8-envs/redimnet2` and
`.stage8-envs/credential-diarization`: Torch 2.11 CPU, ONNX 1.22.0, ONNX
Runtime 1.29.0, and ONNX Script 0.7.1.

## Exporter decision

The preferred `torch_onnx_dynamo_v2` path was attempted first. ReDimNet2 hit a
data-dependent symbolic convolution guard; Pyannote SincNet hit an unsupported
clamp decomposition. Each failure is retained as JSON/log evidence. The
successful export was a separately invoked, versioned
`torch_onnx_legacy_v1` fallback. No code silently changes exporters.

## Predecessor component parity

ReDimNet2 parity used five deterministic durations and two real WAVs. Maximum
normalized absolute error was `8.546201615694526e-07`, maximum cosine distance
was `5.7553961596568115e-12`, and maximum pair-score error was
`9.650736662591974e-07`. Identity decisions and clustering coassignment matched
exactly.

Pyannote parity used three deterministic signals and two real WAVs. Maximum raw
absolute error was `0.00014543533325195312`; mean absolute error was
`7.695594590364859e-06`. Powerset/speech/overlap agreement was 1.0, maximum
boundary delta was zero frames, and downstream regions matched exactly.

The predecessor bounded end-to-end comparison used enrolled and
empty-enrollment 10-second native-vs-ONNX pairs. Its exact surfaces were
transcript text/words/states/labels, event order/types and nonnumeric semantic
payload, RTTM-equivalent speaker structure after cluster permutation, cluster
coassignment, and identity states/labels. Maximum enrolled identity score delta
was `1.7881393432617188e-07`; maximum boundary delta was
`1.7763568394002505e-15` seconds. Those values remain historical evidence and
must not be copied into the v17 result. The controller-managed v17 receipt is
the only final authority and preserves any failure rather than silently falling
back to predecessor scores.

## Run from PowerShell or Anaconda Prompt

```powershell
$Repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$Tool = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
$Out = Join-Path $Tool 'JustPeachyResults\full_pipeline\h2_complete_product_pipeline_v17\portability_artifacts'
Set-Location $Tool

& "$Repo\.stage8-envs\redimnet2\Scripts\python.exe" -m app.h2_portability export `
  --component redimnet2_b2_speaker_embedding `
  --onnx-path "$Out\redimnet2_b2_fp32.onnx" `
  --exporter torch_onnx_dynamo_v1

& "$Repo\.stage8-envs\credential-diarization\Scripts\python.exe" -m app.h2_portability export `
  --component pyannote_segmentation_3_0 `
  --onnx-path "$Out\pyannote_segmentation_3_0_fp32.onnx" `
  --exporter torch_onnx_dynamo_v1

& "$Repo\.venv\Scripts\python.exe" -m pytest tests\h2_portability -q
```

The controller tries the preferred Dynamo path first and records a separate,
versioned legacy export only if the preferred exporter fails for a retained
technical reason. No exporter changes silently. `--replace` is deliberate and
must be supplied to overwrite an existing graph. Full frozen parity and direct
portable-runtime commands are documented in `app/h2_portability/README.md`.

## Outputs

- controller-managed graphs, manifests, exporter evidence, component parity,
  and full-pipeline parity under
  `JustPeachyResults/full_pipeline/h2_complete_product_pipeline_v17/portability_artifacts`;
- predecessor factory evidence remains under its original dated directory and
  is never substituted for the v17 scheduled receipt;
- predecessor-code E2E summary SHA-256:
  `4d43145bfe4067e3708b4b3ac4f1484de8be6b0634ea1c6a2d31ad2890d6e3c8`;
- controller-managed large graphs under
  `results_root/portability_artifacts`, outside compact result ZIPs.
