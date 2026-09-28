# Independent review of the Cortex-A76 native retest

Purpose: review the completed or failed `native-stream-cpu-v2` attempt without
running inference. Require terminal host/Linux receipts before invoking it.
Inputs are its immutable admission, 20 source bindings, model/build/audio
hashes, exact command receipts and the retained V1 comparison, plus the fresh
Linux boot/PID/start-tick observation made while the V2 worker was active.

Checks cover unchanged assets and binary, the exact CPU-only argv difference,
help semantics, timeout limits, per-model result counts, the original strict
six-case reader for any claimed pass, nonempty speech, and exact Windows and
Linux closure. Linux closure incorporates the recorded boot ID; a later boot
cannot contain an old owner. QEMU and every pinned runtime-manifest member
are independently rehashed. Partial streams receive no state-parity credit.
An exact first-pass comparison is diagnostic only; it cannot accept the repeat.

Output: a new private directory containing `LINUX_CLOSURE.json` and `RESULT.json`.
The result has counts, source hashes and aggregate progress, not raw transcript
or word data. Failure evidence is retained. A successful reviewer process means
the audit completed: inspect its explicit status and pass count. A reviewed
timeout remains a failed/incomplete component. No GUI, N4/N5 or Pi acceptance.

The read-only audit uses CPU14 and hidden Linux CPU0, one thread, GPU off,
with a 30-second Linux audit timeout. It must run after the numerical worker
closes, and never terminates a process. No new capture/playback/device/training.
No source bound to that worker is changed.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B review_native_stream_cpu_v2.py --run G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-cpu-v2 --output G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-cpu-v2-audit
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B review_native_stream_cpu_v2.py --run G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-cpu-v2 --output G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-cpu-v2-audit
```

Existing audit destinations are refused. Use a fresh derivative for a needed
repair; do not rewrite the model attempts or weaken conformance requirements.
