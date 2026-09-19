# S6D expanded capture helpers

Purpose: prepare and validate six-output packed S6D recordings under one explicit device owner, with exact transport provenance and restoration. The transport helper is model-free and opens no audio or device handles. Hardware execution belongs only to the separately reviewed capture owner and requires a bound launch plan and safety receipt.

`s6d_capture_transport.py` inputs are finite four-microphone arrays, six-channel decoded PCM counts, a known profile (`P_MAIN6`, `P_SCAN6`, `P_INPUT_QA6`) and explicit file bindings. Outputs are packed counts/bytes, reordered mux arguments, checksums, exact input-QA comparisons and descriptive raw-output QC. It imports neither an old campaign owner nor old report globals. Raw ASR/PP outputs remain unity gain. Historical O0+3dB is a separate host model adapter; new focused-beam gain policy requires dedicated calibration and never per-probe fitting.

Output order is logical `[L_PK0,R_PK0,L_PK1,R_PK1,L_PK2,R_PK2]`; mux setter order is `[L_PK0,L_PK1,L_PK2,R_PK0,R_PK1,R_PK2]`. P_INPUT_QA6 microphones occupy decoded columns2–5. MAIN/SCAN have no microphone echo and cannot prove exact injected microphone samples per scene. Duplicate processed beams are descriptive, not automatic transport failure. All source offsets are common across microphones; no independent waveform alignment or normalization is performed.

Use the existing Anaconda Python3.12 for the physical capture stack (vendor dependencies target CPython3.12). EdgePython3.11 remains the separate model runtime. The pure transport tests work under either interpreter with NumPy; they do not load vendor libraries, enumerate hardware, play sound or create an evaluation result. No installation is required.

PowerShell:

```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$s6dSim\scripts\s6d_capture_transport.py"
```

Anaconda Prompt / Windows CMD:

```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%S6D_SIM%\scripts\s6d_capture_transport.py"
```

Expected output: JSON `PASS_MODEL_FREE`, individual mux/PCM24/QA/swap/duplicate/missing/repeated-source/silence checks, and zero hardware/audio calls. A model-free PASS does not qualify physical routing.

`s6d_telemetry.py` provides a Python lifecycle wrapper for `s6d_native/S6DQueuedTelemetry.cs` through `Run-S6D-Telemetry.ps1`. Inputs: explicit official DLL directory, new output directory, finite duration, fast/gain/slow rates. The capture owner alone starts it while holding the shared hardware lock. There is no direct Python CLI that silently connects. Outputs: exact source/DLL bindings, transaction/sample logs, host-received JSONL, per-field counts/rates, process status and explicit pending-read/cleanup proof. Memory keeps only512 recent rows; complete evidence streams to disk. No alternate xvf_host is run while this reader owns USB.

Fast angles/energy/selected arrays request20Hz each; gain requests2Hz and slow diagnostics0.2Hz, with at most one supplementary field after a fast cycle. Every reply preserves its transaction/host-arrival bounds. Missing optional command-map entries are `UNAVAILABLE`; an existing but type/RW/count-mismatched descriptor rejects admission. PP_AGCGAIN is writable in the map (`CMD_READ_WRITE=2`) but this adapter imports only read USB operations. The required fast queued-response guard is preserved; supplementary parameter reads can have a complete immediate first response, recorded with one attempt. No new DSP-frame or cross-field atomicity is claimed. Nonfinite values remain null; negative/out-of-range RT60 values retain their raw finite number plus invalid reason. AEC flags with zero far-end are not evidence of motion or speaker identity.

Descriptor authority: installed official `resource_indices.yaml`, `aec_cmds.yaml`, `shf_aec_cmds.yaml`, `audio_cmds.yaml`, `shf_pp_cmds.yaml`, and `modules/host_cmd_map/command_map.cpp`. AEC generic dedicated commands retain the proven release offset70 (angles75, energy80, current/min idle77/78); explicitly indexed SHF commands use their own indices (path0, converged3, RT60 9, PP gain13). Audio-manager ordinals are current2, min3, max-control5, I2S current7, min8, selected11. Resource AEC=0x21, PP=0x11, audio=0x23. Type enum INT32=2, FLOAT=3, UINT32=4, RADIANS=5; read-only=0, read-write=2. Idle values are documented10ns ticks; MAX_CONTROL_TIME's unit remains unspecified. Runtime metadata validation checks these declarations before opening USB. Actual physical support remains unqualified until the root's reviewed hardware run.

Compile C# only, without loading either vendor DLL or calling USB (PowerShell):

