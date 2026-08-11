# Machine A CUDA qualification report

Date: 2026-08-10  
Scope: Whisper Base through the ordinary Evaluation Tool on Machine A  
Decision: qualify `core-cuda` with `cuda:0` and explicit `float32`

## Outcome

The real evaluator loaded Whisper Base on the NVIDIA GeForce RTX 3080, allocated CUDA memory, produced standardized predictions, scored them, generated 11 plots, and produced a report. There was no CPU fallback. The operational candidate is CUDA float32 because it was faster than CUDA float16 in the bounded comparison while all three modes produced identical transcripts, WER, and CER.

This is a machine and integration qualification. It is not authorization to launch the massive campaign. Machine B and the canary, small, and standard scientific gates remain incomplete.

## Environment evidence

| Fact | Observed value |
|---|---|
| OS | Windows 11 (`10.0.26200`) |
| Python | 3.12.7 |
| Environment profile | `core-cuda` |
| Interpreter | `.stage8-envs/core-cuda/Scripts/python.exe` |
| PyTorch | `2.11.0+cu128` |
| PyTorch CUDA runtime | 12.8 |
| cuDNN | 91900 |
| GPU | NVIDIA GeForce RTX 3080 |
| VRAM | 10,240 MiB |
| NVIDIA driver | 610.62 |
| FFmpeg | 8.1.2 |
| `pip check` | Passed |
| Repository verifier | 24/24 non-failing checks |

The workstation also had unrelated desktop applications using the GPU during collection. Device-wide utilization, temperature, and power samples are therefore contextual rather than process-isolated. PyTorch allocator measurements are the authoritative Whisper VRAM evidence.

## Model identity

| Field | Value |
|---|---|
| Model | Whisper Base |
| Path | `models/cache/whisper/base.pt` |
| Bytes | 145,262,807 |
| SHA-256 | `ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E` |
| Download policy | Local asset required before inference; implicit downloads prohibited |

## Real one-item evaluator smoke

The passing run selected one CMU Arctic item and produced one prediction, zero failed items, zero missing items, WER 0.25, 11 plots, and a report. Runtime diagnostics recorded `cuda:0`, `float32`, and the backend parameter device on CUDA.

| Measurement | Value |
|---|---:|
| Current allocated VRAM | 288.52 MiB |
| Current reserved VRAM | 426.00 MiB |
| Peak allocated VRAM | 418.89 MiB |
| Peak reserved VRAM | 426.00 MiB |
| Model initialization | 1.155 s |
| ASR inference | 1.323 s |
| ASR real-time factor | 0.341 |

Conclusion: yes, the actual Evaluation Tool ran Whisper Base on the RTX 3080 and used nonzero VRAM.

## Five-item CPU/CUDA comparison

All runs used the same five CMU Arctic records, Whisper Base checkpoint, full-record segmentation, beam size 1, no augmentation, prediction adapter, scoring policy, and report path. Every mode produced five predictions, zero failures, and zero missing outputs. All transcripts were identical. WER was `0.1463414634` and CER was `0.1444444444` in every mode.

| Mode | Total elapsed | ASR inference | ASR RTF | Pipeline RTF | Audio throughput | Peak allocated VRAM |
|---|---:|---:|---:|---:|---:|---:|
| CPU float32 | 12.619 s | 2.921 s | 0.1829 | 0.2553 | 1.266 audio-s/s | N/A |
| CUDA float32 | 11.794 s | 1.635 s | 0.1024 | 0.1951 | 1.354 audio-s/s | 418.89 MiB |
| CUDA float16 | 12.477 s | 2.156 s | 0.1350 | 0.2271 | 1.280 audio-s/s | 418.89 MiB |

Measured CUDA-float32 speedup was 1.787x for ASR inference and 1.070x end to end versus CPU. CUDA-float16 inference was 1.355x faster than CPU, but slower than CUDA float32 on this bounded run. Float16 remains a separately resolvable qualification configuration, not the operating campaign dtype.

## Campaign consequence

Device and dtype are result-affecting public scenario fields. The frozen CPU campaign remains unchanged:

- campaign: `campaign_05_massive_release`
- manifest SHA-256: `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4`
- source catalog SHA-256: `24AD135F8F2F2450EED78D910727FC63B585958602D28429B3B46B5A1060367E`
- profile/device/dtype: `core-cpu` / `cpu` / `float32`

The coverage-preserving CUDA successor is:

- campaign: `campaign_06_massive_release_cuda`
- manifest SHA-256: `A101D43DD3784EEFD1F8738594A13556DD4F9908C55B96F983FBF6B8F628753D`
- source catalog SHA-256: `1FCDEB638470AE55FC0F4EB88DBB77BF7AB8D5B06704DD1CCFCD5D6C3102B511`
- profile/device/dtype: `core-cuda` / `cuda:0` / `float32`
- scenarios/items: 41 / 25,798

All 41 scenario IDs changed because execution device changed. Benchmark manifests, source selection, conditions, RIR identities, model checksum, seed, and scoring policy remain unchanged. Runtime worker assignment and `release_binding.json` identities are generated after checkout so they bind to the exact launch commit.

## Qualification limits

- Machine B has no CUDA installation or preflight evidence yet.
- Component canary, small, and standard GPU scientific gates have not passed.
- No multi-GPU or dual-scenario concurrency was qualified; run one GPU-heavy scenario per machine.
- Bedroom RIR remains unresolved and excluded. Dining Room and Restaurant are the only RIR conditions in this candidate; no substitution is allowed.
- The massive campaign was not launched.
