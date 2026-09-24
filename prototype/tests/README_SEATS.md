# Assigned-seat checks

Purpose: verify session-scoped UUID layouts, front/back-equivalent and overlapping
regions, stale/missing/multi-bearing/music gates, actual retained soft/strong scoring,
Unknown/forced provenance, voice conflict recovery, motion invalidation and touch
transactions. `test_seats.py` uses explicitly synthetic vectors/telemetry and temporary
stores; `test_seat_ui.py` uses real Tk with a fake controller. Neither loads a model,
opens a microphone, writes personal profiles or proves live recognition accuracy.

From the repository root in PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p 'test_seat*.py' -v
& .\.edge-speech-env\python.exe -B -m unittest discover -s prototype/tests -p 'test_*.py' -v
```

CMD / Anaconda Prompt: use the same commands without `&`, with double quotes
around the filename patterns instead of single quotes. Tests output pass/failure
details to the console. Existing Python/runtime dependencies are reused.
Saved real model evidence is checked separately by `tools/check_seat_modes.py`;
see `tools/README_SEATS.md`. Windows measurements do not qualify CM5.