```powershell
& 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -NonInteractive -File "$s6dSim\scripts\s6d_native\Run-S6D-Telemetry.ps1" -DllDirectory '.' -CompileOnly
```

Anaconda Prompt / CMD:

```bat
"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File "%S6D_SIM%\scripts\s6d_native\Run-S6D-Telemetry.ps1" -DllDirectory "." -CompileOnly
```

Expected output is `COMPILED_ONLY`, hardware/DLL calls zero. The PS script's separate `InspectOnly` option loads vendor metadata DLLs; it is not part of this compile command. Actual Run connects to USB and is reserved for the bound owner after root review. No hardware run was executed while developing these helpers.

## Owner inputs, immutable outputs and acceptance

`s6d_capture_owner.py` has two explicit actions: `check-plan` verifies JSON, existing files and hashes without importing the hardware stack; `execute` admits only named attempts from a source-bound plan and coordinator authorization. It never creates a broad campaign implicitly. The owner uses the shared `measurement_app/hardware.lock`, refuses active recorder ports 8765–8767, and refuses unresolved `STARTED` attempts or any prior owner without an exact, hash-bound restoration receipt. An exited process is insufficient restoration evidence.

Every source is an existing finite, four-channel, 16 kHz audio file. `duration_sec` is its exact duration, at most 900 seconds. The helper performs the same one-time even-PCM24 quantization and adds common zero guards: one second before the original source and three seconds after it. The original source samples retain their order and spacing. The source starts at logical input frame 16,000. These guards change silent adaptation relative to the historical S4.5 run; all new same-pass output taps share that changed history. No equality of hidden DSP state with historical captures is claimed.

The entire guarded carrier is submitted in one audio stream. A continuous conversation is one 900-second source inside a 904-second carrier, with no intervening reset or control setter. The native callback can append at most 16,383 additional 48 kHz frames, using valid packed-silence markers. Full callback input blocks, including that terminal padding, are retained. The owner charges `source seconds + 4 + 16383/48000` before the reset or telemetry start, so a failed setup, qualification, repeat, enrollment or continuous pass consumes its attempt and conservative duration. It records actual callback submission progress separately; neither host submission nor a timestamp proves acoustic playback. The hard ceilings are 480 attempts and 21,600 charged seconds across the shared ledger.

Three-second tail space is an explicit guard, not a measured latency claim. Source leading/trailing zero support is recorded. P_INPUT_QA6 must recover every nonzero injected microphone sample with one common exact offset. MAIN/SCAN lack microphone echo, so per-scene exact MIC recovery remains unobservable. Processed output delay and complete useful source-tail coverage remain pending physical tagged-control qualification; results preserve those limits. No output stream receives an independently fitted offset or gain.

`status` and `transport_integrity_status` concern transport, callback, framing, telemetry and (for QA) exact input recovery. `level_screen` separately marks each affected stream `LIMITED` for any rail sample or a missing payload that the plan required. Limited streams retain original PCM and unity gain; the bank does not silently normalize, repair or discard them. This matches the frozen original policy that retained and flagged affected PP output. Focused silence and equal beam outputs can be genuine; their identity requires the physical tagged controls. `PASS_LEVEL_SCREEN` is only a necessary level screen, not route qualification. The original O0 +3 dB host adapter remains separate and is never baked into these raw recordings.

The payload root must be a new child of `G:\Just_Peachy_S6D`; reports must be under this simulation's `reports\S6D`. `shutil.disk_usage` enforces C: at least 50 GiB free, G: at least 75 GiB free after attempt reservation, and at most 40 GiB of newly generated payload below the bound root. Old unrelated recordings are not charged against that new-payload ceiling. Runtime storage checks run every five seconds during capture. The callback queue holds at most 64 blocks of at most 16,384 stereo PCM24 frames; overflow aborts and marks the attempt failed. It never silently drops a block.

Reports are under `report_root\hardware_batches\<batch>`: admission, source epoch, initial state, owner receipt, summary, failure detail and exact restoration. The global `physical_ledger.json` binds every attempt and owner restoration. Per-attempt payloads are under `payload_root\beam_bank\<case>\<profile>\<attempt>`: packed input bytes, native stereo PCM24 WAV, decoded six-channel PCM24 WAV, six linked raw mono WAVs, configuration, callback metadata, telemetry evidence and `case_result.json`. File bindings have absolute `path`, `sha256`, and optional `bytes`.

On every normal or exceptional exit the owner first requires proof that the telemetry process closed USB with no pending read and that audio handles closed. It then disables packed input, restores the initial USB width, reapplies every recorded static setting using the existing exact float32 round-trip recovery, and compares complete identity/settings/observe-only readbacks. Unproven telemetry/audio closure withholds competing control commands and blocks subsequent ownership. No new owner may presume restoration merely because a PID disappeared.

