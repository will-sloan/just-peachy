# Paired Windows shadow diagnostic

Purpose: exercise the G01/G02/G03 observer during actual 1x saved-file Windows
ASR/D1/E0 execution. Inputs are the hash-locked one-file lifecycle harness,
shutdown derivative, accepted assets, the same saved 44.695-second source and
the matching independently reviewed ungated lifecycle. This is a fresh harness;
it does not mutate frozen application source or existing evidence.

Outputs: generated shadow_lifecycle_v1.py / prepare_shadow_lifecycle_v1.py and
a private supervised run containing SHADOW.json plus full lifecycle receipts.
The runner requires exact observed PCM bytes, all source/ASR/D1 sample counts,
unchanged speaker activity and displayed/stored text/source timestamps against
the matching ungated run. All prior rendering, save/reopen/delete, drain, worker
and private-desktop checks remain. The observer is installed only in the saved
FileSource of that private test process. No production gate is enabled.

Six model-free observer checks precede integration. Generation refuses existing
destinations. Admission performs the complete resource census and exact prior
PID closure checks. Keep one numerical run at a time under two logical CPUs,
one native thread per model, GPU off, 128 MiB output and 600-second admission.
Nothing contacts the Pi or enumerates/plays/captures audio. The agent does not
launch a visible application. Review terminal evidence independently before
crediting this narrow shadow result or starting the other composition.

PowerShell from this directory:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $prePiPython -B test_shadow_gate_v1.py -v
& $prePiPython -B build_shadow_harness_v1.py
# Inspect generated code; run only after prior owners have exited:
& $prePiPython -B prepare_shadow_lifecycle_v1.py --name a2-shadow-v1 --backend nemotron_600m
# After closure and independent review:
& $prePiPython -B prepare_shadow_lifecycle_v1.py --name a0-shadow-v1 --backend nemotron_hybrid
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PREPI_PY%" -B test_shadow_gate_v1.py -v
"%PREPI_PY%" -B build_shadow_harness_v1.py
"%PREPI_PY%" -B prepare_shadow_lifecycle_v1.py --name a2-shadow-v1 --backend nemotron_600m
rem Only after independent closed-run review:
"%PREPI_PY%" -B prepare_shadow_lifecycle_v1.py --name a0-shadow-v1 --backend nemotron_hybrid
```

Proposed skip fractions on this synthetic file are not achieved speedups or
real-world/Pi performance. All inference still runs. Recorded observer overhead
includes energy, hashing and record construction; it excludes later JSON output.
Speech-loss accuracy, ASR/VAD cues, stateful applied skipping, full-bank shadow,
30/60-minute target endurance and independent held-out validation remain open.
