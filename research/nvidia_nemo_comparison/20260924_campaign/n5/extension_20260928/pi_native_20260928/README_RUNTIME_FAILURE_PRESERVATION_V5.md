# Failed runtime closure and complete preservation

Purpose: F09/F25 close the actual failed manager through its normal systemd Stop handler, then preserve its complete tree and the failed broker tree. Requires capture closed, all registered child owners dead, the exact current manager identity/service, actual failed gate result and original policy-bound roots. It invokes no capture/model/control restart and never changes a closed ledger. A normal service Stop may publish the manager's own failure/exit intent; actual process death is independently observed before source reads.

The utility inherits the complete current host/native owner, lifecycle, device, RAM/disk and lease inspection. Native CPU3/128MiBAS/1MiBstack/FSIZE0/55s alarm; Stop waits at most47s under existing45s service bound. Complete files/empty directories, stable identity/membership and SHA256 are checked. Original1162file/264directory/32MiBfile limits and each original policy allocation remain. Unchanged code is reconstructed only from exact matching independent PC install copies; other bytes use bounded compressed metadata. The original262144B transport output cap remains, with at most131072B compressed new payload. This is complete data preservation, not model/session success or a fabricated journal BACKUP.

Inputs are the same as the session inspector: actual candidate install, full prior-closure binding, previous inspection, private/local roots, fresh scope, new private output directory. Output includes raw observations/early owner/exact utility closure, complete tree plus independently reread per-file hashes and BACKUP receipt. No deletion or automatic retry. The original install's full host reservation remains charged.

PowerShell:
~~~powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\preserve_runtime_failure_v5.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection PREVIOUS_INSPECTION --candidate-install ACTUAL_INSTALL_DIRECTORY --scope CURRENT_SCOPE --output FRESH_PRIVATE_OUTPUT
~~~
Command Prompt / Anaconda Prompt:
~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B preserve_runtime_failure_v5.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection PREVIOUS_INSPECTION --candidate-install ACTUAL_INSTALL_DIRECTORY --scope CURRENT_SCOPE --output FRESH_PRIVATE_OUTPUT
~~~
Source backup and independent restore must close before use. If Stop, tree stability, ownership or full reconstruction fails, retain all bytes and receipts and investigate; do not relaunch the failed policy/root.

Version2 retains the complete native/host census and fixes the receiver to select RESERVED by its exact record name. It binds all prior nested owners from the current installation and late helper receipts. After normal service Stop and exact candidate closure, it copies the complete manager/broker trees and invokes the already-backed installed rollback service exactly once only if its first attempt has not run. Otherwise it observes the existing attempt. It requires rollback utility exact death, RESULT and capture off. Native alarm150seconds and host160seconds include the unchanged47-second Stop bound; all storage reservations remain. Failure recovery is scoped to this actual preserved failed candidate, not arbitrary crash proof.

Version4 adds only a bounded read-only wait for the already-requested pinned rollback to complete. It does not repeat Stop or rollback. Use only the failed-before-model candidate whose saved MODEL_CLOSURE confirms no acquisition/session/capture. All original caps, exact identities, full tree copies and readback remain.

Version5 preserves the candidate5 failed source-start case and records model/capture attempt status as requiring review of actual source/session receipts. It does not reuse the previous before-model false flags. Capture must actually be closed, all child identities dead and the failed gate closed before normal manager Stop/complete backup/one pinned rollback.
