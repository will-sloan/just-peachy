# Shared backend selector

`backends.py` loads `../config/backends.json` without importing models or opening
devices. Inputs are an immutable composition ID, logical mode, O0/O1 tap and an
explicit matching-spatial-telemetry flag. Outputs are detached composition,
availability and capacity dictionaries, or an explicit startup error.

The visible **BACKEND** button is separate from Mode and Recipe & tap. It lists
the preserved Giga / Pyannote / ReDimNet / final-only punctuation composition
and three implemented N2 alternatives: Nemotron/ReDimNet, Pyannote/TitaNet and
Nemotron/TitaNet, each retaining Giga and final-only punctuation. Four later
ASR compositions remain unavailable planning entries. N2 needs explicit local
asset configuration; see [N2 setup and operation](README_N2.md). Selecting a backend
stops the current session through the controller and preserves mode, recipe
and tap. Compatible selected/highlighted UUIDs are remembered per embedding
store; missing references get a re-enrollment notice and do not block full
captions. Start remains explicit. An unavailable selection never falls
back to baseline inference. Seed entries are not installed implementations or
license admission evidence. Candidate downloads alone cannot enable them.

Each `manifest_id` is SHA-256 of canonical JSON (`sort_keys=True`, compact
separators, UTF-8) for the `composition` payload. It binds model assets, runtime
and preprocessing, including baseline hashes from the existing assets manifest.
Any composition edit requires a new ID. Availability, UI labels and capacity
metadata are separate from the hash payload. Mode/recipe/tap/roster/seat truth
are forbidden in the model payload. This does not replace the campaign's
separate whole-file hash and source freeze.

All logical modes remain listed for every backend. Missing candidate adapters
have the same explicit reason in every mode. Spatial modes require matching
recorded telemetry for saved replay; absent telemetry is an unavailable state,
never synthetic directions. Existing live implementation is separately gated
by the controller's explicit authorization and real telemetry. No capacity or
2 GB CM5 performance is inferred from model file size. N2 verifies eight
Nemotron activity slots; more-than-eight-person overflow remains undetectable
from those channels and is not solved by a larger gallery. One active
stack is allowed by this interface; side-by-side launches are not automatic.

Embedding spaces remain specific to the encoder. Existing ReDimNet profiles
are never passed to TitaNet. Compatible permitted reference audio or explicit
re-enrollment is required when selecting an incompatible encoder. N2 session
adaptation is unavailable; closed-roster names remain explicit assumptions.

## Run the safe checks

From PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m prototype.tests.run_private_desktop --receipt-dir 'G:\Just_Peachy_N1\20260924_campaign\evidence\frontend\manual-check' prototype.tests.test_backend_catalog prototype.tests.test_n1_frontend
```

CMD or Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m prototype.tests.run_private_desktop --receipt-dir "G:\Just_Peachy_N1\20260924_campaign\evidence\frontend\manual-check" prototype.tests.test_backend_catalog prototype.tests.test_n1_frontend
```

Use a fresh receipt directory for each run. These commands consume only source
fixtures and create test/desktop-isolation receipts, with no audio, personal
gallery, USB or model access. The launcher never switches the user's desktop.
See `../tests/README_N1_FRONTEND.md` for rendered-app captures and the common
event contract. Normal application commands are in `../START_PROTOTYPE.md`;
N1's campaign GUI opens idle and saved-audio-only restrictions remain in force.
