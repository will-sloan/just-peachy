# Noise branch contracts

Purpose: deterministic route, failure, identity-domain, enrollment, archive and
actual portrait-widget checks. These use disclosed fake audio/model fixtures;
they do not establish recognition accuracy. Native checks are separate under
`../tools/README_NOISE.md`.

From `C:\Users\amiri\Documents\GitHub\just-peachy\prototype`, PowerShell:

```powershell
& ..\.edge-speech-env\python.exe -m unittest discover -s tests -p test_noise.py -v
& ..\.edge-speech-env\python.exe -m unittest discover -s tests -p test_noise_ui.py -v
& ..\.edge-speech-env\python.exe tools/run_unit_checks.py --output-dir ..\Resumes\.uiiter2_10\unit_repeat
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
..\.edge-speech-env\python.exe -m unittest discover -s tests -p test_noise.py -v
..\.edge-speech-env\python.exe -m unittest discover -s tests -p test_noise_ui.py -v
..\.edge-speech-env\python.exe tools\run_unit_checks.py --output-dir ..\Resumes\.uiiter2_10\unit_repeat
```

Inputs: source tree and installed runtime; no physical device, model download or
personal store. Outputs: unittest assertions; the complete runner also writes
hash-bound JSON and a text log to the chosen directory. Use a new directory.
Run the full suite through the supplied runner: it collects Tk interpreter
cycles on the main thread before later worker tests.

Coverage includes irregular sample tails, route domains/model hashes, raw
fallback without duplicate samples, already-inflight helper output after
fallback, stopping enhanced identity at its exact boundary, unchanged caption
text with cleared stale names, enhanced enrollment hashes/failure, consented
two-stream archives and absent audio without consent, unknown/stale evidence,
safe selection with no automatic Start, and480×800 controls.

