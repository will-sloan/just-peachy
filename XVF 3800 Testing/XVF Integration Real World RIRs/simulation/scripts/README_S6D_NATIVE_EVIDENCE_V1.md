# S6D offline native evidence guards V1

`s6d_native_evidence_v1.py` validates full source consumption and actual final drainage. It closes a specific gap in the frozen native pilot helper: an orderly stopped prefix can reach COMPLETED. It performs no model, policy replay, playback, device, UI, or process-control operation. It never changes existing results or source WAVs.

## Inputs, APIs and outputs

`validate_completion(result, job, finalization, journal_proofs, consumer_closure)` returns an error list, empty only when all required evidence passes. Production callers must predeclare positive integer `job.expected_frames`, `audio_duration_sec`, and `audio_pcm_sha256`. `journal_proofs` contains `source: {frames, sha256}`, `asr: {bytes, sha256}`, and `identity: {bytes, sha256}` from actual closed bytes. Both same-source mono journals must match the whole source PCM body. This API intentionally supports current same-tap jobs only; a future cross-tap job needs separate declared PCM hashes and review. It also checks source/ASR/speaker cursors, committed counts, loss counters, successful finalizer, scheduler and S6D worker/consumer closure. The speaker cursor proves consumed source; separately retain the reported analyzed-through cursor and short tail rather than calling every consumed tail sample model-analyzed.

`validate_dispatch(events, expected_frames)` accepts a full native consumer/journal event iterator and returns contiguous zero-to-full dispatch proof or raises. Tail frames are observed source; final .66-second synthetic ASR padding is excluded. Both scheduler watermarks must close.

`pcm_proof(path, expected_binding)` reads the existing exact mono PCM16/16k WAV header/body with no conversion or gain. `binding` hashes actual raw journal bytes. These full reads belong after finalization, never in a 15-second health heartbeat. The caller must separately verify immutable execution sources, manifest/helper/job and approved owner identity/exit, protocol observer closure, protocol observer errors, and supervisor artifact bindings before committing COMPLETE. These functions are necessary evidence guards, not the entire launch or completion admission policy.

`shift_reference_pieces(pieces, expected_frames)` accepts **already output-mapped** evaluator-only turns and shifts integer intervals by each exact composition start sample. It preserves repeat occurrence IDs, incomplete-reference flags and unavailable alignment. Each piece has `case_id,start_sample,samples,gap_before_samples,all_reference_complete,mapped_turns`; turns have `segment_index,file_support,active_ranges,sole` plus identity/text metadata. Use existing saved support mappings before this API, including their RIR convention exactly once. It does not infer word times or map a continuous session through a canonical scene scorer.

`opportunity_census` checks an explicit occurrence-level denominator. OBSERVED needs a finite actual wait, RIGHT_CENSORED needs null wait and a finite closed horizon; unavailable categories remain separate. This validates reporting, not identity correctness. The bounded analyzer plan supplies the required qualified-event attribution and gallery identity policy.

The CLI is an **offline historical inspection**, taking exact manifest SHA and literal job ID. It reads result, finalization, closure, source PCM, both journals and consumer events, writing one fresh JSON receipt. Missing predeclared frame/hash fields on the old pilot are derived for inspection and explicitly marked; production API admission never derives them. It does not claim process exit, text/name correctness, GUI rendering or scanout. A rejected audit still writes its adverse receipt; callers must inspect `status`.

Metadata limit64MiB; event stream1GiB,8MiB/line,1,000,000 rows. Bound violations fail. No audio globs, model assets or directory-wide payload scans. Existing artifacts are immutable and output uses exclusive creation.

## PowerShell

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edge = Join-Path $repo '.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $edge -B "$sim\scripts\s6d_native_evidence_checks_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_evidence_v1\checks_fresh'
& $edge -B "$sim\scripts\s6d_native_evidence_v1.py" --manifest "$sim\reports\S6D\20260913T195357Z\application\native_pilot_v3\MANIFEST.json" --sha256 ec110adcbaf230c5f33b49629967e163f5d526b7a339123c05fb000a14d7138f --job-id C088_S45_01_06_delivery_repair --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_evidence_v1\pilot_audit_fresh.json'
```

## Anaconda Prompt / CMD

Use the explicit existing interpreter; no environment activation or package installation is required.

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_native_evidence_checks_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_evidence_v1\checks_cmd_fresh"
"%REPO%\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_native_evidence_v1.py" --manifest "%SIM%\reports\S6D\20260913T195357Z\application\native_pilot_v3\MANIFEST.json" --sha256 ec110adcbaf230c5f33b49629967e163f5d526b7a339123c05fb000a14d7138f --job-id C088_S45_01_06_delivery_repair --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_evidence_v1\pilot_audit_cmd_fresh.json"
```

The companion checks script writes17 tiny adversarial tests/log/receipt under the required fresh supplied G directory, including stopped-prefix, corrupted journal, NaN, late observer error, undrained queue, missing closure, dispatch gaps/tail/padding, repeated reference occurrences and never-correct censoring. Only a three-frame synthetic WAV is created. Replace fresh output suffixes for a new justified test run; old receipts are preserved.
