# Roster tools: native proof and configuration export

Use the existing provisioned environment; no installation/download is required.

## Closed-group field correction, 21 September

`check_closed_display.py` reuses the two already-qualified public CMU fixture
profiles and the existing12s B query from `Resumes/.uiiter2_04/native_v2`. It copies
only those test profiles to a fresh output directory; it never opens the personal
gallery or creates a new enrollment. Two actual source-paced cases share models:
selected closed with both profiles, then selected open with only A (B is outside
the selected gallery). Every new closed caption must have a selected display
UUID immediately, including missing-voice assumptions; open B must remain
unnamed. Raw acoustic fields/scores stay distinct. One actual480x800 screenshot
and CLOSED_DISPLAY_CHECK.json record the observations and source hashes.

PowerShell from repository root:

```powershell
& .\.edge-speech-env\python.exe prototype/tools/check_closed_display.py --output Resumes/.closed_group_fix_20260921/native
```

CMD/Anaconda Prompt: the same command without `&`, after
`cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"`. `--fixture` optionally
locates the matching prior task04 fixture/receipt. The output must be new.
No microphone, audible playback, downloads, training or broad sweep. The window
briefly opens for a real screenshot and closes. A PASS demonstrates display
contract/lifecycle, not overlap or real-person identity accuracy.

## Existing tools

`export_mode_matrix.py` reads the actual app mode registry and frozen profile
files. It creates `prototype/docs/MODE_MATRIX.json` with every supported default
mode/recipe/O0/O1 profile, mode semantics, parameter bounds and source/config
hashes. No model is loaded and no personal data is read. Use `--output` to choose
another JSON path; the named output is deliberately replaced when regenerated.

PowerShell from the repository:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\export_mode_matrix.py
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype\tools\export_mode_matrix.py
```

`check_roster_modes.py` uses existing CMU ARCTIC decoded 16k sources and the prior
native fixture's disjoint query files. It extracts two bounded offline references
through the unchanged real enrollment quality gate into a **fresh private test
store**, never into the user's gallery. Six 12-second prepared-file cases reuse
one resident model cache: selected known, selected outsider, all-gallery other,
closed outsider, C079 selected known and C060 selected known. These are actual
ASR/segmentation/ReDimNet/controller runs. File spatial cases explicitly exercise
voice-only fallback without pretending to have physical direction telemetry.

Default inputs on this desktop:

```text
G:\Just_Peachy_S6C\20260910T123540Z\source_inventory\v2\decoded_16k
G:\Just_Peachy_PROTO1\tests\personal_fixture\20260919T020017_461049Z
```

Override with `--sources` and `--prior-fixture` if relocated. The prior fixture
must include `TEST_RECEIPT.json`, `fresh_same_person_query.wav` and
`wrong_person_query.wav`; source hashes must be disjoint from the new reference
pool. Cropping the first 192,000 already-PCM16 samples is byte-equivalence checked
after writing; no mixing/gain/resampling is applied. A failed frozen quality or
recognition assertion is reported, not fixed by lowering thresholds.

PowerShell from the repository (choose a fresh output):

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\check_roster_modes.py --data-root "C:\path\new-private-roster-check"
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype\tools\check_roster_modes.py --data-root "C:\path\new-private-roster-check"
```

Outputs: private fixture people/vectors, 12-second input WAVs, actual linked
session logs/configuration/resource samples, native UI screenshots, and
`ROSTER_NATIVE_CHECK.json`. It verifies narrowed loaded UUIDs and real score
calls, outsiders' open Unknown versus closed assumed captions, all-gallery
recognition, unchanged reference files, model reuse and shutdown. No live mic,
USB control or audible output is opened. Per-case 60s failure deadlines are
safety bounds, not target runtimes. Native offline PASS does not establish
real-room performance, overlap accuracy, physical touch or CM5 qualification.
