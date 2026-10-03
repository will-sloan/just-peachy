# Exit to desktop and manual startup

Purpose: add a safe explicit exit to the desktop and leave the Pi desktop visible
after login/reboot, with existing profile shortcuts as the way to launch apps.
No new recording/model test or personal-data change is required.

`inspect_desktop.py` is the initial read-only inventory. Inputs: current v27
installation receipts, every registered owner/lifetime record, current Pi
process/capture/lease/resource state and desktop/autostart files. Outputs: private
source backup plus independent restore, compact host preread, native identity,
bounded inspection results and exact utility closure. It does not change startup,
close the app, start capture or reboot. Existing finite1088owner/256KiB response
and600second/16MiB host preparation bounds remain.

PowerShell from this directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./inspect_desktop.py --label initial-v1
```

CMD or Anaconda Prompt using the existing project environment:

```bat
python -B inspect_desktop.py --label initial-v1
```

Use a fresh label for each separately justified inspection; never overwrite an
old result. The Pi endpoint retains strict host-key checking at192.168.2.57.
Affected startup/code must be backed up and independently restored before any
subsequent change; further implementation commands will be documented here.

`prepare.py derivatives-v2` compiles and independently backs up the fresh helpers.
`run.py` applies three bounded operations, in order: preserve the interrupted v27
manager and its completed recording without fabricating EXIT; disable the exact
backed login entry; install v28 with the unchanged motion/model capsule and ten
shortcuts, a disabled autostart entry, and the safe **Exit to desktop** button.
Originals remain immutable. The button waits for active recording closure/backup.
The main manager is reached using Return to modes from a recording screen.

PowerShell (use the existing project Python path shown above for each command):

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./run.py preserve --label preserve-v1
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./run.py disable --label manual-startup-v1
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./run.py install --label install-v28
```

CMD / Anaconda Prompt: use `python -B run.py preserve --label preserve-v1`, then
`python -B run.py disable --label manual-startup-v1`, then
`python -B run.py install --label install-v28` in this directory.

These exact labels are consumed once executed; commands document provenance and
must not be repeated against closed roots. Inputs are the prior v27 installation,
all owner/closure records, local assets and complete verified preservation.
Outputs are private backups, admission/current-state receipts, v28 source and
profile manifests, and the installed Pi launcher. No audio or model execution.
Each operation expires after 600 seconds; all previous CPU/RAM/storage limits
and independent full-copy reserves remain. Reboot-interrupted state is copied
as interrupted, never relabeled as a normal exit.

Finish with `python -B finish.py` (CMD/Anaconda), or the same full Python path
above followed by `-B ./finish.py` in PowerShell. It backs up and preserves old
desktop shortcuts in the new profile directory, leaves the current ten profiles
and rollback, verifies the visible Exit button, exits normally, opens one actual
shortcut idle, exits again, and verifies capture remains closed. Inputs include
the v28 install and all current ownership records. Outputs are
`desktop-exit-20261003/exit-reopen-v1` receipts and backed obsolete shortcuts.
`native_smoke.py` is a pinned injected fragment used by this command, not a
standalone script. This bounded check does not record, run models, or reboot.

The first `finish.py` observer timed out after sending asynchronous Exit. The
separate `inspect_current.py --label after-exit-v1` confirmed the original app
then exited normally, with its exact OWNER/EXIT and inactive service. The original
failure is preserved. `check_reopen.py` verifies a fresh shortcut launch, then
uses acknowledged (synchronous) Tk button invocation for the new normal Exit.
Run as `python -B check_reopen.py` in CMD/Anaconda, or the full Python executable
with `-B ./check_reopen.py` in PowerShell. Outputs: `reopen-v2` private receipts.
This does not repeat shortcut retirement or retry the earlier Exit action.

`publish.py` updates existing guides, copies reviewed source to the delivery
worktree, and produces the private v28 handoff with independent ZIP and expanded
readback. Run `python -B publish.py` in CMD/Anaconda or the full project Python
path followed by `-B ./publish.py` in PowerShell. It reads completed deployment,
Exit/reopen and prior curated handoff receipts; it performs no Pi action or Git
push. Its unique `publication-v2` output is consumed once. The first preparation
stopped before editing on a Windows text-decoding error; explicit UTF-8 reads
corrected the publisher. Existing files receive
exact backup/independent restore before replacement. Limit:600s/24MiB metadata.

`python -B finalize.py` (CMD/Anaconda; use the full project Python executable in
PowerShell) reconciles the remaining old renewal wording, verifies the complete
publication whitelist, and writes the final immutable handoff/index with separate
ZIP and expanded restore. It reads `publication-v2`, writes `final-review-v1`,
has a16MiB limit, and performs no native action. Earlier artifacts remain intact.
