# Candidate transaction publication and quota failure

Purpose: fix the V61 static finding in a fresh candidate interface. The bound `field_dependencies_v2.activate` implementation and previous runs remain unchanged. `field_candidate_transaction_v1.py` reuses V2's exact dependency/descriptor checks, but replaces its multiple mutable pointers with one authoritative `state.json` containing current and previous candidates plus an immutable transaction-record hash.

The existing private-data update lock covers reading the expected state, verifying all dependencies/release/data bindings, preflighting all output and publication. Before any candidate write, the helper counts both complete new documents while the old state remains. It checks the bound output root/allowance and fixed-device5GiB+32MiB reserve. A test-only lower additional-byte limit can tighten, never enlarge, this allowance. File contents and transaction/staging directories are fsynced before one `os.replace` commits the state; the candidate root is then fsynced. A prepared transaction and staged state remain preserved on precommit failure. If acknowledgment fails after replacement, read-only `inspect` resolves the visible committed state; the code never automatically retries. Legacy current/previous JSON pointers are rejected in this new root. No conversion or alteration of old pointers occurs.

This bounds managed writes with a1MiB reserve for supervisor/other receipts; it is not a hard filesystem quota against concurrent external writers. Directory/file persistence primitives are exercised, but no actual process-kill, kernel crash, power loss or storage-failure test is claimed. Explicit injected Python exceptions before and after replacement test acknowledgment/recovery logic only.

`field_transaction_protocol_v1.py` uses fresh private directories and descriptors for unchanged installed v5/v7 releases. It qualifies activation-quota and rollback-quota rejection before any candidate-file mutation, a stale authoritative-state rejection, normal activation/rollback, retained precommit failure and read-only resolution of a postcommit failure followed by a distinct explicit rollback. It retains six immutable records, one uncommitted staged state and exact case receipts. Canary/schema/copied config stay exact. The quota tests use injected1-byte additional allowances; they are not physical disk exhaustion. No catalog collection, ldd, import probe, model, capture, playback, GUI or asset/release tree copy.

Inputs: fresh CPU14 census, target-inclusive WINDOW_V5 output/payload/free-space checks, exact baseline/owners/leases, existing V61 reviewed/private-backed-up dependency evidence, immutable lock/probe and existing v5/v7 manifests. Outputs: `field-transaction-v1` admission, original config/install backups, source hashes, new descriptors/private metadata, state/transaction/staged files, case receipts, actual limits/resource/owner result and independent private backup. Retained dependencies are reverified when the changed publication path needs them; previous passed collection/import protocols are not rerun. Candidate state is not consumed by the installed app or original rc5 launcher yet.

Envelope:8MiB combined new output,4MiB target and4MiB host,768MiB AS/1MiB stacks/CPU2,3/shared200%/Tasks64/300s/60sStop/8MiB per file. Initial850MiB available RAM, sampled192MiB minimum/640MiB owned aggregate RSS stop; RSS is not hard-enforced. Original app remains running. Fixed32GB storage and5GiB free reserve remain; no evidence cleanup or quota reset.

PowerShell, fresh execution only:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_transaction_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V143.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_transaction_v1.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_transaction_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V143.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_transaction_v1.py
```

The dispatcher rejects stale census, occupied leases, live owners, changed baseline or insufficient resources. Never rerun completed paths. The independent reader sets hostCPU14/PiCPU3/256MiB, disables bytecode, verifies the state/record digest chain and retained orphan, exact release/dependency identities, negative receipts, actual envelope and natural closure, then hashes every private backup file. It does not invoke the tested helper or load models. A failed run/review stays preserved and needs fresh versioning. Full launcher startup, original baseline activation, power-loss safety, endurance and field release remain outside this protocol.
