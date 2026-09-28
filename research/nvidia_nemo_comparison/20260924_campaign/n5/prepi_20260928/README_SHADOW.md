# Causal silence proposals without removing audio

Purpose: implement G01 exact digital zero, G02 -55 dBFS RMS and G03 -45 dBFS
RMS diagnostics in S01 shadow mode. The fixed initial/trailing guard is 300 ms,
with 20 ms source blocks and an exact final remainder. These are energy
diagnostics, not VAD or ASR-assisted gates. None is approved for applied skipping.

Inputs: already-prepared mono16k PCM16 source arrays from the existing saved-file
reader. The instrumentation forwards each original array to its original
journal before observation. It neither changes the source clock nor removes,
zeros, reorders or compresses audio. Source, ASR and D1 must consume every sample.
It has no future audio, truth labels, whole-file statistics or final transcript
in its decisions. Invalid or nonfinite input fails the diagnostic rather than
being called silence. There is no live-input hook.

Outputs: private source-sample intervals, proposed skips, PCM SHA-256,
below-threshold run lengths, energy duty cycles, and measured observer overhead.
All actually-skipped counts remain zero. The energy duty cycle is not speech
duty cycle: quiet speech and noise require independent annotations. No accuracy,
missed-speech rate, saved inference time or Pi throughput follows from these logs.
Synthetic silence-rich scenarios are conditional diagnostics only. Freeze these
settings before later independent dense/quiet/overlap/returning-speaker holdouts.

The module can instrument an isolated saved-file application process with
`observers = install(app.pipeline)` before Start. Each source gets its own
observer; use `observer.report()` after the source has stopped. A paired run must
check full PCM and sample counts, actual model activity, text/source-timestamp
parity with the ungated composition, normal drain/shutdown and process ownership.
All original sources and releases remain immutable; only the test process is
instrumented. Pending integration must not be called an executed shadow run.

PowerShell from this directory, for model-free safety tests:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $prePiPython -B test_shadow_gate_v1.py -v
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PREPI_PY%" -B test_shadow_gate_v1.py -v
```

The tests check exact-zero versus quiet samples, causal history, initial/trailing
guards, final remainders, invalid-input refusal and unchanged journal forwarding.
They open no models, GUI, devices or audio outputs. The current campaign CPU,
storage, saved-audio and no-Pi limits also apply to later integration runners.
