# Session archive tools

`check_session_archive.py` runs one short existing prepared 16k mono O0 WAV
through the real resident ASR/speaker pipeline. It never opens a microphone or
audible output. Inputs: existing models, WAV and a **fresh** private data root.
Outputs: the linked archive, window NPY/JSON exports, text/full ZIPs, actual Tk
screenshots and `SESSION_ARCHIVE_CHECK.json`. It verifies exact float bytes,
raw/formatted events, resource joins, Save/restart/reopen and corresponding
caption playback through a clearly labelled fake explicit-device sink.

From the repository in PowerShell (replace paths with your chosen fixture and
new directory):

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\check_session_archive.py --wav "C:\path\O0.wav" --data-root "C:\path\new-private-check"
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype\tools\check_session_archive.py --wav "C:\path\O0.wav" --data-root "C:\path\new-private-check"
```

Use a roughly six-second fixture containing speech so native embedding and
segmentation events exist. This is a functional check, not a sweep, accuracy
benchmark or CM5 qualification. The helper imports its fake playback sink from
the test suite, which must be present in the development checkout.

## Export a recorded model window without inference

`export_session_window.py` acquires the same personal-data lock: close the GUI
first. It never captures or loads a model. Obtain conversation/epoch UUIDs from
`conversations/<id>/conversation.json` and its `epochs` list. Listing needs no
audio export consent; writing requires a **saved/pinned** audio source and
explicit `--consent-export`. This creates sensitive unencrypted local data.

PowerShell from the repository:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\export_session_window.py --conversation "CONVERSATION_UUID" --epoch "EPOCH_UUID"
& .\.edge-speech-env\python.exe -B .\prototype\tools\export_session_window.py --conversation "CONVERSATION_UUID" --epoch "EPOCH_UUID" --window w00000001 --output "C:\path\new-window.npy" --consent-export
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype\tools\export_session_window.py --conversation "CONVERSATION_UUID" --epoch "EPOCH_UUID"
.edge-speech-env\python.exe -B prototype\tools\export_session_window.py --conversation "CONVERSATION_UUID" --epoch "EPOCH_UUID" --window w00000001 --output "C:\path\new-window.npy" --consent-export
```

Add `--data-root "C:\path\private-data"` for a nondefault archive. Default follows
`JUST_PEACHY_DATA` or `%USERPROFILE%\JustPeachy\data`. Output is exact float32 `.npy`
source data plus `<output>.json` with recorded padding, tensor shape, indices,
window kind and hash. It does not duplicate every overlapping window or apply
gain again. Existing targets/sidecars and destinations inside the pinned source
are rejected. Partial/missing source ranges fail explicitly. A leftover runtime
lock after an actual process crash requires the existing stale-lock recovery
procedure; do not remove a lock while its owning application is running.

Launch/workflow/storage policy: `../app/README_SESSIONS.md`.

Task08 adds `--portrait-during-run` to the existing bounded archive proof. It
pumps the actual Tk portrait window during saved-file inference, records UI
update gaps and RSS (including model loading), then checks a mode change and
simulated motion invalidation before save/reopen. It uses no live microphone.

PowerShell from repository root:

```powershell
& .\.edge-speech-env\python.exe prototype/tools/check_session_archive.py --wav "C:\path\prepared-16k-mono.wav" --data-root "C:\path\fresh-private-check" --portrait-during-run
```

CMD / Anaconda Prompt: remove the leading `&`. Inputs must be an existing short
16 kHz mono prepared WAV and a fresh output directory. Outputs are the private
archive, screenshots and `SESSION_ARCHIVE_CHECK.json`. This native check needs
the existing shared model store; do not export its fixture audio with releases.
