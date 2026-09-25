# Cached D1 activity and caption integration

`component_d1_replay.py` executes the frozen N2Engine activity, name-map and
caption-span methods using sealed D1 probability frames and model-compatible
embedding vectors. It combines these with actual S7 ASR policy and the common
timestamped-span presentation state. Purpose: implement the D1 application path
without incorrectly sending native speaker slots through D0 clustering.

Inputs: complete verified ASR commands and formatting records; complete D1
component log and summary; exact mono float32 saved waveform (at most 120 sec);
encoder namespace; Balanced anonymous profile; original native session ID.
The D1 component reviewer rescans every frame, query byte/hash, namespace,
source/compute clock, short run and final census before worker creation.
The caller must first verify the source/model/cache/result bindings. No evaluator
reference, known name or ground-truth activity enters the predictor.

The cooperative worker calls the unchanged `N2Engine._accept_activity` and
`_revise_supported_spans`. Its cached `embed` call waits at a bounded barrier
until the query's recorded modeled completion time. The actual N2 RLock stays
held during that wait. Meanwhile raw ASR text can arrive independently; the
actual nonblocking caption-revision method cannot see an unfinished query.
The owner advances the injected clock only while both workers are at barriers.
After each completion, actual N2NameMap, exact query bookkeeping, temporal name
support, short-turn coverage and span-targeted revisions execute before D1's
source watermark advances. Native finish and its queries/revisions complete
before lane closure. Source progress is never replaced by readiness.

No vector is re-inferred or moved to another waveform/model namespace. The
actual query selector must reproduce every sealed query and coverage record
exactly; otherwise replay fails. D1 embeddings never call the D0 S6C tracker.
The first API is explicitly anonymous: E0 and E1 are supported through their
own independently verified vectors. It does not yet supply named, selected,
closed-roster, spatial or adaptation qualification. N2NameMap(None) executes
as it does in the real anonymous application; no known names are invented.

Timing remains modeled independent component FIFOs. Policy/name computation,
policy queue and publication delay are not added; same-time priority is D1,
ASR, formatting. Native probability availability is represented in the injected
zero-origin clock. N2's unchanged name-history/embedding `time.perf_counter`
fields and naming cost remain diagnostic host-execution values, explicitly
outside that modeled clock. Those history stamps do not decide span ownership;
the original raw native stamps also remain in the sealed parent evidence.
Inherited S7 `observed`, `monotonic` and GUI field names do not certify live
measurements. Invalid mixed-clock policy-worker age fields are omitted.

Outputs: full private command/execution census, actual activity/name/revision
events, policy records, caption snapshots/history, query scan and thread cleanup
counts. Raw/final text stays private. Integrated acceptance remains zero;
Controller/widget parity and first-visible latency are not qualified. Complete
named/gallery integration, full-bank scoring, actual Controller parity and paced
GUI/continuity/resource confirmation remain separate requirements.

`test_component_d1_replay.py` uses the real frozen activity loop with small stub
predictors. It verifies exact queries/frames/tail/short runs, text arriving while
the true identity lock is held, exact target revision/span IDs, overlap staying
unassigned, short-turn anonymous activity without an embedding, delayed ASR,
raw/final formatting preservation, reference/namespace/waveform corruption,
forbidden D0 tracker use and real worker-error cleanup. No neural model loads.

`probe_component_d1.py` reuses the accepted eight ASR and four D1 smoke cells to
check all 16 combinations (four ASRs x two encoders x two taps). It verifies
review/admission/result bindings, every source file, paired waveform/profile,
compressed and expanded event hashes/CRC, and exact raw/final census. It forbids
ONNX construction, pins CPU14 below normal, checks the C50/G75-GiB floors with
a 256-MiB reservation, and caps each expanded output at 32 MiB and total private
allocation at 256 MiB. Outputs are round-trip verified JSON gzip files and a
small `RESULT.json`; failures and prior outputs are preserved. Only a redacted
receipt belongs in Git. No new model, recording, desktop window or Pi access.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_d1_replay.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
& $jpPython -B "$jpCode\probe_component_d1.py" --asr-review "$jpLocal\asr-smoke-review-v1\REVIEW.json" --d1-review "$jpLocal\d1-smoke-review-v1\REVIEW.json" --output "$jpLocal\component-d1-probe-v1"
```

Command Prompt / Anaconda Prompt (use the existing application interpreter;
no environment modification):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_d1_replay.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
"%JP_PY%" -B "%JP_CODE%\probe_component_d1.py" --asr-review "%JP_LOCAL%\asr-smoke-review-v1\REVIEW.json" --d1-review "%JP_LOCAL%\d1-smoke-review-v1\REVIEW.json" --output "%JP_LOCAL%\component-d1-probe-v1"
```

Tests use `local/releases/n4-catalog-v3/prototype`; `JP_N4_SOURCE` can select a
verified equivalent. The real probe derives its source only from the verified
admissions. Always choose a fresh output directory when rerunning a probe.
