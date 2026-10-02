# Mounted BMI270: current code and commands

Current deployed release is **field-runtime-v27**, using `bind_runtime_motion_v3.py`
and `prepare_runtime_motion_v3.py`. Three recording slots remain. Read
[MOTION_GUIDE.md](MOTION_GUIDE.md) first for operation, geometry, measured CPU cost
and limits. Ten profiles share one sensor worker; plain saved WAVs never borrow
the current live pose.

For future completed-batch renewal, use `renew_motion_runtime.py` and the
"Renew batches without losing motion integration" section below. Operator helper
sources are already prepared in `operator-tools-v1`; do not rerun their generators.
The combined renewal wrapper is prepared/compiled/planned, not itself executed.
Its preservation/inspection/provision components retain their actual scoped evidence.

PowerShell, from this directory:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./renew_motion_runtime.py --previous-version 27 --version 28 --last-receipt 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/shortcuts-v27-v2' --plan
```
CMD or Anaconda Prompt uses the same arguments after `python -B renew_motion_runtime.py`
in the existing project environment. `--plan` makes no Pi contact. Use the actual
latest native receipt and fresh version/output paths for a later renewal. Remove
`--plan` only when intentionally renewing a completed batch. For recording offload,
use `operator-tools-v1/export_runtime_recording_v4.py` with the current installation
and a new private destination; see the completion MODE_GUIDE and the existing
README_RUNTIME_RECORDING_OFFLOAD_V4.md. Copies retain every original.

Purpose: share one mounted motion stream across existing live source/display and
position consumers. Inputs: pinned installed application, fixed mount config,
BMI270 library and original runtime/model manifests. Outputs: bounded causal
beam/pose metadata, relative rotation correction, explicit invalidation during
motion/gaps, optional diagnostic graphic, and private recording/closure receipts.
These are prepared-workstation tools, not a generic fresh-device installer.

The following preparation/execution history is retained for reproducibility.
Old version-bound checks, recovery, recording and copy commands are **consumed**;
they are not instructions to rerun them. Earlier "current" statements below apply
only to their historical stage. Saved-WAV pose-sidecar replay is not implemented.

# Mounted BMI270 integration

Read-only runtime diagnosis: `python -B run_runtime_inspection.py --version 25
--label v25-after-check1` (one command line). Uses the existing current-owner,
lease, resource and bounded UI/receipt inspector, with fresh scope for this task.
Produces private raw logs and exact inspector closure; no recording or mutation.

Changed integration check: `python -B prepare_motion_check.py`, then
`python -B run_motion_check.py` (use the full executable in PowerShell).
Inputs: newly installed v25, fresh owner/config/resource inventory and original
runtime recording policy. Outputs: private real-button receipts, eight-second
whole-frontend idle CPU observation, optional graphic toggle/tap evidence, one
five-second D1/ReDimNet processed recording, active-loop array geometry getters,
Stop/Save/Return/Close receipts. This does not measure noisy speech accuracy or
claim that frontend CPU is exclusively the IMU. Never rerun the consumed slot.

Deployment reuse: run `python -B prepare_deployment_tools.py` once to create
`deployment-tools-v3` and independently restored derivatives of the existing
preserver, inspector and installer. The changed preserver requires all actual
normal EXIT receipts plus current process absence; it does not fabricate a
Close or treat a reboot as normal closure. It retains complete streamed copies,
per-file readback, all resource bounds and the pinned original rollback.
The installer changes only the common capsule to the backed mounted version.
Use `python -B <generated-script> --help` for the required private/local,
previous-install/preservation, scope, inspection and output paths. PowerShell
uses the explicit Python executable below; CMD/Anaconda use the activated Python.
Each operation requires a fresh <=600-second scope and unused output directory.
The prepared wrapper supplies these exact paths and records source backups:
`python -B run_deployment_phase.py --phase preserve --label v1`, then
`--phase inspect --label v1`, then `--phase install --label v1`.
Do not repeat a consumed phase; investigate retained failures first.
The first installation stopped at the immutable old delivery deadline before
HELLO, file creation or baseline Close. v3 uses a newly backed native installer
for this separately authorized IMU task, with the same <=600-second admission
and 120-second cleanup reserve. The next unused release is v25; v24 is retained
as the failed admission. Fresh inspection output is deployment-inspection-v2.

`inspect_runtime_state.py --output <new-private-directory> --host 192.168.2.57`
is a read-only pre-deployment check. It reads all recorded owners, current
runtime controls/startup outcome and XVF3800 array geometry/type getters under
the hardware lease. It neither initializes audio nor changes routing. Invoke
with the same PowerShell Python path below, or `python -B` in CMD/Anaconda.
Outputs are private source backups, exact native identity/closure, raw command
results and RESULT.json; unavailable firmware getters are kept as failures.

Current preparation: `prepare_runtime_motion_v2.py` uses
`bind_runtime_motion_v2.py`. It preserves the seat validity/warning extension
and adds Settings → Orientation graphic (default hidden). The 78×88 graphic
uses the existing GUI poll, draws at most 10 times/second only while visible,
and tapping it resets the visual zero only. It never resets the identity frame.
One shared BMI270 worker samples at the existing 50 Hz rate; no per-backend or
per-speaker sensor worker is added. Beam getters remain serialized outside the
audio callback. Actual CPU cost is reported from the IMU worker thread clock.

PowerShell: `& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\prepare_runtime_motion_v2.py --output <new-private-output-directory>`

CMD or activated Anaconda Prompt: `python -B prepare_runtime_motion_v2.py --output <new-private-output-directory>`

Inputs are the verified v23 capsule, mounted configuration receipt and prepared
motion derivatives; outputs are a new pinned common capsule, independent
restore, source backups and review. Preparation does not deploy or start audio.

Purpose: integrate the existing BMI270 attitude estimator with the delivered
Just Peachy microphone telemetry and all backend profiles. Native discovery is
read-only; sensor initialization and deployment are separate explicit phases.
Saved recordings use their recorded orientation, never the current live pose.

## Discovery inputs and outputs

`inspect_imu.py` reads the existing private ownership/lifetime receipts and
version23 installation admission, then performs one bounded strict-SSH inspection.
It does not start audio, load models, initialize the IMU, or modify the Pi.
Outputs are bounded private owner, preread, native configuration, process,
geometry and transport/closure receipts in a new `--output` directory.

PowerShell, from this directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./inspect_imu.py --output 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/discovery-v1'
```

