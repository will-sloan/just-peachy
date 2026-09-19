# S6B optional LIVE observer v3

`s6b_paced_optional_live_v3.py` preserves the exact reviewed v2 snapshot reader and adds one policy: a JSONDecodeError from a manifest-whitelisted optional LIVE file becomes an explicitly missing sample (`None`) after successful raw-byte retention and diagnostic logging. The original coordinator already handles None while checking the process tree, resource limits and worker timeout independently. The native child remains the original frozen `s6b_paced.py`; its APP, profiles, models, pacing, source delivery and final validation are unchanged.

The third interrupted observation has preserved evidence: two identical 8,192-byte snapshots contained a 1,244-byte JSON+CRLF prefix followed by 6,948 NUL bytes; metadata changed from 1,244 to 8,192 bytes during the first snapshot. The later closed LIVE file was valid. These facts establish the sampled bytes, not the underlying filesystem cause. No prefix is parsed for operational use and no malformed value is accepted.

## Inputs and strict boundary

Inputs are the exact reviewed manifest and SHA-256, a fresh observer event directory, and original `--mode run` arguments. The pinned v2 source retains the exact-path whitelist, alias checks, two-snapshot consistency, shared one-second/20-individual-attempt limit, 64-KiB size limit, 16-MiB anomaly capacity and bounded PermissionError retries. Only its completed JSONDecodeError retention path can become None. Malformed authoritative WORKER_RESULT/COMPLETE/config/input files remain fatal. Valid-but-semantic caller errors, path/binding errors, size/capacity/deadline failures, missing files and retention failures remain fatal. No prior telemetry value is reused, no prefix is salvaged, and no sample is interpolated.

Final source PCM hashes/length, full duration/cursor and native completion receipts remain required even when LIVE observations are missing. Missingness limits telemetry conclusions: report measured process resources and observed-sample backlog separately; do not claim an unobserved whole-run backlog maximum. The native timeout still bounds each worker. This policy does not promise every optional observation is available.

## Outputs and counters

Outputs are LAUNCH.json, OBSERVER_EVENTS.jsonl, exact rejected_snapshots/*.bin, and COMPLETION.json. Each missing observation emits `optional_live_json_missing`, with the retained reader call number/path/error and `sample_value:null`; that event and preceding retention metadata are flushed/fsynced before returning None. Existing raw snapshot files are independently fsynced. The unchanged coordinator writes the process row with `live:null`.

Stats add `missing_live_json_calls`, `live_calls_by_path` and `missing_live_json_by_path` (absolute path to count). These count calls; final reporting separately counts actually stored trajectory samples and missing LIVE/telemetry values. The inherited `failed_calls` includes retained parser failures represented as missing optional samples and is not a native failure count. All observer versions, interruption gaps, retry waits and sampling gaps remain explicit. Four observer versions are represented by the eventual successful study; native source order stays fixed.

## PowerShell

Use a fresh fixture suffix. Native run requires the separately prepared/reviewed v4 manifest and renewed quiet GO. Replace the SHA placeholder with the exact review-bound value; do not trust changed inputs merely by recalculating a hash.

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$report = "$sim\reports\S6B\20260909T230840Z"
$out = 'G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v4'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_optional_live_v3.py" --check-root "$sim\staging\s6b\20260909T230840Z\paced_optional_live_checks_NEW"
$expectedManifestSha = '<REVIEWED_V4_MANIFEST_SHA256>'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_optional_live_v3.py" --manifest "$out\MANIFEST.json" --manifest-sha256 $expectedManifestSha --events-root "$report\paced\optional_live_overlay_v3_run1" -- --mode run --epoch epoch2 --profiles B00,B36,B10,B17 --repetitions 2 --streams O0,O1 --report $report --output $out
```

## Anaconda Prompt / Windows CMD

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "REPORT=%SIM%\reports\S6B\20260909T230840Z"
set "OUT=G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v4"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_optional_live_v3.py" --check-root "%SIM%\staging\s6b\20260909T230840Z\paced_optional_live_checks_NEW"
set "EXPECTED_MANIFEST_SHA=<REVIEWED_V4_MANIFEST_SHA256>"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_optional_live_v3.py" --manifest "%OUT%\MANIFEST.json" --manifest-sha256 "%EXPECTED_MANIFEST_SHA%" --events-root "%REPORT%\paced\optional_live_overlay_v3_run1" -- --mode run --epoch epoch2 --profiles B00,B36,B10,B17 --repetitions 2 --streams O0,O1 --report "%REPORT%" --output "%OUT%"
```

`--check-root` launches zero models. It tests exact malformed-byte retention before None, later valid recovery, repeated missingness, strict authoritative/unlisted JSON, semantic caller failures, size/deadline/capture failures, and the unchanged native child entry point. The original v2 18-fixture receipt remains applicable to its pinned snapshot implementation. Preserve all earlier code, fixtures and interrupted attempts; never rerun for accuracy.
