# Session archive and touch checks

`test_sessions.py` checks exact float storage, immutable revisions and indexed
formatting, recorded window/padding export, process-interruption recovery,
queue exhaustion, injected disk failure, pinned retention/delete boundaries,
privacy export, resource joins, cached-model reuse and capture/output isolation.
The abrupt-interruption check starts a small child process and exits it before
archive finalization; all data is synthetic and temporary. Playback uses a fake
explicit-device sink, never the PC speakers.

`test_session_ui.py` uses real Tk controls with a synthetic controller to check
audio consent, delete confirmation, output selection and recording/loss display.
Neither test uses live microphone/USB, personal enrollments or neural models.
Inputs: temporary synthetic events/arrays/devices. Outputs: unittest pass/fail.

PowerShell from `prototype`:

```powershell
& '..\.edge-speech-env\python.exe' -B -m unittest discover -s tests -p 'test_session*.py' -v
```

CMD / Anaconda Prompt from `prototype`:

```bat
"..\.edge-speech-env\python.exe" -B -m unittest discover -s tests -p "test_session*.py" -v
```

The normal full suite also discovers these checks. For a short real-model
prepared-file check with restart and actual application screenshots, see
`../tools/README_SESSIONS.md`. Physical playback, real-room usability and CM5
remain separate checks; fake playback is not a hardware PASS.
