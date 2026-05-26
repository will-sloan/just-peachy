# M8 ASR Benchmark Report

## Milestone

M8 - ASR Multi-Model Benchmark and Comparison Report

## Files Changed

- `app/inference_pipeline/benchmarking/__init__.py`
- `app/inference_pipeline/benchmarking/asr_benchmark.py`
- `app/inference_pipeline/metrics/__init__.py`
- `app/inference_pipeline/metrics/asr_metrics.py`
- `scripts/run_asr_benchmark.py`
- `configs/sweeps/asr_models.yaml`
- `tests/inference_pipeline/test_asr_benchmark.py`
- `tests/run_all_tests.py`
- `reports/component_reports/asr/asr_comparison_m8_asr_benchmark_smoke.md`
- `reports/component_reports/asr/asr_comparison_m8_asr_benchmark_smoke.csv`
- `reports/milestones/M8_asr_benchmark_report.md`

## Summary

M8 adds a config-driven ASR benchmark runner that compares multiple ASR
candidate configs over the same selected Evaluation Tool records. Each model
gets a separate output directory, immutable ASR config snapshot, standardized
`predictions/utterances.jsonl`, scorer metrics when references are available,
benchmark metrics, qualitative examples, and shared markdown/CSV comparison
reports.

The default sweep compares `no_op_empty`, `fixed_dummy`, and optional
`whisper_tiny`. The benchmark now resolves the configured relative Whisper cache
against the Evaluation Tool directory, the project root, and the workspace root
where `.venv` and `models/cache/whisper/tiny.pt` live.

## Runner Contract Preservation

- The benchmark still uses `ExternalStubRunner` and `PipelineRunner`.
- Each ASR model receives the same selected metadata records in the same order.
- The pipeline still reads `record["inference_audio_path"]` after runtime
  materialization.
- `recording_id`, `utt_id`, `start_sec`, and `end_sec` are preserved in
  predictions.
- `predictions/utterances.jsonl` schema is unchanged.
- No GUI, dataset registry, scorer, plot generation, or existing report
  generator behavior was redesigned.

## Commands Run

Dependency/model availability check:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -c "import importlib.util; from pathlib import Path; names=['whisper','faster_whisper','torch','soundfile','pytest']; print('\n'.join(f'{name} {importlib.util.find_spec(name) is not None}' for name in names)); print('tiny.pt', Path('models/cache/whisper/tiny.pt').exists())"
/Users/billy/Documents/just-peachy/.venv/bin/python -c "from pathlib import Path; print('project tiny', Path('models/cache/whisper/tiny.pt').exists()); print('home tiny', (Path.home()/'.cache/whisper/tiny.pt').exists())"
/Users/billy/Documents/just-peachy/.venv/bin/python -c "from pathlib import Path; from app.inference_pipeline.benchmarking.asr_benchmark import _whisper_model_available; project=Path('/Users/billy/Documents/just-peachy/Software Validation from Datasets'); print(_whisper_model_available('tiny', availability={'whisper_cache_dir':'models/cache/whisper'}, project_root=project))"
```

Focused and adjacent tests:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_asr_benchmark.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_asr_interface.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_config_registry.py
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py
```

All-test runner:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python tests/run_all_tests.py --python /Users/billy/Documents/just-peachy/.venv/bin/python
```

Benchmark smoke:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/run_asr_benchmark.py --project-root /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets --dataset cmu_arctic --max-recordings 1 --run-id m8_asr_benchmark_smoke --runs-root /private/tmp/m8_asr_benchmark_runs
```

