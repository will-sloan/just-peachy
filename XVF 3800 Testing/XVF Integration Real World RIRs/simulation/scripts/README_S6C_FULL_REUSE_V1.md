# Full native grid with exact panel-job reuse

`s6c_full_reuse_v1.py` builds an all-240-scene native manifest for explicitly
retained candidates while preserving exact job objects from one supplied prior
manifest. The original builder changes only the folder from `recipes` to `full`
for overlapping keys, which hides old receipts from its folder-based reuse
lookup. This helper instead keeps every old job field and its receipt-bearing
folder. Native outputs are never copied, moved, relabeled or rewritten.

Inputs: the frozen native epoch2 manifest/assets/profiles; canonical input and
gallery/cue registries; one explicit prior native job manifest; retained
candidate IDs; optional expected completed/new counts. Every intended full job
is built by the original frozen `make_job`. A prior equal key must match every
field except folder, then the exact prior object is selected. Original
`validate_job` and `verify_job` rehash its input and completed native evidence,
events, summary, closure, vectors and both PCM journals. A failed/incomplete
attempt rejects; this helper does not create an accuracy or fault retry.

Outputs: a new `jobs/epoch2/full_reuse_<name>.json` and a separate source-bound
FULL_REUSE_LEDGER with every folder/key/origin/status and complete receipt.
These register a full grid, not completion. Actual launch rechecks everything
again using the original frozen runner or reviewed coordinator overlay.
The explicit prior source controls provenance; the helper never searches for
whichever historical execution has preferable results.

PowerShell (no neural execution):

```powershell
$s6cScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$s6cReport = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z'
Set-Location -LiteralPath $s6cScripts
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cPython s6c_full_reuse_v1.py --test --name v1
& $s6cPython s6c_full_reuse_v1.py --source-manifest "$s6cReport\jobs\epoch2\recipes_v1.json" --candidates C065 --name C065_v1 --expected-completed 112 --expected-new 368
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
set "S6C_REPORT=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_full_reuse_v1.py --test --name v1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_full_reuse_v1.py --source-manifest "%S6C_REPORT%\jobs\epoch2\recipes_v1.json" --candidates C065 --name C065_v1 --expected-completed 112 --expected-new 368
```

The helper uses the V2 overlay's model-free loader to bind the canonical workspace
environment and exact frozen modules; it does not install the storage overlay,
call `run`, create a process pool or load model objects. SHA checks still read
model files. For multiple retained candidates, list their IDs after `--candidates`
and supply totals appropriate to their actual admitted routes. A new missing
source job may retain its known old folder, but no started/failed folder is
silently reused. Existing target manifests/ledgers require a fresh name.
