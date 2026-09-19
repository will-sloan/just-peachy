# S6A causal reference trackers and physical cue foundation

`s6a_cues.py` reuses completed native H2 baselines, actually recomputes the
baseline's accepted ReDimNet2 windows, and evaluates six reference profiles on
all 240 authorized scenes and both saved XVF taps. The historical 180/60 split
is retained as metadata. This S6 authorization permits use of the former
reserve; no input metadata is rewritten. No hardware, model download,
training, or fresh capture is involved.

The profiles are exact native B0, new voice/time tracking, an anonymous angle
diagnostic, sustained direction-change proposals, decaying position memory,
and reliability-adaptive voice/location/energy fusion. This is exploratory
engineering, not an independent holdout or CM5 qualification. ASR words remain
the exact native final words for these reference profiles. Real component
probes elsewhere in S6A separately rerun recognition where required.

## Inputs and outputs

Inputs: the immutable scene bank, S6A `JOB_MANIFEST.json` with all 480 jobs,
completed native receipts/events/PCM16 journals, exact ReDimNet2 checkpoint,
and each accepted capture's callback metadata and received telemetry. O0
already includes +3 dB once; O1 is unity. Native PCM16 is read at unity.

Outputs: report `cues/features` contains per-output feature metadata and
measured compute costs; local vectors are in
`G:\Just_Peachy_S6A\20260909T202250Z\cue_features`. Prediction events and final
attribution are in `cues/profiles`. Compact indexes, cue CSVs, tracking/attributed
metrics, and tests are suitable for the handoff; vectors and full event traces
stay local. Every completed cache is hash-bound and a changed dependency
requires a new versioned output, not silent reuse.

The model worker has one resident ReDim session and two ORT inner threads.
It calls the actual H2 `SpeakerModels.embed` method on the exact baseline
0.5-second accepted windows. A changed span, normalization, model, provider,
thread cost recipe, runtime, event selection or embedding implementation
invalidates its cache. Tracking changes invalidate downstream predictions,
not exact vectors. No reference schedule is used to select these windows.

## Time and interpretation

The baseline's 10-second segmentation inputs were left-padded at startup and
available only after their final samples and compute. Replay uses a serial
speaker-lane queue: `ready = max(ready, input_end) + measured_compute_seconds`.
Segmentation costs come from exact native events; new embeddings are timed.
These are explicitly modeled availability/costs, not measured live latency.

Cues are taken only from telemetry received by the historical callback
containing the feature's last input sample. Extra modeled compute ages the
observation. Metadata arriving during compute is conservatively omitted.
Accelerated inference wall time is never joined to historical capture QPC.
There is no device frame timestamp, proven DSP freshness, invented historic
AEC/AGC state, or RT60. Manual +/-5 degrees is geometry uncertainty.

Candidate final text uses only the latest tracker decision available by the
native final source cursor. B0 retains its actual native label. No words or
utterance boundaries are changed, no future vector is borrowed, and no final
label is retroactively rewritten. This is a useful common replay protocol but
not a controlled measurement of native cross-thread race timing.

## PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$s6Report = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6A\20260909T202250Z'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest -v test_s6a_cues
& 'C:\Users\amiri\anaconda3\python.exe' s6a_cues.py telemetry --report $s6Report
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s6a_cues.py extract --report $s6Report
& 'C:\Users\amiri\anaconda3\python.exe' s6a_cues.py replay --report $s6Report
& 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6a_cues.py score --report $s6Report
```

## Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set "S6_REPORT=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6A\20260909T202250Z"
"C:\Users\amiri\anaconda3\python.exe" -m unittest -v test_s6a_cues
"C:\Users\amiri\anaconda3\python.exe" s6a_cues.py telemetry --report "%S6_REPORT%"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6a_cues.py extract --report "%S6_REPORT%"
"C:\Users\amiri\anaconda3\python.exe" s6a_cues.py replay --report "%S6_REPORT%"
"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6a_cues.py score --report "%S6_REPORT%"
```

Run extraction only under the S6 root coordinator's worker budget. Repeating
the command resumes compatible complete outputs and processes newly completed
native jobs. Missing native receipts remain `WAITING_NATIVE`, never empty
recognition. `--limit 1` is an explicit smoke-test cap and cannot mark the full
bank complete. Finish all 480 before a full reference claim. Do not modify
this module or the embedding method while a worker is using it.

The fixture suite tests source/compute availability, different future suffixes,
truth-label renaming, stale/missing/reordered telemetry, distinct host chunks,
unique evidence union, prototype protection, bounded memory, linear angle
endpoints, and feature/track cache dependencies. It opens no audio hardware.

## Sanitized delivery for actual app component probes

`s6a_cue_delivery.py` creates one shared sanitized JSONL per physical scene,
usable for both taps through the actual app `--research-telemetry` provider. It
reads accepted callback metadata and received telemetry, projects each
selected-angle host receipt to the first available audio callback sample end,
and includes only already-delivered energy/direction evidence. It omits the
unavailable native DSP/source observation span and all reference fields.
`CUE_DELIVERY_INDEX.json` binds the raw inputs and every resulting JSONL and
reports callback quantization/out-of-capture rows. The actual app provider
parses every output during validation.

After the directory and report variables above are set, run in PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s6a_cue_delivery.py --report $s6Report
```

Or run in Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" s6a_cue_delivery.py --report "%S6_REPORT%"
```

