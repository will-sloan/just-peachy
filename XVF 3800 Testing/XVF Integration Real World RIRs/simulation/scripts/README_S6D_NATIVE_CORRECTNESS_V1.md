# S6D prospective native text/name correctness scorer V1

`s6d_native_correctness_v1.py` scores closed, separately admitted headless native outputs using exact source-bound projected references. It supports single captured-source confirmations and the whole existing host composition with the same reference schema. It does not start models, policy replay, audio playback, devices or Tk. Existing native artifacts, historical scorers, current width/scorer sources and references are unchanged.

## Metric APIs and actual limitations

`dependencies()` hashes exact original S4 normalization, S5 text backend, S6C name helpers, support interval source and the unchanged root-accepted evidence helper (`bb1b5ff8…`). It compiles only named unchanged pure function ASTs for normalization, name/roster correctness and intervals; it does not import the broad S6C pipeline or call canonical scene admission with a fabricated continuous ID. Word error uses the separately pinned existing `app/scoring/wer.py`. Anonymous speaker-attributed error calls actual MeetEval0.4.3 cp-WER through the unchanged pinned S5 backend/rate functions. These versions are checked, not installed.

`text_metrics(reference, finals, dependencies)` reports whole raw normalized transcript, conditioned serialized error counts and global anonymous cp-WER on complete-reference pieces. References group by corpus-qualified original metadata person, hypotheses by actual latest anonymous label; changing known-name presentation cannot manufacture anonymous cp improvement. Serialization is order-sensitive with overlap and explicitly diagnostic. No MIMO claim is made for the continuous session. A missing anonymous label makes cp unavailable rather than assigning a guessed speaker.

Incomplete/disallowed/unmapped pieces stay explicit. A final hypothesis whose actual source span crosses a piece boundary, a gap or excluded source is excluded **whole** and retained with its text/reason. All eligible reference words remain, so missing hypotheses contribute deletions. No word time or arbitrary text split is invented. Report these excluded counts with every conditioned error rate. Full-session all-speaker WER is unavailable whenever reference coverage is incomplete. The output's full raw sequence remains useful for source-matched invariance comparison and is not a ground-truth score.

`name_metrics` uses real source-start/publication/consumption monotonic clocks. All projected occurrences remain present. It attributes only an arrived span in one complete piece with one source occurrence and positive sole support. A label revision retains its row's previous arrived ASR span. Repaired jobs use actual s6d_display receipt visibility/label/profile; original jobs use actual native transcript events. Correct name is the exact loaded profile's corpus-qualified metadata identity, not a permutation of anonymous tracks. First-text publication and headless consumption remain separate. GUI render/scanout are explicitly unavailable.

Name metrics include first any/correct/confirmed/stable correct consumed name, wrong/unknown/correct retained-row exposure, name transitions and final name correctness. Stable means0.5contiguous consumed-row seconds confirmed correct, with no invented expiry. Row-seconds across retained rows can overlap and are not wall-seconds. Every metric returns observed/censored/unavailable denominators alongside p50/p95/p99 of observed waits. Never emitted/correct eligible cases retain null waits and a measured closed horizon. Roster-unavailable, withheld, anonymous-control, incomplete, unmapped and no-sole-support cases stay distinct. Missing/nonfinite/backwards consumer clocks make timing unavailable; they do not become zero latency. Original jobs lack a separate monotonic closure receipt, so their horizon is the last actually consumed event in the already joined/drained session; S6D jobs use their actual closure clock.

`analyze(...)` is the pure scoring API; its caller owns complete input admission. It returns exact scoped metrics, not a full study PASS or model acceptance.

## Closed-input matrix and fresh outputs

The CLI needs `--spec PATH --sha256 EXACT_SHA`, an explicitly accepted `s6d-native-scoring-inputs.v1` JSON with status `APPROVED_CLOSED_NATIVE_INPUTS`, `owner_exit_verified:true`, `source_graph_verified:true`, exact scorer binding/dependency list, original `gallery_map` binding, fresh `output_root` and1..200unique literal `jobs`. The matrix is an explicit source-bound caller approval, not a cryptographic signature or independent process-exit probe. Root must construct it only after its owner/source-graph checks. This task has not created an approved real matrix.

