# M7 - ASR Interface and First ASR Model Adapter

## Files Changed
- `app/inference_pipeline/asr/__init__.py`
- `app/inference_pipeline/asr/base.py`
- `app/inference_pipeline/asr/metrics.py`
- `app/inference_pipeline/asr/report.py`
- `app/inference_pipeline/asr/whisper_adapter.py`
- `app/inference_pipeline/asr/faster_whisper_adapter.py`
- `app/inference_pipeline/pipeline.py`
- `app/inference_pipeline/registry.py`
- `configs/inference/components/asr/whisper_tiny.yaml`
- `configs/inference/components/asr/whisper_base.yaml`
- `tests/inference_pipeline/test_asr_interface.py`
- `tests/run_all_tests.py`
- `reports/component_reports/asr/asr_model_report_m7_asr_smoke.md`

## Selected ASR Backend
- Smoke adapter: `FixedASR`, deterministic local adapter.
- Real adapter boundary: `WhisperASR`, lazy loading only.
- Whisper local run: blocked. The active environment does not have the OpenAI Whisper package installed, and model downloads are disabled for this milestone.
- `faster_whisper`: unavailable in the active environment, so only a lazy unavailable boundary was added.

## Summary
M7 added a backend-swappable ASR interface, deterministic no-op/fixed ASR adapters for offline tests, lazy Whisper adapter boundaries, ASR config files, lightweight ASR quality metrics, runtime-stat capture, and pipeline integration for ASRBase components. The pipeline can still run with the existing dummy ASR path, or with an ASRBase adapter selected directly/config-resolved.

## Runner Contract
The Evaluation Tool runner contract was preserved. `ExternalStubRunner` still receives one selected metadata row at a time, the pipeline still reads `record["inference_audio_path"]`, and final prediction rows still preserve `recording_id`, `utt_id`, `start_sec`, and `end_sec` with the existing `utterances.jsonl` schema.

## Commands Run
- `/Users/billy/Documents/just-peachy/.venv/bin/python -c "import importlib.util; names=['torch','torchaudio','whisper','faster_whisper','transformers','openai_whisper','soundfile','numpy','pytest','psutil']; print('\n'.join(f'{name} {importlib.util.find_spec(name) is not None}' for name in names))"`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m compileall app/inference_pipeline/asr app/inference_pipeline/pipeline.py app/inference_pipeline/registry.py tests/inference_pipeline/test_asr_interface.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_asr_interface.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_config_registry.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_segmentation.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_vad.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_audio_io.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python tests/run_all_tests.py --python /Users/billy/Documents/just-peachy/.venv/bin/python`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -c "from app.inference_pipeline.asr.whisper_adapter import WhisperASR, WhisperASRUnavailableError; adapter=WhisperASR(params={'model_size':'tiny','allow_model_downloads':False}); exec('try:\n    adapter._model()\nexcept WhisperASRUnavailableError as exc:\n    print(\"blocked: \" + str(exc))\nelse:\n    print(\"loaded\")')"`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -c "import json, logging, shutil; from dataclasses import asdict; from pathlib import Path; from app.inference_pipeline.asr.base import FixedASR; from app.inference_pipeline.dummy_components import DummyAudioReader, DummySpeakerLabeler; from app.inference_pipeline.pipeline import PipelineRunner; from app.model_runner.external_stub import ExternalStubRunner; run_dir=Path('/private/tmp/m7_asr_runner_smoke'); shutil.rmtree(run_dir, ignore_errors=True); predictions_dir=run_dir/'predictions'; record={'recording_id':'m7-rec','utt_id':'m7-utt','audio_path_resolved':'synthetic.wav','inference_audio_path':'synthetic.wav','start_sec':0.0,'end_sec':1.0}; run_config={'project_root':'/Users/billy/Documents/just-peachy/Software Validation from Datasets','run_dir':str(run_dir),'augmentation':{'mode':'none','conditions':[{'condition_id':'clean','mode':'none'}]}}; pipeline=PipelineRunner(audio_reader=DummyAudioReader(), asr=FixedASR('M7 adapter transcript'), speaker_labeler=DummySpeakerLabeler()); result=ExternalStubRunner(pipeline).run_batch([record], predictions_dir, run_config, logging.getLogger('m7_smoke')); stats=pipeline.asr.last_runtime_stats; result_dict=asdict(result); result_dict['predictions_path']=str(result_dict['predictions_path']); print(json.dumps({'result': result_dict, 'runtime_stats': stats.to_jsonable(), 'jsonl': (predictions_dir/'utterances.jsonl').read_text().splitlines()}, indent=2))"`
- `/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full --project-root /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets --dataset cmu_arctic --max-recordings 1 --runner external-stub --augmentation none --run-name m7_asr_smoke --runs-root /private/tmp/m7_eval_runs`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -c "import json; from pathlib import Path; from app.prediction_io.schema import UtterancePrediction; run=Path('/private/tmp/m7_eval_runs/20260525_113555_cmu_arctic_full_m7_asr_smoke'); preds=[json.loads(line) for line in (run/'predictions/utterances.jsonl').read_text().splitlines() if line.strip()]; records=[json.loads(line) for line in (run/'dataset_selection_records.jsonl').read_text().splitlines() if line.strip()]; validated=[UtterancePrediction(**row) for row in preds]; pred_keys={(row['recording_id'], row['utt_id']) for row in preds}; record_keys={(row['recording_id'], row['utt_id']) for row in records}; required={'recording_id','utt_id','start_sec','end_sec','speaker_label','text'}; print(json.dumps({'prediction_count': len(preds), 'record_count': len(records), 'schema_valid': len(validated)==len(preds), 'required_keys_present': all(required <= set(row) for row in preds), 'ids_preserved': pred_keys == record_keys, 'pred_keys': sorted(list(pred_keys)), 'record_keys': sorted(list(record_keys))}, indent=2))"`

