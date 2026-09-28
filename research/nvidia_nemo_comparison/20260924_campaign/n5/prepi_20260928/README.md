# Authorized pre-Pi work window

The user resumed software work on September 28 after the original campaign
closed. WINDOW.json records this separate window, ending in a checkpoint at
22:20:48 UTC. The old deadline, failed attempts and immutable releases remain
historical evidence. No Pi connection, microphone, playback, new training or
enrollment is included. Keep the two-CPU total, GPU-off and C50/G75-GiB floors.

Priorities are bounded shutdown/ownership repairs, A0 Sherpa + D1 Nemotron + E0
ReDimNet and A2 Nemotron English + D1 + E0 saved-file checks, and a reproducible
handoff for later authorized Pi installation. No stage acceptance is inferred
from these development tests. Other realtime/gating ideas remain held for
independent dense-speech and real-world validation.

## Late worker cleanup derivative

Purpose: reproduce and repair the Controller race in which a failed session's
finalization thread has exited but a native speaker lane is still returning.
The old Controller immediately rejects Close. A fresh derivative waits at most
five seconds total for owned threads, records thread names and elapsed cleanup,
and retains ownership if any remain. The original 60-second inference drain
and failed-session status remain unchanged. Cleanup success is not inference
success. This does not make a slow diarizer meet the drain gate.

Inputs: an immutable parent DERIVATIVE.json, its exact source files, and a fresh
private output directory. Outputs: prototype source, CHANGES.patch and a new
DERIVATIVE.json; tests use isolated temporary stores and no models or devices.
Parent sources are hash checked and never edited. The new helper and tests are
included in the derivative. Controller errors and finalization failures remain
in last_application.json metrics after a clean application exit.

PowerShell, from this directory:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $prePiPython -B prepare_shutdown_v1.py --parent-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n3-stable-asr-chunks-v1\DERIVATIVE.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\releases\prepi-shutdown-v1'
# Tests: run from the resulting prototype directory, using a private TEMP root.
& $prePiPython -B -m unittest discover -s tests -p test_late_shutdown_v1.py -v
& $prePiPython -B -m unittest discover -s tests -p test_lifecycle.py -v
```

CMD / Anaconda Prompt (existing interpreter; no environment installation):

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PREPI_PY%" -B prepare_shutdown_v1.py --parent-receipt "G:\Just_Peachy_N1\20260924_campaign\local\releases\n3-stable-asr-chunks-v1\DERIVATIVE.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\releases\prepi-shutdown-v1"
cd /d G:\Just_Peachy_N1\20260924_campaign\local\releases\prepi-shutdown-v1\prototype
"%PREPI_PY%" -B -m unittest discover -s tests -p test_late_shutdown_v1.py -v
"%PREPI_PY%" -B -m unittest discover -s tests -p test_lifecycle.py -v
```

The new regression test pins its process to CPU14, BelowNormal, and one native
thread with GPU disabled before loading application modules. Actual inference
requires a separate fresh run admission and exact worker census. Never use the
expired prior campaign admission or rewrite its shared ledger.

## Actual saved-file lifecycle checks

`prepare_lifecycle_v1.py` verifies the derivative, prior accepted CPU assets and
saved WAV, complete recorded N4 allocation census, current supervisor, exact
process identities, physical private bytes and disk headroom. `window_guard.py`
uses this new user authorization for time only; it does not rewrite or extend
the closed campaign policy. It preserves the 50-GiB original payload ceiling,
2.5-GiB remaining reservations, and a 1-GiB total new-window output ceiling.
The existing supervisor dispatches one hidden coordinator and one application
on an isolated Windows desktop, keeping the user input desktop unchanged.

`lifecycle_v1.py` retains the V4 inference/save/reopen/delete, real Tk rendering,
all-sample, native activity, encoder-use and exact process-closure checks.
It accepts the new shutdown derivative and either A0/D1/E0 (`nemotron_hybrid`)
or A2/D1/E0 (`nemotron_600m`). A0 sample accounting uses the unchanged Sherpa
cursor; A2 uses native input count. Controller error/status/metrics are saved
even on failure. Each fresh run has a 600-second total cap, 240-second phase
limit, 128-MiB output cap, CPUs4/14 and one native thread. A failed inference
cannot pass merely because the patched Controller eventually closes.

Inputs are bound in CHECK.json/ADMISSION.json; outputs are private precheck,
resource census, supervisor ownership, phase receipts, captions and RESULT.
No independent application or stage acceptance is implied before review.

PowerShell, from this directory:

```powershell
& $prePiPython -B -m unittest test_window_guard -v
& $prePiPython -B prepare_lifecycle_v1.py --name a0-d1-e0-v1 --backend nemotron_hybrid
# Only after RESULT and exact owner closure are independently checked:
& $prePiPython -B prepare_lifecycle_v1.py --name a2-d1-e0-v1 --backend nemotron_600m
```

CMD / Anaconda Prompt, from this directory:

```bat
"%PREPI_PY%" -B -m unittest test_window_guard -v
"%PREPI_PY%" -B prepare_lifecycle_v1.py --name a0-d1-e0-v1 --backend nemotron_hybrid
rem Only after the first run closes and is reviewed:
"%PREPI_PY%" -B prepare_lifecycle_v1.py --name a2-d1-e0-v1 --backend nemotron_600m
```

Use new names for retries and preserve failed evidence. Do not run these in
parallel or edit any bound source while a worker is active.

The first preflight refused the six existing WSL virtual-environment links and
started no worker. Its sources and failure are preserved under
`local/n5/prepi-20260928/a0-d1-e0-v1-preflight-failed`. The corrected check binds
the previously admitted census and requires exactly the same six reparse paths;
the physical inventory still does not traverse them or credit any removed bytes.
Any new link in window outputs is refused. The fresh actual run uses `v2`.
