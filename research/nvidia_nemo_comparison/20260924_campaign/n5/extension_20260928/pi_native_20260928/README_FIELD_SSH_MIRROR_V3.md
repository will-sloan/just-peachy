# SSH export with a fixed service description

Purpose: correct the now-observed V2 service-list parsing failure. V2 recorded
the full listing: systemd's default description contains the multiline Python
command, so continuation lines were correctly rejected as unexpected first-field
values. V3 supplies one fixed, single-line service description. It retains the
exact single-unit assertion, recorded raw listing, owner ACK and every copy guard.
V1's actual failing listing remains unknown. Both failed trials and their source
bytes remain immutable; neither reached source enumeration or payload copying.

Inputs, outputs, operation and ceilings are documented in
[README_FIELD_SSH_MIRROR_V1.md](README_FIELD_SSH_MIRROR_V1.md), with the recorded
unit gate described in [V2](README_FIELD_SSH_MIRROR_V2.md). V3 uses a fresh unit,
admission and private output. It copies only closed V100 evidence through SSH;
no live source, model, GUI, audio or installed-file change is involved.

Output consists of bounded host receipts plus a sibling `-mirror` tree; BACKUP
is emitted only after exact readback and process closure. Keep all private media
out of Git and do not display it. Existing or partial destinations reject.

## PowerShell

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& $py -B "$p\verify_field_ssh_mirror_v3.py" --admission '<fresh-v3-admission.json>' --output '<fresh-private-v3-host-path>'
```

## CMD / Anaconda Prompt

Use the existing interpreter in either prompt; no downloads or activation.

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"%PY%" -B "%P%\verify_field_ssh_mirror_v3.py" --admission "<fresh-v3-admission.json>" --output "<fresh-private-v3-host-path>"
```

Each invocation requires new admission, closure and allocation evidence. Do not
repeat a healthy copy merely to update a version. This small transport passage
does not qualify the full 80 MiB mirror or the live integration/layout.
