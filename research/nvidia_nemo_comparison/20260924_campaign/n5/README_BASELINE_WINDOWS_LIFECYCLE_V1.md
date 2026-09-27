# Baseline Windows saved-file lifecycle smoke

Purpose: validate the exact immutable N1 baseline through one saved WAV and
two actual Windows processes. The first process uses its real Controller and
Tk GUI, saves a text-only transcript, then closes normally. The second reopens
that transcript, verifies its persisted rows, renders them, deletes only the
test conversation, and closes. A synthetic people-directory sentinel must
remain unchanged. No production personal store is supplied.

Both processes use the qualified N4 private-desktop/owned-job primitive. The
input desktop is never switched and no mouse or keyboard input is injected.
The parent runs below normal on CPU14, one child at a time on CPU4, with one
numerical thread and GPU disabled. The GUI's saved-audio-only mode disables
audio-device observation, capture, enrollment and auto-start. No playback,
device enumeration, Pi connection or new audio is requested. The saved WAV
already has its O0 gain; no new gain is applied.

This is one caption-only/fast baseline smoke, not a full bank, touch/scanout
test, timing comparison, optional backend acceptance or ARM64/CM5 validation.
Page navigation observes modes, backend picker, saved sessions and settings.
It does not claim all combinations shown in those menus have been exercised.

## Inputs and outputs

`baseline_windows_lifecycle_v1.py` takes `--precheck CHECK.json` and a fresh
`--output` directory beneath campaign `local/n5`. The externally admitted
CHECK binds every code dependency, all 240 immutable release payload files,
the release manifest/archive, eight model/tokenizer assets, prepared WAV,
complete resource census, exact closed prior owners and isolated data path.
Its scope is `BASELINE_WINDOWS_SAVED_FILE_LIFECYCLE_ONLY`; it contains UTC
admission/expiry, `output_cap_bytes`, and the SHA256 of the fixed synthetic
sentinel bytes. Start within 120 seconds of admission, through the existing
supervisor only. A stale receipt cannot be reused. The maximum allocation is
600 seconds and 128 MiB, ending before the packaging reserve.

Output: immutable `ADMISSION.json`, per-phase owner records, `infer`/`reopen`
private logs and RESULTs, the first phase's SAVED fingerprint, fresh `data`,
and each owned job's LIFETIME receipt. The final RESULT requires both complete
phases and normal, unforced, empty-job closure. Failure evidence stays intact.
The child has a 240-second operation budget plus 15-second cleanup; the parent
allows 285 seconds per process and terminates only its retained job if needed.
Disk floors, 128-MiB output cap and allocation expiry are checked during work.
No receipt changes shared campaign ledger state or promotes N4/N5 acceptance.

Internal `--child` options require the exact private desktop, registered PID
creation identity and live admitted parent. Do not launch a child directly.

## PowerShell

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
# Model-free receipt refusal tests; no GUI, inference or hardware.
& $py -B -m unittest test_baseline_windows_lifecycle_v1 -v
# After a fresh complete census/admission, prepare a worker spec whose argv is:
# [$py, '-B', absolute baseline_windows_lifecycle_v1.py, '--precheck',
#  absolute fresh CHECK.json, '--output', absolute fresh local/n5 run directory]
# After admitting that fresh worker spec, use the existing start interface:
& $py -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-windows-lifecycle-v1-worker.json
```

## CMD / Anaconda Prompt

The explicit qualified interpreter avoids activating or changing environments.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_baseline_windows_lifecycle_v1 -v
rem Only after admitting a fresh CHECK and matching worker spec:
"%JP_PY%" -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\baseline-windows-lifecycle-v1-worker.json
```

See `../supervision/README.md` for the exact supervisor CLI. A start is allowed
only after a fresh complete census shows no active allocation or competing
worker; retained failed reservations and the latest disk/download allowance
remain included. Preserve existing releases and failed attempts. Use new
versioned output and precheck paths for a later repeat.
