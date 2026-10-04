# Live runtime expansion after v28

This directory contains a new candidate runtime, not an edit to field-runtime-v27
or field-runtime-v28. It separates backend selection from live/saved input,
uses an explicit 300-second normal session policy, stores audio on disk, and
uses storage capacity rather than a four-session allowance. Existing model
assets, galleries, XVF routing and mounted BMI270 code are verified and reused.

The selected production release is **field-runtime-v29-build-16**, staged,
activated and the sole desktop shortcut. Actual Desktop Exec/native_scope/default
data idle, exact optional policy controls and normal Exit passed with zero
Start/workers/models/capture. Login autostart stays disabled; physical touch,
double-click and a new reboot were not tested. See [SOURCE_STATUS.md](SOURCE_STATUS.md)
for exact shared GUI15/production16 module hashes and external-tool boundaries.
This editable directory is not the immutable installed package.

One experimental optional Pyannote/TitaNet/live/window60 selection has actual14
full300 primary/raw/child EOF evidence under source300/load120/drain60/backlog30/
cleanup60. The GUI resolves/displays that unique accepted policy. Unchecked
ordinary defaults stay300/120/120/120/60. Zero optional corrections were observed;
correction quality is unqualified. Other optional selections remain unavailable.
See [GUI policy instructions](README_GUI_OPTIONAL_POLICY.md).

A profile accepting live input does not establish sustained real-time behavior.
The failed whole-application hour remains failed; the component hour is separate.
Source, gallery, raw-clock, model, closure and bounded storage guards remain.
See [NATIVE_RESULTS](NATIVE_RESULTS.md), [RAM_RESOURCE_GUIDE](RAM_RESOURCE_GUIDE.md)
and [START_HERE](START_HERE.md).
## Inputs and outputs

Inputs are a hash-pinned installed v12 engine, preserved v28 reference sources
and profile descriptors, local model assets, existing separate embedding
galleries, a source selection, and a finite SessionPolicy. Saved replay accepts
mono PCM16 16 kHz WAV without silent resampling or gain changes. Live capture
requires the actual installed XVF device and the existing hardware lease.

Outputs are unique persistent session IDs, segmented exact float audio and
replay WAV, indexed captions, timing/health events, native source/closure
receipts and explicitly selected permanent recordings. Stop first drains and
closes processing. The operator can then preserve processed audio or discard
the temporary recording. Failures preserve diagnostic evidence and are never
reported as successful recordings. Existing releases and recordings are not
modified by source preparation or host tests.

## Host commands

Use the existing qualified project interpreter. Do not download replacement
weights. The configuration catalog loads no models. Set N to this source
directory and Q to the private live-runtime evidence root before running.
The commands register an actual CPU14 owner before importing project code.

PowerShell:

```powershell
$env:JP_PIPELINE_CODE = $N
$env:JP_PIPELINE_PRIVATE = $Q
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); import os,json,sys,uuid,runpy; from pathlib import Path; o=Path(os.environ['JP_PIPELINE_PRIVATE'])/('presets-preparation-catalog-'+uuid.uuid4().hex); o.mkdir(); p=psutil.Process(); f=(o/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=p.pid,create_time=p.create_time(),affinity=[14]),f); f.flush(); os.fsync(f.fileno()); f.close(); sys.path.insert(0,os.environ['JP_PIPELINE_CODE']); sys.argv=['profiles.py','--catalog']; runpy.run_path(str(Path(os.environ['JP_PIPELINE_CODE'])/'profiles.py'),run_name='__main__')"
```

Command Prompt or Anaconda Prompt (use this same explicit interpreter):

