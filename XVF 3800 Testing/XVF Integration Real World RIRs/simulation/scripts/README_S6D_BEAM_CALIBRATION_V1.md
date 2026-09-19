# Actual C-only beam calibration preparation

`s6d_beam_calibration_v1.py` reads closed, full-source-validated C collection probes. `extract` joins each actual candidate's entire mature source span to an independently accepted conservative C source-time support interval. It retains unlabelled boundary/overlap, stale, unknown and missing-score populations. It never shifts individual beams, searches lag, invokes a model or uses Q. `propose` applies one fixed conservative rule to exact matching capture-profile/gallery/profile/taps/selected-person contexts: each threshold exceeds the observed C-negative maximum by1e-6, with at least2 distinct C source IDs per class and2 retained positive sources. Correlated windows are not independent sample size. All5 gates must qualify; otherwise selectors remain disabled. Same-person copies cannot manufacture false competition or extra unique duration. Duplicate resolution remains off.

Inputs to `extract`: exact `--manifest`/`--manifest-sha256`, `--job-id`, actual closed protocol `--completion`, bound evaluator-only `--support`, and a fresh G `--output`. Support schema `s6d-C-captured-support.v1` must have status `ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT`, a separately bound `root_acceptance` JSON, exact original case_result, original actual C partition and gallery bindings, `no_per_beam_alignment=true`, `rir_origin_added_again=false`, and `spans`. Each span has role C, original source_id, gallery profile_id (null for original withheld/unknown), and integer captured16k-frame `start_min,start_max,stop_min,stop_max`. These are independently justified bounds on the shared case clock, not just point lag estimates. Equal min/max values may represent already-eroded eligibility fragments with their original uncertainty envelope retained in the support receipt; they do not prove zero DSP uncertainty. An entire candidate must lie in `[start_max,stop_min]` with no other possibly overlapping source support. No such proof is created by this helper.

Extraction requires reviewed collection helper6f716290, full predeclared frames/PCM, exact literal RESULT and full multistream audit, current unchanged journal hashes, actual closed consumer event path and pinned evidence reader. Every probe candidate must join a preceding actual `s6d_beam_identity` event by stream/event ID and identical payload identity/source clocks/capture/route. It must be the profile's actual1.5s mature window with at least80percent clean support. Probe metadata cannot invent a mature event or silently replace its recognized name. Confirmed IDs must belong to the actual gallery. Duplicate feature files/jobs and changed extraction/provenance sources are rejected before threshold proposal.

Calibration labels concern eligible final named-association agreement with original possible C input identity. Common input identity is not a guarantee that every focus stream preserved that speaker, or independent gold for an exact acoustic beam target. Root must assess this limitation and actual competition support before any selector enablement; this helper never declares a unique target for an overlap or two copies of one person.

Outputs: one C feature JSON with source/protocol/audit/support bindings and retained denominators; or a threshold proposal JSON. A proposal is never `ACCEPTED_C_ONLY`. Root independent review must validate the adequate same-window negative/competition data and exact profile digest before publishing the separate engine-compatible calibration receipt. If actual C fails to provide support, this records the limitation rather than declaring a beam-family failure at invented nominal thresholds. MAIN and SCAN may not be pooled. Neither actual collection nor extraction has been launched merely by writing this code.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$sim\scripts\s6d_beam_calibration_v1.py" extract --manifest '<exact closed C manifest.json>' --manifest-sha256 '<SHA256>' --job-id '<literal C job>' --completion '<actual COMPLETION.json>' --support '<accepted conservative captured C support.json>' --output 'G:\Just_Peachy_S6D\20260913T195357Z\application\beam_C_features_v1\case.json'
& $py -B "$sim\scripts\s6d_beam_calibration_v1.py" propose --features '<first exact compatible C feature.json>' '<second exact compatible C feature.json>' --output 'G:\Just_Peachy_S6D\20260913T195357Z\application\beam_C_features_v1\THRESHOLD_PROPOSAL.json'
```

Anaconda Prompt / CMD: set the same SIM path and run the existing interpreter directly with the same arguments:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_beam_calibration_v1.py" propose --features "<first exact C feature.json>" "<second exact C feature.json>" --output "G:\Just_Peachy_S6D\20260913T195357Z\application\beam_C_features_v1\THRESHOLD_PROPOSAL.json"
```

Use fresh output names. Actual input acceptance and scoring are root-owned; source/fixture review is required before these commands are admitted. No output mutates the original gallery thresholds, weights, waveforms, profile, E/C/Q or historical results.

`s6d_beam_calibration_checks_v1.py --output FRESH_G_DIRECTORY` tests conservative interval boundaries, unknown/overlap retention, finite threshold fitting, no negative/separation fallback and rejection of correlated-window sample inflation. Six related tests require the actual mature-event join, reject missing/changed/foreign/short/unclean evidence and require predeclared PCM before any result read. Inputs are tiny in-memory synthetic values; outputs are TESTS.log and RECEIPT.json. No actual C outputs are scored, and no model/device runs.

PowerShell: `& $py -B "$sim\scripts\s6d_beam_calibration_checks_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_calibration_v1_checks'`.

Anaconda Prompt / CMD: `"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_beam_calibration_checks_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\beam_calibration_v1_checks"`.
