# N3 ASR integration

`n3_models.py` admits immutable native ASR bindings and lazily reuses recognizer
weights between independent saved files. `n3_pipeline.py` carries every returned
partial/final through the existing word-first display and identity scheduler.
It consumes the continuous journal, accounts for all samples, flushes once, and
keeps raw native word offsets separate from coarse UI revision support. Native
EOU does not reset the diarizer, identity memory or enrollment gallery.

Inputs: selected backend's `composition.n3` and private `n3_runtime.json`, the
unchanged application config, compatible gallery, and mono 16 kHz saved audio.
Outputs: ordinary captions/archive plus `n3_asr_result`, dispatch and flush
receipts. An optional N2 identity composition retains model-specific E0/E1 spaces.
Personal data and the baseline model files are not modified. Catalog entries
identify implemented adapters; validation stays pending until actual model and
session tests succeed. These are not yet accepted N4 or target-device releases.
Read-along enrollment progress is explicitly unavailable for N3; it does not
open an incompatible streaming object. This campaign does not run enrollment.

PowerShell syntax check from the campaign worktree:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m py_compile prototype/app/n3_models.py prototype/app/n3_pipeline.py
```

CMD or Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m py_compile prototype/app/n3_models.py prototype/app/n3_pipeline.py
```

Run N3's admitted saved-file runner using the campaign README. A GUI launch is
not part of a syntax check and must not disturb the user's active desktop.
Rollback selects the existing Baseline entry and starts a fresh session. The
six frozen shared UI/presentation modules and UI layout are unchanged.
