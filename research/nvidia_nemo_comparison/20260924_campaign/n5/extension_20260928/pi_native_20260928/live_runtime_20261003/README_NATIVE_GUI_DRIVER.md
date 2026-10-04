# Native programmatic GUI integration

`native_gui_driver.py` opens the actual new launcher through `launcher.show`
with a real `Manager`. It discovers the actual Tk widgets by exact labels,
sets their bound controls, and invokes the actual buttons. It does not implement
a replacement GUI or bypass Manager authorization, source ownership, storage
admission or process closure. Importing it does not import Tk or application
models. Its executable entry refuses a Windows/non-CM5 host before any GUI or
model import.

This is **programmatic integration**, not physical-touch or visual-quality
qualification. Start reaches the launcher's actual consent callback; the driver
records its explicit authorized answer without claiming the modal dialog was
visually tested. Every selected control, button invocation, source-count Stop
boundary and exact worker/source closure is written as a private receipt.
It does not set any fake native-qualification flag.

## Workflows and inputs

The default `--workflow inspect` maps the real Tk window, verifies its measured
480×800 fullscreen client geometry at desktop position0,0 for10 consecutive
checks100ms apart, checks actual controls (including disabled provisional
correction and admission-gated optional refinement), selects the requested values and invokes **Exit to desktop**.
It launches zero model workers. Prefer this when headless evidence already
proves unchanged processing functions.

Additional explicitly selected workflows are:

- `capture-discard`: actual Start, programmatic consent for live input, actual
  Stop after the requested committed-sample boundary, exact closure, then
  **Discard audio** and **Exit to desktop**. A pinned saved WAV may replace live
  input; its duration must exceed the planned Stop boundary.
- `capture-save-replay-discard`: the same initial Start/Stop, then **Save
  processed**, **Recordings → Replay recording** for that complete kept session,
  full replay and closure, discard the new replay session, and exit. The original
  kept recording remains. This intentionally starts two model workers.
- `replay-discard`: select an existing kept recording through actual paged
  History, replay its full timeline using the current profile, verify the complete
  accepted sample count, discard only the newly created replay session, and exit.
  This needs one model worker and reuses existing headless audio evidence.

Inputs are the immutable package/binding, actual owned unit and ownership
receipt, a fresh private owner directory, the current runtime data root, and a
SHA256-pinned JSON object containing `RuntimeSelection` fields. The driver sets
only controls actually present in this GUI. Unsupported refinement controls or
provisional correction are rejected. The selection's `input_source` is `saved`
for `replay-discard`; `--saved-session-id` names that kept recording. For a WAV,
provide both `--saved-path` and `--saved-sha256`.

`--stop-after-seconds` defaults to 5 and must be greater than zero and at most
300. The actual GUI retains its existing five-minute SessionPolicy; the driver
does not monkeypatch policy or model constructors. The chosen service must have
enough remaining time for each real Start's full policy and closure allowance,
including a second Start if replay is requested. Output storage reservations
must likewise include all new sessions, work metadata, logs and private receipts.

Before opening Tk and after exit, read-only `wlr-randr` inspection must confirm
the existing enabled display with `Transform: 270`. The driver never changes
rotation, output mode, desktop files or shortcuts. Window geometry and widget
visibility are recorded from Tk. Screenshots are omitted; `GUI_RESULT.json`
explicitly reports that no screenshot, physical-touch or visual-quality
qualification occurred. A separate private screenshot inspection can be added
to an authorized native run when needed.

The launcher requests fullscreen only after its first actual Map event. This
avoids the known desktop top-bar offset without changing the preserved display
rotation. Failure to stabilize at480×800+0+0 within10 seconds fails the driver.
The driver now selects the actual containing tab and scrolls controls wholly
inside the visible Canvas viewport before invocation. Inspection reaches Start,
Save, Discard and direction controls, then invokes orientation show/hide and
visual-only recenter. This tests widget reachability only; an idle inspection
cannot claim live BMI270 or direction quality. See `README_RUNTIME_UI.md`.

## Native invocation contract

Run through a separately reviewed owned-unit wrapper which registers its actual
PID/start-ticks/boot before reading this entrypoint and verifies the full package.
The driver registers a second actual owner receipt before further project
imports. It requires CPU3 inside the shared CPU2/3 service, finite address space
no greater than 768 MiB, 1 MiB stack and a finite positive file allowance. The
existing unit receipt must contain a finite `deadline_monotonic`.

```text
native_gui_driver.py --binding /exact/package/BINDING.json --package-manifest-sha256 <manifest-sha256> --unit <exact-owned-unit> --unit-ownership /private/UNIT_OWNERSHIP.json --owner-directory /private/fresh-gui-driver --data-root /owned/runtime-data --selection /private/GUI_SELECTION.json --selection-sha256 <selection-sha256> --workflow inspect
```

