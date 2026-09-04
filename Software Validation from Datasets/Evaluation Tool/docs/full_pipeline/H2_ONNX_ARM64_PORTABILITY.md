# H2 ONNX and ARM64 portability evidence

## Outcome

The exact ReDimNet2-B2 and Pyannote Segmentation 3.0 native checkpoints were
exported as FP32 ONNX and passed a frozen bounded parity contract on
Windows/x86-64. ARM64 is prepared but not qualified.

The graph files still match the hashes below. However, the August 24
full-pipeline parity receipt belongs to its recorded predecessor code identity;
four of its six frozen result-affecting source hashes no longer match the v17
runtime source. It is therefore supporting evidence only. The autonomous v17
program must produce a fresh checksum-bound enrolled and empty-enrollment
full-pipeline parity result after development selection before any final
current-runtime parity claim is made.

| Component | ONNX SHA-256 | Shape | Exporter | Parity |
|---|---|---|---|---|
| ReDimNet2-B2 | `5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609` | `[1, dynamic samples] -> [1, 192]` | explicit legacy fallback | PASS |
| Pyannote Segmentation 3.0 | `b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a` | `[1, 1, 160000] -> [1, 589, 7]` | explicit legacy fallback | PASS |

The preferred Torch 2.11 Dynamo exporter was attempted first and did not
succeed. ReDimNet2 hit a data-dependent symbolic convolution guard. Pyannote's
SincNet filterbank hit an unsupported clamp decomposition. Failure evidence
was retained; fallback was never automatic.

ReDim parity spans five deterministic durations from 0.5 to 10 seconds plus
two real speech files. Maximum normalized absolute error is
`8.546201615694526e-07`, maximum cosine distance is
`5.7553961596568115e-12`, and maximum pair-score error is
`9.650736662591974e-07`. Frozen open-set decisions and deterministic
clustering coassignment match exactly.

Pyannote parity spans three deterministic 10-second signals plus two real
speech files. Powerset class, speech activity, overlap activity, onset/offset
boundaries, and downstream regions match exactly. The real cases exercise
non-empty speech boundaries.

The common factory also has a separately versioned
`H2_PORTABLE_ONNX_FP32` profile. `H2_REFERENCE` remains the default and its
native construction is unchanged. After freezing the semantic normalization
and tolerances, two predecessor same-input 10-second pairs were executed:

- enrolled ReDimNet2 profile: end-to-end PASS with identity evidence and label
  transitions exercised;
- empty enrollment: end-to-end PASS for anonymous/Unknown behavior.

Both pairs match exactly for event order/types and nonnumeric semantic payload,
transcript text/words/states/labels, RTTM-equivalent speaker structure after
cluster permutation, and cluster coassignment. The enrolled case also matches
identity states and labels exactly. The largest identity score delta was
`1.7881393432617188e-07`; the largest source-boundary delta was
`1.7763568394002505e-15` seconds. The earlier exploratory factory runs were
recorded as engineering smokes and excluded from the final parity decision.

## Scientific boundary

This evidence proves bounded desktop component and full-pipeline parity. It is
not an accuracy campaign, ARM64 numerical parity, physical microphone test, or
Raspberry Pi resource qualification. No scientific threshold, enrollment rule,
clustering threshold, or segmentation policy was retuned.

## Platform classification

`PORT_REQUIRES_WORK`

ONNX Runtime advertises Linux ARM64, Sherpa documents embedded Linux ARM64 and
ALSA operation, and the remaining application dependencies are likely
portable. Factory wiring and a headless portable launch path now exist.
However, actual wheel resolution, ALSA/PipeWire, service lifecycle, ARM64
numerical parity, sustained streaming, and the 2 GiB budget must be validated
on the exact Raspberry Pi OS image and hardware.

The package is under `deployment/h2_arm64`, and operating instructions are in
`app/h2_portability/README.md` and `deployment/h2_arm64/README.md`.

## Autonomous controller contract

The H2 program controller delegates `onnx_export`, `onnx_parity`, and
`linux_portability` to
`app.h2_portability.controller_adapter.execute_portability_job`. The adapter
requires the final `selected_runtime_snapshot` and checksum-binds it into every
job receipt. Large graphs remain under `results_root/portability_artifacts`,
outside the compact summary ZIP. The parity job cannot complete without both
component reports and fresh enrolled plus empty-enrollment full-pipeline
passes. The Linux job can complete only the package-preparation scope and must
continue to report `PORT_REQUIRES_WORK` and
`linux_arm64_ready_claimed=false` until target hardware evidence exists.
