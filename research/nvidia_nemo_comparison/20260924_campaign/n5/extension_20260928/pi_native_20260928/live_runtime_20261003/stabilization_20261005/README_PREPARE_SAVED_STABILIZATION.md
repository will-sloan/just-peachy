# Prepare a saved-session backend replay payload

`prepare_saved_stabilization_payload_v1.py` prepares one fresh host payload for
the already backed `native_saved_stabilization_check.py`. It never connects to
the Pi, launches a model, captures sound, starts a GUI or fabricates a session.
The selected `host_stabilization_operations_v2.py --writes` dispatcher performs
its own current owner, boot, unit, lease, resource and admission checks later.

The generator supports the six intended operator choices:

- `pyannote_redimnet`
- `pyannote_titanet`
- `delayed_redimnet`
- `delayed_titanet`
- `chunk52_2t_redimnet`
- `chunk52_2t_titanet`

It binds only the explicit build24 package and Saved source. It reads the real
host package manifest and every declared member before loading only its pure
profile catalogue. The exact returned selection and chooser label are used;
there is no implicit backend fallback. Enrolled names is the default application
Mode. Spatial and assigned-seat Modes require the retained rich-session evidence
described in `README_NATIVE_SAVED_STABILIZATION_CHECK.md`.

## Inputs

Supply the current observed boot UUID, selected host package directory, actual
staged build24 path and raw-byte `PACKAGE_MANIFEST.json` SHA, actual kept recording
UUID and original raw-byte `session.json` SHA. The original recording must be
mono16k, kept, no longer than 30 seconds and visible in the bounded History page.
`--session-json` optionally verifies the same metadata in an existing private PC
mirror; it does not replace the native source verification.

Provide a fresh `classic-ui-check-NN` label and distinct host dispatch label. Do
not reuse a failed or consumed label. A payload lifetime is explicit, 60 through
600 seconds, default 590. Prepare each backend operation immediately before its
dispatch after the preceding operation and its independent copies are closed.
Do not prepare six expiring payloads in advance.

Both target and complete independent PC copy reserve are **100663296 bytes
(96 MiB)**. This is a new finite qualification reservation, not a change to an
old admission or normal storage policy. The generator uses a cumulative 8 MiB,
600-second host preparation scope and preserves C: 50 GiB and G: 75 GiB free
floors plus its preparation and independent PC reserve.

Use `--operation finalize` only after independent native job closure; it binds
the existing test output root. `--discard-output` affects only the new replay
output; default behavior retains it using the actual Save control. Original
recordings are read only. Assigned Modes alone accept `--seating FILE.json` with
exact keys `rows`, `strength`, `acknowledged`; the actual retained seat editor
validates actual person IDs and layout. The draft refers to the recorded array
reference, not a current live pose.

## Outputs

A fresh private directory below `live-runtime-20261003/audit-preparation` holds
early CPU14 `REGISTERED_OWNER.json`, the finite scope, exact source backups and
independent restores, compact source pins, `SOURCE_CLOSED.json`, and exit intent.
Normal preparation writes `PAYLOAD.json`, `ACTION.py` and independent backup and
restore copies of both, plus `RESULT.json` with the ready dispatcher argument
list. Status is `PREPARED_HOST_SAVED_PAYLOAD_NOT_DISPATCHED`.

The result does not claim a native admission, source availability, model/ASR
result, native replay, physical capture or closure. The dispatcher and helper
still require those actual checks and natural closure before certification and
the full private PC copy. No base64, private speech text or recording payload is
printed. Exit intent is separate from an independently checked exact process
closure.

`--self-check` backs and independently restores this generator, this README,
the pinned native helper and selected dispatcher before compilation. It checks
only changed source syntax and three invalid UUID/label/hash inputs; it does not
load a package or issue a synthetic payload.

## PowerShell

Replace the capitalized placeholders with the actual observed values. The
paths below intentionally do not invent a recording UUID, boot or package pin.

```powershell
$s = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$python = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $python -B ($s+'/prepare_saved_stabilization_payload_v1.py') --operator-id pyannote_redimnet --source saved --package-dir 'ACTUAL_HOST_BUILD24_PACKAGE' --native-package '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-24' --package-manifest-sha256 ACTUAL_BUILD24_MANIFEST_SHA --boot-id ACTUAL_BOOT_UUID --session-id ACTUAL_KEPT_UUID --session-metadata-sha256 ACTUAL_RAW_SESSION_JSON_SHA --session-json 'ACTUAL_PRIVATE_SOURCE_SESSION_JSON' --native-label classic-ui-check-NN --dispatch-label saved-backend-NN-launch --data-root '/home/peachyprototype/JustPeachy/data/runtime-v29' --ttl-seconds 590
```

Read the returned `RESULT.json`. Its `command_argv` names the exact action and
payload files. After the preparer owner is independently closed and while the
payload remains fresh, the authorized operator can use:

```powershell
& $python -B ($s+'/host_stabilization_operations_v2.py') --label saved-backend-NN-launch --action 'ACTUAL_PREPARATION_OUTPUT/ACTION.py' --payload 'ACTUAL_PREPARATION_OUTPUT/PAYLOAD.json' --writes
```

For finalize, generate another fresh payload with the same native test label,
actual pins and `--operation finalize`, then use a distinct host dispatch label.

## CMD and Anaconda Prompt

Both use the same pinned project Python; no package installation is needed.

```cmd
set JP_STABILIZATION=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_STABILIZATION%/prepare_saved_stabilization_payload_v1.py" --operator-id pyannote_redimnet --source saved --package-dir "ACTUAL_HOST_BUILD24_PACKAGE" --native-package /home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-24 --package-manifest-sha256 ACTUAL_BUILD24_MANIFEST_SHA --boot-id ACTUAL_BOOT_UUID --session-id ACTUAL_KEPT_UUID --session-metadata-sha256 ACTUAL_RAW_SESSION_JSON_SHA --session-json "ACTUAL_PRIVATE_SOURCE_SESSION_JSON" --native-label classic-ui-check-NN --dispatch-label saved-backend-NN-launch --data-root /home/peachyprototype/JustPeachy/data/runtime-v29 --ttl-seconds 590
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_STABILIZATION%/host_stabilization_operations_v2.py" --label saved-backend-NN-launch --action "ACTUAL_PREPARATION_OUTPUT/ACTION.py" --payload "ACTUAL_PREPARATION_OUTPUT/PAYLOAD.json" --writes
```

For the one focused host source check only, run the generator with `--self-check`
instead of the preparation inputs after native prereads permit a short host
owner. Do not rerun a healthy check simply for a version number.
