# First SSH connection to the CM5

Purpose: after Raspberry Pi OS has created the user's account, verify the target
is a Compute Module 5 and append a dedicated desktop public key to that user's
authorized_keys. This allows subsequent deployment commands without retaining or
repeatedly requesting the Pi password. It does not install software, alter sudo
policy, change other keys, enable root login, capture audio or change the screen.

Inputs: confirmed Pi address, ordinary username, and an existing Ed25519 key pair
in the Windows user's `.ssh` directory. Password and first-connection host trust
are entered directly in the visible OpenSSH window; no password is sent in
arguments, saved by the helper, or entered into chat. SSH retains its normal
host-key check (`ask` for bootstrap, `yes` for subsequent commands).

Outputs: public key appended once to `~/.ssh/authorized_keys` on the CM5,
permissions 700/600, and nonsecret hardware/hostname/Python status in the window.
The private key stays on Windows, outside the repository. Existing keys are
preserved; symlinked SSH paths are refused. A successful key install is not
application or microphone qualification.

Current confirmed target (2026-09-22): `192.168.2.57`, advertising
`raspberrypi.local`, username `peachyprototype`. The user confirmed this is their
only networked Pi. Its intended hostname `PeachyPrototype` was not applied by
Imager; inspect the returned hostname before relying on that name.

Create a dedicated key once, from a normal interactive PowerShell/CMD/Anaconda
Prompt (do not overwrite an existing key):

```bat
ssh-keygen -t ed25519 -f "%USERPROFILE%\.ssh\just_peachy_cm5_ed25519" -C just-peachy-cm5
```

In PowerShell replace `%USERPROFILE%` with `$env:USERPROFILE` inside double
quotes. A passphrase requires an appropriately configured ssh-agent for later
unattended commands. This desktop's dedicated bootstrap key is locally stored
without a passphrase for the authorised deployment; protect the Windows account
and never copy the private file into application releases or source control.

PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype\release_tools\connect_cm5.ps1'
```

CMD / Anaconda Prompt (no environment activation needed):

```bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\amiri\Documents\GitHub\just-peachy\prototype\release_tools\connect_cm5.ps1"
```

Override `-PiHost`, `-UserName`, `-IdentityFile` only with verified target values.
After SUCCESS, verify key access from PowerShell/CMD/Anaconda:

```bat
ssh -i "%USERPROFILE%\.ssh\just_peachy_cm5_ed25519" -o BatchMode=yes -o StrictHostKeyChecking=yes peachyprototype@192.168.2.57 "uname -m"
```

In PowerShell use `$env:USERPROFILE` as above. If a host-key change is reported,
inspect it; do not remove known_hosts entries or disable checking automatically.
The private-key path and known_hosts remain on this PC. To revoke this access,
remove only the public-key line whose comment is `just-peachy-cm5` from the Pi's
authorized_keys. Removing the key does not delete the account or its data.
