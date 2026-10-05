# Mode guide — restored build21

**field-runtime-v29-build-21 is installed and activated.** Open the single
Just Peachy shortcut, choose backend/embedding/recipe and independent Live/Saved
input, press OK, then use the original portrait application with Modes, People
and Settings. It opens idle; Exit returns to the desktop. Autostart remains
disabled; build17 and v27/v28 remain preserved.

Backend selection and application Mode are separate. Sherpa/PnC remain shared;
Pyannote or one of twelve Nemotron geometries supplies diarization. ReDimNet and
TitaNet use separate enrollment/gallery domains; vectors are never converted.
Anonymous avoids personal names. The chooser has123 backend/embedding/recipe
variants, with independent source choice; the underlying allowlist retains246
ordinary configurations. Availability is not Cartesian native testing or a
real-time guarantee. Experimental profiles require explicit permission.

## Original application Modes

| Mode | Behavior and limit |
|---|---|
| Caption only | Text without personal naming. |
| Enrolled names | All compatible people; insufficient evidence stays Unknown. |
| Selected focus | Selected participants only; outsiders may stay Unknown. |
| Selected closed | Forces a selected name, including explicit assumed fallback; can misname outsiders. Assumptions never train identity. |
| Spatial assisted | Conservative spatial prior; voice evidence still required for names. |
| Strongly spatial assisted | Experimental stronger prior; conflict/freshness/decay retained. |
| Spatial selected | Conservative spatial prior within selected roster. |
| Strongly spatial selected | Experimental stronger prior within selected roster. |
| Assigned direction | Applied seat region gives a closed-table assumption, not verified identity. |
| Assigned hybrid | Voice evidence plus applied seats; Unknown/conflict release remain possible. |
| Anonymous conversation | Numbered continuity without names; tracks may split/merge. |
| Open with names | Cautious enrolled names plus anonymous continuity. |

Anonymous backends support caption-only/anonymous Modes. Spatial Modes require
Live input; recorded spatial replay is not connected. Assigned seats currently
require **Pyannote + ReDimNet** because recovered C088 calibration cannot be
silently applied to TitaNet/Nemotron. Apply anchors the current device position;
motion can invalidate seat trust. Participant roster constrains lookup; the
separate display roster filters presentation without changing recorded evidence.
Fast/classic/balanced/patient recipes keep explicit dependencies.

The [application Mode integration/math](../extension_20260928/pi_native_20260928/live_runtime_20261003/full_application_20261004/APPLICATION_MODES_AND_MATH.md)
page explains exact IDs, effective profiles, cosine/seat scoring, gallery
ownership and clocks. The [17 pipeline pages](../extension_20260928/pi_native_20260928/live_runtime_20261003/README_PIPELINES.md)
explain each backend geometry and its high/low-level implementation.

## Operator workflow

1. Select backend/source while idle; press OK; choose Mode/rosters/seats.
2. For names, use People and explicit-consent paragraph enrollment separately
   for each encoder. Gallery helpers close before live model construction.
3. Press Start and confirm consent, or select the saved replay WAV.
4. Press Stop; wait for drain and source/model/worker closure.
5. Save the complete session with processed or qualified raw+processed audio,
   or Discard the entire temporary UUID, including transcript/artifacts.
6. History supports reopen, rename, deliberate delete and export. Return closes
   workers before changing backend; Exit returns to desktop.

Normal Live uses **manual Stop**, without an arbitrary120/300-second cutoff.
Capacity-derived recording/export reserves, disk floors, bounded queues/caches
and finite load/backlog/drain/cleanup still apply. Safety faults can Stop.
Kept history uses persistent UUIDs, pagination and storage capacity, not four
global slots. v27/v28 rollback recordings are not automatically migrated.

## Recording and provenance

Kept sessions contain exact segmented16kHz float32 model input/PCM16 replay WAV,
captions/revisions/transcript, configuration, gallery/model pins/snapshots and
available beam/BMI streams. Qualified raw is four physical **16kHz PCM32
little-endian** channels; its48kHz stereo transport does not make stored raw48kHz
ADC audio. Processed XVF output is never called raw.

Beam reads/BMI poses retain actual monotonic observation times; separate audio
callback/sample anchors permit an honest join, not proven DSP acoustic time.
Gaps/reference changes remain explicit; saved WAV never borrows current pose.

Store: /home/peachyprototype/JustPeachy/data/runtime-v29/recordings
Export: /home/peachyprototype/JustPeachy/data/runtime-v29/recording_exports

Keep the complete ZIP; copy/export preserves the Pi source.

## Actual evidence and limits

Representative native checks passed Pyannote/ReDimNet, Pyannote/TitaNet,
CurrentDelayed/ReDimNet, CurrentDelayed/TitaNet, Chunk52/ReDimNet and anonymous.
The manual-Stop trial retained **310.2s /4,963,200 processed samples**, complete
raw, restored routes and exact closure. Real encoder/quality models prepared
without mic/person creation for both enrollment helpers. Anonymous Discard
removed the entire temporary session. Build21 normal desktop launch/idle/Exit
passed with ten stable480x800 states and no capture/model. Rich Export09 copied
a2,152,081B ZIP with all30members/CRC/readback verified. These are programmatic
real-widget functional checks, not touch/human enrollment/noisy accuracy tests.
[Restoration findings](../extension_20260928/pi_native_20260928/live_runtime_20261003/full_application_20261004/RESTORATION_FINDINGS.md)
preserves all failed trials and new corrections.

[BACKEND_COMBINATIONS](BACKEND_COMBINATIONS.md) retains original measured scopes:
CurrentDelayed roughly21.3s first output; Chunk52 component RTF about1.08;
two-thread component hour0.88445 average/about0.94late/85.35Cpeak; official
low/very-low/ultra-low prefix RTF4.819/5.791/8.119; compact3.04s short RTF0.8568,
quality unqualified. Buffer latency excludes compute. Whole-application hour04
FAILED at3,584.955/3,600seconds; OS closure/backup do not pass it. Primary bounded
late labels/sparse extraction remain; older parallel refinement is disabled.

The actual2GB CM5 has2,108,473,344B MemTotal.768MiB process virtual-AS,
CPU2–3/shared200%,64tasks and1MiB stacks remain. AS differs from RSS/PSS.
4/8GB may help residency when memory is limiting; it does not cure CPU/thermal
backlog or relax software guards. No larger-board benchmark is claimed.

Assigned seats are Pyannote/ReDimNet only. Saved spatial replay, DPDFNet,
adaptive promotion, Windows transcript review and RAM audio excerpts are
explicitly unavailable; metadata problem markers work. BMI270 cannot supply
reliable absolute translation or drift-free heading. Human enrollment quality,
representative noise, touch/offline coldboot, battery and a successful whole-app
hour remain real-world validation.

The future stationary recording / separate enrollments / matched Pi replay /
timed display / Windows offload workflow is in [FIELD_VALIDATION](FIELD_VALIDATION.md).
Batch automation is deliberately not implemented now. Read [recovery](INSTALL_HEALTH_AND_RECOVERY.md),
[motion](MOTION_GUIDE.md), [paths/backups](PATHS_AND_BACKUPS.md) and
[RAM/resources](../extension_20260928/pi_native_20260928/live_runtime_20261003/RAM_RESOURCE_GUIDE.md).
