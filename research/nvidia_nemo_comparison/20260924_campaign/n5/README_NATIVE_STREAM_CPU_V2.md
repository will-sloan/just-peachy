# Native Nemotron ARM64 protocol with explicit Cortex-A76

Purpose: isolate whether the emulator CPU selection that repaired baseline
Sherpa output also changes the native A2 repeat-stream timeout. This fresh
V2 derivative preserves the V1 executable, shared runtime, Q8 models, saved
audio and six-case conformance reader. Only `-cpu cortex-a76` is inserted in
the model command. QEMU help uses the independently tested V5 parser. The separate
`native_stream_cpu_config_v2.py` checks the eight-argument native invocation;
its refusal tests and the reused reader/help tests total 14 checks.
No claim of native Pi throughput follows from emulation timing.

Inputs: exact V1 ADMISSION/build/binary/model/WAV hashes; independent baseline
CPU retest audit; fresh complete guarded census and 128-MiB stage allocation;
new `EMULATED_NATIVE_ASR_CORTEX_A76_V2` precheck and supervisor worker spec.
No existing result, release, shared ledger or source bound to another plan is
modified. Source/model hashes are verified before inference. No downloads.

Outputs: private ADMISSION, exact Windows/WSL/Linux owners, CPU-help receipt,
INPUTS, per-model A2/A3 JSONL and command/result receipts, closed terminal
RESULT. Private raw text stays outside Git. An independent review is required
before accepting a result. Keep failure and timeout evidence unchanged.

A2 then A3 run sequentially, each retaining its original 1,800-second cap.
Cases are empty, one sample, short tail, saved source, resident fresh repeat
and forced endpoint. Exact repeated final text/word offsets and complete
stream/recognizer closure must pass the unchanged strict reader. A timeout
ends the allocation and leaves the next model unattempted. Ordinary closed
model errors are recorded separately. No lowered gate or partial-pass credit.

Limits: one Linux CPU/nice10, one CPU14 host coordinator, one native math
thread, GPU off, 8-GiB QEMU virtual-address screening cap (not measured Pi RAM),
128-MiB output, C: >=50/G: >=75 GiB free. 3,750s Linux outer timeout, 3,800s
host watchdog and at most 3,900s admission, all before the fixed September 28
02:48:19 UTC packaging reserve. No physical Pi, microphone, playback,
training, enrollment or visible desktop activity.

From the campaign N5 directory, PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B -m unittest test_native_stream_review_v1 test_baseline_asr_cpu_v5 test_native_stream_cpu_config_v2 -v
& $jpPy -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-cpu-v2-worker.json
```

CMD / Anaconda Prompt, same existing pinned interpreter:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_native_stream_review_v1 test_baseline_asr_cpu_v5 test_native_stream_cpu_config_v2 -v
"%JP_PY%" -B ..\supervision\supervisor.py start --root G:\Just_Peachy_N1\20260924_campaign\local\supervision --spec G:\Just_Peachy_N1\20260924_campaign\local\n5\native-stream-cpu-v2-worker.json
```

The spec calls `run_native_stream_cpu_host_v2.py --precheck FRESH_CHECK
--output FRESH_RUN` with absolute paths and this cwd. The host alone owns the
internal Linux driver. Never launch it separately or reuse stale admission.
Review existing worker and exact creation identities before any launch; keep
the current evaluation undisturbed. Existing outputs are refused. GUI,
N4/N5 completion and CM5 hardware acceptance remain separate obligations.
