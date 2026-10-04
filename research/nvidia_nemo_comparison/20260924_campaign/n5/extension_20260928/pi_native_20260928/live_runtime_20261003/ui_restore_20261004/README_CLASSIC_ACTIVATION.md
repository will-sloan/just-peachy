# One restored chooser shortcut

`activate_classic_desktop_action.py` is an injected Pi action for the separately
guarded `host_repair_operations_v4.py` coordinator. It verifies the complete new
build17 package and a fresh actual portrait/microphone/worker-closure result,
then backs up and independently restores the two exact observed owned Desktop
entries. It atomically installs `Just Peachy.desktop` and archives the redundant
v28-named entry. It does not start the app or edit models, calibration, galleries,
recordings, login autostart, or preserved releases.

Inputs: a fresh bounded JSON payload containing current boot, build17 manifest,
unchanged `/home/peachyprototype/JustPeachy/data/runtime-v29`, actual closed native
check path, exact previous Desktop hashes, and a unique activation evidence root.
Output: one chooser shortcut, exact before/restore/archive files, `ACTIVATION.json`
and the guarded coordinator's natural SSH/independent native-owner closure.
The current app and other workers must already be closed by the coordinator's
ordinary admission guards. No old payload/root may be reused after failure.

PowerShell, with `$R` set to this folder, `$PY` to the existing environment Python,
and `$PAYLOAD` to the reviewed fresh payload:

```powershell
& $PY -B "$R/host_repair_operations_v4.py" --label classic-desktop-activation-01 --action "$R/activate_classic_desktop_action.py" --payload $PAYLOAD --writes
```

Command Prompt and Anaconda Prompt use the pinned executable, not a new install:

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "R=FULL_PATH_TO_ui_restore_20261004"
set "PAYLOAD=FULL_PATH_TO_FRESH_REVIEWED_ACTIVATION_JSON"
"%PY%" -B "%R%\host_repair_operations_v4.py" --label classic-desktop-activation-01 --action "%R%\activate_classic_desktop_action.py" --payload "%PAYLOAD%" --writes
```

The coordinator backs up/restores action and payload before use, prereads all
owners/lifetimes, retains free-space/resource/current-boot checks, and checks its
own exact native death. Native evidence has a separate 16 MiB reservation and
the existing 5 GiB Pi floor. This command is an operator deployment action, not
the normal way to open Just Peachy. Operators click the one Desktop icon, select
a backend and Live/Saved input, press OK, and then press Start in the app.

## Rollback

Exit the application first. The ACTIVATION receipt names an immutable evidence directory containing before/ and independent restore/ copies of both old shortcuts plus the unchanged disabled login-autostart entry. The preserved build16 and v27/v28 directories are not modified. For a reviewed rollback, compare SHA256 against the receipt, stage the exact prior Desktop bytes from restore/ to a fresh sibling file, fsync/readback, and atomically replace only the owned shortcut. Restore the archived duplicate only if intentionally restoring the old two-icon desktop. Use the guarded coordinator with a fresh current-boot action; do not rerun this consumed activation or restore login autostart merely to change the launcher. User recordings remain in the unchanged data root.
