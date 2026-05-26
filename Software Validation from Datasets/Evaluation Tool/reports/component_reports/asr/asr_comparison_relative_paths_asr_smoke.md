# ASR Multi-Model Benchmark Comparison

## Milestone

M8 - ASR Multi-Model Benchmark and Comparison Report

- Run id: `relative_paths_asr_smoke`
- Dataset: `CMU Arctic`
- Record count: `1`
- Recommended default ASR: `whisper_tiny`

## Compared Models

| Model | Status | WER | CER | RTF | Throughput | Failure Rate | Empty Rate | Composite |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_op_empty` | ran | 1.0000 | 1.0000 | 0.0054 | 48.0585 | 1.0000 | 1.0000 | 27.3666 |
| `fixed_dummy` | ran | 1.0000 | 0.7297 | 0.0002 | 1185.5364 | 0.0000 | 0.0000 | 42.4946 |
| `whisper_tiny` | ran | 0.3750 | 0.0811 | 0.1904 | 1.3538 | 0.0000 | 0.0000 | 72.8769 |

## Runtime And Robustness

| Model | Load Sec | Runtime Sec | Peak GPU MB | CPU MB | Repeated Word | Repeated N-Gram | Duplicate Token | Hallucination |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_op_empty` | 0.0000 | 0.0208 | n/a | n/a | 0.0000 | 0.0000 | 0.0000 | n/a |
| `fixed_dummy` | 0.0000 | 0.0008 | n/a | n/a | 0.0000 | 0.0000 | 0.0000 | n/a |
| `whisper_tiny` | 0.2776 | 0.7386 | n/a | n/a | 0.0000 | 0.0000 | 0.0000 | n/a |

## Qualitative Examples

### `no_op_empty`

- best: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=``
- median: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=``
- worst: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=``
- high_stutter: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=``
- empty_output: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=``
- hallucination: `n/a`

### `fixed_dummy`

- best: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=`dummy pipeline transcript`
- median: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=`dummy pipeline transcript`
- worst: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=`dummy pipeline transcript`
- high_stutter: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `1.0000` ref=`author of the danger trail philip steels etc` hyp=`dummy pipeline transcript`
- empty_output: `n/a`
- hallucination: `n/a`

### `whisper_tiny`

- best: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `0.3750` ref=`author of the danger trail philip steels etc` hyp=`author of the danger trail, philip steels, etc.`
- median: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `0.3750` ref=`author of the danger trail philip steels etc` hyp=`author of the danger trail, philip steels, etc.`
- worst: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `0.3750` ref=`author of the danger trail philip steels etc` hyp=`author of the danger trail, philip steels, etc.`
- high_stutter: `CMU_ARCTIC_aew_arctic_a0001/arctic_a0001` WER `0.3750` ref=`author of the danger trail philip steels etc` hyp=`author of the danger trail, philip steels, etc.`
- empty_output: `n/a`
- hallucination: `n/a`

## Metrics By Augmentation Condition

### `no_op_empty`

- `clean`: WER `1.0000`, CER `1.0000`, records `1`

### `fixed_dummy`

- `clean`: WER `1.0000`, CER `0.7297`, records `1`

### `whisper_tiny`

- `clean`: WER `0.3750`, CER `0.0811`, records `1`

## Blockers

- None.

## Incomplete

- Speaker diarization, speaker embeddings, speaker matching, optimization, quantization, ExecuTorch export, and hardware acceleration remain out of scope for M8.
- CER is computed by benchmark helper logic; WER is taken from existing scorer output when dataset references are available.