For a full history pass add `--workflow replay-discard --saved-session-id <id>`
instead of `inspect`. For the two-session workflow choose
`--workflow capture-save-replay-discard --stop-after-seconds 5`.
The reviewed `launch_gui_check_action.py` uses the existing shared qualification
wrapper to verify the full package and invoke this entrypoint in that owned
service. It does not bypass profile, raw or model admission. Do not run the
native command from the PC or improvise an unowned GUI process.

Outputs include `REGISTERED_OWNER.json`, `DISPLAY_BEFORE.json`, numbered
action/geometry/widget/consent/closure receipts, `DISPLAY_AFTER.json`, and
`GUI_RESULT.json`. Normal runtime sessions retain their own worker/source
receipts. Save and Discard are invoked only after successful reaping, reader
join and exact nested source closure. Any GUI error or admission refusal requests
Stop; exit waits for closure. A killed or failed run cannot certify success.
The external unit monitor still proves final process/cgroup closure and copies
all private output independently.

## Full integrated native job

Inject `launch_gui_check_action.py` through the registered `host_operations.py`
workflow. The pinned JSON payload supplies `package`,
`package_manifest_sha256`, fresh `boot_id`/numeric `expires_unix`, unique label
`gui-qualification-NN`, the exact selected `RuntimeSelection` fields, complete
default `SessionPolicy` (`maximum_session_seconds:300`, `developer_soak:false`,
`max_drain_seconds:120`, `max_backlog_seconds:120`, `model_load_seconds:120`,
`cleanup_seconds:60`), `workflow:"capture-save-replay-discard"`,
`stop_after_seconds:45`, `stop_mode:"button"`, `save_raw:false`, `runtime_seconds:1500`, and the exact derived
`maximum_output_bytes`. Initial saved-file input additionally needs its exact
canonical `saved_path` and `saved_sha256`; History replay always uses the kept
session and all of its authoritative float segments.

The independent reservation sums two complete300-second storage estimates,
including qualified raw for the first live session when enabled, processed-only
replay, metadata/SQLite duplicates, bounded native/log copies, and24MiB for
GUI/wrapper output. The helper recomputes the total and refuses a different
number; its absolute upper bound is1GiB with1024 regular files. It never sizes
the reservation from the shorter45-second functional test. Each session retains
the actual300-second GUI policy and600-second complete deadline. The1500-second
unit accommodates both deadlines plus startup/second-Start room; service Stop
remains30 seconds. Normal native and independent PC free-space floors remain.
The monitor must support this reviewed GUI allocation before dispatch; the
older256MiB/256-file monitor cannot be used for this larger workflow.

The dispatcher reads only display-address variables from the actual existing
systemd user manager, requires DISPLAY/WAYLAND_DISPLAY/XDG_RUNTIME_DIR, and
passes those exact values. Missing display addresses fail instead of guessing.
It changes no rotation, desktop entry or autostart setting. Output uses fresh
`.../live-runtime-tests-20261003/gui-qualification-NN/gui` for driver receipts
and sibling `data` for Manager/session storage. Each of at most256 action
receipts is bounded to64KiB. The full workflow records programmatic live consent,
actual Start, valid cached device-direction/motion arrival, orientation toggle
and visual-only recenter, finite Stop, exact worker/source closure, Save
processed, full History Replay, replay closure, Discard, and Exit to desktop.
No physical-touch, screenshot or acoustic/spatial accuracy claim is inferred.

PowerShell command inside the early CPU14 wrapper from
`README_QUALIFICATION_DISPATCH.md`:

```text
host_operations.py --label gui-launch-NN --action launch_gui_check_action.py --payload G:/PRIVATE/REVIEWED_GUI_PAYLOAD.json --writes
```

Command Prompt and Anaconda Prompt use the identical arguments and the qualified
`C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe`.
Inputs must use actual fresh reviewed hashes/paths. No dispatcher/native GUI
execution occurs in the host tests. To check its capacity/deadline rules, run
`test_qualification_dispatch.DispatchTests.test_gui_reserves_two_full_operator_sessions_and_second_start_room`
in the registered test wrapper, with `LIVE_QUALIFICATION_TEST_ROOT` pointing to
an owned private test subdirectory.

## Hardware-free tests from PowerShell

The tests create no Tk instance, model, microphone, network connection or native
process. They check exact control lookup, explicit programmatic consent,
closed-before-disposition rules, unsupported controls, viewport scrolling with
clipping refusal, and host-entry refusal.

```powershell
$env:LIVE_GUI_CHECK_ENTRY = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/storage-preparation/gui-driver-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $env:LIVE_GUI_CHECK_ENTRY | Out-Null
Set-Location 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_GUI_CHECK_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_native_gui_driver')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,gui_created=False,native_executed=False))); raise SystemExit(not r.wasSuccessful())"
```

## Command Prompt and Anaconda Prompt

```bat
set "LIVE_GUI_CHECK_ENTRY=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\gui-driver-%RANDOM%-%RANDOM%"
mkdir "%LIVE_GUI_CHECK_ENTRY%"
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_GUI_CHECK_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_native_gui_driver')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,gui_created=False,native_executed=False))); raise SystemExit(not r.wasSuccessful())"
```

