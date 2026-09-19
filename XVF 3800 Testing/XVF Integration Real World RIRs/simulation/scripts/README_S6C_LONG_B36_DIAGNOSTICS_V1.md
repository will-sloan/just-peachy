# Original B36 continuous diagnostics

This source-only reporting adapter is for one **completed** original S6B epoch2 B36 continuous session on the existing 1,827.426625-second S6C composition. It does not launch a worker, load models, read PCM, replay a policy, or score scene/person correctness. B36's native source, profile, fixed limits and output remain unchanged.

It uses the pinned inventory V5 metadata API to admit the original manifest, native result, outer result, physical launch, owned process closure, archived quiet lease and current PID/creation states. One physical spawn is one session; the 38 composition pieces are not independent sessions. An active study quiet lease blocks preparation and execution.

The exact five historical observation functions are compiled from their pinned AST, without importing the historical scorer or APP. They retain actual event-wall/source clocks, native display equality and original periodic process semantics. Every native event line is streamed once under the declared hash; vectors and frame arrays are discarded after parsing, while every event's clock/type occupies its original position. Payloads retained in the emission projection are only source/completion, speaker decision and transcript events. Original admission and watermark rows are saved separately. Output is published only after exact stream validation.

## Inputs

- Exact completed long-B36 MANIFEST.json and SHA-256 supplied by the owner. The prepared B36 O0 manifest is not proof of execution.
- Original manifest-bound WORKER_RESULT, CONTINUOUS_OUTCOME/ADMISSION, LAUNCH, outer RESULT and coordinator invocation/closure metadata.
- Exact native events, session summary, DISPLAY_EVENTS and PROCESS_SAMPLES buffers.
- The one invocation's OBSERVER_EVENTS and any explicitly retained malformed LIVE bytes. These are newly hash-bound reporting inputs, not represented as pre-existing outer-artifact bindings.
- Pinned inventory V5, original B36 wrapper and historical observation helper. The README and helper are included in the analysis source binding.

PCM/model authority is transitive through the reviewed native/outer completion. This adapter does not freshly verify PCM/model bytes. Metadata remains separate from observed neural/runtime claims.

## Outputs

- Checks: an immutable source/fixture receipt; no actual manifest or native payload admission.
- Prepare: PLAN.json and exact metadata snapshots in a fresh report namespace. PREPARATION_FAILURE.json preserves a failed admission.
- Run: RESULT.json, ACTUAL_EMISSIONS.json, ORIGINAL_ADMISSIONS_AND_WATERMARKS.json, PROCESS_OBSERVATIONS.json. FAILURE.json preserves a failed reporting attempt. Existing outputs cannot be overwritten.
- No prediction index, transcript-reference metric, continuous WER, named-person score or fabricated correctness.

## Meaning and limits

Original S6B debt is a global since-observation admission flag. It is not the new per-track debt ledger. The helper preserves unavailable S6C context-age, archive/retirement population and known-name correctness as null. Distinct observed anonymous IDs do not equal simultaneous live tracks. Original lineage event counts are observed operations only; no tracker replay or final tracker state is invented.

Full dispatch is verified from integer source spans, including the actual tail count and separate synthetic ASR drain. Padding is not source audio. The complete original scheduler snapshot remains native evidence; its retained utterance/history counts are bounded-state counts, not lifetime output totals. Original 30-second drain, 65-second join and capacity limits are untouched.

Actual UTC emission minus source cursor is source-attributed processing/decision time, not GUI, phonetic or current-speaker latency. Wall reversals remain explicit. Modeled lane availability and actual emission are distinct. No C naming API runs on these historical schemas.

Process summaries use only actual periodic rows. The single terminal row is independently validated as closure, never turned into a synthetic tree/LIVE sample. Memory is sampled: RSS upper bound, USS private resident, private commit and PSS are distinct. Coordinator RSS is separate. Tree-complete is the original sampler flag, which can miss a root-only fallback after descendant-enumeration failure. CPU counters cover observed process lifetimes, not just the sampled interval. Directory/resource scans make sample spacing irregular. Nested cost phases and concurrent lanes must not be added into an artificial whole-worker total.

Observer read calls and missing-JSON calls have separate denominators from trajectory rows; terminal LIVE is intentionally absent. Retained anomalous bytes are checked exactly without prefix parsing, prior-value reuse or interpolation. Zero periodic samples remains unavailable process telemetry.

## Run from PowerShell

Use the existing environment; no dependency installation is needed. Checks are the only authorized operation before the helper is independently reviewed. Do not run prepare/run until the native owner confirms completion and releases the quiet interval.

    $s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
    $s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
    Set-Location -LiteralPath $s6cSim
    & $s6cPython 'scripts\s6c_long_b36_diagnostics_v1.py' checks --output 'reports\S6C\20260910T123540Z\long_b36_diagnostics\SOURCE_CHECKS_V1.json'

After independently reviewed native closure, replace the two placeholders with the owner's exact completed manifest and its SHA:

    & $s6cPython 'scripts\s6c_long_b36_diagnostics_v1.py' prepare --name 'b36_o0_closed_v1' --manifest '<EXACT_COMPLETED_MANIFEST_PATH>' --manifest-sha256 '<MANIFEST_SHA256>'

Use the printed PLAN binding's SHA for execution:

    & $s6cPython 'scripts\s6c_long_b36_diagnostics_v1.py' run --plan 'reports\S6C\20260910T123540Z\long_b36_diagnostics\b36_o0_closed_v1\PLAN.json' --plan-sha256 '<PRINTED_PLAN_SHA256>'

## Run from Anaconda Prompt or Windows Command Prompt

The explicit interpreter path is required; conda activation is unnecessary.

    cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" scripts\s6c_long_b36_diagnostics_v1.py checks --output reports\S6C\20260910T123540Z\long_b36_diagnostics\SOURCE_CHECKS_V1.json
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" scripts\s6c_long_b36_diagnostics_v1.py prepare --name b36_o0_closed_v1 --manifest "<EXACT_COMPLETED_MANIFEST_PATH>" --manifest-sha256 "<MANIFEST_SHA256>"
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" scripts\s6c_long_b36_diagnostics_v1.py run --plan reports\S6C\20260910T123540Z\long_b36_diagnostics\b36_o0_closed_v1\PLAN.json --plan-sha256 "<PRINTED_PLAN_SHA256>"

Choose a fresh output/check path if any prior result exists; never relabel or overwrite an earlier receipt. The JSON cap is 128 MiB, event stream cap 1 GiB and per-line cap 32 MiB. Exceeding a bound is a preserved reporting failure, not silent truncation.

