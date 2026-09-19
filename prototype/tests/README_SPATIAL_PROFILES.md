# Existing spatial profile regression checks

`test_spatial_profiles.py` verifies the prototype's two selectable spatial modes
against the actual existing S6C tracker. It checks exact complete parent settings,
preserved Balanced/Patient frontend and C088 naming settings, stronger location
influence for ambiguous voice, clear voice overriding seats and relocating,
missing/stale/unreliable cue fallback, time decay, and live provider wiring.

Inputs: bundled JSON profiles and explicit synthetic 192-dimensional vectors and
sensor observations. No microphone, people store, native model, recording, model
download, dataset sweep, or hardware access is used. These are deterministic
implementation checks, not measurements of real-person identification accuracy.
Output: unittest results on the terminal; no research report or audio output.

From PowerShell at the repository root:

```powershell
& '.\.edge-speech-env\python.exe' -B -m unittest discover -s '.\prototype\tests' -p 'test_spatial_profiles.py' -v
```

From Command Prompt or Anaconda Prompt at the repository root:

```bat
".edge-speech-env\python.exe" -B -m unittest discover -s "prototype\tests" -p "test_spatial_profiles.py" -v
```

For an exported installation, activate its documented Python environment, change
to the exported `prototype` directory, and run:

```text
python -B -m unittest discover -s tests -p test_spatial_profiles.py -v
```

See `../docs/SPATIAL_PROFILE_PROVENANCE.md` for the historical source and actual
composition. See `../README.md` for GUI launch/setup, assets and private storage.