## Results
- Focused ASR tests: `12 passed in 0.85s`.
- Config registry tests: `10 passed in 0.04s`.
- External bridge tests: `4 passed in 0.68s`.
- Segmentation tests: `15 passed in 0.03s`.
- VAD tests: `13 passed, 1 warning in 1.13s`.
- Audio I/O tests: `17 passed in 0.97s`.
- `tests/run_all_tests.py`: all mapped commands passed, including M7.

## Smoke and Metrics
- Direct `ExternalStubRunner` smoke with `FixedASR`: wrote `/private/tmp/m7_asr_runner_smoke/predictions/utterances.jsonl`.
- Direct smoke ASR text: `m7 adapter transcript`.
- Direct smoke ASR runtime: load `0.0s`, inference `0.00016266689635813236s`, audio duration `1.0s`, real-time factor `0.00016266689635813236`, device `cpu`, dtype `float32`.
- Direct smoke repeated word rate: `0.0`.
- Direct smoke repeated n-gram rate: `0.0`.
- Direct smoke consecutive duplicate token rate: `0.0`.
- Direct smoke empty-output rate: `0.0`.
- Hallucinated-output rate on silence/noise: not available; no silence/noise model smoke was run.
- Full Evaluation Tool external-stub smoke: completed scoring and reporting at `/private/tmp/m7_eval_runs/20260525_113555_cmu_arctic_full_m7_asr_smoke`.
- Full smoke `predictions/utterances.jsonl`: created and schema-valid.
- Full smoke ID preservation: passed for all rows.
- Full smoke aggregate WER: `1.0`.
- CER: not available from the existing aggregate metrics.
- Peak GPU memory: not available.
- CPU memory: not available; `psutil` is not installed.

## Blockers
- Real Whisper transcription did not run because the active environment does not have the `whisper` package installed.
- Local model downloads were intentionally disabled, so no model asset was fetched.
- The full CLI smoke does not yet expose ASR component selection; the real M7 ASR adapter was exercised through the direct runner/pipeline smoke instead.
- The full CLI smoke reported `audio_missing=1` for the CMU Arctic source path, but the external-stub run still produced predictions, scoring, plots, and report output.

## Incomplete
- Real model transcription is incomplete until a local Whisper-compatible package and model asset are available.
- Word timestamps are supported by the adapter boundary when the backend returns them, but were not validated with a real Whisper model in M7.
- Speaker diarization, speaker embeddings, speaker matching, optimization, quantization, ExecuTorch export, and hardware acceleration remain intentionally out of scope for M7.
