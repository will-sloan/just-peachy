# Exact historical B36 continuous host session

`s6c_long_b36_v1.py` admits one uninterrupted, paced, mono session through the **unchanged `s6b_paced.worker` function** and the sealed S6B epoch2 B36 profile, APP and model assets. It uses one existing tap of the already composed 1,827.426625-second (29,238,826-frame) S6C recording. It never copies, regenerates, trims or changes the gain of that input. This is a distinct continuous-source schema, not a canonical single-case paced cell or a v3 reproduction of B36.

The original B36 configuration remains `original_common`, max256 tracks, no cues, empty gallery, original greedy ASR/100ms delivery, and the original one-thread model settings. The child calls the original worker directly because that driver's CLI rejects timeouts above600 seconds. This changes only the outer invocation boundary. The original worker function, model classes, APP, state settings, 30-second lane drain and65-second final join remain unchanged. Original scheduler caps (20,000 pending events,1,000,000 events,4,096 utterances) remain operative. Saturation or failure is recorded, never repaired by changing them.

## Inputs and outputs

Inputs are the exact sealed S6B artifact index/epoch2/effective B36 profile, exact existing `long_session/v1/COMPOSITION.json`, one declared O0 or O1 source WAV and its existing PCM-body hash, and source-bound wrapper/observer dependencies. `checks` only reads metadata and code; `prepare` and each native admission additionally rehash the selected WAV, exact APP inventory and model assets. The worker uses the isolated new session/empty-gallery directories. No private gallery, reference text, microphone, speaker playback or hardware is read.

`checks --output` creates a fresh JSON source/check receipt. `prepare` creates `REPORT/long_b36/<namespace>/MANIFEST.json` and reserves a separate `G:/Just_Peachy_S6C/20260910T123540Z/long_b36/<namespace>` namespace, without starting a model. Reusing or overwriting a prior attempt is unsupported; recovery needs a separately reviewed fresh namespace.

A later authorized `run` writes the original worker's `WORKER_IDENTITY`, `LIVE`, `WORKER_RESULT`, `DISPLAY_EVENTS`, native session journal/events/summary, an external `PROCESS_SAMPLES.jsonl`, launch/admission/outcome records, and a new continuous `RESULT.json`. Its schema explicitly separates actual **S6B_epoch2** execution from **S6C_epoch2** source composition. `RESULT` certifies native completion and observed child closure; invocation `NATIVE_OUTCOME` precedes quiet-lease release and `CLOSURE` reports the actual release result. The still-exiting coordinator PID/creation requires later inventory observation.

The original full PCM/body hash, ASR cursor and no-gap/no-duplicate dispatch proof are mandatory. Final artifacts are rehashed. All original text/revision events remain available without policy replay. Failed/partial results and unknown owner state are retained. One launch is one physical attempt; no copied/index reference is counted as a new model session.

The coordinator records successful `Popen` immediately in `CHILD_SPAWN.json`, before querying PID creation time. If that identity query fails, it reaps the owned Popen handle when possible but retains the quiet lease because identity/descendant closure is unverified. Such a spawn is an explicit unverified physical attempt. Final trajectory counts name periodic rows, the one terminal process-closure row, and their total separately. The terminal row contains no invented final LIVE observation.

## Resource and timing scope

One child is allowed, with OMP/OpenBLAS/MKL/NumExpr set to1 before it starts. The shared `REPORT/PACED_QUIET_OWNER.json` lease coordinates historical controls, canonical paced, sentinel and long runs. A separate root-authored quiet admission must name the exact manifest and declare all other model/HIL and heavy analysis work stopped. It must cover the full timeout plus cleanup reserve. The adapter also checks recorded study workers; it is not a census of all unrelated applications.

Available-space floors are C50GiB/G75GiB, available RAM12GiB, total new S6C output cap120GiB. Admission reserves4GiB of output space. Exact current directory-entry accounting covers S6C report/staging/payload; checks run at admission, approximately every20 seconds and closure. Directory scans and OS reads are not atomic snapshots, cannot preempt blocking I/O, and add real observation overhead.

