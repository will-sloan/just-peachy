# Bounded Pi-to-host evidence stream

Purpose: connect a closed, pinned Pi evidence tree to the bounded host mirror.
This checks backup transport only. It does not start a model, GUI or audio source,
qualify live capture, or change installed code/configuration. Old evidence and
old local-copy code remain unchanged. This entry admits only the closed V100
`d1-visible-entry-v2` tree; the future live-run entry requires a fresh derivative.

`field_ssh_mirror_v1.py` implements framed metadata and 16 KiB payload reads,
exclusive destination files, per-file hash/readback, whole destination membership,
and completion publication after a caller-provided exact process-closure check.
Metadata frames are at most 256 KiB, files at most 32 MiB, with at most 256 files
and 64 directories. Payload bytes plus 64 KiB per directory must fit the explicit
allowance. Only a bounded manifest is buffered. Hidden guards, empty files and
preserved pending files retain their original names. Existing destinations reject;
partial copies are preserved and never automatically retried, overwritten or
deleted. This is not a hard filesystem quota or a crash/concurrency guarantee.

`field_ssh_export_v1.py` is injected into memory by the admitted host coordinator.
It checks the actual CM5/aarch64, baseline identities, install/config digests,
closed capture, research/hardware leases, prior exact owners and active units.
Its fresh user unit uses CPU2/3, shared 200%, Tasks64, 128 MiB AS, 1 MiB stack,
90-second unit lifetime and 10-second stop grace. The independent Python alarm
is 80 seconds; the copy deadline is 75 seconds. LimitFSIZE=0 prohibits regular
file payload writes. There are no target code or data writes. The actual unit
properties and exporter boot/PID/start ticks are recorded on the host before ACK.
Source enumeration begins only after ACK. Source identity, membership, size and
hashes are checked during the stream; initial RAM is at least 850 MiB, sampled
available RAM at least 192 MiB, and Pi free space at least 5 GiB.

`verify_field_ssh_mirror_v1.py` sets CPU14 before project reads, loads a fresh
immutable admission and the retained exact V100 BACKUP.json manifest, checks all
admitted code/input hashes, and uses the established strict SSH key/host alias.
No key contents are read or emitted. It uses one fresh systemd unit, a bounded
stderr reader (64 KiB), a 110-second host watchdog and separate SSH reaping.
The exact remote PID/start/boot identity is checked dead before BACKUP.json.
Failures preserve a partial destination and host failure/result/closure evidence.
If transport fails before a remote owner is received, the admission expires and
the independently bounded remote unit must be inspected before any later dispatch.
No generic failure-cleanup or arbitrary remote process termination is claimed.

Inputs: an admission JSON with fresh expiry, source manifest and code pins,
closed owner list, current target-inclusive census, output path and explicit
4 MiB host reservation. The small verification copy allows 1,600,000 bytes
including directory reserve. The source manifest must already be independently
verified and closed. A declaration is not evidence of closure; refresh the
campaign census and all lifetime/owner records first. This tool does not change
WINDOW_V5 or create an allowance policy.

Outputs: a new host directory containing ADMISSION, REGISTERED_OWNER, PREFLIGHT
(remote identity/properties), BACKUP only on success, RESULT, raw stderr and
coordinator closure; a sibling `-mirror` directory contains the exact source tree.
Private screenshots/media in that tree must not enter Git or be displayed.

## PowerShell

Use the existing interpreter; no download or environment change. Replace both
placeholders with a freshly admitted JSON and its exact never-used output path.
Do not reuse a closed admission or repeat the successful copy to refresh a version.

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& $py -B "$p\verify_field_ssh_mirror_v1.py" --admission '<fresh-admission.json>' --output '<fresh-private-host-path>'
```

## CMD and Anaconda Prompt

The same absolute interpreter works in either prompt; activation is unnecessary.

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"%PY%" -B "%P%\verify_field_ssh_mirror_v1.py" --admission "<fresh-admission.json>" --output "<fresh-private-host-path>"
```

The reusable receiver requires an externally enforced blocking-I/O deadline.
Its reusable ceiling does not qualify an 80 MiB network copy; only measured
admitted passages may be reported. Live writer interception, complete physical
path census, real D1 endpoint binding, source/model/Stop/save/reopen and offline
field acceptance remain separate gates.
