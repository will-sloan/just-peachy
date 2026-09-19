# Verified public entry point for S6A probe resume

s6a_probe_resume.py is the supported public entry point for starting or resuming the frozen V2 probe runner. It reads PROBE_JOB_MANIFEST_V2.json and independently rehashes every declared file binding before calling the unchanged s6a_probes.run. This includes execution code, each effective profile, raw and gained audio, sanitized telemetry, model assets, and panel/provenance bindings. Each unique path is read in full with SHA256; no mtime/length cache can bypass the check.

The guard also checks complete job-key/identity consistency and duplicated job/identity input bindings. Existing native job identities, model files, profiles and the native runner stay unchanged, so valid completed outputs remain reusable. If no manifest exists, fresh creation delegates to existing s6a_probes.prepare, then its declared dependencies are verified. No automatic repair, file rewrite, new model export or input substitution is performed.

## Inputs and run

Use the existing Anaconda interpreter. Run after the previous coordinator has closed; the unchanged native runner still owns the coordinator lock and process budget. STOP_REQUEST.json still prevents new work and is never removed by the guard.

PowerShell:

~~~powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' .\s6a_probe_resume.py --verify-only
& 'C:\Users\amiri\anaconda3\python.exe' .\s6a_probe_resume.py --workers 2
~~~

Anaconda Prompt or Windows Command Prompt:

~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s6a_probe_resume.py --verify-only
"C:\Users\amiri\anaconda3\python.exe" s6a_probe_resume.py --workers 2
~~~

Use --workers 1 through 4 according to the active run's resource allocation. Optional --limit 2 checks/runs the first two jobs; omit it for the complete frozen manifest. Verify-only reads and hashes dependencies and writes a guard receipt without invoking model inference. The underlying native runner is internal and requires verified immutable dependencies; do not invoke it directly for public resume.

## Outputs and limitations

Each successful guard creates a unique report/resume_guards/<timestamp_id>/LAUNCH.json binding its source, manifest, verified files, PID/creation time, worker count and limit. PROBE_RESUME_GUARD_LATEST.json points to the latest finished guard/run. Existing native receipts and payload destinations remain those of s6a_probes.py.

A missing file, changed byte content, changed declared length, inconsistent identity or mutation observed during hashing fails closed before runner entry. Preserve the mismatch and create an explicitly versioned scientific run if a change is intended; do not rewrite old receipts.

This is invocation-boundary validation. All dependencies must remain immutable while the runner executes. It does not lock every file against arbitrary concurrent modification after verification. Existing native completion and per-job checks still run.

## Isolated tests

test_s6a_probe_resume.py exercises the actual guard/dispatch function with synthetic dependency files in a new isolated directory. It changes execution-code, profile, raw/gained audio, telemetry, asset and panel bytes while preserving byte length, mtime and the supplied manifest identity. A test spy must never be called on mismatch. Exact original/restored inputs invoke only the spy, never a model.

PowerShell:

~~~powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\test_s6a_probe_resume.py" --report "$sim\reports\S6A\20260909T202250Z" --output "$sim\staging\s6a\20260909T202250Z\resume_guard_tests_v1"
~~~

Anaconda Prompt or CMD:

~~~bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\test_s6a_probe_resume.py" --report "%SIM%\reports\S6A\20260909T202250Z" --output "%SIM%\staging\s6a\20260909T202250Z\resume_guard_tests_v1"
~~~

The output directory must be new; choose another versioned name for repeat runs. PROBE_RESUME_GUARD_TESTS.json contains results and exact guard/test hashes. Test sources are restored; active files are never edited. The complementary NATIVE_CACHE_MUTATION_RECEIPT.json proves declared full-identity changes reject in the actual completed-result reuse branch.

