# Prepare a focused six-choice live-check payload

`prepare_stabilization_live_check.py` is Windows host-only preparation for the
existing backed `native_stabilization_check.py` used by check13. It does not
connect to the Pi, launch GUI/capture/models, alter galleries or activate a
runtime. It prepares one explicit check; it does not dispatch an automatic sweep.

## Inputs

Supply the actual immutable private package folder, its complete manifest SHA,
actual current boot UUID, exact chooser label, validated selection JSON and an
unused `classic-ui-check-NN` label (14 or higher). No native boot, manifest pin,
process identity or qualification is invented.

The package inventory is read completely and independently checked. Only its
existing pure profiles/operator catalogue are executed for selection validation;
chooser, launcher, source and model functions are never called. The selection
must equal the catalogue's ordinary Live/default-attribution choice:

| Chooser label | Minimal selection JSON fields in addition to input_source=live |
|---|---|
| Pyannote + ReDimNet | diarizer=pyannote, embedding=redimnet |
| Pyannote + TitaNet | diarizer=pyannote, embedding=titanet |
| Nemotron Delayed + ReDimNet | diarizer=nemotron, embedding=redimnet, nemotron_profile=current_delayed |
| Nemotron Delayed + TitaNet | diarizer=nemotron, embedding=titanet, nemotron_profile=current_delayed |
| Nemotron Chunk52 2T + ReDimNet | diarizer=nemotron, embedding=redimnet, nemotron_profile=chunk52_threads2, allow_experimental=true |
| Nemotron Chunk52 2T + TitaNet | diarizer=nemotron, embedding=titanet, nemotron_profile=chunk52_threads2, allow_experimental=true |

The generator expands the selection using the actual retained validator and
compares every resulting field. Hidden/anonymous/source-saved/advanced mismatches
are rejected rather than silently corrected. Later Advanced testing requires its
own reviewed UI helper; this helper selects the standard six Radio choices.

The retained native helper uses **30 s source policy**, **20 s ordinary Stop**,
model load/drain/cleanup guards, **96 MiB target plus independent 96 MiB PC copy**.
It remains programmatic GUI control, not physical-touch or quality evidence.
Default keeps the new recording; `--discard-session` explicitly selects discard
for later checks. Enrollment/prepare_gallery stays false.

## Outputs and guards

Before project reads, actual CPU14/affinity16384/PID/creation_filetime/create_time
are registered. A unique private preparation directory holds exact
PREPARER.py, README, ACTION.py, PAYLOAD.json and original selection input, with
independent .backup/.restore copies and source closure.

ACTION and helper_source_b64 contain the same unchanged check13 helper, SHA
`a0c0936d9e52d1cceff20c8f916ac2584700f75fff77efa1945b3a6a17314bea`.
Preparation retains a finite 600 s/2 MiB scope and C50/G75 GiB floors. Package
reads retain 16 MiB expanded/2 MiB member bounds. Payload expires in 590 s:
prepare it only immediately before the existing full-owner preread/admission.

The separately guarded native dispatcher must use the printed ACTION/PAYLOAD
paths, then independently close/finalize the JOB and preserve its full private
PC mirror. Host process closure must be checked before dispatch. This generator
does not issue native-resource admission or mark a functional/native pass.

## PowerShell

Use the pinned interpreter. Replace package/hash/boot with the actual supplied
values. This example keeps check14's recording:

```powershell
$src = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$package = 'ACTUAL_PRIVATE_BUILD24_PACKAGE_FOLDER'
$manifest = 'ACTUAL_64_HEX_MANIFEST_SHA'
$boot = 'ACTUAL_CURRENT_BOOT_UUID'
& $py -B "$src/prepare_stabilization_live_check.py" --package $package --manifest-sha256 $manifest --boot-id $boot --chooser-label 'Pyannote + ReDimNet' --selection-json '{"diarizer":"pyannote","embedding":"redimnet","input_source":"live"}' --label classic-ui-check-14
```

For reliable JSON argument passing in any shell, use `--selection-file` pointing
to the caller's actual JSON file instead of `--selection-json`. For a later
fresh check, add `--discard-session` only when discard is intended.

## CMD or Anaconda Prompt

Use a real selection JSON file with the fields above, and actual values:

```cmd
set JP_SOURCE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
set JP_PACKAGE=ACTUAL_PRIVATE_BUILD24_PACKAGE_FOLDER
set JP_MANIFEST=ACTUAL_64_HEX_MANIFEST_SHA
set JP_BOOT=ACTUAL_CURRENT_BOOT_UUID
set JP_SELECTION=ACTUAL_SELECTION_JSON_FILE
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/prepare_stabilization_live_check.py" --package "%JP_PACKAGE%" --manifest-sha256 "%JP_MANIFEST%" --boot-id "%JP_BOOT%" --chooser-label "Pyannote + ReDimNet" --selection-file "%JP_SELECTION%" --label classic-ui-check-14
```

Each later backend gets its explicit fresh label and selection. Do not prepare
all six expiring payloads hours ahead, reuse a failed/native label, or reinterpret
quiet source execution as intelligible speech, embedding accuracy or hour
qualification. See README_NATIVE_STABILIZATION_CHECK.md for actual native
workflow, receipts and limits.

