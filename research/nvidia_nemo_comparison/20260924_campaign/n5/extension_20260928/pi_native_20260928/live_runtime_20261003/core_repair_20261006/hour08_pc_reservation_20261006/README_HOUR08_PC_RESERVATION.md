# Hour08: reserve one complete PC mirror

This standalone host operator folder corrects a duplicated PC disk reservation
for the exact build35 `full-app-hour-08` experiment. The preparer and monitor
create one PC mirror and independently read/hash that same tree. Independent
readback does not create a second full output tree. The native output remains
a separate complete allocation on the Pi.

`prepare_core_endurance35.py` derives from the frozen OPS35 preparer SHA
`01a840e3f963985ebee6691d52e00c3459e78662a0aaff613172ae7f95cea511`.
`monitor_native_job_hour08.py` derives from the existing monitor SHA
`bc6b2322b3cf8b7ed4712e55e4750156507b2f9e9ba79398b1494d4f0391a4e9`.
Each adds a small reservation function and substitutes one disk arithmetic
expression. Removing the function and reversing that expression restores the
entire original UTF-8 source exactly. No original helper or sealed runtime
package is edited. `SOURCE_DERIVATION.json` records those source-only checks,
all copied dependencies, hashes, and independent backups/restores. This is
source preparation, not an execution or native success receipt.

Root subsequently reviewed both exact derivatives and reported a fresh host
preparation PASS at
`Q/audit-preparation/hour08-single-pc-1791327153474`, with observed natural
return and independent external process closure. That result covers payload
preparation only. The hour08 native launch/processing, complete mirror and
performance outcome remain pending; this README claims no native success.
The pre-status README was backed up and independently restored before this
evidence-only paragraph was added. The two code sources and copied dependencies
are unchanged after that preparation.

The one-copy exception requires the exact label, current boot, build35 PIN,
2,306,682,336-byte allocation and 2,048-file contract. The preparer additionally
requires its computed 4,680-second unit plan. The monitor additionally requires
the exact hour08 native output root/unit, repeated-WAV workflow, source duration
and repeat duration of 3,600 seconds, and the full independent PC-copy field.
All other jobs retain the original twice-output reservation. Original job
schema, interval, output ceilings, owner checks, SSH, copy and complete-file
readback logic are unchanged.

The C: floor remains 50 GiB and the G: floor remains 75 GiB. For this one
experiment, each host floor is supplemented by **one full 2,306,682,336-byte PC
copy plus 8 MiB metadata headroom**. The measured G: free space was
84,914,462,720 bytes. The corrected G: requirement is 82,845,707,744 bytes;
the previous double charge required 85,152,390,080 bytes. No evidence was
deleted to create room. The native launch still reserves its full output above
its existing physical free-space floor; model AS remains finite at 1 GiB.

## Files, purpose, inputs and outputs

- `prepare_core_endurance35.py`: CPU14 host preparation. Inputs are the sealed
  build35 package/PIN, accepted backup14 census and COMPLETE pins, current boot,
  C24 input02 destination, selected ordinary operator row, reviewer and a fresh
  private output directory. Outputs include registered owner, source
  backups/restores, lossless C24 PCM join/readback, `PAYLOAD.json`, unused input
  staging payload, source closure and pre-return host exit receipt.
- `monitor_native_job_hour08.py`: CPU14 strict read-only SSH monitor. Inputs are
  the actual returned JOB JSON and a fresh private mirror directory. Outputs
  include owner, status/utility closure receipts, one `closed-output` tree,
  complete file hashes, `MIRROR_MANIFEST.json`, `MIRROR_COMPLETE.json` and result.
- The remaining Python files are exact copied OPS35 dependencies/actions;
  `native_job_probe.py` is the exact original read-only probe SHA
  `65f74d4c3928c64190a61b195e2e76967a00d9210a40d0103bff07076d44e5e1`.
  They retain their original purposes and inputs/outputs described by the
  copied `README_CORE_BUILD35_HELPERS.md` and `README_JOB_MONITOR.md`. This
  README supersedes only their old twice-output host reservation instructions.
  `launch_full_app_soak_action.py` remains an exact byte copy of the sealed
  hour35 action, SHA
  `5d1a683a43d55166781a6f81935713cb960b3f7292e0cd17974c1dc6e493efc0`.
- `preserved/` and `SOURCE_DERIVATION.json` are local source construction
  evidence. Exclude them from public source handoff selection.

All copied code and original sources were backed up and independently restored
before operator use. The existing preparer still repeats its runtime source
backups/readbacks before package/source processing; the monitor still backs up
and restores its JOB, monitor source and probe before the first SSH probe.
Root must also observe natural host return and independently verify exact
PID/creation identity absence. Preserve failures and use a fresh output label.

## PowerShell