CMD or Anaconda Prompt, from this directory:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B inspect_imu.py --output "G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/discovery-v1"
```

Use a fresh output name after a failed inspection; retained failures are never
overwritten. Original display270, audio routing, recordings and model assets stay
intact. Discovery is not calibration or proof of physical direction accuracy.

## Current direct-IP discovery and physical check

Use `inspect_imu_v2.py --host 192.168.2.57` with the same output argument and a
fresh directory. It preserves strict host-key checking and records SSH failures
without inventing a native identity.

`calibrate_imu.py` takes a successful `--inspection` directory and fresh
`--output`. It verifies owners, an idle capture device, the free IMU lease, boot,
config and existing library hash before initializing only the BMI270. No audio
or model runs; no Pi files/configuration change. The startup reference is automatic
after two quiet seconds. On `READY_ROTATE`, turn about 90 degrees, pause, return,
and leave still. Collection ends 50 seconds after readiness. Output contains
private time-stamped sensor/attitude samples and actual process closure receipts.

PowerShell (from this directory):

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./calibrate_imu.py --inspection 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/discovery-v3' --output 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/physical-v1'
```

CMD / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B calibrate_imu.py --inspection "G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/discovery-v3" --output "G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/physical-v1"
```

`mounted_spatial.py` supplies a bounded beam callback queue/receiver and the
confirmed approximate mounting geometry. Its API inputs are XVF getter values
and monotonic request/receipt/callback times; outputs are <=1024-byte packets
inside the original 2048-byte audio metadata cap. `derive_mounted_imu.derive`
takes existing `imu.py` and `live_spatial.py` bytes and returns compiled new
source bytes/digests that keep visual beams device-relative and project retained
reference bearings back onto the current microphone axis. These are preparation
APIs, not an installed runtime. Missing recorded motion in a plain WAV is reported
explicitly; it never borrows the current live pose. The physical check and future
runtime integration are separate qualification steps.

## Save the confirmed mount (one use)

`prepare_mount_writer.py` generates `save_mount_config.py` from the inspected
driver. The writer binds the actual boot, idle hardware, original configuration
and library hash. It independently backs up/restores the original configuration
on the PC before one fsynced atomic replacement. It saves fixed mounting and the
approximate (-4.5,-16,-1.5)cm offset; gyro bias is still acquired automatically
at rest on each startup, not treated as a permanent temperature-independent value.
Do not rerun a completed configuration mutation.

PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./prepare_mount_writer.py
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./save_mount_config.py --host 192.168.2.57 --output 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/mount-save-v1'
```

