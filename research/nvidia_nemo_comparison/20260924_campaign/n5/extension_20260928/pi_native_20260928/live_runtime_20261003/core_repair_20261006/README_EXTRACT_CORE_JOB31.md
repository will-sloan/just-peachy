# Extract an actual build31 JOB

Purpose: `extract_core_job31.py` validates the actual `action_result` returned
by a successful guarded dispatch, then persists that JOB for the existing
native job monitor. One generic host-only CLI handles live, saved and continuous
hour jobs. It never starts, stops or probes a native unit, calls SSH, opens
SQLite, imports the runtime package, loads models, or manufactures a future
PID, invocation, source clock or deadline.

Status: source prepared; no Python or native execution has been performed for
this extractor. A source preparation receipt is not a functional or quality
PASS. Root reviews and runs it after each actual dispatch.

Inputs:

- `--result`: actual private guarded dispatcher `dispatch/RESULT.json`, with
  returned `action_result` JOB, current boot and dispatch utility absence.
- `--label`: that JOB's exact native output/unit label. Current planned jobs
  are Live47 `classic-ui-check-47`, Saved48 `classic-ui-check-48`, and
  `full-app-hour-02`. Labels must match their workflow prefix and actual
  returned fields; no numeric label-count limit is imposed by this tool.
- `--kind live|saved|hour`, `--manifest-sha256`, `--boot-id`: explicit inputs
  matching the fixed actual reviewed build31/current boot pins below. The CLI
  does not discover a boot or silently substitute a manifest.
- Unchanged frozen parent sources under `stabilization_20261005`:
  `extract_stabilization_job_v6.py` SHA
  `5f97f0d6c56190dad10ffee18a2c2d313df9daeb400ab45a5c41d729d7b92ee8`
  and `extract_saved_stabilization_job_v2.py` SHA
  `5079476887b4b7fe04c490b0bde9a5dd885193ef5b4168230307ac599751411a`.
  Their existing duplicate-key JSON, ordinary-file, CPU14 ownership,
  CreateNew/readback and finite metadata safety pattern is retained.

Actual pins:

- Build31 manifest:
  `4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767`.
- Current observed boot: `e60e67c2-f3f5-4b8b-8eab-2613df2de37e`.
- Live helperV2:
  `5c6eab13e00076aabf3f022f69410e1f330dc16a4cbad69b49b8fe016109e37e`.
- Saved helperV2:
  `01fc4288e8496a99eb318875e1aaebac51af8b2fca80b232798693d93cc27237`.

Outputs: new `Q/LABEL-JOB.json`, `.backup`, and `.restore`; fresh private
`Q/audit-preparation/core-job31-LABEL-<32hex>` with early CPU14 owner receipt,
full extractor/README/parent source backups and independent restores,
unchanged dispatch result copies, JOB copies, RESULT and SOURCE_CLOSED.
JSON is canonically serialized, with every returned JOB field/value preserved.
No fields are added to the JOB. Existing output paths are never overwritten.
Root must independently verify natural process exit0 and exact PID/creation
FILETIME absence; the script's SOURCE_CLOSED does not claim its own exit.

Validation binds the exact owner `{pid,start_ticks,boot_id}`, unit, invocation,
cgroup, `properties.MainPID/InvocationID/ControlGroup`, output root, manifest,
boot, finite issued/deadline clocks and workflow reservations. Live/saved V2
JOBs have native256MiB and issued-to-deadline at most600seconds. The actual V2
JOB omits `independent_pc_copy_bytes`; its hash-pinned launcher admits256MiB
per side. That fact is recorded separately in RESULT without inventing a JOB
field. A live/saved JOB's original `NATIVE_CHECK.json` launch path is preserved;
later finalized `NATIVE_CHECK_V2.json` is separate proof.

