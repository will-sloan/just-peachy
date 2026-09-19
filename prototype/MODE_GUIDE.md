# Modes, recipes and personal references

Start the app using `Start-Prototype.cmd`, or run these commands from the
repository directory. It opens idle with the microphone off.

PowerShell:

```powershell
& .\.edge-speech-env\python.exe .\prototype\main.py gui
```

CMD or Anaconda Prompt:

```bat
.edge-speech-env\python.exe prototype\main.py gui
```

The input is consented XVF speech or an explicitly selected prepared file.
Outputs are captions and optional provisional identity labels. Choosing a mode
controls labels/emphasis; a recipe controls inference policy; O0/O1 select a
compatible audio tap. The backend validates combinations and starts a fresh
audio/identity epoch when a change needs it. Finished captions remain visible.

| Mode | What appears | Important limit |
|---|---|---|
| Captions | All words under a neutral caption label | Optional speaker inference is off; previously loaded weights may remain resident. |
| Enrolled names | Personal names or Unknown, with all words visible | Internal association may still run. A quieter label display is not proof of lower compute cost. |
| Anonymous | Provisional speaker continuity without personal-gallery lookup | One person can split into labels or different people can merge. |
| Conversation + names | Anonymous continuity plus cautious personal-name matches | Personalization is a new application condition; research accuracy is not a guarantee. |
| Selected focus | Selected people emphasized in the full transcript | Matching remains experimental. Unknown or wrong identities can occur. |

Selected-only filtering is a separate experimental action with a warning. It
hides text based on identity; it does not remove other voices acoustically.
The full retained transcript remains internally available. **Show all captions**
always returns to caption-only display. Use it immediately if words seem missing.

## Recipes and audio taps

| Recipe | Existing implementation reused | Availability |
|---|---|---|
| Fast captions | C065/M0 accepted greedy ASR with no speaker calls | Caption-only |
| Classic continuity | Actual B36 original tracker inside the corrected scheduler | Caption-only or anonymous |
| Balanced identity | C065 short/mature evidence; C088 conservative personal naming where enabled | All five modes |
| Patient identity | C067/N03 longer mature evidence plus short path, C088 naming where enabled | All five modes; initial identity can take longer |
| Spatial-assisted | C079 parent retained for reference | Disabled: live telemetry alignment/calibration is not qualified |

The menu uses the backend's current supported list and reasons. There is no
invented B28 or multibeam substitute. O0's required host +3 dB is applied once
by the live adapter; prepared O0 files already carry their gain. O1 is unity.
The UI performs no gain processing or hardware routing itself.

All active recipes receive XVF's beamformed audio. They do **not** currently
receive numerical angle metadata for enrollment or voice identity. The disabled
Spatial-assisted recipe would add that software cue; it remains unqualified
until live audio/telemetry alignment, reliability and person-to-beam association
are verified. Voice enrollment and matching remain usable independently.

Settings → Beam diagnostics displays read-only device beam angles with stable
beam colors. These are device-relative 0–180° linear-array directions, not
identified people. Music and reflections can attract a beam. Named-person
arrows remain unavailable without fresh verified person-to-beam evidence.
The research ±5° manual-label uncertainty is not a live-angle correction or
a device accuracy guarantee. See `docs/BEAM_DIAGNOSTICS.md`.

## People and enrollment

People → Add person opens a touch keyboard. Names need not be unique: independent
UUIDs identify profiles, and the short ID is visible in lists. Rename, delete,
add-reference, import and export are separate actions. The default personal
store is empty, outside the code/release. Research galleries are not preloaded.
Import/export requires explicit consent because ordinary profile archives contain
sensitive voice data and are not claimed to be encrypted.

Choose a 15/30/60-second **usable speech** goal (30 seconds by default), consent,
then Start recording. Read the editable guide or speak naturally; it is never an
expected transcript. Progress separates elapsed time from unique usable speech,
and reports level/clipping. Targets do not stop recording automatically. Continue
with different speech if needed, then Stop, inspect quality and Save when enabled.
Background speech, overlap, clipping and inconsistency can prevent Save. These
tiers are interface options, not proven optimal enrollment lengths.

Live enrollment requires the actual person. No unattended microphone capture or
synthetic saved reference substitutes for that check. On return, the user should:

1. Start with consent and read a short passage; confirm real partial/final captions.
2. Stop, add their own reference, inspect usable time and save.
3. Close/reopen; confirm the person persists and test different fresh speech.
4. Try another consenting speaker and silence; inspect Unknown/wrong-name behavior.
5. Exercise selected focus and its full-caption rescue on the physical touch target.

These human checks remain pending. File replay, stub tests and research fixtures
are recorded separately; they do not establish room-specific enrollment accuracy.

## Display, storage and device limits

Settings offers caption sizes and high contrast without reloading models. The
480×800 pixel-check is distinct from comfort zoom. Back to live restores caption
following after scrolling. Diagnostics shows raw text separately from provisional
and final display text. UI verification commands and inputs/outputs are in
`docs/UI_ITERATION.md`.

Stop delegates actual capture release to the controller. The evaluation firmware
has an eight-hour limit; stop between sessions and follow the device recovery
guide. The app must not reset the device during speech or change default speakers.
Personal reference data is durable; session buffers and journals are bounded by
the documented backend policy. The UI does not start ambient recording on open.
Settings/Diagnostics → Mark a problem offers a diagnostic mark without audio,
or a separately consented saved copy of up to 30 seconds already in RAM. The
excerpt may contain others' voices; obtain their consent. Nothing is played or
newly captured by this action. The saved location is reported in status and
Diagnostics. Session text journaling can be turned off/on when offered by the
backend; existing private references and pinned problem evidence are preserved.
The supported retention controls offer 3/10/20 completed sessions,
64/128/256 MiB session quotas and 60/120 seconds of RAM history. RAM changes take
effect for the next session. Settings also reports remaining disk capacity.
CM5 performance, physical touchscreen comfort and unspecified camera/IMU/GPIO
wiring remain hardware-pending.
