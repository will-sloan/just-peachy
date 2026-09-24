# Bounded native noise checks

`check_noise_native.py` measures one fixed12-case comparison using existing
Sherpa/Pyannote/ReDimNet and the single DPDFNet baseline. It then runs all four
application routes sequentially, with separate original/enhanced reference
domains, a fresh known query and an outsider, exact consented archive/window
checks, and an existing post-XVF prepared-file example. No capture/playback,
threshold search, large sweep, metrics package or training. It uses a private
fixture store, never the production people directory.

Inputs: existing CMU ARCTIC corpus, first indexed S45_01_01 post-XVF prepared O0
file and its hash-bound scene index, installed base assets and the optional hash
directory in `config/enhancement.json`. All source recordings remain intact.
Outputs: private `NATIVE_NOISE_CHECK.json`, per-branch float WAVs (fresh full run),
fixture profiles, captions, epochs and exported model-window NPY files.
These include speaker vectors and must stay local. One native helper is active;
the four combinations reuse the two measured clip branches, then each route is
also exercised through the actual application. Overlap has two valid transcripts
but no uniquely ordered single-output WER, so its WER is explicitly null.

From the repository `prototype` directory, PowerShell:

```powershell
& ..\.edge-speech-env\python.exe tools/check_noise_native.py --output ..\Resumes\.uiiter2_10\native_repeat
& ..\.edge-speech-env\python.exe tools/check_noise_ui.py --output ..\Resumes\.uiiter2_10\ui_repeat
& ..\.edge-speech-env\python.exe tools/check_noise_enrollment.py --output ..\Resumes\.uiiter2_10\enrollment_repeat --wav ..\Resumes\.uiiter2_10\native_repeat\known.wav
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
..\.edge-speech-env\python.exe tools\check_noise_native.py --output ..\Resumes\.uiiter2_10\native_repeat
..\.edge-speech-env\python.exe tools\check_noise_ui.py --output ..\Resumes\.uiiter2_10\ui_repeat
..\.edge-speech-env\python.exe tools\check_noise_enrollment.py --output ..\Resumes\.uiiter2_10\enrollment_repeat --wav ..\Resumes\.uiiter2_10\native_repeat\known.wav
```

Choose fresh output paths. `--corpus "path"` can override the CMU root.
`--reuse-cases "previous\NATIVE_NOISE_CHECK.json"` reuses completed native
clip/state checks after runtime-hash validation, and reruns route integration;
it records the source receipt/hash and original resources. This avoids repeated
inference after an integration-harness failure; it never changes a failed result
into PASS or skips the unfinished application checks.

`check_noise_ui.py` opens an actual480×800 window with an isolated Controller,
loads only the optional helper, exercises all route choices, saves PNGs plus
`UI_CHECK.json`, returns the private setting to Bypass and closes the window.
No microphone Start, enrollment or listening command is sent. Widget stub tests
are explicitly distinguished from this real-controller check.

`check_noise_enrollment.py` passes a prerecorded mono16k WAV through the actual
enrollment quality worker and resident models for all four routes. It proves the
exact ASR and identity arrays differ only as selected, retains quality-domain
hashes and writes `ENROLLMENT_NOISE_CHECK.json`. Its queue is the explicit file
fixture; it does not open an input device or create a user's enrollment.

Word metrics use deterministic unit-cost Levenshtein S/D/I, casefolding and
word/apostrophe tokens. Ground truth is canonical full-clip text or explicitly
empty digital controls. Noise is fixed seed10/0dB SNR; quiet is−20dB; the click
and narrow instrumental control have declared constructions. These small
examples expose failures; they do not estimate population accuracy. CPU is
process user+system, RSS sampled every50ms, incremental helper load measured
after core-model loading. Desktop values do not certify CM5 feasibility.