CMD / Anaconda Prompt: use the same arguments with
`"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_mount_writer.py`
and then `... -B save_mount_config.py --host 192.168.2.57 --output <fresh-private-directory>`.
Outputs retain the old and new hashes, configuration text, full bounded raw
failure/success output and process closure. This does not install the new runtime.

## Changed integration checks

`check_mounted_spatial.py --output <fresh-private-directory>` verifies the exact
installed app source pins, prepares/backs up new source bytes, then checks the
new device/reference-frame split, acceleration invalidation, causal bounded
beam transport, explicit overflow, and saved-file isolation. It registers CPU14
before project reads and opens no hardware/models/audio. Inputs are the retained
version12 installed app mirror and the new local sources; outputs are prepared
source copies, digests and a scoped result, not deployment evidence.

PowerShell: `& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./check_mounted_spatial.py --output '<fresh-private-directory>'`

CMD / Anaconda: `"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_mounted_spatial.py --output "<fresh-private-directory>"`

`read_runtime_capsule.py --output <fresh-private-directory>` is read-only with
respect to the Pi and old evidence. It compares the two complete preserved
version23 common capsules, validates all manifest members, and extracts selected
source bytes plus a compact index for implementation review. Use the same Python
PowerShell/CMD/Anaconda commands above with this script name. It does not execute
the extracted runtime or claim a new deployment.

## Prepare the shared runtime integration

`prepare_runtime_motion.py --output <fresh-private-directory>` binds the exact
preserved version23 capsule, changed app sources that passed the focused checks,
and the newly saved mount hash. It generates a new common capsule shared by all
ten existing profiles. Inputs and code are independently backed up; every output
member is decoded, hashed and compiled from a separate restore copy. This is
preparation only. A fresh versioned installation/admission and integrated native
check are still required before using it.

`bind_runtime_motion.derive` is the pure API used by that command. It carries beam
telemetry through the original <=2048-byte audio-block metadata contract, retains
native audio fields, starts the IMU when the profile frontend opens, and closes
it through the existing Controller Close path. It opens the existing IMU lease
read-only, never creates a second writer. Live records retain callback-bound
beam data and causal orientation samples (up to10Hz) in the existing bounded
source trace. Current live motion is excluded from saved-WAV inference. The
frontend keeps device-relative beam arrows and shows motion status. Existing
voice/location algorithms receive corrected cues where they already consume
spatial input; this does not add spatial reasoning inside the D1 model.

PowerShell: `& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./prepare_runtime_motion.py --output '<fresh-private-directory>'`

CMD / Anaconda: `"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_runtime_motion.py --output "<fresh-private-directory>"`

Original 64-member, 2MiB code,128KiB member,1MiB packed capsule and source-trace
limits remain. Old bound source/capsules/releases are never rewritten.

## Mounted runtime deployment and focused recovery

The v25 composition failed before capture when the optional Canvas used its
item-raise method as a widget raise. `prepare_motion_revision.py` creates new
`bind_runtime_motion_v3.py` and `prepare_runtime_motion_v3.py`: the corrected
widget raise and direct IMU thread CPU/sample counters in the existing causal
orientation trace. Inputs remain the independently verified version23 capsule
and mounted source/mount receipts. Outputs go to a fresh private capsule folder;
old v25 bytes and failure are preserved.

