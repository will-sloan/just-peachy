# S4.5 final resource, conservation and restoration audit

`s45_final_audit.py` is an offline closeout utility for the coordinator to run **only after the S4.5 supervisor and all its children have ended**. It reads existing evidence and Windows/Git metadata, then creates `reports\S4_5\20260909T031300Z\FINAL_RESOURCE_AND_RESTORATION.json`. It never opens audio/USB endpoints, executes models, changes power requests, controls processes, regenerates RIRs, or reads reserve task scores. Its only write is its own new audit receipt; existing receipts, source code, media and historical results are preserved.

Inputs use the existing `s45_common.py` run paths: active `scene_bank\s45_v2_20260909T031300Z`, report folder above, and `G:\Just_Peachy_S4_5\20260909T031300Z`. `PRESERVATION_CHECKPOINT.json` supplies the exact 121 RIR WAV paths and hashes. Its manifest, original Revision 9 workbook and historical S4 handoff ZIP hashes must also equal the established fixed authorities. No original dataset tree or whole drive is searched.

The audit checks:

- Current bytes of the RIR manifest, all 121 indexed RIR WAVs, original `XVF_Measurement_V9.docx` and prior S4 ZIP; checkpoint WAV identities must match the canonical manifest.
- Active v2 bank/source/noise/legacy and frozen renderer/owner code bindings; accepted case receipts versus inputs and physical ledger; frozen output-policy recipe versus the selected case and its batch contract, matching manifest/code keys, and explicit `reserve_task_scored:false`. Preserved failed attempts and all acquired/charged batch restorations remain bound. Exact settings, identity, observe-only values and original USB width are checked from receipts. No new device readback is claimed.
- Actual canonical/reference/diagnostic passes and charged playback seconds, including failures; recorded model statuses, child-PID evidence, missing timing and model process wall time. Native completed H2 jobs require recorded native/unique-completion flags, complete-input sample counts equal to adapter counts, one hash-bound PCM16 journal with exactly two bytes per sample, one completion event with no failure/stop events, and three explicitly present zero-drop counters. Journal bytes are hashed without audio decoding; the frozen runner's recorded adapter-to-PCM16 value comparison is not rerun. A missing model time is counted as missing, not a zero-cost invocation. Intended and actual counts remain distinct; optional references stay outside 240.
- Live S4.5 supervisor/campaign/hardware/model/native-telemetry processes; cleared owner markers, completed supervisor receipt, no unresolved supervisor child or STARTED physical/model receipt. An inaccessible process identity blocks PASS unless the strict reused-service-PID proof below succeeds. Historical PIDs reused by an identified unrelated process are reported without calling them current S4.5 owners.
- Current C:/G: free bytes and the authoritative Win32 logical-volume → partition → physical-drive associations. Each mapped drive needs exactly one `Get-PhysicalDisk` row with the same nonempty, trimmed serial number and model/FriendlyName, reporting `Healthy` and `OK`. G: must still map to Kingston SNVS2000G Win32 PhysicalDrive3/index 3. `Get-Disk` is an optional same-index supplement: when present its exact identity must agree and its health/status must be `Healthy`/`Online`; its absence alone does not fail health. Free-space floors remain unchanged. This is a storage-provider observation, not a comprehensive SMART/disk test.
- Logical bytes in known new-run payload/report/v1+v2 bank/staging/code/handoff paths. This expanded count and the original common-helper PAYLOAD/REPORT/activeBANK scope are both reported. No whole-drive delta or allocated-block precision is implied. Reparse points are rejected, not traversed. The new audit receipt itself is outside its pre-write count.
- Current Git HEAD, branch and short status; SHA256 of each authorized runtime.py/cli.py HEAD-to-worktree diff; current two-file source identities versus the active v3 lifecycle-fix receipt and other bound baseline sources. Git uses read-only commands with optional index locks disabled. No model weights are rehashed.

