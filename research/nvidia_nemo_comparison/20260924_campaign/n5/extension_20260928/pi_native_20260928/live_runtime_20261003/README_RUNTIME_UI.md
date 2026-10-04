# Tablet layout and retained direction channel

`runtime_ui.py` supplies scrollable Launch/Developer pages, readable persistent
History labels and direction/orientation controls for the unified launcher.
`runtime_ui_channel.py` separates bounded spatial display records from worker
diagnostics. Inputs are the existing retained spatial/motion snapshot, current
session state and native Tk widgets. Outputs are the on-screen caption/direction
view and one latest spatial record in Manager RAM, without a refresh log on disk.

The launcher still requests fullscreen480×800+0+0 after Map, preserves the
270-degree desktop, starts with capture off, and waits for Stop/drain/exact
source-worker closure before Exit. Vertical scrollbars and wheel/touch-generated
scroll events make the full Launch and Developer interiors reachable. History
has its own scrollbar and7-row native-fixture pagination checks. Its label uses
date/time, duration and the persistent ID prefix; no repeated global slot labels.

The retained mounted provider keeps beam angles in device coordinates and
motion-compensated association logic separate. Display geometry follows the
installed `app.beam_diagnostics.arrow_tip`:0° right,180° left,90° folded
front/rear ambiguity. No mounting, calibration, yaw compensation or source-clock
math is reimplemented. Fresh directions are solid; stale ones are dashed.
Speaker-location annotations are marked estimated and speaker names remain
voice matches. Saved replay never uses current motion to invent recorded
directions.

`SpatialViews` sends each already received beam observation and committed audio
block once to each of two retained `LiveSpatialProvider` instances. The existing
primary instance keeps its original motion compensation, decision handling and
tracker evidence. The second display instance has `motion=None`; its device
angles are never compensated or inverted a second time. It uses the same
retained bounded deques and performs no new sensor reads. The engine's normal
`snapshot()` remains the primary snapshot; only GUI `display_snapshot()` chooses
device arrows and includes the primary cached motion for the orientation graphic.
Relative-anchor speaker locations are listed separately from device arrows;
they are never silently plotted as device bearings. Native performance remains
to be measured with this additional bounded display computation.

`Orientation graphic · show / hide` and `Recenter orientation graphic (visual
only)` restore the v28 orientation-debug behavior. Recenter stores a local
display offset; it never resets/recalibrates the BMI270 or alters direction
association physics. Invalid/absent motion stays visibly unavailable.

The isolated source forwards the existing BeamDiagnostics cached state, so
the parent no longer pretends the diagnostic object is absent. It does not
invent RUNNING or perform a new hardware read. While the direction panel is
actually visible, the session-owned `GUI_SPATIAL_ON` marker permits the engine
to sample its existing spatial provider at most5Hz. Worker sends one <=4096-byte
atomic pipe record. Manager recognizes it, keeps only the newest record in RAM,
and omits it from the bounded WORKER.log. Diagnostic bytes retain their original
bounded log path. Hidden/idle/saved panels do not request live spatial samples.
These source/module changes require their own native checks; old frozen raw
qualification does not silently carry forward.

Developer keeps sparse embedding and single-D1 late labels as separate explicit
experimental choices. The distinct optional Pyannote-primary plus anonymous
CurrentDelayed refiner checkbox is visible but disabled, defaults false, and
does not replace either attribution mode. It requires measured combined native
admission before a normal operator can enable it. Provisional correction remains
separately disabled. The ordinary default profile is unchanged.

The worker/launcher also restore the retained **pre-exec** allocator settings
`MALLOC_ARENA_MAX=1`, `MALLOC_MMAP_THRESHOLD_=131072`, and
`MALLOC_TRIM_THRESHOLD_=131072`. Worker checks inherited values after registering
its owner and records them in ENVELOPE. Address-space/CPU/stack/file bounds are
unchanged. Environment restoration alone is not evidence that combined model
loading fits; model-stage native measurements remain authoritative.

## Host-only checks in PowerShell

