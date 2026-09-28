# Declared 16-second ARM64 Nemotron functional smoke

Purpose: test A2 and A3 lifecycle correctness on an explicitly smaller saved
input after the full 44.695-second V2 protocol timed out during A2 repetition.
This is the N5 small saved-input functional smoke, not a repair or acceptance
of the failed full-source protocol. V1/V2 failures remain immutable.

Inputs: the exact first 256,000 PCM frames (16 seconds, mono 16-bit 16 kHz)
of the existing saved source; private SOURCE.json recording original and
derived hashes; independently reviewed V2 failure; unchanged qualified ARM64
binary/runtime/Q8 models and strict six-case reader; explicit Cortex-A76;
fresh complete resource census and supervisor admission. No filtering,
resampling, speech selection, new recording or download occurs.

The unchanged cases are empty, one sample, short tail, saved source, resident
fresh repeat and forced endpoint. Repeated final text and word times, valid
source timestamps, stream/reset/recognizer closure and endpoint behavior
must pass on the declared 256,000-frame input. A pass covers only this clip.
Independent review is still required after the process closes. A2 then A3
execute sequentially; timeout ends the allocation and preserves an unattempted
next model. Final text/word payloads remain private.

Outputs: a fresh private native-stream-short-v3 directory containing admission,
Windows/WSL/Linux identities, CPU-help/INPUTS receipts, per-model raw output,
command and strict-reader results and terminal status. Never reuse an existing
output or stale admission. Preparation, terminal success and this smoke do
not establish full ARM64 Python/Tk/speaker/GUI, N4/N5 or native CM5 acceptance.

Limits: 1,500 seconds per model, 3,050-second Linux outer timeout, 3,100-second
host watchdog, at most 3,150-second admission strictly before 2026-09-28
02:48:19 UTC. Total two logical CPUs: Linux CPU0/nice10 and CPU14 host below
normal; pinned native threads, GPU off, 128 MiB output, C:50/G:75 GiB free.
The existing 8-GiB QEMU virtual-address ceiling is not a measured target RAM
requirement or native Pi performance measurement. No Pi contact or visible UI.

PowerShell, after checking exact identities and creating the fresh bound
precheck/spec through the existing stage admission and supervision interfaces:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-short-v3-worker.json
```

CMD or Anaconda Prompt (use the existing pinned environment, no installation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-short-v3-worker.json
```

The spec invokes run_native_stream_short_host_v3.py --precheck FRESH_CHECK
--output FRESH_RUN using absolute paths. Only that host invokes the internal
run_native_stream_short_v3.py Linux driver. Do not launch it separately or
start another numerical worker while this admission is live. Reused reader
and CPU helpers retain the 14 prior passing checks with exact source hashes;
the derivative changes only declared input, scope and tighter timeout limits.
