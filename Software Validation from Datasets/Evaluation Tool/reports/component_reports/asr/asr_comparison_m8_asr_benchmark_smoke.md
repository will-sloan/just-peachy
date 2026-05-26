# ASR Multi-Model Benchmark Comparison

## Milestone

M8 - ASR Multi-Model Benchmark and Comparison Report

- Run id: `m8_asr_benchmark_smoke`
- Dataset: `CMU Arctic`
- Record count: `1`
- Recommended default ASR: `fixed_dummy`

## Compared Models

| Model | Status | WER | CER | RTF | Throughput | Failure Rate | Empty Rate | Composite |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_op_empty` | ran | 1.0000 | 1.0000 | 0.0053 | 48.8749 | 1.0000 | 1.0000 | 27.3689 |
| `fixed_dummy` | ran | 1.0000 | 0.7297 | 0.0002 | 1602.6697 | 0.0000 | 0.0000 | 42.4960 |
| `whisper_tiny` | failed (inference failed/skipped for 1 of 1 record(s); see benchmark log) | 1.0000 | 1.0000 | 0.0937 | 0.0000 | 1.0000 | 1.0000 | 25.3575 |

## Runtime And Robustness

| Model | Load Sec | Runtime Sec | Peak GPU MB | CPU MB | Repeated Word | Repeated N-Gram | Duplicate Token | Hallucination |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_op_empty` | 0.0000 | 0.0205 | n/a | n/a | 0.0000 | 0.0000 | 0.0000 | n/a |
| `fixed_dummy` | 0.0000 | 0.0006 | n/a | n/a | 0.0000 | 0.0000 | 0.0000 | n/a |
| `whisper_tiny` | n/a | 0.3637 | n/a | n/a | 0.0000 | 0.0000 | 0.0000 | n/a |

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

inference failed/skipped for 1 of 1 record(s); see benchmark log

## Metrics By Augmentation Condition

### `no_op_empty`

- `clean`: WER `1.0000`, CER `1.0000`, records `1`

### `fixed_dummy`

- `clean`: WER `1.0000`, CER `0.7297`, records `1`

### `whisper_tiny`

- `clean`: WER `1.0000`, CER `1.0000`, records `1`

## Blockers

- `whisper_tiny`: inference failed/skipped for 1 of 1 record(s); see benchmark log

## Incomplete

- Speaker diarization, speaker embeddings, speaker matching, optimization, quantization, ExecuTorch export, and hardware acceleration remain out of scope for M8.
- CER is computed by benchmark helper logic; WER is taken from existing scorer output when dataset references are available.