Current07 selector review: the driver requires the Nemotron preset to be cleared
and disabled for Pyannote, and selects it only for Nemotron. It checks that the
revision-window entry is enabled only for the single-D1 late-label route. A
nondefault retained revision window is rejected before Tk/native startup because
the GUI has no active control for it. The new no-Tk `test_review_fixes` checks are
run through the same CPU14/early-owner PowerShell, CMD or Anaconda wrapper; this
source fix does not substitute for a native GUI exercise.

## Build08 optional state checks

The driver accepts an explicitly selected optional mode only when the real checkbox reports reviewed combined admission and is enabled. An unavailable control must remain disabled; optional capture defaults off. The revision window is consumed only by selected optional/single-D1-late attribution. Native Start still goes through Manager's exact receipt and current-resource checks; the GUI driver cannot generate a permit or bypass them. See [README_OPTIONAL_REFINER](README_OPTIONAL_REFINER.md).

## Actual07 failure and08 repair

The closed/mirrored `gui-qualification-01` failed before Start: `gui/013-failure.json` could not locate the sparse-refresh label. Frozen07 launcher text contained the U+00E2/U+20AC mojibake sequence while the driver expected a real dash; the revision label, saved-WAV button and title had the same encoding defect. GUI_RESULT records zero model sessions, no Stop invocation, successful Exit and ten stable fullscreen measurements. This is a programmatic GUI locator/configuration failure, not a speech-model or saved-input failure.07 files/evidence remain unchanged.

Build08 repairs only those exact visible strings with ASCII punctuation, and the focused test reads actual launcher/driver AST strings. It checks every string in launcher/runtime_ui/runtime_ui_channel/driver for the known mojibake sequence and matches the affected real labels. It does not open Tk or certify touch/visual quality.

## Explicit300-second policy boundary and raw retention

Default `--stop-mode button` invokes the real Stop button at its requested1–300s committed-sample target. `--stop-mode policy --stop-after-seconds 300` is a distinct live capture experiment: the driver injects no Stop, waits for the existing normal300s source policy, then requires exactly4,800,000 processed samples and successful stopped state. A300s policy alone is never reported as300s observed capture. Premature EOF or failure refuses the workflow. The outer unit/runtime and two complete300s storage reservations are unchanged.

For the requested live workflow use:

```text
--workflow capture-save-replay-discard --stop-mode policy --stop-after-seconds 300 --save-raw
```

The action payload carries `stop_mode:"policy"`, `stop_after_seconds:300`, `save_raw:true` and the ordinary policy. It requires an actually raw-enabled binding; admission still verifies the exact source proof.

After physical closure, `--save-raw` invokes the actual **Save raw + processed** button. It requires a qualified raw mode, `include_raw=true`, and exact raw/processed sample-clock agreement. History Replay uses the entire kept processed timeline and waits for natural EOF; the driver no longer injects Stop at the replay boundary. The new replay is discarded only after exact closure/full sample count, and original kept raw/processed counters and choice must remain unchanged. The default save choice stays processed-only. `GUI_RESULT` distinguishes requested mode, actual policy boundary, injected Stop count, saved raw choice and completed natural replay.

Five focused host checks passed at `G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-gui-repair-tests-63002d44d66f411bb0f485faba3b03be/RESULT.json`. Run `test_gui_repair` using the same registered CPU14/early-owner PowerShell, CMD or Anaconda wrapper above. Inputs are actual source strings and synthetic metadata; outputs are private TESTS/RESULT. These host checks alone prove no native capture. The subsequent separate actual08 GUI02 check passed policy300 at4800000 samples, raw+processed Save, full saved EOF, replay discard and Exit; see `NATIVE_RESULTS.md`. Physical touch and visual quality were not evaluated.

## Actual immutable08 GUI02 storage and replay evidence

The closed `gui-qualification-02-monitor-01` PC mirror and independent
`storage-preparation/gui02-review-02/REVIEW.json` confirm a300-second live
recording:4,800,000 processed and qualified physical raw samples,30 segments per
stream, Save raw + processed after closure, full History replay to natural EOF,
replay-only Discard and Exit. Original kept session
`5e9d3ff46f654c178ea2e2dffa497433` remains intact. The review checked all201 files,
contiguous clocks and concatenated raw SHA, without media or transcript display.
See README_GUI_RECORDING_REVIEW.md for exact aggregates, commands and limits.

Both sessions have zero caption rows, so this run establishes no caption-render,
recognition-quality or speaker-accuracy result. Programmatic Tk actions and10
stable480x800 fullscreen checks do not establish physical touch or visual quality.
External export01 subsequently failed before storage import; its closed failure
is preserved. Fresh-child export V2/production09 is a separate native evidence
gate, documented in README_OWNED_EXPORT.md. No hour-runtime claim follows from
this300-second recording/replay result.
