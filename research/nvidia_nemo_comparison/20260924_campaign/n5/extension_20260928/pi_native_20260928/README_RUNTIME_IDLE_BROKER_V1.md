# Close an unstarted owned broker
Purpose: finish cleanup after the functional driver failed before opening any child session. Requires exactly one current active broker, no child OWNER, actual pinned policy/current ownership, closed capture, original resource checks and one visible enabled Close button. Sends one normal Close, waits for its exact process to end, preserves every slot/tree, and leaves the manager active. It does not reopen or retry a recording.
Inputs: actual candidate install, complete prior binding, previous inspection, bounded host scope and new private output. Outputs: early owner, raw diagnostics, exact broker/helper closure, actual button bounds and RESULT. Native inspection CPU3/128MiBAS/1MiBstack/FSIZE0/time limits remain unchanged; no microphone/model action.
PowerShell:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\control_runtime_idle_broker_v1.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_JSON --previous-inspection LAST_INSPECTION --candidate-install ACTUAL_INSTALL --scope CURRENT_SCOPE --output NEW_PRIVATE_OUTPUT
~~~
CMD / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B control_runtime_idle_broker_v1.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_JSON --previous-inspection LAST_INSPECTION --candidate-install ACTUAL_INSTALL --scope CURRENT_SCOPE --output NEW_PRIVATE_OUTPUT
~~~
Back up source and independently restore/read back before use. This closes a driver-owned unused broker, not the user's idle baseline app.