The child and coordinator execution bound is source duration+120 seconds (1,947.426625s); an interrupted/failed attempt has one shared25-second cleanup deadline across unregistered Popen-handle cleanup, registered-owner termination/kill and final reap. No new wait starts after that budget is exhausted; blocking OS calls cannot be preempted. Total cleanup elapsed and errors are separately logged. Original model-startup, speaker/ASR queues and finalization behavior are not stretched to pass. Parent sampling continues through synchronous child model load and native final join. Samples are observations at stored times, not guaranteed continuous peaks. RSS is a shared-page upper bound; USS is private resident memory; Windows private commit is distinct; missing/PSS/unreadable values stay null. Missing LIVE is never zero backlog, interpolated or a reused prior value. The pinned optional-LIVE observer may retain exact malformed status bytes and return an explicit missing observation; authoritative JSON remains strict.

The original worker retains event/display collections in memory and scans its session directory. These are part of the measured historical process, not a claimed minimal model-weight footprint. Native emission, modeled scheduler availability, observation time, source cursor, startup and final join remain separate clocks. There is no physical XVF continuity, GUI latency, or CM5 real-time-factor claim. Historical model declarations carry exact byte lengths under their nested `binding`; the wrapper checks that binding against the asset's path/SHA before rehashing.

## PowerShell

Run from the repository. The exact EDGE interpreter is mandatory. Replace only the fresh namespace/deadline/output placeholders. Do not start `run` until root has reserved the quiet interval.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$report = "$sim\reports\S6C\20260910T123540Z"
$env:PYTHONDONTWRITEBYTECODE = '1'
& $py -B "$sim\scripts\s6c_long_b36_v1.py" checks --output "$report\long_b36\SOURCE_CHECKS_V1.json"
& $py -B "$sim\scripts\s6c_long_b36_v1.py" prepare --namespace b36_o0_continuous_v1 --tap O0 --deadline-utc '2026-09-13T11:35:40+00:00'
& $py -B "$sim\scripts\s6c_long_b36_v1.py" run --manifest "$report\long_b36\b36_o0_continuous_v1\MANIFEST.json" --quiet-admission "$report\long_b36\b36_o0_continuous_v1\QUIET_ADMISSION.json"
```

`worker` is internal and requires the live parent-owned quiet lease. It cannot be used to bypass admission. The run command prints PID/creation and20-second progress; `HEARTBEAT.json` is an observer status, not an authoritative completion.

## Anaconda Prompt / CMD

No activation or package installation is needed. Use this exact Python executable, not base Anaconda.

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "REPORT=%SIM%\reports\S6C\20260910T123540Z"
set "PYTHONDONTWRITEBYTECODE=1"
"%PY%" -B "%SIM%\scripts\s6c_long_b36_v1.py" checks --output "%REPORT%\long_b36\SOURCE_CHECKS_V1.json"
"%PY%" -B "%SIM%\scripts\s6c_long_b36_v1.py" prepare --namespace b36_o0_continuous_v1 --tap O0 --deadline-utc "2026-09-13T11:35:40+00:00"
"%PY%" -B "%SIM%\scripts\s6c_long_b36_v1.py" run --manifest "%REPORT%\long_b36\b36_o0_continuous_v1\MANIFEST.json" --quiet-admission "%REPORT%\long_b36\b36_o0_continuous_v1\QUIET_ADMISSION.json"
```

Root creates the separate quiet JSON only when the interval is actually available. Required fields are `status="AUTHORIZED_FOR_QUIET_LONG_B36"`, `manifest={path,bytes,sha256}`, `all_other_model_hil_work_stopped=true`, `all_heavy_analysis_stopped=true`, and timezone-qualified `expires_utc`. This README does not grant that admission or claim any native run completed.
