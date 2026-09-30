# Explicit application diarizer controls V1

Purpose: implement the delayed/streaming/chunk52 choice as a separate application control with honest readiness and ownership boundaries. Nemotron diarizer modes and speed methods remain the priority. This is a new control component and prepared class adapter, not a released or capturable application.

D1Controls uses the Controller queue API. It validates before enqueue and again when the command executes. Only IDLE/STOPPED, a D1 backend, no engine/live consumer/enrollment/resident diarizer and no mapped native D1 runtime permit selection. Closing a model does not unload its shared libraries; a runtime change therefore requires a fresh process. Pending selection is separate from committed selection; no optimistic UI update. Queue-full rejects roll back the pending flag. Execution-time failures preserve the previous selection and a control-specific error across the old command-loop reset. Completion yields a detached, exact catalog/geometry/retained-runtime request marked launchable=false.

D1ModePanel has real Tk mode buttons, descriptions and explicit disabled Start. Delayed has a new-factory native pass; streaming/chunk52 display pending new-factory checks and prior latency/throughput limitations. Selecting them is configuration preparation only. D1Controls._start_session rejects D1 before delegating to the old profile-only loader. No mode selection loads/resets/closes a model, stops a source, or claims physical ownership release. The production controller_class wrapper constructor and the original full page/layout are PREPARED, not executed here. The ui_class adapter inserts a navigation button when the base _page creates Mode, and supplies show_diarizer_modes plus a refresh hook. Future installation must bind these exact source hashes and connect a real guarded worker to its independent session, output and Stop/closure path before enabling Start. Do not route a new selection into the old runtime by changing only streaming_profile.

Inputs: D1_APPLICATION_CONTROLS_BINDING_V1.json pins installed v12 Controller/UI/N2ResidentModels sources, exact d1_modes_v1 selector and catalogue. They are read in place; no full release/catalogue or assets copied. New protocol compiles only the exact installed _enqueue/_commands and UI _call methods without alteration. Controller/PrototypeUI objects are detached; original constructors, models and source are not run. The page parent/status display, old Start delegate and consumer-alive cases are declared stand-ins. Runtime presence rejection uses one declared mapped-path fixture; other checks read actual /proc maps. These are not physical capture/cleanup or full lifecycle tests.

Tests:18 changed native cases cover actual Tk navigation and queued selection; duplicate pending request; state change between click and execution with failure retained through command error reset; completed streaming/chunk52 selection and honest availability; RUNNING/STOPPING/ERROR, retained engine/consumer/enrollment/model/runtime, wrong backend, full queue; actual selected UI _call error display; blocked Start and isolated nonlaunchable request. Three real command-loop threads must join with zero pending commands. Tk stays withdrawn throughout, then is destroyed. No visible rendering, touch, healthy model/controller/transport/timer rerun or speed/accuracy claim.

Outputs: fresh Pi d1-application-controls-v1/code/control, reused outer mapped logs/resources/results/closures, passage/CASES.json, CONTROL_SNAPSHOT.json, LAUNCH_REQUEST.json and passage_closure/CONTROL_CLOSURE.json. Host private -evidence directory receives admission/preflight/review/exact backup and audits. All failures/partial bytes retained, no retry or deletion. Source hashes checked before execution and again in independent review. Original app/config unchanged; research/hardware leases and recorded PID/boot/start identities independently checked closed afterward.

Fresh WINDOW_V5 census/admission required:4MiB target+4MiB host,52GiB total/5GiB combined output without reset; fixed32GB Pi/5GiB free. Main768MiB AS/1MiB stack/CPU2,3/shared200%/Tasks64/300s/Stop60s/32MiB file, one model-thread environment; no model loaded. Gate/bootstrap128MiB CPU3. Existing V81 stage/outer writers and passage512KiB/6files plus closure64KiB/2files enforce this small scope. Two extra declared directories reserve128KiB extents. Not full V3 field allocation, filesystem hardquota, source failure cleanup or portable full-host writer qualification. External host metadata remains admission-scoped. Checkpoint2026-10-01T17:47:34Z unchanged.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B dispatch_d1_application_controls_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V180.json'
& $py -B review_d1_application_controls_v1.py
& $py -B backup_d1_application_controls_v1.py
```

## Command Prompt / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_d1_application_controls_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V180.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_d1_application_controls_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_d1_application_controls_v1.py
```

Commands are immutable run-specific recipes, not permission to replay a completed run. Do not invoke --worker/--gate directly. A changed integration or mode needs a fresh destination, binding, README and admission. Review precedes exact backup. The component is imported only by an admitted launcher or integration; it has no unguarded CLI that starts inference.
