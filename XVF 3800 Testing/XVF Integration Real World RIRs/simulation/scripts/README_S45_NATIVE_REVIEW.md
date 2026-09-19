# Independent S4.5 native evidence review

`s45_native_review.py` audits existing development-only H2 outputs and the 24 frozen dry controls. It does not import the H2 engine or scorer, load models, open audio/USB endpoints, signal processes, or modify any job evidence. Its only outputs are its own report JSON files. It reads the actual gained mono WAV and native PCM16 spool to verify every sample, then independently checks lifecycle events, native summary, baseline source/config/asset identities, embedding gate counts, emitted labels, supported turn labels and returning-participant consistency. The analysis identity is joined to the accepted take's audio analysis, level disposition and independently measured output delay; the retained 50 ms RIR margin is added exactly once. Anonymous labels remain local to each session; no reconciled identity, enrollment naming, DER or output winner is inferred.

Inputs are the existing `reports\S4_5\20260909T031300Z` contract, accepted-capture manifest, frozen sentinel/dry/gain plans and completed job receipts; the active `scene_bank\s45_v2_20260909T031300Z` manifest; exact source and native artifact paths bound by those receipts. Active plan paths and hashes must equal the executed contract, and the dry plan must bind those same scene/sentinel authorities. Quarantined metric identity, fixed gain and level classification must match its job and the accepted take's analysis receipt. Only 24 predeclared development sentinels (O0/O1) and 24 development dry controls are allowed. Reserve task metrics are never opened. Baseline model weight files are not rehashed; native summary asset identities and unchanged internal-validation source paths provide the same qualified evidence as the first-native review.

Use the existing Anaconda environment with NumPy and SoundFile; no installation is needed. The process observation uses Windows PowerShell/CIM for the recorded **completed job PIDs only**. Later pending model jobs can continue. A live PID with the same adapter command blocks review; a demonstrably unrelated reused PID is retained as such. The tool never waits for or controls a model process.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\amiri\anaconda3\python.exe' s45_native_review.py
# After all 48 output dispositions and all 24 dry jobs are terminal:
& 'C:\Users\amiri\anaconda3\python.exe' s45_native_review.py --final
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\anaconda3\python.exe" s45_native_review.py
REM After all intended output dispositions and dry controls finish:
"C:\Users\amiri\anaconda3\python.exe" s45_native_review.py --final
```

The default updates only `H2_NATIVE_REVIEW_PROGRESS.json` atomically. Missing, actively written or nonterminal receipts remain explicitly pending/unsuccessful; they are not read as finished native evidence. A completed receipt failing an invariant is a review failure. Each invocation rechecks the current completed jobs; common source files are hashed once per invocation. No scientific results are recomputed by an H2 model or changed.

`--final` exclusively creates `H2_FINAL_NATIVE_REVIEW.json` and refuses to overwrite it. It requires all 72 intended dispositions verified: output quarantine is permitted only with zero model invocations and unscored metrics; all dry jobs must be native complete. This final report cannot be created from partial progress. Exit 0 means the observed subset passed (possibly `PARTIAL_NATIVE_REVIEW`); exit 2 means evidence failures. Read the report status and counts rather than equating exit 0 with all jobs complete.

The active audit also requires `staging\s45_native_review\v2\TEST_RECEIPT.json` to bind its exact current code, tests and this README, with all recorded fixtures passing. Reports bind that receipt and those files. The original audit/test receipt and the peer-review revision's prior bytes/diff are preserved under `staging\s45_native_review`; the two additional provenance checks came from synthetic review cases, not observed corrupted experiment data.

Meaningful helper fixtures use synthetic arrays/events and no actual job files, subprocesses, models or devices:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_native_review -v
```

In Anaconda Prompt/CMD use the same command without the leading `&`. Tests cover mixed-format JSON, altered adapter/journal rejection, native event and unavailable-lineage assertions, gate reconstruction, and missing/returning-label evidence. Test success validates these helpers; it is separate from the actual evidence audit.