Hour JOBs must retain the exact continuous repeated-WAV workflow,3600-second
duration/repeat,2,306,682,336-byte native and independent PC reservations,
2048-file bound, and issued-to-deadline at most4725seconds. This reflects the
actual4680-second unit plus original stop/registration slack; the extractor's
600-second host scope does not shorten that unit. The returned verified c24
source must be966400frames/60.4seconds, retained lossless PCM16 with unchanged
WAV SHA `9a83534025736c2f057f20068f3c0584b45770815289a7842a501fcae52b65c8`
and PCM SHA `0f13e54972e4140f5797b996bdeb48d802acd4dcbb9407065d46190bda887e97`.
Natural-conversation, GUI endurance and quality flags must remain false.

Host safety: CPU14/affinity16384 and PID/creation FILETIME are registered before
project reads; finite1MiB total metadata writes/600seconds,256KiB dispatch input,
64KiB individual source input, ordinary single-link canonical files, duplicate
JSON key rejection, and C:50GiB/G:75GiB free-space floors. These are utility
bounds; they do not restrict product recording duration/profile availability.
No model/source/native resource budget changes are made.

## PowerShell

Use one root-coordinated host slot and the existing interpreter. Replace
`ACTUAL_...` with the actual dispatcher result path. Never construct a JOB
from a planned service name or copied PID values.

```powershell
$D='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$N=Split-Path $D
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$PIN='4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
$BOOT='e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
& $PY -B "$D/extract_core_job31.py" --result 'ACTUAL_LIVE47_DISPATCH_RESULT_JSON' --label classic-ui-check-47 --manifest-sha256 $PIN --boot-id $BOOT --kind live
if($LASTEXITCODE -ne 0){throw 'Live JOB extraction failed; preserve private receipts'}
# Only after a separate actual saved dispatch:
& $PY -B "$D/extract_core_job31.py" --result 'ACTUAL_SAVED48_DISPATCH_RESULT_JSON' --label classic-ui-check-48 --manifest-sha256 $PIN --boot-id $BOOT --kind saved
# Only after a separate actual hour02 dispatch:
& $PY -B "$D/extract_core_job31.py" --result 'ACTUAL_HOUR02_DISPATCH_RESULT_JSON' --label full-app-hour-02 --manifest-sha256 $PIN --boot-id $BOOT --kind hour
```

After each extractor naturally exits and root independently closes its exact
owner, use the actual created JOB for the existing monitor. The monitor is a
separate root-controlled native read-only operation:

```powershell
$LABEL='classic-ui-check-47' # Change only to the actual extracted saved/hour label.
$MIRROR="$Q/$LABEL-monitor-$([guid]::NewGuid().ToString('N'))"
& $PY -B "$N/monitor_native_job.py" --job "$Q/$LABEL-JOB.json" --output $MIRROR --poll-seconds 15 --copy-deadline-seconds 7200
```

The monitor's copy allowance extends only closure/transfer. Extracting a JOB
does not prove the native unit is closed or functional: require actual full
mirror, exact owner/unit/nested-worker closure and the appropriate finalized
UI proof or numeric hour reviewer afterward. Do not rerun extraction against
an existing LABEL-JOB; inspect the preserved actual file/receipts instead.

## CMD and Anaconda Prompt

No installation or environment switch is needed. Call the existing interpreter
explicitly from either prompt; the inputs are the same as PowerShell.

```bat
set "D=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PIN=4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767"
set "BOOT=e60e67c2-f3f5-4b8b-8eab-2613df2de37e"
"%PY%" -B "%D%\extract_core_job31.py" --result ACTUAL_LIVE47_DISPATCH_RESULT_JSON --label classic-ui-check-47 --manifest-sha256 %PIN% --boot-id %BOOT% --kind live
"%PY%" -B "%D%\extract_core_job31.py" --result ACTUAL_SAVED48_DISPATCH_RESULT_JSON --label classic-ui-check-48 --manifest-sha256 %PIN% --boot-id %BOOT% --kind saved
"%PY%" -B "%D%\extract_core_job31.py" --result ACTUAL_HOUR02_DISPATCH_RESULT_JSON --label full-app-hour-02 --manifest-sha256 %PIN% --boot-id %BOOT% --kind hour
```

Update this maintained README with actual extractor closure and input/output
pins after authorized execution. A later build/boot/helper/reservation change
needs a separately reviewed derivative; do not edit sealed JOB files.
