# Closed paced study accounting

`s6b_paced_closure.py` runs only after the final observer and native workers have exited. It consumes the final complete 64-cell SUMMARY/MANIFEST, three ordered preserved paced namespaces and the two repaired observer directories. It independently verifies logical job identities, all final artifact hashes, physical launch/result accounting and PID-plus-creation closure. Its outputs are a fresh `PACED_CLOSURE.json` and compact `.md`, with resource ranges, native repetition results, observer counters, sampling gaps and a current RAM/C:/G: free-space snapshot.

The expected completed scope is 64 successful physical sessions plus the two preserved interrupted sessions, across three namespaces. Copied receipt references count as reuse, never fresh native work. This helper does not alter native artifacts or the immutable pre-paced 3,936-job accounting. It hashes only the explicit paced artifacts. A final incomplete summary, changed binding, live owned process, differing job plan or unexpected attempt accounting fails closed. It does not stop processes or run inference.

The complete unique job-ID grid and each row's profile/case/tap/repetition identity must match the final manifest, as must all 32 distinct repetition-{1,2} pairs. Every final worker must report its exact job key, full duration/sample count and expected admitted PCM body hash/length. The copied trajectory must match the original trajectory binding inside its unchanged COMPLETE receipt. Namespace splits are asserted as fresh-complete 2/22/40, interrupted 1/1/0, and copied references 0/2/24.

`--check-root` runs only isolated synthetic grid, worker metadata, copied trajectory and accounting rejection fixtures. It writes a fresh CHECK_RECEIPT.json and tiny fixture trajectory, starts zero models, and reads no active measurement artifacts. Run it before freezing the helper; use a fresh suffix to preserve earlier checks.

The final original-driver summary remains the detailed per-cell authority. This helper projects its resource rows into min/median/max ranges by profile and tap, retains per-cell memory trends and counts repetition parity without selecting a favorable repetition. `.5 s` observation intervals are measured as actual consecutive trajectory gaps; none are interpolated. Three observer versions and two interruptions limit claims of identical resource conditions. USS is private resident, RSS is a sum upper bound, private commit is committed virtual memory, and unavailable PSS remains null. Model thread settings are distinct from total OS threads. No CM5 fit, throughput or thermal claim is made.

Each cell starts a fresh process and uses one bundle for that complete scene, so it cannot establish continuous multi-scene memory growth. B00 has journal/cursor/full-tail validation but no candidate per-dispatch trace. Native emission, modeled source availability and GUI/phonetic latency are distinct. Interrupted attempt costs are not replaced with successful costs. All source audio, settings and successful repetitions remain those admitted before the study.

## PowerShell

Run only after the `live_reader_overlay_v2_run1` coordinator has exited, and use a new output suffix for any later independent report. This is a report-only command using the existing project Python.

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$paced = "$sim\reports\S6B\20260909T230840Z\paced"
$payload = 'G:\Just_Peachy_S6B\20260909T230840Z'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_closure.py" --check-root "$sim\staging\s6b\20260909T230840Z\paced_closure_checks_NEW"
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_closure.py" --final "$payload\paced_finalists_epoch2_v3" --namespaces "$payload\paced_finalists_epoch2_v1" "$payload\paced_finalists_epoch2_v2" "$payload\paced_finalists_epoch2_v3" --observer-roots "$paced\read_retry_overlay_v1_run1" "$paced\live_reader_overlay_v2_run1" --output "$paced\final_closure_v1"
```

## Anaconda Prompt / Windows CMD

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PACED=%SIM%\reports\S6B\20260909T230840Z\paced"
set "PAYLOAD=G:\Just_Peachy_S6B\20260909T230840Z"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_closure.py" --check-root "%SIM%\staging\s6b\20260909T230840Z\paced_closure_checks_NEW"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_closure.py" --final "%PAYLOAD%\paced_finalists_epoch2_v3" --namespaces "%PAYLOAD%\paced_finalists_epoch2_v1" "%PAYLOAD%\paced_finalists_epoch2_v2" "%PAYLOAD%\paced_finalists_epoch2_v3" --observer-roots "%PACED%\read_retry_overlay_v1_run1" "%PACED%\live_reader_overlay_v2_run1" --output "%PACED%\final_closure_v1"
```

The JSON includes exact script/README/summary/manifest bindings and detailed artifact receipts. The Markdown is an analysis appendix, not a replacement for the original native summaries or the independent repair admission. Preserve it with the final handoff's process, fault and storage review.