Keep-awake fields are copied as actually recorded. The frozen cleanup code records `active:false`, restoration intent and prior flags, but does not retain the cleanup `SetThreadExecutionState` return value. The audit therefore explicitly sets `independent_OS_keep_awake_state_verified:false`; closed processes and the software receipt are separate evidence.

## Environment and commands

Use the existing Anaconda Python; only the standard library and existing path constants are imported. Windows PowerShell with CIM/Storage cmdlets and Git must already be available. No installation is needed. The audit does not import the hardware, campaign, model runner or scoring modules.

PowerShell, **after supervisor closure**:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:\Users\amiri\anaconda3\python.exe' s45_final_audit.py --check-only
# Once the check is PASS and the final receipt does not already exist:
& 'C:\Users\amiri\anaconda3\python.exe' s45_final_audit.py
```

Anaconda Prompt / Command Prompt, **after supervisor closure**:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\anaconda3\python.exe" s45_final_audit.py --check-only
REM Once PASS and before the final receipt exists:
"C:\Users\amiri\anaconda3\python.exe" s45_final_audit.py
```

`--check-only` prints the full current result and writes nothing. Normal execution exclusively creates the final receipt and refuses to replace an existing one, even if the earlier result failed. Preserve any prior audit before arranging a separately authorized new final observation. Exit 0 means this audit is PASS; exit 2 means blocked/failed or invalid invocation. A closed but incomplete campaign can pass conservation/resources/restoration while retaining explicit pending counts: audit PASS never certifies task accuracy or all planned work. Existing final analysis and completion receipts establish that separate conclusion.

The live-process check runs before expensive conservation checks and again at the end. Consumed evidence is rechecked before PASS. The result is a bounded observation, not a lock preventing another process from starting afterward. No new hardware/model stage should be launched during finalization.

## Temporary, model-free fixtures

`test_s45_final_audit.py` tests the closure gate, related native/model process detection, unavailable process evidence, unresolved markers, missing keep-awake receipts, exact restoration, bound failure recovery, immutable evidence and physical budget accounting. A fixture invokes the actual audit's early gate with temporary paths and mocked process evidence; it proves that missing supervisor closure never proceeds to RIR, disk or Git checks. It creates no actual final report and runs no external commands, audio or models.

PowerShell from the scripts directory:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_final_audit -v
```

Anaconda Prompt / Command Prompt from the same directory:

```bat
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_final_audit -v
```

These fixtures do not establish the final host/resource/restoration result. Only the coordinator's later actual audit can create that receipt.

The initial 15 temporary fixtures passed on 2026-09-09 in 0.115 seconds, observed through the command tool. No separate stdout artifact was retained and the actual final audit was not executed during utility preparation. This observation is limited to the tested closure/restoration/budget functions; later actual provenance/resource checks remain required.

Independent review then identified missing recipe/batch-contract and native-completion metadata joins in this reporting audit; it did not identify an observed hardware/model defect. The prior utility, tests and this README are preserved byte-for-byte under `staging\s45_final_audit_review\v1\original`, with `PRESERVATION.json`. The review additions affect only this unexecuted final audit. New fixtures cover hash-valid wrong-recipe/contract evidence, missing reserve prohibitions, missing native completion flags, truncated or multiple PCM16 journals, duplicate/failure/stop events and missing/nonzero drop counters. The dated `FIXTURE_RECEIPT.json`, retained test stdout and `review_additions.patch` in that folder bind the updated code and observed test outcome. Execution/scoring code and existing campaign evidence remain unchanged.

The updated **23 tests passed** at 2026-09-09 08:24:52–08:24:53 UTC (unittest duration 0.504 seconds; enclosing child wall time 0.781 seconds). Exact stdout/stderr are retained in that review folder. The actual final audit remains unexecuted at this test observation.

## Storage-provider join correction

A later coordinator `--check-only` run found that `Get-Disk` did not enumerate the G: Win32 PhysicalDrive3, although the logical/partition/Win32 association and a uniquely matching `Get-PhysicalDisk` serial/model were available. Treating the two providers' numeric identifiers as interchangeable made the reporting audit fail before any final receipt was created. The correction retains the Win32 association as volume identity and joins health by **exact trimmed serial plus model**, without inferring why one provider omits a drive. In particular, absence does not establish a dynamic-disk explanation or a physical disk fault.

Missing/blank identity, no unique exact health match, ambiguous matching physical-disk rows, unhealthy/missing operational status, a conflicting present `Get-Disk` supplement, the wrong G: Win32 index/model, or inadequate C:/G: free bytes still block. An unavailable optional `Get-Disk` query is recorded separately; it cannot substitute for the required `Get-PhysicalDisk` health evidence. `Get-PhysicalDisk` and `Get-Disk` size values remain raw observations and are not forced equal to Win32 capacity representations. Other conservation, restoration, process closure, new-byte budget, Git and native-completion gates are unchanged.

The prior utility, fixtures and README are preserved byte-for-byte in `staging\s45_final_audit_review\v2_storage_provider\original`, with `PRESERVATION.json` and baseline fixture stdout/stderr. The v2 review receipt records the added fixture results, actual read-only provider observation, source bindings and `storage_provider_join.patch`. It is **not** `FINAL_RESOURCE_AND_RESTORATION.json` and does not stand in for the coordinator's full final audit.

To run only the provider observation, with no final audit or receipt write, use the existing scripts directory and environment above.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_final_audit.StorageProviderJoinTests -v
& 'C:\Users\amiri\anaconda3\python.exe' -c "import json; import s45_final_audit as a; print(json.dumps(a.ssd_and_space(), indent=2))"
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_final_audit.StorageProviderJoinTests -v
"C:\Users\amiri\anaconda3\python.exe" -c "import json; import s45_final_audit as a; print(json.dumps(a.ssd_and_space(), indent=2))"
```

