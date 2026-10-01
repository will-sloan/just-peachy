# Runtime policy V3: selectable speaker embedding

Purpose: extend the finite production policy's explicit profile map with the user's restored TitaNet choices. Reuses all V2 policy, ownership, resource, recording, backup and expiration checks. Only the complete profile-key tuple and exact profile-to-engine mapping change; all other function ASTs are identical to V2.

Inputs/outputs and full original commands: README_FIELD_RUNTIME_POLICY_V2.md and README_FIELD_RUNTIME_V1.md. Every policy must now explicitly describe all ten profile keys, including unavailable reasons. A profile identifier is not an implemented engine or native pass. Existing V2 capsules stay immutable; new manager/broker capsules must pin and consume V3 before dispatch. Native integration is pending.

The new keys are baseline-titanet, d1-delayed-titanet, d1-streaming-titanet-saved, d1-chunk52-titanet-saved and baseline-anonymous. Their source type is unchanged: names ending -saved require saved input; the others require an admitted microphone operation. No quality assertion, silent fallback or model download. field_runtime_profiles_v1.py binds the previous actual model/catalogue bytes and separate namespaces.

Allocation remains the full independent Plan2 proposal, with no deletion/replenishment credits. Additional E1 gallery directories, installed assets or other new physical writers need their own measured allocation before use; this profile-key extension does not allocate or authorize them.

PowerShell compile-only command from this directory:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; compile(Path('field_runtime_policy_v3.py').read_bytes(),'field_runtime_policy_v3.py','exec')"
~~~

CMD / Anaconda Prompt:
~~~bat
C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; compile(Path('field_runtime_policy_v3.py').read_bytes(),'field_runtime_policy_v3.py','exec')"
~~~

API remains validate, issue_operation, validate_operation, next_slot, validate_broker_policy and load_broker_policy. It performs no deployment or capture. Future user launch is through the installed versioned manager and verified desktop shortcuts, never a consumed research root.
