# Exact Pi tree directory allowance

Purpose: finish the bounded SSH export with the measured physical tree. V3 passed
the recorded service gate but rejected the copy plan before payload: the Pi tree
has 75 files/352,621 bytes and 20 directories, including six empty directories not
present in the previous local backup. At 64 KiB per directory, the actual reserve
is 1,663,341 bytes, above V3's 1,600,000-byte allowance. That failed admission is
unchanged. V4 explicitly admits 1,700,000 bytes under the same cumulative 4 MiB
host reservation and unchanged WINDOW_V5 policy. No directory is discarded.

The fresh exporter/coordinator retain V3's fixed service description, raw listing,
identity ACK, independent deadlines, source/hash/identity checks, exclusive
destination writes, readback and closure gate. No old failed output is retried.
Read [V1](README_FIELD_SSH_MIRROR_V1.md) for the protocol, inputs, outputs and
all limits; [V2](README_FIELD_SSH_MIRROR_V2.md) and
[V3](README_FIELD_SSH_MIRROR_V3.md) preserve the earlier failed gates.

Inputs: fresh V4 admission, current closed-tree census and exact source manifest,
code pins and a never-used private output path. Outputs: bounded host receipts
and an exact `-mirror` sibling preserving all files and empty directories.
Only BACKUP.json after exact readback and natural process closure means success.
No source/model/GUI/capture or installed payload write occurs. Private screenshots
remain private; do not publish or display them. This does not qualify the full
80 MiB live mirror, writer interception or offline app.

## PowerShell

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& $py -B "$p\verify_field_ssh_mirror_v4.py" --admission '<fresh-v4-admission.json>' --output '<fresh-private-v4-host-path>'
```

## CMD and Anaconda Prompt

Use the existing interpreter in either prompt; no installation or activation.

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"%PY%" -B "%P%\verify_field_ssh_mirror_v4.py" --admission "<fresh-v4-admission.json>" --output "<fresh-private-v4-host-path>"
```

Never reuse a closed admission or repeat a healthy copy only for a new version.
