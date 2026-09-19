# Independent width protocol model-free fixtures

`s6d_width_protocol_checks.py` tests the code-only operational-width protocol wrapper. It does not import or execute the reviewed policy replay helper, neural models or device code. It creates a synthetic3840-cell plan and tiny JSON outputs, verifies the wrapper's exact-matrix semantic gates and progress receipts, and tests the real wrapper control flow with a fake in-process helper. Only temporary fixture PLAN_SHA/HELPER_SHA globals and helper import dispatch are replaced inside the fixture Python process; no production source or approved plan is changed.

Inputs: `--wrapper` path (default adjacent `s6d_width_protocol_v1.py`) and a fresh `--output` directory. Dependencies are the existing Python standard library and psutil already used by the wrapper. Outputs: retained synthetic matrix/results, synthetic per-test protocol artifacts, FIXTURE_LOG.txt, and source-bound FIXTURE_RECEIPT.json. Failed assertions are preserved adverse results, not successful production execution. Tests cover arbitrary but count-correct matrices, duplicate/missing/failed/wrong-hash rows, output reuse, identity tap mismatch, incomplete/unknown cell receipts, foreign and same-owner STOP, real interrupt_main handling, helper failure, missing index, success/drain, and changed admission.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& (Join-Path $repo '.edge-speech-env\python.exe') (Join-Path $sim 'scripts\s6d_width_protocol_checks.py') --wrapper (Join-Path $sim 'scripts\s6d_width_protocol_v1.py') --output (Join-Path $sim 'reports\S6D\20260913T195357Z\runner\width_protocol_review_v1\fixed_fixtures_v1')
```

Anaconda Prompt or CMD:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_width_protocol_checks.py" --wrapper "%SIM%\scripts\s6d_width_protocol_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\runner\width_protocol_review_v1\fixed_fixtures_v1"
```

Choose a fresh output name on rerun. To reproduce the preserved adverse implementation, point `--wrapper` at `reports\S6D\20260913T195357Z\runner\width_protocol_review_v1\adverse_source\s6d_width_protocol_v1.py` and choose a fresh output. The tests support both the original two-argument and fixed three-argument validate_index APIs; the fixed observer receives expected_cells. Synthetic files remain local and count toward new-payload accounting. No automatic production launch follows a fixture pass.

The extended14-test suite also supplies schema-invalid but parseable cell JSON and a deterministic close request during an active receipt read. It requires the RUNNING scan to yield between entries so close cannot wait for the remaining3840-file scan. A previous fixed wrapper's natural3840-cell success fixture failed its five-second observer join; that source/log remains under `width_protocol_review_v1/fixed_source_v1` and `fixed_fixtures_v1`. Subsequent fixture outputs must use a new directory such as `fixed_fixtures_v2`.

The resumed18-test suite adds final-scan revalidation after receipt mutation/removal, STOP after observer join and immediately after the final scan, and a partial-STOP error classification probe. STOP requests in the normal foreign/matching owner test now use the wrapper's atomic save, matching the supervisor; the original fixture used non-atomic truncation and could trigger a JSON-read error instead of matching-owner STOP. Its adverse log is retained. Tests now synchronize on actual foreign-request observation and retain observer errors, rather than relying on a short sleep.

For a targeted check, add `--tests` followed by exact test method names; the default runs all21. For example, `--tests test_foreign_stop_ignored_and_exact_owner_stop_signalled test_partial_stop_document_is_error_not_matching_owner_stop` checks the synthetic-writer correction without running any policy. Each invocation still requires a fresh output directory and records the exact wrapper hash and fixture count. Final approval uses the full regression suite on a frozen reviewed copy.

Three atomic-save probes were added after a real WinError5 os.replace failure during final heartbeat publication in the frozen18-test run. The external cause of that access refusal was not identified. The probes require transient PermissionError retry without exposing a partial destination, bounded failure for persistent refusal, and immediate failure for other OS errors. To run only these small fixtures in either shell, append `--tests test_atomic_save_retries_transient_permission_without_partial_target test_atomic_save_persistent_permission_is_bounded_and_preserves_old_target test_atomic_save_does_not_retry_other_os_errors` to the command above and choose a fresh output. When every selected method begins `test_atomic_save_`, no3840-file synthetic matrix is constructed. Original failure artifacts remain preserved.

To avoid reconstructing the synthetic input matrix, add `--reuse-matrix` followed by an existing fixture's `synthetic_matrix` directory in either shell. The helper verifies3840 distinct local files contain the exact tiny synthetic payload, reuses their existing PLAN binding read-only, and records that binding in the new receipt. It does not overwrite or delete reused inputs. Each invocation still requires fresh output directories for its own logs and synthetic cell receipts; a full control-flow regression writes about12,000 tiny cell receipts. Do not run it while a storage hold remains in effect without the coordinator's explicit release.