The reference replay and application probe clocks are explicitly modeled
delivery protocols, not live end-to-end latency. The direct reference bridge
ages the selected observation at the feature's containing callback; the app
JSONL conservatively delays each selected receipt to callback availability.
Those small quantization differences are retained in their separate cache
identities. Matched component factorial cells use the same JSONL.

## Score definitions and auditable validation

`s6a_cue_score.py` is a reference-only evaluator. Its reusable
`tracking_metrics(support, stream, decisions, duration_samples)` accepts the
frozen support record and actual decision dictionaries with
`available_at_sec`, `source_end_sec`, and `anonymous_label`. It integrates
decision states over integer sample intervals, excludes simultaneous source
activity from sole-speaker identity support, and expires old states 0.75
seconds after their input end. Unmapped outputs retain all source turns with
unavailable scores. It reports unknown coverage, mixed-identity label support,
fragmentation, short-turn support, return consistency, and actual lineage
operations. These are approximate activity-support diagnostics, not DER or
phonetic timing. Attributed cpWER uses unchanged final words and one global
reference/predicted-label assignment. It is not named-person recognition.

The one-person and all-unknown controls both fail a two-speaker combined
unknown/conflation fixture. Unknown output cannot win by hiding identity
errors. Actual first decisions remain unchanged even when a later bounded
revision is emitted. Revised-correctness is not retroactively credited.

After complete scoring, `s6a_cue_result_audit.py` verifies all 777 intentionally
inserted utterances survive every method/tap's turn table and short-bin
counts, all six references preserve each native final word sequence, and
the degenerate controls expose unknown or mixed-identity support. It also
compares B0 cpWER counts against the independent full-bank baseline scorer.
If that scorer is still running, the audit retains pending outputs and is
repeated when it finishes. It writes `CUE_REFERENCE_COVERAGE_PARITY.json`.
The audit also totals the shared measured ReDim cost, inherited segmentation
cost and additional per-profile policy cost. Actual emitted revision excerpts
are retained in `CUE_OBSERVED_REVISIONS.json`; their identity correctness and
retroactive text improvement are not inferred from the operation count.

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s6a_cue_result_audit.py --report $s6Report
```

```bat
"C:\Users\amiri\anaconda3\python.exe" s6a_cue_result_audit.py --report "%S6_REPORT%"
```

`s6a_cue_validation.py` runs all cue, delivery, and scoring fixture suites,
then replays a deterministic 12-output sample of actual cached feature
streams across all five new methods. It checks altered future audio/metadata,
reference-field renaming, exact voice fallback with missing/stale metadata,
and two host delivery chunk patterns. No model is loaded. It writes
`CUE_TEST_RECEIPT.json`, detailed test receipts, physical cue population
strata, and explicitly posthoc adverse examples. Run after feature extraction;
repeat after the final 480-output cache to bind the completed index.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s6a_cue_validation.py --report $s6Report
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" s6a_cue_validation.py --report "%S6_REPORT%"
```

Direct final scoring uses the analysis interpreter shown in the main command
sequence because it contains the pinned MeetEval 0.4.3 backend. No installation
is needed. The scorer requires all 2,880 six-profile outputs and writes an
additional 960 diagnostic control outputs. Its B0 parity audit checks that
every newly computed exact vector reproduces the archived baseline's speaker
label decisions; this is separate from whether those labels are correct.

`s6a_cue_report.py` composes the compact analysis-first
`CUE_REFERENCE_HANDOFF.md` and a hash-bound `CUE_HANDOFF_INDEX.json`. It reads
the physical, test, feature-parity and final reference receipts. Before full
coverage it clearly emits PARTIAL and withholds final reference conclusions.
When present, the compact handoff also binds the physical integrity and
exact extraction-source archive receipts produced by the provenance audit.
After scoring, repeat it to include the complete comparison and operation
counts. Its index excludes raw audio, vector arrays, and full prediction
traces from the compact handoff.

After complete reference scoring, `s6a_cue_plot.py` creates one standalone
scientific PNG with O0/O1 panels and the underlying compact CSV. It displays
unknown and mixed-identity support using the same complete-reference
sole-speech denominator for all six methods and both diagnostic controls.
The 203-scene count and equal denominators are checked before rendering.
This is not DER or a production-winner score. Its receipt records plotting
version and source/table/image hashes. Then repeat `s6a_cue_report.py` to
include the figure and table in the compact handoff index.

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s6a_cue_plot.py --report $s6Report
```

```bat
"C:\Users\amiri\anaconda3\python.exe" s6a_cue_plot.py --report "%S6_REPORT%"
```

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s6a_cue_report.py --report $s6Report
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" s6a_cue_report.py --report "%S6_REPORT%"
```

`s6a_cue_provenance.py` verifies accepted physical frame/callback continuity,
raw telemetry order/counts, and all bound sanitized inputs. It also preserves
the exact extraction source versions referenced by feature receipts. The
one-window smoke version and subsequent invocation-bookkeeping version have
identical neural feature functions; archived bytes must match the originally
recorded SHA256. Historical source is stored as `.source.txt`, for inspection
only; use the current commands above to resume, not archived code. A rejected
Windows line-ending archive attempt is retained and explicitly distinguished
from the verified exact-byte archives. No acquired source is rewritten.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s6a_cue_provenance.py --report $s6Report
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" s6a_cue_provenance.py --report "%S6_REPORT%"
```
