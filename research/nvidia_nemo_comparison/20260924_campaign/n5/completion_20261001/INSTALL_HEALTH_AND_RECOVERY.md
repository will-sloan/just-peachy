# Installation, health and recovery

See CURRENT_RUNTIME_PROGRESS for the actual build21 restoration, activation and native evidence.
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

Normal Live uses manual Stop without arbitrary300-second expiry; storage-derived ceilings and finite load/backlog/drain/cleanup remain. Stop drains and closes the source/model/storage before
offering permanent processed, qualified raw+processed, or discard choices.
New recordings use persistent UUIDs and capacity checks, with no four-recording
global limit or reinstall requirement. History is paged; select recordings
explicitly for replay/export/delete. Deletion never authorizes touching another
session. Failed data and its fault are retained until an explicit safe action.

Exit to desktop closes the launcher. Startup stays desktop-first with capture
off. The GUI has no normal live-session expiry; its300-second idle timeout is separate. Reopening the
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
source/control/configuration, user data, referenced galleries, sole current
desktop entry and retained old restoration files, with full independent PC readback.

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

The earlier source failure was an XVF3800 AEC_MIC_ARRAY_TYPE readiness error after priming; SOURCE_NOT_STARTED alone was not the cause. The retained build17 readiness path checks the exact current-boot failed source and its physical closure before one conditional TEST_CORE_BURN 0 recovery. Exact tool/config/display/settings backups and independent restore readbacks precede that action. Successful readiness is cached for the bound failure and boot; failed or uncertain recovery is not automatically retried. Original failure records stay intact. See [repair findings](../extension_20260928/pi_native_20260928/live_runtime_20261003/ui_restore_20261004/UI_REPAIR_FINDINGS.md) and [recovery implementation](../extension_20260928/pi_native_20260928/live_runtime_20261003/ui_restore_20261004/README_XVF_READINESS.md).

## Current restored application

Build21 is installed at /home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-21.
Manifest9abaaaffe35d328fd97f5fc47f1f5b938803705dffb728c5d804d225a646ba6e.
The sole Desktop/Just Peachy.desktop SHA is7349e29b426e42cd92bbd4b13df02776c07b65110b7e5bad05aad2168f85ee72.
Actual normal desktop launch/idle/Exit passed; capture/models stayed off.

Immediate rollback is the exact build17 shortcut saved in the activation evidence
field-runtime-v29-classic-activation-84c3b00fa02f4fa1821aae01916d3e83 under the Pi campaign.
Use its before/restore readbacks and exact previous SHA before an atomic restore;
do not overwrite build17 or move/delete current data. A rollback also needs the
same no-capture/closed-owner checks; do not replay the consumed activation helper.
The source wrapper/commands are in full_application_20261004/README_DELIVERY_ACTIONS.md.

Assigned seats currently require Pyannote/ReDimNet; recorded spatial replay and
optional legacy adaptations are explicitly unavailable. See MODE_GUIDE.
The new backup path/completion is named in PATHS_AND_BACKUPS; a prepared scope
is never proof of complete backup. Older backup03 remains preserved.
