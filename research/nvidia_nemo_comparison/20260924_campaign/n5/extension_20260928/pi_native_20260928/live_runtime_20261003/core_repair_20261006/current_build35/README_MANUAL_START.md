# Manual Start without a second listening confirmation

Purpose: remove the repeated “I consent · Start listening” page from the
retained portrait application. An explicit press of the existing Start button
authorizes live microphone acquisition. The application still opens idle;
Start/Stop, backend availability, ownership, acquisition and cleanup guards
remain in effect. All live backend selections share this presentation path.

Inputs: the pinned installed portrait UI, current runtime Manager/controller,
the selected live or saved source and the operator's Start/Stop click.
Outputs: the same portrait application and one existing controller call for
live Start, with `consent=True`. No new audio route, recording, persisted
permission setting or automatic capture is introduced by this change.

`classic_frontend.frontend_type(...).PortraitUI.toggle_listening` sets only the
transient UI consent flag when the operator presses Start for live input. It
then delegates to the retained method, which still checks backend availability
and calls the existing controller. Stop delegates before changing the flag.
Saved input still opens its file/replay selector instead of a microphone.

`mature_frontend.frontend_type(...).MatureUI.show_settings` removes the redundant
Microphone permission and automatic-listening widgets from the page. Existing
personal settings remain on disk; `auto_start_listening=False` is still enforced
by the controller. Enrollment consent and gallery import/export confirmation
are unchanged and remain explicit. Recording save/discard/delete choices are
also unchanged.

When an exact closed XVF startup fault needs bounded readiness maintenance,
the controller reports `STARTING` with the Manager's readiness notice. Stop
changes this to `STOPPING` and cancels the pending automatic retry. The original
Stop button remains available; Mode, People, Settings and backend changes wait.
Controller guards also reject recording actions, exports and gallery changes
during this pending interval. Exit waits for the helper to finish, be reaped and
join before the GUI, recording store or launcher lease may close. Readiness
work itself is not a microphone/model Start and does not qualify audio.

## Run on the Pi

After the sources are frozen, backed up and deployed as a new immutable runtime,
open the single **Just Peachy** desktop shortcut, select a backend and input,
then press **OK**. The original portrait application opens with its microphone
off. Press **Start** once to begin. Press **Stop** to close capture and drain.
Use **Settings → Exit to desktop** when finished. Do not edit an installed old
runtime or run this presentation module as an unowned standalone application.

## Review from PowerShell

From this source directory, inspect the focused change without starting Python,
the GUI, any model or the microphone:

```powershell
Select-String -Path .\classic_frontend.py -Pattern 'def toggle_listening' -Context 0,13
Select-String -Path .\mature_frontend.py -Pattern 'def show_settings' -Context 0,12
Select-String -Path .\classic_frontend.py,.\application_controller.py -Pattern 'consent is not True|consent=False'
```

## Command Prompt and Anaconda Prompt

From the same directory, these read-only commands inspect the relevant source:

```bat
findstr /n /c:"def toggle_listening" /c:"self._mic_consented = True" classic_frontend.py
findstr /n /c:"microphone_permission" /c:"auto_listening" mature_frontend.py
findstr /n /c:"consent is not True" classic_frontend.py application_controller.py
```

## Focused verification

Verify that initial display remains idle and no Start occurs during Settings
navigation. One manual live Start should invoke the controller exactly once
with `consent=True` and show no extra consent page. A second Start/Stop press
must invoke Stop, not another Start. An unavailable backend must still refuse
acquisition. Saved input must still browse/replay without starting a microphone.
Repeated Settings visits with either old permission value must leave both
listening controls absent. Enrollment and gallery transfer confirmations must
remain present. Native acquisition/error recovery is separate from this small
UI change; source checks alone are not proof that the microphone works.

For the readiness path, verify pending recovery shows STARTING, a Stop click
shows STOPPING, and neither state opens a second worker or allows gallery/export
admission. Settings/mode callbacks must also reject a direct invocation while
pending. Exit must stay pending until the helper has joined. A completed
readiness check may resume the original Start once; a cancellation must not.