`prepare_recovery_revision.py` prepares `deployment-tools-v4`: full failed-tree
preservation with exact process closure and pinned rollback; a strict previous
batch reader accepting independently verified failed backups as failed; a fresh
baseline inspector; and installer for the new common capsule. It retains the
full independent allocation, existing limits, ten profiles and model assets.
`run_recovery_revision.py --phase preserve|inspect|install` performs these in
that order with independent source restore copies and a new <=600-second scope
per phase. Its exact inputs are failed runtime25 and fresh runtime26; these are
one-use versioned operations, never rerun after completion. Outputs are private
raw failures, owner/closure receipts, complete hash/readback copies and install
bindings. It does not rewrite an old release or turn failed recordings into passes.

PowerShell, from this directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./prepare_motion_revision.py
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./prepare_runtime_motion_v3.py --output '<fresh-private-capsule-directory>'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./prepare_recovery_revision.py
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./run_recovery_revision.py --phase preserve
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./run_recovery_revision.py --phase inspect
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./run_recovery_revision.py --phase install
```

CMD / Anaconda Prompt uses the same script names/arguments:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B run_recovery_revision.py --phase preserve
```

Replace only the script/arguments for the sequential commands above. No conda
environment change or package installation is needed. Generators also use unique
output directories; archived commands document provenance, not repeat authority.

`run_motion_check_v3.py` uses the independently backed `motion-check-v2` driver
on fresh runtime26/recording01. It opens D1 delayed through the normal manager,
observes eight idle seconds, shows/taps/hides the debug graphic, then performs
one short processed recording, read-only array geometry getters, Stop, Save,
Return and manager Close. Inputs are the new installation and fresh inspection;
outputs are bounded private control/closure/failure receipts. It never turns
programmatic taps into physical-touch or noisy-human accuracy evidence.

PowerShell: `& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./run_motion_check_v3.py`

CMD / Anaconda: `"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B run_motion_check_v3.py`

The v26 graphic passed, but native source startup returned the existing
AEC_MIC_ARRAY_TYPE255 fault with an active audio loop and zero converted samples.
`run_recovery_revision_v2.py` binds the same failed-source preservation to v26
and reserves fresh v27. `prepare_source_recovery.py` and `run_source_recovery.py`
reuse the previously exercised conditional maintenance only for this exact
preserved failure, after fresh baseline inspection and independent config/tool
backups. One matching fresh failure permits at most one TEST_CORE_BURN0 send;
uncertain sends are not retried. No audio is opened by maintenance. Outputs are
raw command/intent events, firmware readback, unchanged file pins and closure.
This is not periodic firmware reset or a claim that old volatile state is restored.

PowerShell: use the explicit Python above with `-B ./prepare_source_recovery.py`,
then `-B ./run_recovery_revision_v2.py --phase inspect`, then
`-B ./run_source_recovery.py`. CMD/Anaconda use the same scripts and arguments
after the quoted executable. These exact paths are one-use; never rerun a send.

The first maintenance derivative stopped before device access because its old
fault inspector required the TitaNet profile; the actual new failure was D1 with
ReDimNet. `run_source_recovery_v2.py` binds that exact profile and a new unit/output.
The previous attempt's raw assertion and exact process absence remain retained.

`prepare_history_revision.py` prepares deployment-tools-v5 and the v3 recovery
runner. It explicitly reserves a bounded continuation of up to1088 historical
identities, retains every old identity, and leaves the256KiB total request cap
unchanged. Actual old request184685B/1012identities;64 maximal-sized extra records
project191213B. This is a metadata-count allowance only, not extra recording,
storage, CPU or deadline authority. All old policies and source bytes remain.
Run this generator once with the same Python invocation, then
`run_recovery_revision_v3.py --phase inspect`, `run_source_recovery_v2.py`, and
`run_recovery_revision_v3.py --phase install` after confirmed maintenance outcome.
The wrappers independently back up sources/README before execution.

## Renew batches without losing motion integration

