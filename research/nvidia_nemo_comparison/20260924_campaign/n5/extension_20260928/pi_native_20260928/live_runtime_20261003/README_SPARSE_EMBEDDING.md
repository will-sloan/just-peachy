# Experimental sparse clean-turn embeddings

`sparse_embedding.py` reduces optional repeated identity queries on the same
predicted exclusive Nemotron turn. It reuses the exact installed timeline's
contiguous 0.5-to-2-second windows and the selected ReDimNet or TitaNet encoder.
The first eligible window of every newly observed exclusive turn is scheduled
immediately; subsequent windows are scheduled at least every configured refresh
interval, rounded up to the existing 0.5-second candidate grid. The default
refresh interval is 2 seconds. A returning turn after overlap or silence gets a
new first query. This is an experimental scheduling adaptation inspired by online
segmentation/embedding work, not an implementation of DIART overlap-aware pooling.

The normal `continuous` schedule remains the default. Sparse mode requires
`diarizer=nemotron`, a named embedding backend, and explicit experimental opt-in.
It processes every ASR and diarization sample and does not change source gain,
activity thresholds, identity thresholds, namespaces or resolver decisions.
Anonymous mode already bypasses identity embeddings and cannot select this mode.
There is no measured speedup, accuracy or native real-time claim.

## Inputs, API and outputs

After `engine.begin()` and before source input starts, the new runtime calls:

```python
from sparse_embedding import attach_sparse_schedule
schedule = attach_sparse_schedule(engine, emit)
```

`engine.mode_configuration['selection']` must contain the validated
`RuntimeSelection` dictionary, including `embedding_schedule='sparse_clean_turn'`
and `embedding_refresh_seconds=2.0`. `emit` accepts one JSON-safe event dictionary
and should write it through the runtime's bounded metadata sink. Native use stays
inside the admitted CPU2/3, single-thread model envelope. The helper itself loads
no model and is not a standalone inference program.

The helper wraps the actual `ActivityTimeline.exclusive_windows` boundary and
observes the engine's existing `research_embedding` receipt. It does not write to
the installed source. Output events contain exact half-open 16 kHz sample
intervals, original and observed run starts, slot, decision reason and counters:

- `embedding_schedule_decision`: `scheduled` or `skipped`. Both explicitly say
  `embedding_computed=false`; a dispatch intention is not an evaluation result.
- `embedding_schedule_evaluated`: only after the actual installed embedding
  receipt, with its evidence event ID and `embedding_computed=true`.

Separate considered and evaluated cursors stop skipped windows from being
reconsidered and prevent fabricated query history. State has at most eight slot
entries, 512 pending receipts and 256 retained log entries by default. Pending
receipts expire with the source ring. The external sink also needs its existing
byte limit. An evicted start of a still-overlapping continuous run keeps its
original run identity. No synthetic interval can create an evaluated receipt.

Sparse queries can reduce name evidence coverage or delay confirmation on a long
turn. A known label is still supported only by the installed resolver's actual
evidence intervals; skipped windows do not become evidence. Select this mode for
an explicit matched-input comparison, not as an implicit default optimization.

## PowerShell configuration or focused tests

Use the existing Anaconda environment with `psutil`; no downloads are needed.
This wrapper pins CPU14 and durably registers numeric process identity before
reading project code. Configuration mode prints JSON only. It runs no model.

```powershell
$env:JP_PIPELINE_CODE = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$env:JP_PIPELINE_PRIVATE = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$taskCode = @'
import psutil
psutil.Process().cpu_affinity([14])
import json, os, sys, uuid, runpy
from pathlib import Path
out = Path(os.environ['JP_PIPELINE_PRIVATE']) / ('presets-preparation-sparse-' + uuid.uuid4().hex)
out.mkdir()
p = psutil.Process()
with (out / 'REGISTERED_OWNER.json').open('x') as f:
    json.dump(dict(pid=p.pid, create_time=p.create_time(), affinity=p.cpu_affinity()), f)
    f.flush(); os.fsync(f.fileno())
sys.path.insert(0, os.environ['JP_PIPELINE_CODE'])
sys.argv = ['profiles.py', '--diarizer', 'nemotron', '--profile', 'current_delayed', '--embedding', 'redimnet', '--source', 'saved', '--experimental', '--embedding-schedule', 'sparse_clean_turn', '--embedding-refresh', '2']
runpy.run_module('profiles', run_name='__main__')
'@
& 'C:/Users/amiri/anaconda3/python.exe' -B -c $taskCode
```

To run focused synthetic tests instead, replace the last two Python lines with:

```python
import unittest
r = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_sparse_embedding'))
sys.exit(0 if r.wasSuccessful() else 1)
```

## Command Prompt or Anaconda Prompt

These commands run the same focused tests and create a fresh owner receipt.
Inputs are synthetic candidate windows and actual-receipt fixtures; output is a
console test report. They do not execute the installed application or models.

```bat
set "JP_PIPELINE_CODE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003"
set "JP_PIPELINE_PRIVATE=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
"C:\Users\amiri\anaconda3\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import os,json,sys,uuid,unittest; from pathlib import Path; o=Path(os.environ['JP_PIPELINE_PRIVATE'])/('presets-preparation-sparse-'+uuid.uuid4().hex); o.mkdir(); p=psutil.Process(); f=(o/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); sys.path.insert(0,os.environ['JP_PIPELINE_CODE']); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_sparse_embedding')); sys.exit(0 if r.wasSuccessful() else 1)"
```

To print configuration in CMD/Anaconda Prompt, use the same early-registration
prefix and replace the final `r=...; sys.exit(...)` portion with:

```python
from profiles import RuntimeSelection; print(json.dumps(RuntimeSelection(diarizer='nemotron', embedding='titanet', input_source='saved', nemotron_profile='current_delayed', allow_experimental=True, embedding_schedule='sparse_clean_turn', embedding_refresh_seconds=2).validate(), indent=2))
```

Six focused schedule contracts and twelve existing component contracts passed
on 2026-10-03. Receipt:
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-sparse-tests-6f8e94f58ce24f198d725d84fbdfbf9e/RESULT.json`.
These check first/returning turns, overlap abstention, query eviction, bounded
state, opt-in validation and genuine receipt accounting. They are not quality
tests. This change belongs to the next prepared build; the frozen build01 remains
unchanged. See [research choices](RESEARCH_ARCHITECTURES.md) and
[native component benchmark](README_NATIVE_BENCHMARK.md).