```bat
set "JP_PIPELINE_CODE=%N%"
set "JP_PIPELINE_PRIVATE=%Q%"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import os,json,sys,uuid,runpy; from pathlib import Path; o=Path(os.environ['JP_PIPELINE_PRIVATE'])/('presets-preparation-catalog-'+uuid.uuid4().hex); o.mkdir(); p=psutil.Process(); f=(o/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=p.pid,create_time=p.create_time(),affinity=[14]),f); f.flush(); os.fsync(f.fileno()); f.close(); sys.path.insert(0,os.environ['JP_PIPELINE_CODE']); sys.argv=['profiles.py','--catalog']; runpy.run_path(str(Path(os.environ['JP_PIPELINE_CODE'])/'profiles.py'),run_name='__main__')"
```

Catalog JSON is printed to stdout and its owner receipt remains private. See
[README_HOST_TESTS.md](README_HOST_TESTS.md) for focused test purposes, inputs,
outputs and registered host commands. Use the exact test and preparation
commands in the component READMEs. Native
launches require a freshly verified candidate binding, a finite process unit,
current owner/lease/resource checks and an independently verified package
backup. Do not invoke worker.py directly or reuse a historical campaign
admission. Candidate package and native invocation commands are documented by
the package builder when prepared.

## Code map

* profiles.py: source-independent mode selection and finite session policy.
* launcher.py: one scrolling launcher, post-Stop choices and paginated history.
* worker.py: one owned process per session and closure-before-next-session.
* installed_engine.py: binds the retained speech, embedding and motion engines.
  After engine initialization it optionally attaches `sparse_embedding.py` to
  genuine clean-turn windows. Select `embedding_schedule=sparse_clean_turn`
  with `allow_experimental=true` for Nemotron plus either named embedding
  backend; continuous scheduling remains the default. Source audio, ASR,
  diarizer processing and identity thresholds stay unchanged. Diagnostics
  distinguish scheduled embedding windows from actually evaluated windows.
* installed_source.py: isolated processed XVF acquisition and route restoration.
* storage.py and audio_journal.py: disk-backed audio, unique sessions, history,
  export, deliberate deletion and storage-floor checks.
* runtime_support.py: source verification, leases, durable receipts and bounded
  segmented metadata writers with a shared allocation.
* nemotron_binding.py: explicit validated geometry and native result bounds.
* correction.py, refinement.py: bounded source-time correction machinery;
  independent native dual-worker admission remains required.
* telemetry.py: rolling compute/backlog measurements, separate from buffering.

Native diagnostics report measured 2 GB memory availability and process RSS
separately from address-space limits and CPU/queue behavior. Possible 4 GB or
8 GB benefits are estimates unless measured on that hardware. Additional RAM
can make more resident models feasible; it does not by itself reduce a
CPU-bound model's computation per second of audio. See the research and
individual pipeline notes for the resource tradeoffs.

See README_PIPELINES.md and pipelines/ for the individual architectures,
geometry, math and limitations. See README_STORAGE.md,
README_AUDIO_JOURNAL.md, README_INSTALLED_SOURCE.md and
README_INTEGRATION_TESTS.md for focused contracts. The implementation checklist
tracks pending native tests and delivery work; preparation is not acceptance.

`test_engine_presentation.py` checks the changed controller/S7 boundary using
synthetic rows: pending text cannot count as first speaker output; actual
supported-history segments work without an invented `voice_available` field;
late speaker updates preserve the caption/text identity and suppress duplicate
updates. It loads no installed model. Use the CPU14/early-owner PowerShell,
Command Prompt or Anaconda test commands in `README_PIPELINES.md`, substituting
`test_engine_presentation` for `test_pipelines`. Inputs are the synthetic test
fixtures; outputs are the unittest log and the host test receipt. Actual CM5
caption integration remains a separate required check.
# Tablet window placement

The native launcher requests480×800+0+0 and enters fullscreen after the window
manager maps it, preventing the known top-bar clipping while retaining the
existing270-degree desktop rotation. `README_NATIVE_GUI_DRIVER.md` describes
the actual10-sample fullscreen check and distinguishes programmatic invocation
from physical-touch/visual-quality qualification. Host tests open no GUI.

