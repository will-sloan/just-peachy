# Read-only sparse/late-label comparison reviewer

Purpose: compare the existing complete `pipeline-qualification-04` baseline with exactly one later CurrentDelayed/ReDimNet saved run using `sparse_clean_turn` and `single_d1_late_labels`. This tool never runs a baseline, model, capture, native worker or SSH action. It writes only a fresh private review directory. It does not change a recording, package or acceptance receipt.

Inputs are two independently closed monitor directories containing `MIRROR_COMPLETE.json`, `MIRROR_MANIFEST.json` and every regular file under `closed-output`. Both must contain one successful current worker result, authoritative `HOST_CLOSURE.json`, a kept715127-sample recording and the exact matched input SHA. The baseline is continuous/retained; the candidate changes only the two experimental selection fields plus explicit experimental permission. Policies must match. The retained package identities remain distinct.

The reviewer rehashes all listed mirror members, verifies natural exit/empty cgroup/owner closure/leases, reads SQLite with read-only immutable/query-only settings after refusing a nonempty WAL, and checks the concatenated processed float32 stream. It uses the existing bounded storage event decoder, compact-event reader and final-row archive reader. No transcript, word, speaker name or embedding vector is printed or written to the comparison report. Final ASR comparisons use counts and hashes only. The original private mirror remains the evidence source.

Outputs are a fresh `presets-preparation-research-comparison-UUID/REGISTERED_OWNER.json` and `COMPARISON.json` (maximum128KiB), or a bounded `FAILED.json`. The report includes embedding calls/queried samples/compute time, exact source agreement, final ASR word and utterance-window hash agreement, caption/upsert/revision/provenance counts, sparse schedule receipts, final unsupported-caption interval unions, and recorded worker health/timing. Whole-unit samples are included only if actually present. Missing observations are not zero. Final-caption Unknown coverage is based on coarse ASR windows and is not acoustic speaker time, DER or identity accuracy. Native upstream revisions are separate from what the bounded late-label view showed. Fewer embedding queries and matching words do not establish quality or sustained real-time improvement.

The late-label archive has source intervals, stable span IDs, evidence and revision deadlines but no publication timestamp on each archived row. The reviewer therefore reports provenance/status counts and final interval unions, while explicitly leaving actual Unknown wall duration and deadline-compliance timing unmeasured. A worker writes its own result while alive; `physical_process_closed=false` there is not a failed closure when its matching authoritative host reap and full cgroup closure prove the later exit.

The host process pins CPU14 and records numeric PID/create time before project imports/input reads. Limits are256 regular files/256MiB per mirror,100000 event rows,4096 captions/final utterances,65536 historical span identities,1MiB per input record,384MiB sampled reviewer RSS,120 CPU seconds and180 wall seconds. These are review limits for the short matched runs, not a new hour-review tool. A refused limit never truncates the evidence into a pass.

Run after the future comparison has completed and its entire mirror is verified. Replace only the candidate monitor directory with that actual closed result; do not point both arguments at the baseline.

PowerShell:

```powershell
$code = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$private = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$code/review_research_comparison.py" --baseline "$private/pipeline-qualification-04-monitor-01" --candidate "$private/pipeline-qualification-06-monitor-01"
```

CMD or Anaconda Prompt, using the same existing interpreter:

```bat
set "CODE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003"
set "PRIVATE=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%CODE%/review_research_comparison.py" --baseline "%PRIVATE%/pipeline-qualification-04-monitor-01" --candidate "%PRIVATE%/pipeline-qualification-06-monitor-01"
```

No new environment or package installation is required. The candidate path is a planned label, not evidence that it has run. Reports preserve original execution identities and never promote a release automatically. Compare the [research architecture scope](RESEARCH_ARCHITECTURES.md) and [native results](NATIVE_RESULTS.md) before interpreting timing differences.


The reviewer also requires the complete `n2_diarization_frames` event stream:4470 contiguous rows, eight ordered columns, a stable10ms native frame step, and final EOF at715127 input samples. It reconstructs every probability as little-endian float32 and compares the stream SHA256 plus frame/column provenance. This ignores publication batch timing, emits no probability arrays or speaker names, and does not equate numerical agreement with DER or identity accuracy. The retained baseline has2112+2112+246 rows; no baseline model execution is repeated. Exact processed float32 stream SHA and sample count are still required independently. The reviewer retains at most two143,040-byte float32 buffers for this exact short source, compares all35,760 values, and reports maximum absolute difference and the count above an explicit1e-5 absolute tolerance. These buffers are removed before report serialization. Hash equality, numeric tolerance and frame/column provenance are separate fields; no invented accuracy value is supplied.

The upcoming build13 research selection also includes a reviewed source batching change. The comparison therefore cannot isolate all timing changes to sparse embeddings. Original baseline04 stays at its actual build07 identity, and the new candidate must retain its real manifest and source-difference provenance.
