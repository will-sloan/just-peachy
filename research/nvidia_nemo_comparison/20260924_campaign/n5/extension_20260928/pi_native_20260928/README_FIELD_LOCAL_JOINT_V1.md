# Local manager and broker binding preparation

Prepared only. Neither new native path has been executed. This is not a launcher or a capture admission.

`field_local_joint_contract_v1.py` validates and binds the existing one-session broker and manager capsules to a finite release and research operation. Inputs are decoded capsule objects, a release policy, an operation, and exact prior Pi identities. Output is a new broker request plus initial-reserve, gate and finish bindings. The output explicitly does not issue admission.

`field_local_manager_initialize_v1.py` is an unexecuted initializer draft, intended for a future bounded dispatcher which injects `REQUEST`. It installs a fresh manager capsule and calls Supervisor3 install-reserve. Its early OWNER and later EXIT intent require independent process-death verification. It does not launch a broker, activate a release, or establish successful recording or backup.

The initializer retains CPU3, 128 MiB address space, 1 MiB stack, 32 MiB file limit and 150-second alarm. Its code aggregate uses the existing Plan2 2 MiB/16-file allocation; the earlier metadata-only initializer's 128 KiB aggregate was too small for the prepared 133,840-byte capsule. Member limit remains 128 KiB. Before native use it still needs premutation canonical-root and strict-request validation, complete reservation free-space checks, a fresh issuer/dispatcher, exact nested-owner collection and complete success/failure-tree host backup.

## Inspection commands

PowerShell, from the campaign worktree:

```powershell
$p = 'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
Get-Content "$p/field_local_joint_contract_v1.py"
Get-Content "$p/field_local_manager_initialize_v1.py"
```

CMD or Anaconda Prompt, from the same worktree:

```bat
type research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\field_local_joint_contract_v1.py
type research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\field_local_manager_initialize_v1.py
```

There is deliberately no standalone native run command: the reviewed dispatcher, current admission and failure backup are not yet implemented. Importing the initializer directly without its request is invalid. Existing capsules and closed policies are not authorization. CPU14 and early owner registration are required for any host Python caller.
