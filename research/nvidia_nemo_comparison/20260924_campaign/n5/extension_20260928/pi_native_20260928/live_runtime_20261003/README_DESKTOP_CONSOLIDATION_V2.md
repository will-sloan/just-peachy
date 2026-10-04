# Verified metadata imports for Desktop consolidation V2

Purpose: make the existing exact11-shortcut consolidation transaction callable from the guarded injected action. The original action loaded release_authorization without establishing canonical imports for its profiles and optional-refiner metadata dependencies. V2 uses the same manifest-pinned import context already reviewed in desktop_activation_action.py. It restores Python module/path state afterward and reports the exact imported path/size/SHA. No models, capture, network or application are started by this metadata validation.

Inputs and outputs are unchanged from README_DESKTOP_CONSOLIDATION.md: actual accepted production package/manifest, selected current shortcut/activation plan and old copies, exact11-original plus startup pins in the complete backup manifest, fresh boot/expiry, and a new16MiB archive. The current planned production target is14; it has not been accepted or executed by this preparation. Never replace real package/acceptance/hash values with those of a qualification build. Archive and restore code and the literal11/startup pins are AST-identical to the original action. The original source and its receipts remain preserved.

Use the full reviewed JSON schema in README_DESKTOP_CONSOLIDATION.md. The order remains successful activation plus independent old-byte/readback proof, then consolidation, then exact Desktop Exec idle/normal Exit last. Only after actual production acceptance and complete backup may the root operator run this command.

## PowerShell

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
& $py -B "$n/host_operations_v4.py" --label desktop-consolidation-01 --action "$n/desktop_consolidation_action_v2.py" --payload "$q/reviewed-desktop-consolidation.json" --writes
```

Host operations registers CPU14 before project reads; its strict owner/space/SSH checks remain. The payload must be a freshly reviewed actual production input, not a template. Explicit restore uses the same V2 action, a fresh restore label/expiry, mode=restore and the exact completed archive; see the original README for all11 restoration and failure-preservation rules.

## Command Prompt / Anaconda Prompt

Enter `powershell -NoProfile`, then run the complete block above. The qualified interpreter needs no new installation or environment activation. The command contacts the device and can change only the exact owned Desktop entries; it was not run in preparation.

## Host-only checks and scope

Using the CPU14/early REGISTERED_OWNER test wrapper in README_STORAGE.md, run only test_desktop_consolidation_v2. Three focused checks cover exact helper/transaction AST preservation; real frozen12 production-metadata imports in a synthetic acceptance fixture with host namespace restored and Desktop unchanged; and all-function symtable checks across consolidationV2, activation, idle dispatcher and idle controller. Only documented injected PAYLOAD/BASELINE globals are exempt. These checks catch unresolved global references such as the prior backup publisher issue without executing a native action. They do not prove Tk, native imports, physical touch, activation or rollback on the device. Native production idle must still prove exact parsed Desktop Exec/native_scope, the actual nested unit/GUI owner, normal Exit and unchanged startup/display state.