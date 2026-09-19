# Actual native enrollment integration review

This bounded audit compares separately completed native gallery runs with the exact same candidate/case/tap cached-policy outputs. It verifies the actual native source-index and receipt chain, exact profile/gallery/cue bindings, actual ProfileStore loader counts and template IDs, resolver loader metadata and native lane/writer closure. It retains core/name score differences and first/latest/display export differences. This is integration evidence on duplicated scenes, not another independent accuracy population.

Two fixed groups are supported: `gallery` uses336 native cells (28 enrollment configurations ×6 cases ×2 taps) and `common` uses72 (six common-roster duration configurations ×6 ×2). The six cases are01_06,03_01,04_05,06_07,08_07,12_01. They differ from the earlier anonymous family gate's six cases. Sources are eight explicitly SHA-pinned completed core/name receipts in the script; each native/cached pair must share the exact reference support and gallery policy.

Inputs: completed core/name receipt tables, their exact compressed prediction buffers, native source-index/receipt/finalization JSON and small gallery manifests. Compressed bytes are checked before decompression. Audio, events, embedding vectors and model payloads are not reopened; their provenance remains transitive through the completed native receipt and original shared-parity check. No models, policy replay or scoring is run. Numeric missing values stay missing. Name timeline sample deltas are separate from final export label comparisons and measured clocks.

Output: a fresh `gallery_native_integration_review_v1` or `common_native_integration_review_v1` directory containing per-cell anonymous comparisons, per-occurrence name comparisons, actual gallery admission summaries, per-profile/tap summaries and a source-bound RESULT.json. Existing outputs are never overwritten. Four explicit export clock fields are excluded from semantic equality: first_display_time, first_final_time, latest_label_time and first_known_name_time. All other exported words, source boundaries, anonymous/name fields remain. Gallery loader equality excludes only loaded_elapsed_sec; actual per-job admission remains separately reported.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $py "$sim\scripts\s6c_native_gallery_review.py" --test
& $py "$sim\scripts\s6c_native_gallery_review.py" --group gallery
& $py "$sim\scripts\s6c_native_gallery_review.py" --group common
```

Anaconda Prompt / Windows Command Prompt:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%PY%" "%SIM%\scripts\s6c_native_gallery_review.py" --test
"%PY%" "%SIM%\scripts\s6c_native_gallery_review.py" --group gallery
"%PY%" "%SIM%\scripts\s6c_native_gallery_review.py" --group common
```

Run one group at a time outside paced measurement. Twelve fixtures exercise delta sign, missingness, source/roster/support mismatch, duplicate keys, explicit clock projection, actual native cue-condition/telemetry equality and canonical paired-audio declarations. Finalization must also have no finalization_error, matching the native worker admission. A successful fixture run is not evidence that any empirical group has been audited. A result receipt alone records completion.

The first unexecuted helper/README and seven-fixture receipt are preserved under `independent_review/native_gallery_review_source_v1`. Before the first actual audit, independent review added the explicit native-versus-predictor cue guard, canonical audio declarations and finalization-error guard. The corrected source has its own V2 fixture receipt; no completed source score or native output changed.
