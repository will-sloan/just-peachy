# Recovered historical controls post-analysis

This adapter processes the completed B00/B01 `controls_fast_v1` cells after a separately reviewed external archive recovery. It does not archive or remove the shared quiet lease, change native results, load models, or rerun audio. The original coordinator's failed observer exit remains failed history. A distinct recovery authority must establish the exact closed 80-cell grid and released lease before analysis can start.

The helper privately reuses the exact code objects of the held fast adapter's preparation/run/context functions, with an explicitly bound recovery inventory. The original historical converter retains its scientific functions, B00 versus B01 generation handling, actual timing, repetition separation and policy parity arithmetic. No module globals are patched.

The held recovery overlay source is pinned to SHA256 `e2f6dece6c9062e35f8cdeece73376a670e4ba3d390059a8b04de85548afadf8`. Actual preparation/run still requires independent admission review and the root coordinator's explicit post-recovery analysis authorization. Source/tiny-context checks do not establish actual recovery or native completion. The earlier unexecuted draft and checks are preserved under `simulation/staging/s6c/20260910T123540Z/controls_recovery_analysis/before_overlay_pin_v1`.

## Inputs

- One exact external recovery receipt, supplied as absolute path and SHA256.
- One finite observer index with the original worker exits and failed parent observer exit retained, plus the explicit recovery context admitted by the reviewed inventory overlay. Never replace the failed exit with a successful one.
- The unchanged original manifest:
  `G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_fast_v1\MANIFEST.json`
  with SHA256 `8fb281fe4788e549cfb294bdcfb6adf326144cfeefbb1d09c76cf22f7b26c044`.
- For run, the exact request and original PLAN bindings returned by prepare.
- The existing EDGE interpreter and unchanged historical code/assets referenced by the original converter.

Only these generation/output pairs are admitted:

| Generation | Candidate | Fresh analysis namespace |
| --- | --- | --- |
| baseline | B00 | controls_b00_recovered_fast_v1 |
| research | B01 | controls_b01_recovered_fast_v1 |

Each generation must run in a fresh process. Both use the same recovered 80-cell manifest, but each analysis selects its own 40 actual cells. Original B00 unlogged embedding vectors or research drain instrumentation remain unavailable; no new name, word-boundary, full-campaign or operating-preset claim follows from this conversion.

## Outputs

The unchanged converter writes `PLAN.json`, `RESULT.json`, per-cell measurements and repetition-specific prediction indexes under:

`simulation\reports\S6C\20260910T123540Z\historical_paced_analysis\<namespace>`

The held fast adapter writes its immutable `REQUEST.json` under:

`simulation\reports\S6C\20260910T123540Z\fast_post_analysis_admission\historical\<namespace>`

Requests/plans bind this new helper, README, recovery overlay, exact recovery receipt, explicit observer index, and the held original sources. CLI JSON output adds the distinct recovery binding and code-identity proof around the original prepared-plan/result binding. Original scientific artifacts and all previous failed native/observer records stay unchanged. A failed preparation/run keeps the original converter's failure records. Do not reuse a failed namespace.

## PowerShell

Only perform actual prepare/run after the root coordinator confirms quiet is released and the reviewed external recovery is complete. Replace each `REPLACE_...` value with the approved exact binding; do not guess paths or hashes.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edge = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$helper = Join-Path $sim 'scripts\s6c_controls_recovery_analysis_v1.py'
& $edge -B $helper checks
```

For B00:

```powershell
$recoveryPath = 'REPLACE_APPROVED_RECOVERY_PATH'
$recoverySha = 'REPLACE_APPROVED_RECOVERY_SHA256'
$observerPath = 'REPLACE_FINITE_OBSERVER_INDEX_PATH'
$observerSha = 'REPLACE_FINITE_OBSERVER_INDEX_SHA256'
$manifestPath = 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_fast_v1\MANIFEST.json'
$manifestSha = '8fb281fe4788e549cfb294bdcfb6adf326144cfeefbb1d09c76cf22f7b26c044'
& $edge -B $helper prepare --recovery $recoveryPath $recoverySha --observer-index $observerPath $observerSha --manifest $manifestPath $manifestSha --generation baseline --namespace controls_b00_recovered_fast_v1
& $edge -B $helper run --recovery $recoveryPath $recoverySha --request 'REPLACE_REQUEST_PATH' 'REPLACE_REQUEST_SHA256' --plan 'REPLACE_PLAN_PATH' 'REPLACE_PLAN_SHA256'
```

For B01, use a new process with the same explicit recovery/index/manifest arguments, `--generation research --namespace controls_b01_recovered_fast_v1`, and then its own returned request/plan bindings. Do not feed B00's plan to B01.

## Anaconda Prompt / Command Prompt

The absolute EDGE executable selects the original environment without changing the active Conda environment.

```bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_EDGE=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "S6C_HELPER=%S6C_SIM%\scripts\s6c_controls_recovery_analysis_v1.py"
"%S6C_EDGE%" -B "%S6C_HELPER%" checks
set "S6C_RECOVERY=REPLACE_APPROVED_RECOVERY_PATH"
set "S6C_RECOVERY_SHA=REPLACE_APPROVED_RECOVERY_SHA256"
set "S6C_OBSERVER=REPLACE_FINITE_OBSERVER_INDEX_PATH"
set "S6C_OBSERVER_SHA=REPLACE_FINITE_OBSERVER_INDEX_SHA256"
set "S6C_MANIFEST=G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_fast_v1\MANIFEST.json"
"%S6C_EDGE%" -B "%S6C_HELPER%" prepare --recovery "%S6C_RECOVERY%" "%S6C_RECOVERY_SHA%" --observer-index "%S6C_OBSERVER%" "%S6C_OBSERVER_SHA%" --manifest "%S6C_MANIFEST%" 8fb281fe4788e549cfb294bdcfb6adf326144cfeefbb1d09c76cf22f7b26c044 --generation baseline --namespace controls_b00_recovered_fast_v1
"%S6C_EDGE%" -B "%S6C_HELPER%" run --recovery "%S6C_RECOVERY%" "%S6C_RECOVERY_SHA%" --request "REPLACE_REQUEST_PATH" "REPLACE_REQUEST_SHA256" --plan "REPLACE_PLAN_PATH" "REPLACE_PLAN_SHA256"
```

Run B01 with `--generation research --namespace controls_b01_recovered_fast_v1` in its own invocation and its own returned request/plan. No automation or continuous monitoring is installed.

## Validation and limits

Focused checks verify exact held function code, private globals/readers, unchanged original scientific objects, fixed manifest/generation/output guards, and generation separation without actual recovery/index/native reads. The recovery inventory separately establishes actual receipt, owner, lease and failed-exit semantics. Source checks are not evidence that an actual batch has been analyzed. The adapter still refuses a present shared lease and retains all original scientific admission checks.
