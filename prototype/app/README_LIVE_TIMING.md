# Live sample timing and Stop

`live_timing.py` validates one live epoch from integer 48 kHz frames and 16 kHz
sample counts. Inputs are the paired perf-counter startup/callback timestamps,
the exact pre-admission priming count, resampler phase and block epoch. Outputs
are a fixed stream-start feasibility bound and at most 64 metadata-only trace
rows. No model, file I/O, USB query or wait is added to the audio callback.

The first callback's arrival can be delayed or delivered in a driver batch.
Reported input latency is an estimate, not a maximum arrival-age contract.
The stream-start call entry plus counted priming now establishes the immutable
frame-count bound. ADC/currentTime remain independent diagnostics (this installed
WASAPI build reports future ADC values). Neither a delayed consumer nor a later
callback can rebase the origin or conceal noncontiguous frames. Genuine stream
gaps, rate/clock mismatch and resampler-count errors fail with a named check.

The source/model timeline remains nominal sample time. The factor-three causal
FIR emits sample indices 0,3,6,...; a final partial block can have an exclusive
model extent up to two native ticks beyond its receptive input. The scheduler
origin includes that exact 2/48000-second representation offset, separately from
the unchanged 1 ms FIR group delay. No samples are padded, removed, stretched,
or flushed with zeros. This is not acoustic-latency or long-term oscillator
calibration. An unaccounted priming gap invalidates this binding and fails.

Launch from the repository in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
& .\.edge-speech-env\python.exe -B .\prototype\tools\run_unit_checks.py --output-dir "$env:TEMP\jp-timing-check-01"
```

CMD/Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
.edge-speech-env\python.exe -B prototype\tools\run_unit_checks.py --output-dir "%TEMP%\jp-timing-check-01"
```

Choose a fresh check directory. The ordinary app opens idle and microphone
capture still needs consent. No timing toggle or threshold tuning is required.
`source_timing` events and `source_stopped.timing` retain the clock/sample trace
outside audio data; source/config hashes identify the runtime. Failure cleanup
retains its original cause and continues joining native lanes and writers.
See `../docs/UIITER2_01_HANDOFF.md` for executed checks and rollback instructions.
