# Motion contract checks

`test_motion.py` validates timestamps, uncertainty, stale/out-of-order events,
no automatic anchor restoration, and byte-preserved synthetic voice profiles.
No GPIO, sensor, microphone or native inference is opened. Inputs are built-in
synthetic fixtures; output is unittest PASS/FAIL with temporary data removed.

Run from repository root in PowerShell:

```powershell
& .\.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p test_motion.py -v
```

CMD / Anaconda Prompt: the same command without the leading `&`.
Full regression receipt: `.edge-speech-env\python.exe prototype/tools/run_unit_checks.py --output-dir "C:\path\fresh-checks"`.
