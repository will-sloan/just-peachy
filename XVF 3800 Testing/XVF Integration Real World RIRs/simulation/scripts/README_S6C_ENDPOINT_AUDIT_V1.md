# Actual endpoint-advice incidence and token-position audit

Purpose: report what the completed C065/C079/C195/C196 factorial actually emitted, without changing its frozen native code. This is a separate audit over existing predictions and their exact native receipts. It constructs no model, never plays or captures hardware, and does not recompute the official cp/MIMO metrics. `checks` is model-free; `prepare` and `run` wait for complete future sources and root's queue authorization.

Inputs are explicitly caller-pinned COMPLETE prediction indices, the epoch6/V7/panel/endpoint amendment, fixed canonical bank/input bindings, each selected prediction's native receipt/events/summary/finalization, and inherited normalization/reference-layout code. Four candidates ×56 fixed cases ×both same-tap routes =448 logical views are required. All11 empty/music cases are retained for each candidate/tap. Different duplicate results for one selected key reject; identical repeated references are deduplicated. No outcome selects a scene.

C195/C196 require their own actual epoch6 full-profile+cue native sources. C065/C079 can use the established compatible N01 cached ASR source when all actual neural settings/routes match and the source has no endpoint advice or policy-driven cadence. Every actual source must belong to a SHA-pinned epoch2/4/5/6 manifest with exact29 APP inventory, whole native worker/common module, asset/environment/input/state equality; changed epoch3 is not admitted. The output retains both logical candidate and actual native candidate. Each distinct receipt's event log is scanned once and hash-verified; a parent source reused by two policies is not another inference. Existing PCM/vector/model bindings remain transitively preserved, and PCM frame/hash receipts are compared to the canonical inputs; audio/vector/model payloads are not reopened.

Outputs under `reports/S6C/20260910T123540Z/endpoint_audit/<name>`:

- `PLAN.json`: exact448 selected prediction/native-source bindings and source code hashes, before event scans.
- `NATIVE_SOURCES.json`: one record per actual source receipt, exact event counts, advisory reasons/proposals/acceptance, native-only/advice-only/coincident reset counts, raw final observations, EOF coverage, nested costs and available queue fields.
- `CELLS.json`: logical candidate/route/source relation, population, actual raw first/last words, token-position diagnostics and source references.
- `PAIRED_DIAGNOSTICS.json`: both endpoint contrasts and both tracking contrasts, same cases/taps, word/reset differences and exact source reuse.
- `RESULT.json`: scoped completion, counts and limitations. No file is overwritten.

The frozen loop logs advisor status on each full ASR cost event, and logs one actual reset event for native, advice, or coincident signals. The audit verifies the OR flag and exactly one matching reset for every requested dispatch. Coincident acceptance is not an additional reset. Final short ASR tails are decoded but do not receive an extra advisor observation. The finalization receipt verifies closed lanes/writers and complete paired sample counters. Raw empty reset returns are not logged, so their count stays null; a missing final event is not called an empty return.

Text diagnostics use the exact inherited lowercase/punctuation/whitespace normalization and whole-utterance reference serialization. A bounded unit-cost token alignment reports deletion/substitution reference positions, insertion hypothesis positions/boundaries, and the actual aligned operation on the first and last reference tokens. Tie priority in backward traversal is equal, substitution, deletion, insertion; repeated words may allow other optimum alignments. These positions do not provide acoustic timestamps or demonstrate phonetic clipping. Complete overlap is retained as a **serialized overlap diagnostic**, not the official MIMO/word-recall score. Incomplete all-speaker reference has null full-ASR token-loss scores. Empty/music cases retain decoded-word insertions with no WER denominator. Official first-display/first-final/latest cp and MIMO rates remain in the frozen scorer's separate output.

Costs preserve logged model/API/decode/advisor/reset/full-dispatch/drain fields by event type with observed event counts. They are nested and concurrent, so do not sum them into elapsed time. Native/worker/process CPU and bundle-admission values remain distinct; bundle admission is not necessarily cold model load. Scheduler maintained max-pending, final journal lags and unprocessed short speaker tail are explicit. Continuous journal peak and causal explanation for changed words remain unavailable.

PowerShell checks now (one immutable receipt, no actual native logs):

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$report = Join-Path $sim 'reports\S6C\20260910T123540Z'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_endpoint_audit_v1.py" checks
```

After the completed parent/child prediction indices are available, substitute their exact independently admitted paths/hashes. Multiple indices can cover the four candidates; unrelated rows are excluded by the fixed candidate/panel grid.

```powershell
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_endpoint_audit_v1.py" prepare --name actual_factorial_v1 --index 'C:\exact\parent_PREDICTION_INDEX.json' 'EXACT_PARENT_SHA256' --index 'C:\exact\endpoint_PREDICTION_INDEX.json' 'EXACT_CHILD_SHA256'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_endpoint_audit_v1.py" run --plan "$report\endpoint_audit\actual_factorial_v1\PLAN.json" --plan-sha256 'EXACT_PUBLISHED_PLAN_SHA256'
```

Anaconda Prompt / CMD (existing interpreter, no installation):

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "REPORT=%SIM%\reports\S6C\20260910T123540Z"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_endpoint_audit_v1.py" checks
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_endpoint_audit_v1.py" prepare --name actual_factorial_v1 --index "C:\exact\parent_PREDICTION_INDEX.json" "EXACT_PARENT_SHA256" --index "C:\exact\endpoint_PREDICTION_INDEX.json" "EXACT_CHILD_SHA256"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_endpoint_audit_v1.py" run --plan "%REPORT%\endpoint_audit\actual_factorial_v1\PLAN.json" --plan-sha256 "EXACT_PUBLISHED_PLAN_SHA256"
```

An incomplete/failed prediction index prevents this completed-grid audit and remains explicit in its original execution/scoring status. Failures are never silently converted to empty output. Any audit failure preserves its namespace; use a separately reviewed new version for a repair. No results or final study completion are claimed by helper preparation or synthetic fixtures.

Before first use, the source-epoch admission was strengthened. Original15-fixture source/README/receipt remain exactly under `staging/s6c/20260910T123540Z/endpoint_audit/before_epoch_guard_v1`; `AUDIT_HELPER_CHECKS_V2.json` resolves them and adds actual metadata/source epoch equality admission. Independent review then added exact integer tail-count/span equality and prediction cue-condition/canonical case+tap telemetry checks, including cached C079 controls. The V2 source/README/receipt remain exactly under `endpoint_audit/before_tail_cue_guards_v2`. Current `checks` publishes `AUDIT_HELPER_CHECKS_V3.json` once, with19 token/reset/tail/parser checks and6 synthetic canonical-cue source checks plus the unchanged actual source-epoch admission. No real plan, event scan or model ran under the earlier helpers.
