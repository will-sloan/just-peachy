# Build bounded native job manifests

`s6c_jobs.py` turns a frozen S6C epoch into explicit, validated native jobs. It
does not run models. Inputs are the frozen profiles, source index, metadata
panel, original bank, and exact gallery/cue assignments where needed. Outputs
are immutable `reports/S6C/20260910T123540Z/jobs/<epoch>/<stage>_<attempt>.json`.

Stages:

- `smoke`: N01 dual evidence on three varied whole scenes/both taps.
- `recipes`: each changed neural recipe on all 56 metadata-panel scenes/both
  taps, including the policy-dependent uncertainty companion.
- `families`: six varied scene pairs for each of eight structures with cue-off
  and real-cue branches at matched capacity64.
- `split`: four explicitly declared routes over the panel. SAME-route aliases
  are labeled controls, not extra independent mechanisms.
- `full --candidates ...`: all240, all applicable declared routes for explicit
  retained candidates. Missing galleries/conditions stop admission.
- `paced --candidates ...`: twelve balanced family scenarios per applicable tap
  for actual source-speed acceptance. Repeat cells use a named `--attempt`.

## PowerShell

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' .\s6c_jobs.py smoke --epoch epoch1
```

## Anaconda Prompt / CMD

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_jobs.py smoke --epoch epoch1
```

Use the returned manifest with the frozen `s6c_execution.py run --jobs ...`
command in README_S6C_EXECUTION.md. `--candidates C011 C012` filters a stage or
explicitly sets full/paced confirmation. `--attempt v2` creates a separate
namespace after a diagnosed failure or registered repeat; it never erases
earlier results. Regenerating an existing manifest must reproduce its exact
jobs. The same execution command then reuses verified completed receipts.

The 12-scenario paced panel is runtime confirmation; broad retained accuracy
claims still require all240. Repeated cells and 30–60 minute endurance have
separate declared manifests and are not inferred from these short jobs.
See README_S6C.md for scope/resource/stop/rollback requirements.

The enrollment stage uses the same six frozen varied F01/F03/F04/F06/F08/F12 scenes as the family stage, both taps, for every registered nonempty-gallery condition/tier (including explicitly unavailable empty manifests). It exercises actual native ProfileStore/name integration. Example: s6c_jobs.py enrollment --epoch epoch2. These bounded native checks do not replace all240 enrollment-aware finalist confirmation.

Epoch3 fresh_families stage selects all eight structural families with the same N01 dual-evidence frontend, capacity64 and retirement policy, cue-off/real-cue pairs, and the frozen six varied scenes. Example: s6c_jobs.py fresh_families --epoch epoch3. This is the registered admission-rescue companion to the N00 family screen.