The V3 owner stores mutable audio closure state outside the capture return value. It marks this state unclosed before the RawStream constructor, then updates it in `finally` before writing metadata. Constructor failure or an unclosed stream therefore remains fail-closed even if metadata writing also raises and no capture result returns. The targeted fixture combines unclosed mocked handles and a metadata-write error and verifies that restoration remains withheld despite proven telemetry closure. V2 source/receipts remain preserved separately.

## Plan and coordinator authorization schema

The coordinator writes real input bindings and the existing setup acknowledgement; placeholders below are documentation only. The safety acknowledgement is strictly about the XVF's own analog outputs. It says nothing about PC output devices the user may keep for listening. It must record the actual earlier user confirmation, not an invented response.

```json
{
  "schema": "s6d-capture-plan.v1",
  "report_root": "C:/.../simulation/reports/S6D/20260913T195357Z",
  "payload_root": "G:/Just_Peachy_S6D/20260913T195357Z",
  "limits": {"attempts": 480, "charged_playback_seconds": 21600, "payload_bytes": 42949672960},
  "safety": {"path": "C:/.../xvf_analog_setup_ack.json", "sha256": "ACTUAL_HASH"},
  "baseline": {"path": "C:/.../S4_5/20260909T031300Z/HARDWARE_BASELINE.json", "sha256": "ACTUAL_HASH"},
  "output_level_policy": {"path": "C:/.../S4_5/20260909T031300Z/OUTPUT_LEVEL_POLICY.json", "sha256": "ACTUAL_HASH"},
  "initialization_policy": {"path": "C:/.../S4_5/20260909T031300Z/INITIALIZATION_POLICY.json", "sha256": "ACTUAL_HASH"},
  "audio_acceptance_policy": {"path": "C:/.../s6d_audio_acceptance.json", "sha256": "ACTUAL_HASH"},
  "attempts": [{
    "attempt_id": "qual_tag_main_01", "case_id": "tagged_control", "profile": "P_MAIN6",
    "role": "qualification", "reset_before": true, "duration_sec": 10.0,
    "source_audio": {"path": "G:/.../tagged_four_mic.wav", "sha256": "ACTUAL_HASH"},
    "payload_expectation": "nonzero", "required_nonzero_streams": ["auto_asr_raw", "auto_pp_raw"],
    "telemetry_rates": {"fast_hz": 20.0, "gain_hz": 2.0, "slow_hz": 0.2}
  }]
}
```

Allowed roles are `canonical`, `qualification`, `repeat`, `enrollment`, `continuous`, and `stress`. Each independent pass resets first. A `continuous` role additionally requires `continuous_dsp_seconds: 900` and `duration_sec: 900`, with one uninterrupted DSP pass. For a zero-input control use `payload_expectation: "silence"` and an empty required-stream list. Nonzero scenes must require both automatic taps; additional focused tap requirements may be predeclared where justified. Every name must occur in that exact profile. Raw focused silence is not independently treated as a dropped transport sample.

The bound safety JSON has `xvf_own_analog_outputs_off_or_disconnected: true` and `user_confirmation_text` copied from the actual setup acknowledgement. The acceptance policy is:

```json
{"schema":"s6d-audio-acceptance.v1","raw_gain":1.0,"max_rail_samples_per_stream":0,"rail_exceedance_action":"LIMITED","missing_required_payload_action":"LIMITED"}
```

The coordinator authorization has `root_review_passed: true`, the exact `plan_sha256`, and `source_bindings` for all executed dependencies. Required files are this README, the owner, transport, Python telemetry wrapper, C# telemetry, PS launcher, `measurement_app/core.py`, `measurement_app/__init__.py`, `measurement_app/queued_telemetry.py`, `measurement_app/telemetry.py`, `s3_hardware.py`, `s4_restore.py`, `s0_common.py`, `s4_common.py`, and the official `xvf_host.exe`, `device_usb.dll`, and `command_map.dll`. Include official descriptor source authorities too. Imported older helpers are bound but their campaign globals/files are never changed. Bindings are checked again after the batch. The snapshot stores each basename once, so source basenames must be unique. A changed file requires a new authorization/source epoch; do not edit frozen launch artifacts.

Check a real prepared plan without hardware (PowerShell):

```powershell
$s6dReport = "$s6dSim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\anaconda3\python.exe' -B "$s6dSim\scripts\s6d_capture_owner.py" check-plan --plan "$s6dReport\physical_plan.json" --authorization "$s6dReport\physical_authorization.json"
```

