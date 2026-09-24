# proto1-0.2.0 — run, export, update and recover

Purpose: one source release for the existing Windows desktop and future native
Linux ARM64 installation. Includes accepted tasks01–08; optional09–12 remain
pending. No new model/package/threshold study. Models stay once in a shared
content-addressed store; people/settings/vocabulary/sessions stay outside releases.

## This desktop: idle launch and live use

PowerShell, from any directory:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype\Start-Prototype.ps1'
```

CMD / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\prototype\Start-Prototype.cmd"
```

Opens the 480×800 window idle, mic Off. For live use: connect XVF → verify external
`C:\Users\amiri\JustPeachy\data\live_config.json` identifies that device and its
matching host helper → choose mode/roster/tap → Start and consent → speak → Stop
and wait for drain. Changing the Windows default mic is insufficient. The app
never silently substitutes another microphone. Enrollment needs a consenting
person. Existing profiles are reused; no fresh enrollment was performed in08.
Sessions controls optional audio storage/export separately from microphone use.

## Versioned source export

Deliverable: `G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.2.0.zip` and
its `.receipt.json`. The ZIP's `RELEASE_MANIFEST.json` binds every payload file.
It excludes voice vectors, private sessions/audio, model weights and research.
It is **hashed, not signed**. Trust the delivery channel separately.

To verify and extract a copy in PowerShell (new destination required):

```powershell
$jpZip = 'G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.2.0.zip'
$jpReceipt = Get-Content -Raw ($jpZip -replace '\.zip$','.receipt.json') | ConvertFrom-Json
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $jpZip).Hash.ToLower() -ne $jpReceipt.sha256) { throw 'Archive checksum mismatch' }
Expand-Archive -LiteralPath $jpZip -DestinationPath "$env:USERPROFILE\JustPeachy\exports\proto1-0.2.0"
& "$env:USERPROFILE\JustPeachy\exports\proto1-0.2.0\Start-Prototype.ps1" -Python 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -Models "$env:USERPROFILE\JustPeachy\shared\models" -DataRoot "$env:USERPROFILE\JustPeachy\data"
```

CMD / Anaconda Prompt after verified extraction:

```bat
set "JUST_PEACHY_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JUST_PEACHY_MODELS=%USERPROFILE%\JustPeachy\shared\models"
set "JUST_PEACHY_DATA=%USERPROFILE%\JustPeachy\data"
"%USERPROFILE%\JustPeachy\exports\proto1-0.2.0\Start-Prototype.cmd"
```

The archive contains source, not a bundled Windows Python or XMOS executable.
Use the existing qualified environment on this desktop. An unrelated Windows
machine needs its own reviewed native runtime and explicit device configuration.
Never put data/models inside the extracted release.

To build a later immutable version from repository root (choose an unused version):

```powershell
& .\.edge-speech-env\python.exe prototype/release_tools/release.py build --source prototype --output 'G:\Just_Peachy_PROTO1\releases' --version proto1-NEXT
```

CMD / Anaconda Prompt: remove the leading `&` and use double quotes for paths.
Inputs: source tree + version. Outputs: ZIP and SHA256 receipt; it never overwrites
an existing version. Task08 is already built; do not rerun with its version.

## Future CM5: transfer, install and launch

No remote machine was contacted. Before these commands, complete
`CM5_WIRING_AND_BRINGUP.md` and separately provision the OS/libraries described
in `release_tools/README.md`. Existing offline wheelhouse:
`G:\Just_Peachy_PROTO1\arm64 cp311 wheels`; 13 pinned wheels, no re-download.

For wired transfer, fill the verified host/user/key and paths. PowerShell example
(initial installation includes models; omit `-Models` for subsequent reuse):

```powershell
& .\prototype\release_tools\deploy_pi.ps1 -PiHost 'VERIFIED-HOST' -UserName 'YOUR_USER' -IdentityFile 'C:\path\verified-private-key' -Archive 'G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.2.0.zip' -RemoteRoot '/home/YOUR_USER/JustPeachy/install' -RemoteDataRoot '/home/YOUR_USER/JustPeachy/data' -Wheelhouse 'G:\Just_Peachy_PROTO1\arm64 cp311 wheels' -Models 'C:\Users\amiri\JustPeachy\shared\models' -DryRun
```

Review, then remove `-DryRun` to stage. Add `-Activate` only with the app stopped.
SSH host-key checking stays enabled. A trusted USB copy is an alternative:
extract trusted source separately, verify the receipt, then on the actual CM5:

```bash
bash /path/to/trusted-source/release_tools/install_pi.sh --archive /path/to/just-peachy-proto1-0.2.0.zip --sha256 SHA256_FROM_VERIFIED_RECEIPT --root "$HOME/JustPeachy/install" --data-root "$HOME/JustPeachy/data" --wheelhouse /path/to/arm64-wheels --models /path/to/shared-models --activate
```

Installer stages source and per-version Python environment, verifies hashes,
space/imports/models and compatibility before activation. It does not use sudo,
flash anything, configure services or start the mic. A failed stage leaves the
active version intact; a failed GUI startup must be inspected before retrying.

Idle GUI from the ordinary graphical CM5 session:

```bash
python3.11 "$HOME/JustPeachy/install/releases/proto1-0.2.0/release_tools/launch_current.py" --root "$HOME/JustPeachy/install" --data-root "$HOME/JustPeachy/data"
```

For a headless saved-file check (no touch, camera, sensor or XVF needed):

```bash
"$HOME/JustPeachy/install/runtimes/proto1-0.2.0/bin/python" "$HOME/JustPeachy/install/releases/proto1-0.2.0/main.py" file --wav /path/to/prepared-mono-16k.wav --models "$HOME/JustPeachy/install/models" --data-root "$HOME/JustPeachy/replay-check" --mode caption_only --recipe fast --tap O0 --result "$HOME/JustPeachy/replay-result.json"
```

For live use, first qualify ELF64/AArch64 XVF control and populate the external
`live_config.json` with matching host path, ALSA endpoint and lease path. The
current adapter expects the qualified v3.2.1 **UA io48 linear** configuration,
48 kHz stereo capture and existing route/gain rules. Unknown hardware planning
values remain null; changing them does not change this contract. Launch the GUI,
then Start/consent. ARM32 vendor binaries are not a native ARM64 substitute.

Health and rollback, after stopping/closing the app:

```bash
python3.11 "$HOME/JustPeachy/install/releases/proto1-0.2.0/release_tools/release.py" healthcheck --root "$HOME/JustPeachy/install" --data-root "$HOME/JustPeachy/data" --models
python3.11 "$HOME/JustPeachy/install/releases/proto1-0.2.0/release_tools/release.py" rollback --root "$HOME/JustPeachy/install" --data-root "$HOME/JustPeachy/data"
```

Use the selected release's runtime for `--imports`. Rollback switches code/runtime
only; it does not revert or delete personal data. A missing previous pointer or
incompatible paragraph reader is refused. Keep a known compatible previous
version and a private backup. Never delete an active `runtime.lock` automatically.
No schema migration runs in08. Feature compatibility is additional to schema1.

Existing bounded retention stays in effect. GUI choices control session limits
and RAM horizon; per-epoch archive queues/byte limits and free-space protection
report storage loss explicitly. Saved conversations/enrollments are not silently
deleted to make room. CM5 eMMC capacity and sustained memory/thermal behavior
still require the arrival tests.
