# Failed helper cleanup and rollback observation

F09 manager6 corrects the failed-helper cleanup path in manager5: poll previously closed stdout/stderr before raising a helper failure; failure_poll then read the closed stream, raised again, and skipped UI/update/Close every turn. It now leaves failure pipes for cleanup and skips already-closed pipes defensively. Only poll/failure_poll differ from manager5. All guards, first-fault latch, real process reaping, exact death, immutable failure/exit publication and Stop remain. Manager6 is prepared, not installed or native-qualified. Manager5 supplies the prepared after-map geometry/scrollbar fix.

F18 inspect_runtime_recovery_v2.py extends the file-only session inspector to an already-closed registered manager. It keeps the recorded manager identity distinct from current service MainPID0, requires exact dead historical owners, and reads rollback attempt receipts, current restored baseline service/processes, capture/leases/settings/display and service logs. It does not invoke rollback, start a model or mutate files. Full host/native owner checks remain, including late control/inspection/preservation helpers.

PowerShell:
~~~powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\inspect_runtime_recovery_v2.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection PRESERVATION_DIRECTORY --candidate-install ORIGINAL_INSTALL --scope FRESH_SCOPE --output NEW_OUTPUT
~~~
Command Prompt / Anaconda Prompt:
~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B inspect_runtime_recovery_v2.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection PRESERVATION_DIRECTORY --candidate-install ORIGINAL_INSTALL --scope FRESH_SCOPE --output NEW_OUTPUT
~~~
Inputs/outputs and original65s host/55s native resource bounds are in README_RUNTIME_SESSION_INSPECTION_V2. Source backup/independent restore must close first. The manager entry after a fresh installation remains python -B code/field_runtime_manager_v6.py --root INSTALLED_ROOT --policy-sha256 EXACT_SHA --profile PROFILE through the reviewed service shortcut. Never run it against an old manifest or reuse a failed root.

Version2 adds complete prior nested runtime envelope bindings from the actual candidate admission and includes all late candidate utility owners. Native inspection behavior is unchanged; no runtime action.
