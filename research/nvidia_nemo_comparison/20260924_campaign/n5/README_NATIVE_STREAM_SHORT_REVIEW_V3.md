# Independent review of the short ARM64 native protocol

Purpose: review a closed native-stream-short-v3 attempt without invoking a
speech model. This is acceptance only of the declared 16-second, six-case
native protocol. It cannot clear the prior full-source timeout or qualify the
ARM64 Python/Tk/speaker/GUI application, actual word-time accuracy, or CM5 speed.

Inputs: fresh run ADMISSION/RESULT/INPUTS, exact native stdout/command receipts,
the original and first-16-second saved WAV hashes, full-source failure audit,
23 bound evaluator sources and existing models/runtime, and the captured Linux
boot/PID/start-tick plus Windows creation identities in LIVE_VERIFICATION.json.
The reviewer independently rechecks the unchanged strict six-case reader,
nonempty final text and word objects, exact resident repeat text/word parity,
forced-endpoint/flush/closure, command arguments and per-model limits. It checks
the derived PCM is exactly the declared prefix, not an arbitrary shorter file.

Outputs: fresh private RESULT.json and LINUX_CLOSURE.json containing verified
bindings, coverage and exact closed owners. A small hidden local WSL Python
process verifies QEMU/runtime hashes and boot-aware process/group absence;
it never invokes the recognizer or connects to the Pi. Host CPU14 and Linux
CPU0 are pinned below normal/nice10. No microphone, playback, training or UI.

Native raw word offsets are also reported against source duration as a separate
diagnostic. The reused protocol checks finiteness and exact repeat parity, not
ground-truth alignment or source-end clipping. The existing Windows wrapper
explicitly labels native offsets unadjusted. Record any out-of-source offsets;
do not silently clip evidence or claim application timestamp qualification.

PowerShell from N5 (destinations must not already exist):

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B review_native_stream_short_v3.py --run G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-short-v3 --output G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-short-v3-audit
```

CMD / Anaconda Prompt, existing pinned interpreter:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B review_native_stream_short_v3.py --run G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-short-v3 --output G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-short-v3-audit
```

The original reader/CPU helper tests remain qualified by their unchanged
bindings. This reviewer reuses the independently audited V2 closure procedure
in a fresh derivative, with declared-prefix verification and separate raw
offset diagnostics. Keep all failed attempts, private raw text and model
weights outside Git. No shared ledger or existing source/result is edited.