The older Refresh-JustPeachy helper reconstructs the historical capsule. For the
mounted runtime use `renew_motion_runtime.py`, after `prepare_motion_operator.py`
has prepared its verified sources. Inputs are an increasing unused version,
previous installation and latest native utility receipt. The current manager
must remain idle/open, with every recording CLOSED and locally backed up. The
tool preserves the complete batch, performs pinned rollback, inspects the
baseline and installs a fresh batch using the exact motion capsule. No recording
is deleted or slot reused; each phase has its own <=600second scope and full
independent allocation. Failed batches require their specific recovery first.
The combined CLI is prepared/compiled; its component paths have actual execution
evidence. It is not another runtime test or an automatic renewal service.

PowerShell (from this directory; replace receipt if a newer operation ran):

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./renew_motion_runtime.py --previous-version 27 --version 28 --last-receipt 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/shortcuts-v27-v2' --plan
```

Remove `--plan` to perform the explicitly requested renewal. CMD/Anaconda uses
the same arguments after the quoted executable and `-B renew_motion_runtime.py`.
Plan mode does not contact the Pi. The output paths and retained capsule hash
are printed. For later recording offload use
`operator-tools-v1/export_runtime_recording_v4.py --help`; its required inputs
match README_RUNTIME_RECORDING_OFFLOAD_V4.md, with the current installation and
fresh output paths. All source and recording originals are retained.

After the single recovery succeeded, `run_motion_recording.py` binds fresh
runtime27/recording01 and checks only the previously blocked source/recording
path. The graphic and eight-second idle observations are reused from v26;
no healthy model comparison is rerun. Use the full executable with
`-B ./run_motion_recording.py` in PowerShell or `-B run_motion_recording.py` in
CMD/Anaconda. Inputs: installation27, maintenance receipt, unchanged common
capsule. Outputs: one short quiet processed recording and normal Stop/Save/
Return/Close receipts; source traces contain direct IMU thread CPU/sample data.

`copy_motion_recording.py --root-kind original` and then `--root-kind local`
use the existing complete exporter for runtime27/recording01 and its independent
Pi-local backup. Inputs: actual CLOSED/BACKUP plus current owner/installation
bindings. Outputs: separate private PC trees with every member/byte hash and
independent readback, exact exporter closure, and a BACKUP receipt. Copy only;
originals remain on the Pi. Each copy independently reserves189080108B+4MiB
metadata within a new600second scope. Use the same full executable with `-B`
in PowerShell/CMD/Anaconda. Paths are one-use and cannot overwrite old copies.

`finish_motion_shortcuts.py` reuses the qualified shortcut retirement operation
for current runtime27. It independently backs up old generated icons before
moving them to the release's retired-shortcuts folder; personal icons are
untouched. It leaves ten current profiles plus rollback and the idle manager
running. Inputs: installation27, latest copy/owner receipts; outputs: exact
retirement plan, two PC copies, move/readback and closure. Invoke with the same
PowerShell executable `-B ./finish_motion_shortcuts.py`, or CMD/Anaconda
`python -B finish_motion_shortcuts.py`. This is one-use, with a new600second
scope and the original2MiB metadata/128KiB shortcut bytes/512-file limits.

`review_motion_delivery.py` reads the retained copies and actual receipts only.
It checks sample continuity, causal beam/pose timestamps, explicit invalidation,
direct IMU CPU/sample counters, all ten profile/common pins and current idle
shortcut closure. Output is a compact private RESULT/INPUT_PINS; no hardware,
model execution or old healthy copy test is repeated. Run with the same Python
PowerShell/CMD/Anaconda invocation and `-B review_motion_delivery.py`.

The first shortcut inspector rejected the presence of the completed recording
before any backup acknowledgement, directory creation or rename. New
`prepare_shortcut_revision.py` / `finish_motion_shortcuts_v2.py` preserve this
failure and bind the exact already verified recording01 BACKUP hash and its
successful capture/process closure. All old shortcut matching/backup/move
guards remain. Run the generator then the v2 helper using the same Python
PowerShell/CMD/Anaconda syntax; each output is unique and one-use.
