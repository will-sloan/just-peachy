# S6D capture owner V5 and bridge V2

These additive files change restoration evidence only:

- `s6d_restoration_policy_v1.py`: pure `restoration_decision(initial, after, reapply)` and receipt verification; no I/O.
- `s6d_capture_owner_v5.py`: V4 capture implementation with the guarded policy and explicitly authorized recovery bindings.
- `s6d_capture_supervisor_bridge_v2.py`: same-process bridge that recomputes the policy before publishing RESTORED or capture COMPLETE.
- `s6d_capture_checks_v5.py`: file-only regression fixtures on a fresh G directory. It imports the owner but never calls its execution path or loads device libraries.

V4, bridge V1, their receipts, all prepared audio, the existing DSP recipe, GAIN setter, full STATIC getter list, telemetry, callback/queue limits, exact source PCM acceptance, STOP protocol and 480 attempts / 21,600 charged seconds / 40 GiB payload caps remain unchanged. Runtime reserves remain C >= 50 GiB and G >= 75 GiB after the proposed payload. The original failed bank pre-QA remains capture PASS / V4 restoration FAIL; a new policy evaluation is separate evidence and cannot rewrite that outcome.

## Why current gain is separate

The local v3.2.1 authority is `../tools/xvf321/source/sources/app_xvf3800/autogeneration/yaml_files/control_commands/shf_pp_cmds.yaml` relative to the simulation directory. `PP_AGCGAIN` is the **current** AGC gain factor, a read/write float in [1, 1000]. `PP_AGCONOFF` enables AGC; `PP_AGCMAXGAIN` is a separate static maximum setting. `s4_restore.restore_exposed` still must obtain an exact immediate getter match for the entire requested settings map, including gain. Its bounded adjacent-float setter recovery is unchanged and is not a later-readback tolerance.

`exact_static_plus_verified_dynamic_agc.v1` requires exact initial/final settings keys and all settings other than current gain, exact identity, exact ancillary getters and exact USB width; an exact bound immediate reapply receipt for **all** settings; and finite single numeric gain values in [1,1000], excluding booleans and strings. A later gain change is allowed only when initial, immediate and final AGC are enabled and both recorded firmware versions are 3.2.1. There is no numerical drift tolerance: the explicit range is the documented gain domain. Every actual delta remains recorded. This rule does not restore hidden adaptive history or assert that two current gain observations are equal.

The decision exposes `accepted`, `exact_static_configuration_match`, `requested_gain_set_verified`, `exact_full_snapshot_match`, `autonomous_gain_drift_observed`, the three actual gain values/delta, and errors. A normal V5 `restoration.json` has `schema_version=edge-s6d-restoration.v5`, the exact policy string and complete raw readback/reapply. Its legacy `exact_recorded_configuration_match` remains the **full snapshot** result and can be false alongside V5 policy PASS. Bridge V2 never interprets that combination as old exact-all-fields PASS.

Normal capture queue predicates must require:

```
semantic_checks.restoration.checks.restoration_policy_valid = true
semantic_checks.restoration.checks.exact_static_configuration_match = true
semantic_checks.restoration.checks.requested_gain_set_verified = true
semantic_checks.restoration.checks.packed_input_disabled = true
```

Unchanged same-owner, ledger/hash, telemetry/audio/lease closure, actual attempt completion, observer and STOP checks also remain required. A no-setter/no-playback abort has `policy=no_setters_or_playback.v1`; it can close ownership with an empty batch, but carries no gain-set claim and cannot satisfy the normal capture predicates or COMPLETE.

## Inputs and outputs

The owner accepts the same exact capture plan, root authorization, batch ID and literal attempt IDs documented in `README_S6D_CAPTURE.md` and `README_S6D_PHYSICAL_PREPARATION.md`. The root authorization now also binds this README, the new policy source, the V5 owner and the V2 bridge. Each source hash is verified before execution and after the batch. Run the maintained scripts location whose paths the authorization binds; frozen copies are review evidence, not an alternate hardware execution root.

An authorization may contain `reviewed_recoveries: [{path, bytes, sha256}, ...]`. Without an explicitly listed matching receipt, every old failed owner still blocks. Exactly one matching `edge-s6d-restoration-recovery.v1` receipt is required for an old failure. It binds the original ledger owner/restoration, original initial-state file and unchanged immediate reapply, a fresh getter-only readback, the exact recomputed `policy_evaluation`, and true lease/audio/telemetry/packed/no-playback/no-setter closure fields. Original owner closure must already be proven. Root's `s6d_readonly_state_recovery_v1.py` produces this schema only after separately accepted source and actual getter-only recovery. Its README describes that root-owned operation. No recovery or approval is fabricated by these files.

Owner outputs retain all native WAVs, decoded streams, source/recipe bindings, telemetry, `case_result.json`, batch admission/source epoch/SUMMARY/restoration and physical ledger records. Bridge outputs retain distinct heartbeat, RESTORED, COMPLETE or failure receipts. Fixtures output small synthetic report trees, `RECEIPT.json` and a clearly labeled saved-V4-failure policy observation. They never write the historical input receipts.

## Run the model-free checks

Use an environment containing numpy and psutil (the existing Anaconda environment is sufficient). Choose a **fresh** G output suffix; the tool refuses an existing destination. No hardware, audio streams, setters, resets, native inference or GUI is invoked.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6D\20260913T195357Z"
$out = 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\dynamic_gain_restoration_v5\checks_v1'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_capture_checks_v5.py" --source-root "$sim\scripts" --baseline-batch "$r\hardware_batches\bank_v1_P_MAIN6_B1_pre_QA" --output $out
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
set "OUT=G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\dynamic_gain_restoration_v5\checks_v1"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_capture_checks_v5.py" --source-root "%SIM%\scripts" --baseline-batch "%R%\hardware_batches\bank_v1_P_MAIN6_B1_pre_QA" --output "%OUT%"
```

Read-only plan validation, after root supplies an exact plan and authorization, uses `python -B s6d_capture_owner_v5.py check-plan --plan PLAN.json --authorization AUTHORIZATION.json`. It reads and hashes only. It does not establish hardware qualification.

Production remains root-owned. The reviewed runner's literal job uses the same bridge argument shape with `s6d_capture_supervisor_bridge_v2.py --owner <maintained s6d_capture_owner_v5.py> --owner-sha256 <reviewed hash> --plan <root plan> --plan-sha256 <hash> --authorization <root authorization> --authorization-sha256 <hash> --batch <fresh ID> --attempt-ids <exact IDs>`. The runner supplies identity/heartbeat/STOP/closure environment variables; do not invoke it outside that admitted queue. Source review, verified recovery, fresh QA under a new ID and root queue adoption are separate prerequisites, not outputs of the model-free checks.
