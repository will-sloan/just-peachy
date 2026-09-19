# Model-free S4.5 closeout tests

`test_s45_closeout.py` checks the actual `verified_analysis_summary` and supervisor `step` function bodies without importing their application modules. It loads only those named functions through Python's AST. All subprocess calls, waits, SSD checks and clocks are in-memory fixtures; every generated file is inside an automatically cleaned temporary directory. No hardware, model, full audio, real child process, active report or packaged evidence is opened or changed.

The inputs are the local `s45_package.py`, `s45_execute_v2.py` and historical `s45_execute.py` source files. Supervisor behavior is tested against v2; v1 was active when these fixtures were originally prepared, and v2 was later used for the actual 09:13:33 and 09:24:53 UTC resumes. One bounded fixture reproduces both known v1 failures and verifies the historical file's exact SHA256. Outputs are the unittest result on the console and an exit code. This checks completion/provenance and lifecycle bookkeeping; it does not certify an actual capture, model result or complete handoff.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' test_s45_closeout.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" test_s45_closeout.py
```

To inspect only the package completion gate, use the same working directory:

```bat
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s45_closeout.PackageGateTests -v
```

Latest observed on 2026-09-09: **31 tests passed**, in 1.536 seconds. The 10 analysis-summary package-gate tests cover a positive current summary, missing/empty/malformed/partial summaries, stale denominators, reserve task access, wrong hashes, missing files, missing critical provenance, a foreign run and valid hashes pointing to foreign artifact paths.

Another 10 tests exercise the indexed-plot and report-review gates: current valid bindings, missing/malformed/stale/tampered artifacts, foreign paths, duplicate/count/reserve guards, exclusion of unindexed PNGs, the exact accepted `PASS_TOOL_INSPECTION` QA value, and both nonempty findings files. These tests use a tiny PNG and CSV inside the temporary fixture. They do not inspect or modify real campaign plots and never run `s45_package.main()` against the active report.

Ten supervisor tests cover unique versioned logs/receipts on repeated stages, nonzero child exit, finite stop at the cutoff, a cleanup timeout that marks the owned child unresolved and blocks follow-up stages while still allowing checkpoint packaging, confirmed exit after an exception, process creation failure, initial invocation/PID status write errors, monitor errors with an already confirmed nonzero exit, and a failed stop-request write that still allows the bounded owned-child wait. The eleventh supervisor fixture reproduces the two historical v1 failures and checks that the main stage ordering is unchanged in v2.

The earlier **16-test run had 14 passes and two failures** in 1.056 seconds. Its exact test/source/readme bytes and observed-result provenance are preserved in `simulation/staging/s45_supervisor_fix/v2/original_v1` and `PRESERVATION.json`. The reproduced v1 failures were:

- After an injected supervisor exception, the fixture child exits during the bounded cleanup wait, but `supervisor_process.json` still retains its PID and its invocation receipt remains `STARTED`.
- If process creation raises before a child exists, the versioned invocation receipt remains `STARTED` instead of recording the failure.

The v1 supervisor was already loaded and running at the time these fixtures were added. Its executed source remains unchanged. V2 fixed those bookkeeping gaps before the actual later resumes. These model-free reproductions remain distinct from the campaign's observed control-query timeouts, failed finite capture and restoration-readback failures. The historical two-failure test run remains recorded as such. The earlier 21-pass v2 result is retained in its fix receipt; the recorded 31-pass result added the 10 reporting-review gate tests without changing either supervisor version. Prior package/test/README bytes and that dated receipt are under `simulation/staging/s45_package_review/v1`. Later history/index-only reporting changes preserve their own before/diff/compile receipts under `v2_execution_history` and `v3_multiple_resumes`; they do not claim these tests were rerun. See `README_S45_EXECUTE.md` for actual stage chronology and current completion evidence.

The run was observed through the subagent command tool; a separate stdout artifact was not retained. The console output must not be represented as a newly executed hardware or model test. If either tested production function changes later, rerun the relevant fixture and preserve its prior source/receipt according to the campaign's versioning rules.