Anaconda Prompt / CMD:

```bat
set "S6D_REPORT=%S6D_SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\anaconda3\python.exe" -B "%S6D_SIM%\scripts\s6d_capture_owner.py" check-plan --plan "%S6D_REPORT%\physical_plan.json" --authorization "%S6D_REPORT%\physical_authorization.json"
```

Only the coordinator executes a reviewed named batch. This command opens USB/audio and performs the declared setters/playback, unlike every model-free command above:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -B "$s6dSim\scripts\s6d_capture_owner.py" execute --plan "$s6dReport\physical_plan.json" --authorization "$s6dReport\physical_authorization.json" --batch qual_tagged_v1 --attempt-ids qual_tag_main_01
```

```bat
"C:\Users\amiri\anaconda3\python.exe" -B "%S6D_SIM%\scripts\s6d_capture_owner.py" execute --plan "%S6D_REPORT%\physical_plan.json" --authorization "%S6D_REPORT%\physical_authorization.json" --batch qual_tagged_v1 --attempt-ids qual_tag_main_01
```

To request a coordinated stop, create `report_root\STOP_REQUEST.json`; the content can state a reason. The owner checks before each attempt, before opening audio and every 50 ms during capture. Preserve that request and the failed/partial attempt for diagnosis; do not clear a stop or retry an existing ID without coordinator review.

## Model-free fixtures and metadata inspection

`s6d_capture_checks.py` inputs are the current helper sources and original pure packed decoder. It extracts only that decoder function's AST, avoiding the application's audio imports. Outputs are a JSON receipt and optional immutable `--output` file, with source hashes. Fixtures cover mux tags, swaps, duplicates, corrupt markers, missing/repeated samples, no-sound controls, common guards, exact callback bytes, charged padding, STOP before audio, failed-attempt budgets, unresolved owners, bound restoration and retained LIMITED rail evidence. They use mocked audio objects and temporary fixture directories; no device or audio handle is opened.

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -B "$s6dSim\scripts\s6d_capture_checks.py" --output "$s6dReport\capture_implementation\MODEL_FREE_CHECKS_NEW.json"
& 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -NonInteractive -File "$s6dSim\scripts\s6d_native\Run-S6D-Telemetry.ps1" -DllDirectory '.' -SelfTest
```

```bat
"C:\Users\amiri\anaconda3\python.exe" -B "%S6D_SIM%\scripts\s6d_capture_checks.py" --output "%S6D_REPORT%\capture_implementation\MODEL_FREE_CHECKS_NEW.json"
"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File "%S6D_SIM%\scripts\s6d_native\Run-S6D-Telemetry.ps1" -DllDirectory "." -SelfTest
```

Use a fresh output name; receipts are never overwritten. `SelfTest` compiles and checks actual payload decoding for signed/unsigned fields, NaN/null semantics, RT60 invalid values, writable-but-read AGC metadata and malformed payload rejection, with zero vendor DLL calls.

The following exact metadata-only inspection loads the installed official DLL command map, validates all field descriptors and USB identity metadata, and does **not** initialize USB or query the device. It is reserved here for the root's source review checkpoint. Unlike `CompileOnly` and `SelfTest`, it does load vendor DLLs. The supplied DLL folder is the same proven `xvf_host.exe` folder used by the existing recorder.

```powershell
$s6dDll = (Resolve-Path "$s6dSim\..\tools\xvf321\binary\host_v3.0.0\win32").Path
& 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -NonInteractive -File "$s6dSim\scripts\s6d_native\Run-S6D-Telemetry.ps1" -DllDirectory $s6dDll -InspectOnly
```

```bat
set "S6D_DLL=%S6D_SIM%\..\tools\xvf321\binary\host_v3.0.0\win32"
"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File "%S6D_SIM%\scripts\s6d_native\Run-S6D-Telemetry.ps1" -DllDirectory "%S6D_DLL%" -InspectOnly
```

Optional telemetry now has a 20 ms slack requirement and at most a 10 ms retry-poll budget after a fast cycle. A slow completed optional reply disables that field; an incomplete optional read disables it and is explicitly drained once after subsequent fast cycles, with no new optional request meanwhile. An unresolved read after two seconds fails and remains visible through cleanup. Native synchronous USB calls cannot be preempted within C#; all observed call durations are logged, and the wrapper has a finite process deadline. No claim of an absolute per-call latency bound is made. Optional degradation events and final availability/status remain in native results; required fast samples are never replaced by zero.