Direct Whisper adapter smoke with the actual local CMU Arctic WAV:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -c "import json, logging, shutil; from dataclasses import asdict; from pathlib import Path; from app.inference_pipeline.asr.whisper_adapter import WhisperASR; from app.inference_pipeline.dummy_components import DummyAudioReader, DummySpeakerLabeler; from app.inference_pipeline.pipeline import PipelineRunner; from app.model_runner.external_stub import ExternalStubRunner; project=Path('/Users/billy/Documents/just-peachy/Software Validation from Datasets'); audio=project/'RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_a0001.wav'; run_dir=Path('/private/tmp/m8_whisper_direct_smoke'); shutil.rmtree(run_dir, ignore_errors=True); record={'recording_id':'CMU_ARCTIC_aew_arctic_a0001','utt_id':'arctic_a0001','audio_path_resolved':str(audio),'inference_audio_path':str(audio),'start_sec':0.0,'end_sec':3.880063,'reference_text':'author of the danger trail philip steels etc'}; run_config={'project_root':str(project),'run_dir':str(run_dir),'augmentation':{'mode':'none','conditions':[{'condition_id':'clean','mode':'none'}]}}; asr=WhisperASR({'model_size':'tiny','model_name':'whisper_tiny','language':'en','device':'cpu','dtype':'float32','cache_dir':'models/cache/whisper','allow_model_downloads':False}); pipeline=PipelineRunner(audio_reader=DummyAudioReader(), asr=asr, speaker_labeler=DummySpeakerLabeler()); result=ExternalStubRunner(pipeline).run_batch([record], run_dir/'predictions', run_config, logging.getLogger('m8_whisper_direct')); result_dict=asdict(result); result_dict['predictions_path']=str(result_dict['predictions_path']); print(json.dumps({'result':result_dict,'runtime':asr.last_runtime_stats.to_jsonable() if asr.last_runtime_stats else None,'predictions':(run_dir/'predictions/utterances.jsonl').read_text().splitlines()}, indent=2))"
```

## Test Results

- `tests/inference_pipeline/test_asr_benchmark.py`: `8 passed`.
- `tests/inference_pipeline/test_asr_interface.py`: `12 passed`.
- `tests/inference_pipeline/test_config_registry.py`: `10 passed`.
- `tests/model_runner/test_external_stub_bridge.py`: `4 passed`.
- `tests/run_all_tests.py`: all mapped test commands passed, including M8.
- Existing M5 VAD warning remains: PyTorch warns that `torch.jit.load` is not
  supported in Python 3.14+.

## Benchmark Smoke Result

- Benchmark root: `/private/tmp/m8_asr_benchmark_runs/m8_asr_benchmark_smoke`
- Markdown comparison report:
  `reports/component_reports/asr/asr_comparison_m8_asr_benchmark_smoke.md`
- CSV comparison report:
  `reports/component_reports/asr/asr_comparison_m8_asr_benchmark_smoke.csv`
- Models compared:
  - `no_op_empty`: ran
  - `fixed_dummy`: ran
  - `whisper_tiny`: attempted, but failed on the selected dataset record because
    the normalized metadata resolved the audio path to a non-existent Windows
    path.
- Recommended default ASR for the next milestone: `fixed_dummy`

## Whisper Status

The `whisper` Python package is importable and `tiny.pt` was found at:

```text
/Users/billy/Documents/just-peachy/models/cache/whisper/tiny.pt
```

The direct Whisper adapter smoke against the actual local WAV succeeded and
wrote one prediction:

```text
author of the danger trail, philip steels, etc.
```

The benchmark dataset smoke still failed for `whisper_tiny` because the CMU
Arctic selected metadata record resolved `audio_path_resolved` to:

```text
/Users/billy/Documents/just-peachy/Software Validation from Datasets/C:/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic/cmu_us_aew_arctic/wav/arctic_a0001.wav
```

That file does not exist locally. No model assets were downloaded.

## What Remains Incomplete

- `whisper_tiny` can run through the adapter with a valid local WAV path, but
  the dataset benchmark needs the normalized metadata audio path rebasing issue
  fixed before it can score Whisper output end to end.
- The benchmark script is intentionally separate from `run_evaluation.py`; plain
  `run_evaluation.py full` still does not select ASR configs.
- Speaker diarization, speaker embeddings, speaker matching, optimization,
  quantization, ExecuTorch export, and hardware acceleration remain out of
  scope for M8.
