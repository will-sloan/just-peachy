# Typed owner preflight for the V2 installed integration

Purpose: dispatch the prepared, byte-identical V2 protocol and v12 package after fixing a read-only owner enumeration failure. The V2 dispatcher used `*OWNER*.json` as if every matching JSON described a PID. It matched the new OWNERSHIP_CLOSURE.json receipt and raised KeyError before staging or target mutation. The rejection and confirmed absent V2 target are preserved privately. V1 remains the earlier installed UTF-8 failure.

The fresh V3 dispatcher retains every V2 resource, byte, identity, baseline, expiry and lease guard. It separately validates only the specifically named OWNERSHIP_CLOSURE.json with its exact five-key schema, boolean closure flags, valid borrower counts and pending-command value. Such receipts are not process identities; all other owner matches still must provide boot/PID/start ticks and be closed. No general missing-field fallback is allowed. The protocol/code/config and V2 planned tests are unchanged. The fresh collect_native_closure_v5.py applies the same distinction and records nonidentity closure path/hash/receipt separately from the process-identity census. Existing V4 collectors and closed receipts are preserved.

Inputs and outputs: same fresh V159 census and authority/code/16MiB target+16MiB host admission as README_FIELD_ARTIFACT_INSTALL_V2.md. The executable dispatcher is now dispatch_field_artifact_install_v3.py; its RUN stays field-artifact-install-v2 because that target was independently confirmed absent. Target receipts bind this new dispatcher and this addendum. No models, source, inference, GUI, audio copy or pointer activation.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_artifact_install_v3.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V159.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_artifact_install_v1.py --run field-artifact-install-v2
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_artifact_install_v1.py --run field-artifact-install-v2
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B collect_native_closure_v5.py --version 159
```

CMD / Anaconda Prompt: `cd /d` to the directory above; use the same quoted Python executable without PowerShell's leading `&` and the same script/arguments for each step. For example:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_artifact_install_v3.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V159.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 159
```

Read all existing receipts first. Completed exclusive paths must not be rerun. Closure version159 is an output name, not permission to reuse stale state. Host Python coordinators set CPU14 before reads; Pi preflight/closure readers set CPU3. No baseline or closed ledger is edited.