These are operator commands for root after source review. No command below was
executed as part of preparing this folder. Do not overlap native model owners;
respect the existing two-host-process budget. Use the bundled environment,
not the WindowsApps Python alias.

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$D="$N/core_repair_20261006"
$H="$D/hour08_pc_reservation_20261006"
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PACK="$Q/audit-preparation/startup-package35-731570a885aa4241aae912cbd69d3acc/package"
$PIN='5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f'
$BOOT='e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
$INPUT='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/core-c24-endurance-input-02/c24-processed.wav'
$PREP="$Q/audit-preparation/hour08-single-pc-preparation-$([guid]::NewGuid().ToString('N'))"
& $PY -B "$H/prepare_core_endurance35.py" --package $PACK --manifest-sha256 $PIN --backup-root "$Q/production-backup-14-reconcile-01" --census-sha256 509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263 --complete-sha256 9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e --boot-id $BOOT --native-input-path $INPUT --operator-id delayed_redimnet --label full-app-hour-08 --reviewer root-reviewed-hour08-single-pc --output $PREP
if ($LASTEXITCODE -ne 0) { throw 'Preparation failed; preserve output' }
```

The existing input02 is already staged. Do not dispatch `STAGE_PAYLOAD.json`.
The native hour action rechecks the original C24 membership/hashes and the
staged WAV/PCM bytes under the source lease. Payloads expire after 590 seconds;
refresh preparation into a new directory if necessary. The unchanged source
policy is developer soak/manual stop, duration3,600, load120, drain600,
cleanup60, backlogNone; policy deadline4,380 and original unit4,680 seconds.

Root dispatches the exact copied action through the unchanged V12 operator:

```powershell
$OP='core-hour35-launch-'+[guid]::NewGuid().ToString('N')
& $PY -B "$D/host_core_operations_v12.py" --label $OP --action "$H/launch_full_app_soak_action.py" --payload "$PREP/PAYLOAD.json" --writes
if ($LASTEXITCODE -ne 0) { throw 'Launch failed; retain dispatch receipts' }
& $PY -B "$H/extract_core_job35.py" --result "$Q/operation-$OP/dispatch/RESULT.json" --label full-app-hour-08 --manifest-sha256 $PIN --boot-id $BOOT --kind hour
if ($LASTEXITCODE -ne 0) { throw 'Actual JOB extraction failed' }
# The extractor writes the actual, hash-backed JSON; it invents no owner/time fields.
$JOB="$Q/full-app-hour-08-JOB.json"
$MIRROR="$Q/full-app-hour-08-monitor-"+[guid]::NewGuid().ToString('N')
& $PY -B "$H/monitor_native_job_hour08.py" --job $JOB --output $MIRROR --sample-memory --poll-seconds 15 --copy-deadline-seconds 7200
if ($LASTEXITCODE -ne 0) { throw 'Incomplete monitor; retain all evidence' }
```

Only root runs those native/read-only network actions. Full mirroring and exact
owner/cgroup/lease closure remain required. A completed finite developer hour
does not by itself establish real-time speed, quality, natural conversation or
normal GUI qualification.

## CMD and Anaconda Prompt

Use the same bundled interpreter and exact inputs. In an Anaconda Prompt no
environment installation is required; its Python selection is bypassed by
the explicit interpreter path. Choose a fresh preparation directory manually.

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "H=%N%\core_repair_20261006\hour08_pc_reservation_20261006"
set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
set "PACK=%Q%\audit-preparation\startup-package35-731570a885aa4241aae912cbd69d3acc\package"
set "PREP=%Q%\audit-preparation\hour08-single-pc-preparation-REPLACE_WITH_FRESH_LABEL"
"%PY%" -B "%H%\prepare_core_endurance35.py" --package "%PACK%" --manifest-sha256 5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f --backup-root "%Q%\production-backup-14-reconcile-01" --census-sha256 509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263 --complete-sha256 9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e --boot-id e60e67c2-f3f5-4b8b-8eab-2613df2de37e --native-input-path /home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/core-c24-endurance-input-02/c24-processed.wav --operator-id delayed_redimnet --label full-app-hour-08 --reviewer root-reviewed-hour08-single-pc --output "%PREP%"
if errorlevel 1 exit /b 1
set "JOB=%Q%\full-app-hour-08-JOB.json"
set "MIRROR=%Q%\full-app-hour-08-monitor-REPLACE_WITH_FRESH_LABEL"
"%PY%" -B "%H%\monitor_native_job_hour08.py" --job "%JOB%" --output "%MIRROR%" --sample-memory --poll-seconds 15 --copy-deadline-seconds 7200
```

The monitor command is used only after root's admitted launch and exact actual
JOB extraction. Do not substitute old hour proofs or edit payload/JOB fields.
