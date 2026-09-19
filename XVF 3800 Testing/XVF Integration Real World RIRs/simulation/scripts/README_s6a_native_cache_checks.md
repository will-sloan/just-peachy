# Native completed-result cache mutation checks

Purpose: exercise the actual s6a_probes.run_job completed-result reuse path without starting inference or changing any active input. The test selects the first complete V2 P0X1 job in the frozen manifest, copies only its run receipt into an isolated fixture directory, and uses the original immutable native outputs read-only.

An exact identity must reuse and pass the real full native audio/completion check. Prospectively changed dependencies must reject the completed receipt before native verification, launch eligibility, subprocess creation, or receipt writes. Supported profile mutations are validated by the real ResearchProfile class. Content/code/asset/provider mutations are prospective identity changes: original files are never modified.

This validates conservative complete-result invalidation. It does not execute changed neural graphs, prove alternative decoder accuracy, or implement a minimal branch-level cache. The separate cue feature-cache tests cover exact accepted-window reuse and downstream-only policy keys.

## Inputs

- Existing frozen PROBE_JOB_MANIFEST_V2.json and at least one complete P0X1 result.
- Existing local model/input/code bindings and completed native evidence, read-only.
- The unchanged actual s6a_probes.py and supporting modules.
- A NEW isolated --output directory. It must not already exist.
- Existing .edge-speech-env. No installation, hardware or model download.

## PowerShell

~~~powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$report = Join-Path $sim 'reports\S6A\20260909T202250Z'
$out = Join-Path $sim 'staging\s6a\20260909T202250Z\native_cache_validation_v1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6a_native_cache_checks.py" --repo "$repo" --report "$report" --output "$out"
~~~

## Anaconda Prompt or Windows Command Prompt

No conda activation is required because this uses the existing isolated interpreter.

~~~bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "REPORT=%SIM%\reports\S6A\20260909T202250Z"
set "OUT=%SIM%\staging\s6a\20260909T202250Z\native_cache_validation_v1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6a_native_cache_checks.py" --repo "%REPO%" --report "%REPORT%" --output "%OUT%"
~~~

For another execution, choose a new versioned output directory; preserve previous outputs. The test is safe to run alongside frozen probe jobs because it only writes its new isolated directory and its dedicated report receipt. It hashes protected source/input/model and completed-output bindings before and after.

## Outputs

NATIVE_CACHE_MUTATION_RECEIPT.json is written both under --output and --report. It records each exact-hit/rejected-mutation result, source and runner hashes, the original receipt before/after, protected bindings, native verification call count, and zero launch/write guard counts. The isolated_completed_copy folder contains an unchanged copied receipt.

Profile mutations include endpoint rules, decoder, blank penalty, host dispatch, segmentation stride/post-policy, embedding duration/cadence/RMS, tracker policy, tap declaration, model threads, display timing and explicitly owned gain. Other identity mutations cover raw/gained audio, physical tap binding, upstream once-only gain, telemetry change/absence, code, assets, provider, lifecycle and output contract. A stale-key/changed-identity fixture also exercises the identity equality guard.

Failures stop the test and leave the isolated fixture for inspection. Never point --output to an active result directory. This script does not stop any process, create any model worker, or overwrite active manifests/inputs.

