# Recovery V4: exact original or recorded failed configuration

`s6d_closed_telemetry_restore_v4.py` fixes the next actual pre-setter failure while preserving V1/V2/V3 sources and failures. The actual V3 getter snapshot had exactly the failed capture's MIC_GAIN1, REF_GAIN1, SYS_DELAY0, packed1 and USB24/24. The original state had 10,1.5,-32,packed0 and USB16/16. Treating gains/delay as immutable blocked the intended restore before setters.

V4 accepts either the complete exact original identity or the complete exact failed configured identity. It projects only MIC_GAIN, REF_GAIN, SYS_DELAY, packed input and USB width from the bound failed17 configuration; firmware, geometry, microphone count, build and DAC remain exactly original. Mixed states, unknown values and tolerances are not accepted. The existing ten read-only getters plus raw build query and strict post-restore identity/policy remain. The process/TCP/native/lease/reset/setter lifecycle is unchanged.

The root source review now requires `original_bindings.failed_configuration` binding the actual `G:\Just_Peachy_S6D\20260913T195357Z\bank_captures_v1\beam_bank\S45_01_17\P_MAIN6\P_MAIN6_S45_01_17\configuration.json`. The helper verifies its unique original admitted attempt, case/profile/source, failed charged ledger row and exact immediate configured readback. The existing original admission binds its plan; future verification uses the immutable original ledger snapshot. The pure recovery verifier recomputes the configuration and exact pre-restore decision from bound files.

Inputs retain all prior authority, native telemetry, confirmation and original failure bindings. Execution status is `ROOT_ACCEPTED_TELEMETRY_RECOVERY_V2_SOURCES_V4`; intended new output is `R/closed_telemetry_restore_v4`. Same `verify_recovery_record(receipt, owner_binding=..., restoration_binding=..., initial_binding=...)`, `edge-s6d-restoration-recovery.v2` schema and `closed_native_telemetry_fresh_restore` kind. Owner V9 changes only V8's recovery helper/README dependencies. The hardware40GiB cap and all floors/caps remain.

Outputs retain process/TCP snapshots, commands, immutable original ledger, RESTORE_STARTED, RESULT and (only after verified restoration/released lease) RECOVERY. RESULT additionally records `failed_configuration_proof` and `pre_restore_identity_comparison`: exact reason, projected identity, actual deltas and `tolerance_used=false`. Old failures remain failed; this does not clear guards or admit any queue.

`s6d_closed_telemetry_restore_checks_v4.py` reads the actual initial state, V3 saved before_identity and failed configuration. It executes full `recover_prevalidated` with fake services and the actual retained restore method, reproduces V3's refusal, checks original/configured positives, unknown/mixed/immutable negatives, strict post-policy failure, source/profile joins and persisted pure verifier joins. It uses no live process census, locks, control queries, setters, audio or models. All fixture outputs are on G and marked fixture-only. No fake root approval is written.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_closed_telemetry_restore_checks_v4.py" --source-root "$sim\scripts" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v4\checks_v1'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_closed_telemetry_restore_checks_v4.py" --source-root "%SIM%\scripts" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\closed_telemetry_restore_v4\checks_v1"
```

Use a fresh fixture suffix. With root's exact reviewed JSON and SHA, file-only input inspection is `python -B s6d_closed_telemetry_restore_v4.py inspect-inputs --source-review REVIEW.json --source-review-sha256 SHA256`. Root alone may run the same command with `execute` after source and actual restore admission. The helper writes no root approval and performs no automatic retry. See the preserved V2 README for retained lifecycle details, using V4's names/status and fresh output.