Each job supplies bindings for `manifest`, actual `result`, reviewed full-source `completion_audit`, evaluator `reference`, `consumer_events`, `latest` transcript and `gallery_row`, plus literal `job_id`. The audit must be PASS with predeclared frames and match that exact result/manifest/events. `admit_full_source` independently requires positive integer `expected_frames`, a predeclared lowercase64hex `audio_pcm_sha256`, matching duration and any declared identity frame count. The audit must bind unchanged accepted evidence-helper bytes, and its source WAV/PCM/frame/byte proof plus both journal byte/hash proofs must match those predeclared values. Historical audit enrichment cannot make a missing PCM declaration eligible for production scoring. The reference's input_audio/frame count must equal the runtime job. The completed original scorer map must contain the named gallery row and actual loaded profiles/count must match. A NONE gallery row is exactly `{gallery_condition:'NONE', manifest:null, profiles:[], available_identities:[], intended_identities:[]}`. Original map SHA is pinned. Gallery-row files are evaluator-only exact projections, never replacements for native gallery inputs.

Optional `comparison_pairs` has `left_job_id,right_job_id` and a descriptive role. Both must use identical audio bindings. The index reports whole normalized equality and all raw utterance differences, retaining missing rows. Each output `NNN_SCORE.json` is exclusively created, and final `INDEX.json` binds scores and input acceptance. A failed namespace is preserved; never overwrite or reuse it. No actual scoring may be run until input acceptance exists.

`execution_manifests` binds the entire predeclared population (1..200 unique jobs). The exact union of scored `jobs` and `unavailable_jobs` must equal it, without duplicates; unavailable rows explicitly state ABSENT_NATIVE, FAILED_NATIVE or UNADMITTED_NATIVE and a reason. They never receive zero metrics. Comparison pairs with an unavailable member remain unavailable. First-text paired p50/p95/p99 require equivalent entire normalized output, exact raw final rows, matching valid final source spans, and then equal first raw text/start/end for each stable utterance ID. The CLI always supplies final source spans; direct pure callers compare spans when supplied and remain responsible for admission. Changed/missing rows retain their raw values, individual observed clocks, differences and opportunity counts, with null comparative delays and no contribution to timing-benefit quantiles. Both-never cases remain represented in reference-level censored opportunity tables.

Source-dependent text/display/completion publication before the actual source-start clock or before its journal position is impossible for an admitted source and makes timing unavailable. All reference occurrences and every metric denominator remain present with unavailable status and null quantiles. Earlier non-source-dependent session metadata is allowed. This gate does not invent word timestamps or reinterpret unknown clocks.

The initial scorer SHA `7f81eeaa…` and its reproduced adverse probes remain immutable in the G review epochs. The narrow repair source is frozen separately after review; original references, evidence helper and native artifacts remain unchanged. See `README_S6D_NATIVE_CORRECTNESS_REPAIR_CHECKS_V1.md` for9 related checks and the unchanged7 independent regression probes. Existing unapproved prospective matrices bind the old source/dependency list and must receive new exact bindings in a separately admitted matrix; they are not silently rewritten.

Bounds:4096final rows,100000relevant events,1GiB per event stream and8MiB/line via the reviewed evidence reader; metadata64MiB. Scorer reads explicit files only. It retains bounded relevant events and name intervals, not the entire full event stream. Large files and journals belong to prior completion admission. No H2 jobs are touched.

## PowerShell

Use the existing analysis interpreter with pinned MeetEval0.4.3 for the tiny fixture suite. This is a scoring-only runtime; it does not load speech models.

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$analysis = Join-Path $sim 'staging\s5_text_metrics\analysis_env\Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $analysis -B "$sim\scripts\s6d_native_correctness_checks_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_correctness_v1\checks_fresh'
# Only after root accepts exact closed inputs and this scorer epoch:
& $analysis -B "$sim\scripts\s6d_native_correctness_v1.py" --spec 'G:\EXACT_ACCEPTED_INPUTS.json' --sha256 'EXACT_ACCEPTED_INPUTS_SHA256'
```

## Anaconda Prompt / CMD

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "ANALYSIS=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"
"%ANALYSIS%" -B "%SIM%\scripts\s6d_native_correctness_checks_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_correctness_v1\checks_cmd_fresh"
rem Only after separate exact closed-input acceptance:
"%ANALYSIS%" -B "%SIM%\scripts\s6d_native_correctness_v1.py" --spec "G:\EXACT_ACCEPTED_INPUTS.json" --sha256 "EXACT_ACCEPTED_INPUTS_SHA256"
```

The companion fixture file exercises actual pinned word/cp routines only on tiny strings, plus adverse missing/cross-boundary/incomplete/reference-identity, wrong→correct, censoring, unavailable gallery, revision-span, hidden-row and clock cases. It writes a fresh G log/receipt. No actual native result is scored by these checks. See `README_S6D_NATIVE_REFERENCE_PLAN_V1.md` for source-bound evaluator preparation and `README_S6D_NATIVE_EVIDENCE_V1.md` for independent full-source/drain acceptance.
