# Deterministic live timing regressions

`test_live_timing.py` uses synthetic callback metadata and the actual FIR and
session watcher. No microphone, models or personal profiles are used. It shows
the old latency-estimate epoch rejecting valid batched frames after a delayed
first callback, then verifies the stream-start/count bound accepts exactly the
same sample sequence. It also checks variable/final partial blocks, independent
clock origins, consumer delay, discontinuities, stale epochs, priming gaps,
resampler count mismatch and finalization after a source failure.

PowerShell from repository:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\run_unit_checks.py --output-dir "$env:TEMP\jp-timing-tests-01"
```

CMD/Anaconda Prompt: omit `&`, and replace `$env:TEMP` with `%TEMP%` in double
quotes. Inputs are code and fixtures; output is the bounded suite log/JSON with
source hashes. Use a fresh output directory to preserve previous results. Live
speech and CM5 results must be recorded separately from these fixture checks.
