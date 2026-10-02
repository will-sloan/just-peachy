# Preserve source-start failure receipts

Purpose: F09 prevent an absent source thread from aborting the final failure report. The actual source can fail before creating its consumer thread. The fresh capsule records source_thread_created=false and source_thread_joined=false in that case, then continues publishing model/application/result receipts. It does not claim a thread was joined when none existed. Existing positive-path behavior, resource bounds and first-fault state remain.

Input: exact candidate5 COMMON_BUNDLE.json after the compact archive fix. Output: a new bytes capsule and derivation receipt. Only the worker receipt expression changes; all other function bodies and allocation constants remain. The old failed source and capsule are immutable. This pure API is consumed by the next backed installer; it does not launch an application.

PowerShell, CMD and Anaconda all use the existing pinned Python:
~~~text
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B install_field_runtime_v7.py [arguments in README_RUNTIME_ACTIVATION_V7.md]
~~~
In PowerShell prefix the quoted executable with &. The installer/source instructions must be present and backed before use. Developer API: field_runtime_source_failure_v1.derive(raw_capsule_bytes) returns (new_capsule_bytes, review_dict). No standalone native or recording command is authorized by this API.
