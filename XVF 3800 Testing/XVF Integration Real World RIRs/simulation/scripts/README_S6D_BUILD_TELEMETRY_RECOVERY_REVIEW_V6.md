# Root authority for the failed B3 pre-QA recovery

Purpose: record root-reviewed V6/ownerV11 sources for the exact bank_v4_P_MAIN6_B3_pre_QA failure. This is a metadata-only derivative of the V5 authority builder. It verifies the supplied exact corrected source freeze and matching independent review, source/copy bindings, all passing focused fixtures (at least28), canonical28 execution dependencies, original121-entry ledger and614-row telemetry proof. It preserves prior V5 root authority5d025f36 and its output-disconnection confirmation. No new user confirmation is needed.

Inputs: final source-freeze path/SHA, independent review path/SHA, and a fresh complete root `capture_telemetry_recovery_v3/ROOT_PROCESS_SNAPSHOT.json`. The snapshot must show no matching task control processes or query errors. The future V6 runtime will repeat its own complete process/TCP checks under its sole hardware lease. A prior snapshot never substitutes for those checks.

Outputs: an explicitly unapproved `PROPOSED_SOURCE_REVIEW_V6.json` is checked by the exact file/native/configuration inspector before accepted canonical files are published. It also checks fixture population length and exact helper/owner source bindings. Only after those checks and input rehash succeed does it publish fresh `runner/capture_owner_v11_source_v1/SOURCE_FREEZE.json`, `capture_telemetry_recovery_v3/ROOT_SOURCE_REVIEW_V6.json` and `ROOT_SOURCE_INPUT_VERIFICATION_V6.json`. Existing outputs cause refusal. Failed staging creates no accepted restoration authority. The helper admits only fresh full-state restoration; it does not launch it, clear prior guards, retry a capture, start a supervisor or change telemetry/census/caps/deadlines. Actual V6 `execute` and any new capture queue require separate root actions and documented receipts. Physical and C12 supervisor allocations remain separate root decisions.

PowerShell / Anaconda PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_build_telemetry_recovery_review_v6.py" --source-freeze '<final corrected SOURCE_FREEZE.json>' --source-freeze-sha256 '<exact SHA256>' --independent-review '<actual independent review.json>' --independent-sha256 '<exact SHA256>'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_build_telemetry_recovery_review_v6.py" --source-freeze "<final corrected SOURCE_FREEZE.json>" --source-freeze-sha256 "<exact SHA256>" --independent-review "<actual independent review.json>" --independent-sha256 "<exact SHA256>"
```

Use the maintained script path so its exact source/README binding matches. Root must review the concrete final hashes first. The actual restoration command belongs in the recovery directory's separate execution README once launched. The original failures, uncertain historical host exits and compile-only negative-control limitation remain unchanged.
