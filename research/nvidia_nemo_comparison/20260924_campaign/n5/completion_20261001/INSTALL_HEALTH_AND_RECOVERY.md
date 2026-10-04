# Installation, health and recovery

See CURRENT_RUNTIME_PROGRESS for the actual build17 repair, activation and native evidence.
v27 remains untouched as the rollback/reference; v28 remains the prior
desktop-first release. Use the final v29 release index and actual manifests,
not an old campaign dispatcher, to identify deployed code.

The runtime is an overlay for this prepared CM5, not an arbitrary-device OS
image. It relies on the pinned aarch64 Python environment, installed application,
local Sherpa/PnC/Pyannote/Nemotron libraries and assets, separate ReDimNet/TitaNet
galleries, XVF3800 route, and mounted BMI270 configuration. Nothing is downloaded
when a field session starts. The ChatGPT ZIP does not contain these model assets.

## Normal operation

Open the unified launcher once. Select backend/profile, embedding and Live
microphone or Saved input, then press OK to open the familiar portrait caption app with Mode, People and Settings tabs. Opening either view leaves capture off. Start
checks the accepted combination, exact assets, source availability, ownership,
RAM and finite storage allocation. Experimental permission never promises
real-time performance or silently changes to another backend.

Normal policy is300s. Stop drains and closes the source/model/storage before
offering permanent processed, qualified raw+processed, or discard choices.
New recordings use persistent UUIDs and capacity checks, with no four-recording
global limit or reinstall requirement. History is paged; select recordings
explicitly for replay/export/delete. Deletion never authorizes touching another
session. Failed data and its fault are retained until an explicit safe action.

Exit to desktop closes the launcher. Startup stays desktop-first with capture
off. The finite GUI process also closes after an idle interval; reopening the
launcher creates a fresh owned envelope, without deleting recordings.

## Resource and failure behavior

The2GB device retains OS/storage headroom. Source queues, revision windows,
diagnostics and disk allocations are bounded. Ordinary model processes retain
the768MiB virtual-address limit, shared CPU2–3/200% and64-task envelope; the
explicit two-thread Chunk52 variant is separate from single-thread profiles.
These are software policies, not physical-RAM measurements. See RAM_RESOURCE_GUIDE.

A source, archive, ownership or resource failure ends that trial explicitly.
Preserve its logs and original audio; do not erase pending records, relabel a
partial session complete, reset firmware repeatedly, or bypass a guard.
A larger RAM device does not automatically relax software limits or cure CPU
backlog. Long developer tests need explicit finite duration and storage reserves.

## Rollback and restoration

Keep the immutable v27/v28 directories, galleries, recordings and existing
desktop/startup backups. The final selected-release backup must include current
source/control/configuration, user data, referenced galleries and all old owned
desktop entries, with independent full PC readback before activation.

Shortcut consolidation archives old owned entries after exact backups; unrelated
desktop files remain untouched. Use the final activation/consolidation receipts
and their documented restore procedure to restore exact previous bytes. Do not
extract a consumed release over an existing runtime, replay expired research
commands, or overwrite current recordings.

Physical power-cut durability, cable-disconnected coldboot and arbitrary-crash
recovery are not inferred from normal Stop/Exit. Follow OFFLINE_ACCEPTANCE and
FIELD_VALIDATION for the separately observed operator checks. Motion gaps make
spatial trust unavailable; they must not invent a corrected speaker position.

Technical interfaces and commands:
[release authorization](../extension_20260928/pi_native_20260928/live_runtime_20261003/README_RELEASE_AUTHORIZATION.md),
[backup](../extension_20260928/pi_native_20260928/live_runtime_20261003/README_BACKUP_EXTERNAL_V2.md),
[desktop activation](../extension_20260928/pi_native_20260928/live_runtime_20261003/README_DESKTOP_ACTIVATION.md),
[recording offload](../extension_20260928/pi_native_20260928/live_runtime_20261003/README_OFFLOAD.md).

## Current microphone startup repair

The earlier source failure was an XVF3800 AEC_MIC_ARRAY_TYPE readiness error after priming; SOURCE_NOT_STARTED alone was not the cause. Build17 checks the exact current-boot failed source and its physical closure before one conditional TEST_CORE_BURN 0 recovery. Exact tool/config/display/settings backups and independent restore readbacks precede that action. Successful readiness is cached for the bound failure and boot; failed or uncertain recovery is not automatically retried. Original failure records stay intact. See [repair findings](../extension_20260928/pi_native_20260928/live_runtime_20261003/ui_restore_20261004/UI_REPAIR_FINDINGS.md) and [recovery implementation](../extension_20260928/pi_native_20260928/live_runtime_20261003/ui_restore_20261004/README_XVF_READINESS.md).
