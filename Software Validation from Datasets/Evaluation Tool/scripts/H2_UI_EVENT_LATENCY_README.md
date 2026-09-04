# H2 UI event-latency benchmark

## Purpose

`measure_h2_ui_event_latency.py` fills the H2 engineering-evidence gap between
an emitted runtime event and the common application's Tk presentation. It uses
the frozen application's real durable JSONL cursor, bounded/coalescing update
queue, background polling handoff, state projector, and widget-render methods.

The benchmark does **not** run ASR, diarization, speaker embeddings, audio
capture, or a physical display. Its result is therefore UI-presentation
latency, not complete speech-to-screen latency and not physical monitor
scan-out latency. It cannot affect development selection, frozen thresholds,
held-out evaluation, or the production recommendation.

## Inputs

- An H2 workspace containing `runtime_implementation_identity.json`.
- The current repository source. The script recomputes the complete
  result-affecting runtime identity and refuses to run if it differs from the
  frozen workspace identity.
- `--samples`: measured events after warm-up; default `100`.
- `--warmup`: unreported warm-up events; default `10`.
- `--timeout-sec`: maximum wait for each event to reach Tk; default `5`.

All temporary and final data remains on drive C. Temporary session data is
deleted automatically after measurement.

## Output

The default output is:

```text
automated_runs\h2_complete_product_pipeline_v17\engineering_validation\ui_event_latency_receipt.json
```

It contains:

- every monotonic emission/render timestamp and latency sample;
- minimum, mean, median, p50, p95, p99, maximum, and population standard
  deviation;
- exact source-file hashes and the frozen runtime identity;
- environment and Tk version;
- explicit included/excluded measurement stages;
- widget-level verification; and
- a canonical SHA-256 signature over the receipt.

The final package augmenter copies and independently validates this receipt,
the benchmark source, the relevant runtime sources, this README, and its tests.

## Run from PowerShell

From the Evaluation Tool directory:

```powershell
$Workspace = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17'
$Output = Join-Path $Workspace 'engineering_validation\ui_event_latency_receipt.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' .\scripts\measure_h2_ui_event_latency.py --workspace $Workspace --output $Output --samples 100 --warmup 10 --timeout-sec 5
```

Validate an existing receipt without opening Tk:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' .\scripts\measure_h2_ui_event_latency.py --validate $Output
```

## Run from Anaconda Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" scripts\measure_h2_ui_event_latency.py --workspace "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17" --samples 100 --warmup 10 --timeout-sec 5
```

## Tests

PowerShell or Anaconda Prompt:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_ui_event_latency_benchmark.py
```

The Tk integration test skips only when the host genuinely cannot initialize
Tk. On the Windows evaluation host it must execute and pass.
