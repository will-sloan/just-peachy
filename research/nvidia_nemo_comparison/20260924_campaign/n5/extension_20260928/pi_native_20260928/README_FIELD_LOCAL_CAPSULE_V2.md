# Local capsules: current execution index V2

Read [V1](README_FIELD_LOCAL_CAPSULE_V1.md) for selected code, purpose, inputs, outputs, resource/backup allocation and all shell setup steps. New native paths remain unexecuted. Plan2, Journal5, contract2, Supervisor2, Gate11, entry7, one-session qualifier2 and builder7 are selected. The original V1 projection path in the frozen V1 README is wrong: it lacks SHA256 fields. Use the independently closed publication CAPSULE_PROJECTION_V2.json below. Do not retry consumed capsules-v1, which contains only its registered failed host owner.

The first host builder failed on missing sha256 before producing a capsule or contacting the Pi. The selected builder source is unchanged; the fresh invocation changes the input to the actual hash-pinned projection and uses a fresh output. Readonly collector309 also failed before SSH because census249 was still pending. Fresh collector310 ran only after census completion. No new native identity gap or app failure occurred.

After setting src/ev/py in V1, PowerShell:
    & $py -B "$src\build_field_operator_broker_bundle_v7.py" --plan "$ev\operator-qualification-v4-preparation\PLAN_V1.json" --projection "$ev\operator-broker-native-v1-publication\CAPSULE_PROJECTION_V2.json" --owners "$ev\operator-local-capsule-v1-preparation\EXTRA_OWNER_CLOSURE_V1.json" --output "$ev\operator-local-capsule-v1-preparation\capsules-v2"

After setting SRC/EV/PY in V1, Command Prompt or Anaconda Prompt:
    "%PY%" -B "%SRC%\build_field_operator_broker_bundle_v7.py" --plan "%EV%\operator-qualification-v4-preparation\PLAN_V1.json" --projection "%EV%\operator-broker-native-v1-publication\CAPSULE_PROJECTION_V2.json" --owners "%EV%\operator-local-capsule-v1-preparation\EXTRA_OWNER_CLOSURE_V1.json" --output "%EV%\operator-local-capsule-v1-preparation\capsules-v2"

The changed allocation check passed three positive groups and10rejects. Its allocation-v1 output is consumed and must not be rerun unchanged. Synthetic policy caps were used only to exercise changed arithmetic: no new native resource policy, admission, root or production lifetime was issued.

For one recording/three launches, the proposed complete reservation is306783320target +310977624host =617760944bytes. This retains the original151114284one-slot target and independent151114284Pi-local copy and adds a full151114284host copy of that local mirror. It does not enlarge the native broker or local copier's one-slot maximum. Fresh measured native admission and complete backup adapters remain required.
