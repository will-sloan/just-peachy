# Live spatial adapter regression checks

`test_live_spatial.py` tests the live adapter using explicit synthetic host
receipt timestamps, real `LiveBlock` structures, and the actual retained
Balanced / Spatial-assisted profile. It does not open audio devices, query USB,
load neural models, use personal profiles, or run a dataset sweep.

## Run from the repository root

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& '.\.edge-speech-env\python.exe' prototype/tests/test_live_spatial.py
```

Command Prompt or Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
".edge-speech-env\python.exe" prototype\tests\test_live_spatial.py
```

On another installed host, use that installation's Python environment:

```sh
python prototype/tests/test_live_spatial.py
```

The test locates the adjacent application and vendored pipeline automatically.
The existing prototype dependencies must already be installed. During staged
development, replace the working directory with the directory containing the
staged `prototype` and invoke the same installed interpreter by its absolute
path.

## Inputs and outputs

Inputs are in-memory callback blocks, synthetic angle/energy replies, a fake
clock and diagnostic state, plus the checked-in S6C profile configuration.
Output is unittest's console result and a zero exit status when all checks pass.
It creates no recordings, galleries, reports, telemetry files or model outputs.

The suite covers causal audio-window joins, delayed consumer behavior,
independent energy freshness, NaN/no-fallback behavior, transaction limits,
reordered/future receipts, disconnection, clean session state, voice-qualified
estimated associations, independent name expiration, overlap, and the optional
scheduler hook. Missing energy retains the historical finite selected-angle
speech gate; fresh zero energy invalidates a cue. Neither behavior is a VAD
accuracy claim.

Confirmed voice names remain visibly estimated direction associations. These
tests do not establish physical direction accuracy, named-beam calibration,
real-person enrollment accuracy, or CM5 hardware readiness.