Inputs to that subcheck are current read-only CIM/Storage provider metadata and unchanged free-space constants. Its output is JSON on stdout containing both providers' raw identity/health observations, the verified association and identity join, the optional supplement status, current free bytes and explicit scope. It opens no audio/USB endpoint and changes no storage, driver, service or power setting. The full fixture command above also retains regression coverage of the audit's other gates; running the storage-only command does not execute those other audit sections.

## Strict reuse of a protected service PID

A later final-audit attempt found a historical completed model PID now assigned to a protected `svchost.exe` whose command line was unavailable. The utility now attaches read-only `Win32_Service` metadata to live recorded-PID rows with missing command lines. The fallback requires the current name `svchost.exe`, a valid timezone-aware creation time strictly after the exit and completion times of **every bound COMPLETE/exit-0 model receipt for that PID**, and exactly one associated running service with the same PID and the exact `SystemRoot\System32\svchost.exe` executable. A quoted executable followed by service arguments is supported; alternate paths, environment-variable spellings, traversal paths, multiple services, missing timestamps, unknown names and query errors remain blocked. A recognizable S4.5 command always remains a live-owner blocker.

The initial and final live snapshots retain `confirmed_reused_service_pids` with the current process/service identity and historical receipt timestamps. This proof establishes PID reuse from metadata; it neither opens nor controls the process. Other closure, model-completion, storage and conservation checks remain in force. The previously blocked final receipt is preserved by the coordinator before any separately authorized rerun; this development task does not run the full audit or write a final receipt.

Prior code/tests/README, the diff, fixture stdout/stderr and the actual PID/service helper observation are retained under `staging\s45_final_audit_review\v3_pid_reuse`. Run its model-free fixtures from the scripts directory using either shell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s45_final_audit.ServicePidReuseTests -v
```

```bat
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_final_audit.ServicePidReuseTests -v
```

These fixtures supply temporary in-memory process/service/model-receipt metadata and produce unittest output only. The existing full fixture command runs them together with the earlier 31 tests. Actual `process_snapshot(recorded_pids)` is read-only and returns current CIM metadata; the strict helper additionally requires the bound historical model receipts and does not infer missing completion evidence.
