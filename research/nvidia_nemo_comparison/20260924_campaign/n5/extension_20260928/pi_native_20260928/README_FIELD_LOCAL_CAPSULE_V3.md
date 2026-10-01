# Local capsules: selected dependency binding V3

Selected prepared sources: Plan2/contract2, Journal6, Supervisor3, copier2, Gate12, broker entry7/one-session qualifier2 and builder8. All new native paths remain UNEXECUTED. Read [V1](README_FIELD_LOCAL_CAPSULE_V1.md) for purpose/inputs/outputs and resource rationale; [V2](README_FIELD_LOCAL_CAPSULE_V2.md) corrects the historical hash-pinned projection path and preserves both earlier host input failures.

The fresh capsules-v2 attempt failed before output/native dispatch because the actual recursive manager graph had17modules. Copier1 imported old Journal2.sync and Plan1, while the new journal used Plan2. Copier2 changes only these dependencies: exact same sync comes from Journal6 and operation/encoding from Plan2. All copier functions retain their original AST. Journal6 imports copier2 only inside methods, so this dependency does not create an eager import cycle. The original copier1 native result remains separate; copier2 has not executed natively.

Builder8 preserves the original maximum16module/2MiB/128KiB manager limits, now accepts1..16modules instead of assuming exactly16, and selects the new linked versions. Broker limit64 and child51code+4data are unchanged. No guard was raised. Gate12 still requires exact pre-import manager manifest/code/origins and STARTED before ACK.

After setting src/ev/py from V1, PowerShell:
    & $py -B "$src\build_field_operator_broker_bundle_v8.py" --plan "$ev\operator-qualification-v4-preparation\PLAN_V1.json" --projection "$ev\operator-broker-native-v1-publication\CAPSULE_PROJECTION_V2.json" --owners "$ev\operator-local-capsule-v1-preparation\EXTRA_OWNER_CLOSURE_V1.json" --output "$ev\operator-local-capsule-v1-preparation\capsules-v3"

After setting SRC/EV/PY from V1, Command Prompt or Anaconda Prompt:
    "%PY%" -B "%SRC%\build_field_operator_broker_bundle_v8.py" --plan "%EV%\operator-qualification-v4-preparation\PLAN_V1.json" --projection "%EV%\operator-broker-native-v1-publication\CAPSULE_PROJECTION_V2.json" --owners "%EV%\operator-local-capsule-v1-preparation\EXTRA_OWNER_CLOSURE_V1.json" --output "%EV%\operator-local-capsule-v1-preparation\capsules-v3"

Use a fresh output; earlier capsules-v1/v2 remain consumed failure evidence. The unchanged passing allocation check must not be rerun. BUNDLE and MANAGER_BUNDLE remain unadmitted templates without a local_manager binding. Joint admission/dispatch, native manager initialization, complete host mirrors, exact new nested-owner collector bindings, production activation/rollback and failure recovery are still open. Proposed full one-recording/three-launch reservation617760944bytes is unadmitted; old resource policies remain unchanged.