The tests instantiate no Tk window or model and contact no device. They check
the retained0/90/180 degree mapping, visual-only zero, fragmented bounded
telemetry/diagnostic separation, explicit remote diagnostic state and History
identity. Inputs are this source directory and a fresh private receipt directory.
Outputs are the actual early CPU14 owner and TEST_RESULT.
The focused integration test
`test_runtime_integration.RuntimeIntegrationTests.test_gui_snapshot_stays_in_memory_and_allocator_is_set_before_exec`
also checks the real Manager collector, pre-exec environment and visible-panel
marker without creating a Tk window. Use that test name in the same wrappers.

```powershell
$env:LIVE_UI_ENTRY = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/storage-preparation/runtime-ui-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $env:LIVE_UI_ENTRY | Out-Null
Set-Location 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_UI_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_runtime_ui')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun))); raise SystemExit(not r.wasSuccessful())"
```

Command Prompt and Anaconda Prompt:

```bat
set "LIVE_UI_ENTRY=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\runtime-ui-%RANDOM%-%RANDOM%"
mkdir "%LIVE_UI_ENTRY%"
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_UI_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_runtime_ui')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun))); raise SystemExit(not r.wasSuccessful())"
```

For real native controls use `README_NATIVE_GUI_DRIVER.md`. Its inspect workflow
checks10 stable fullscreen samples, scrolls each required control wholly into
the viewport, invokes orientation show/hide and visual recenter, and exits.
Full live Save/Discard/History Replay requires its explicit workflow and actual
admission. Host checks do not prove native visibility, sensor quality or touch.

## Current07 review fixes and focused verification

`emit_spatial` remains the compatible worker callback, and now also projects
health and optional-refiner diagnostics through `status_message`. It reuses
already-collected state; it adds no hardware/SQLite polling and no disk log.
Each UTF-8 record is at most4096 bytes. Health emits at most once per second;
diagnostics are immediate. `StreamDecoder` routes these into only Manager's
latest health and latest diagnostic records, outside WORKER.log. Developer
renders them during a session, including backlog, source/drop counters, explicitly
scoped diarizer-push rolling RTF, current-process memory/CPU and child failure/lag.
Current-process memory is never presented as whole-unit residency. Captions keep
the existing SQLite consumer; no caption/transcript array enters this channel.
SpatialViews geometry, provider observations and primary motion are unchanged.

The Nemotron preset is cleared and disabled while Pyannote is selected. The
revision-window entry is disabled unless a correction/late-label mode consumes
it. Switching to Nemotron enables its preset again. The native programmatic GUI
driver verifies the disabled controls and refuses a nondefault retained revision
window that the actual GUI cannot edit. No capture starts from these changes.

Run only the new `test_review_fixes` module through the registered CPU14 owner
wrapper below / in [README_PIPELINES](README_PIPELINES.md#run-the-focused-tests):
PowerShell uses `& 'C:/Users/amiri/anaconda3/python.exe' -B 'G:/PRIVATE/registered_tests.py'`;
CMD or Anaconda Prompt uses `"C:\Users\amiri\anaconda3\python.exe" -B "G:\PRIVATE\registered_tests.py"`.
The wrapper must set affinity[14], write numeric PID/create_time REGISTERED_OWNER
in a fresh private preparation directory, then load that test module. Inputs are
synthetic maps, fake device/inode records and fragmented channel messages; outputs
are test results, no Tk window or native inference. Five new focused checks passed:
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-review-tests-4352f3f25200401f8a7a16aba22c7c08/RESULT.json`.
The earlier07 GUI driver failed before Start on a locator mismatch. Build08
GUI02 subsequently passed the repaired programmatic300s live/raw Save, complete
saved replay, discard and Exit workflow, with43 Tk controls checked and full
physical closure. Saved pipeline04 and Pyannote/TitaNet pipeline05 also passed
their complete matched input. These are scoped functional results; physical
touch, visual quality, representative quiet-room speech/identity quality and
optional parallel qualification are separate. See `NATIVE_RESULTS.md`.

## Build08 reviewed optional eligibility

The optional checkbox remains off and disabled without an exact reviewed v2 combined receipt. Its label and explanation update with selection. If a reviewed ordinary policy matches, it can be selected explicitly; Manager and worker repeat the proof/resource checks. Health includes separately scoped whole-owned-unit RSS/PSS for this child experiment. Qualification permits cannot enable the normal UI. See [optional admission and actual metric scopes](README_OPTIONAL_REFINER.md).
