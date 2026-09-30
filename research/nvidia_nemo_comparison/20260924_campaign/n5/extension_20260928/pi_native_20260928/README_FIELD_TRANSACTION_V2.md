# Transaction harness with persistent guard accounting

Purpose: finish qualification of the new single-state publication boundary after V1's post-run data-membership assertion failed. The actual release lock intentionally keeps an empty `.runtime.guard` inode after releasing ownership. V1 compared all data-directory files against its three originals and rejected this fourth file after the six transaction records and final rollback had been written. V1 natural exit1, missing final case receipt, source/admission and all34 target files/157353 bytes are privately backed up; that trial remains failed. No traceback was retained by V1, so the failure-site diagnosis combines its bound control flow and exact final file inventory, not a recorded stack trace.

Fresh `field_transaction_protocol_v2.py` checks the original three file hashes exactly, permits only the additional empty `.runtime.guard`, and still rejects an active runtime.lock or other extra member. It writes each rejection/interruption receipt immediately. `dispatch_field_transaction_v2.py` also retains a bounded traceback on future errors. The actual `field_candidate_transaction_v1.py` publication code is byte-identical to V1. Old helpers, pointers, records, release files and failures remain immutable. V2 uses fresh directories and repeats this changed incomplete protocol, with no model/capture/import/catalogue collection.

The independent `review_field_transaction_v2.py` verifies the authoritative state and five-record committed chain, retained sixth uncommitted transaction/staged state, exact descriptor/dependency/release bindings, three immediate rejection receipts, two immediate injected-interruption receipts, preserved private file hashes, empty/unlocked guard, actual limits/natural owners and full hashed private backup. It does not import or call the transaction helper. Inputs/outputs, single-commit semantics, fsync behavior, retained-failure policy and limits are described in [V1's preserved run README](README_FIELD_TRANSACTION_V1.md). Injected Python exceptions are not process-kill or power-loss tests; the lower quota is not real disk exhaustion. Candidate state remains unused by the original app/installer.

Inputs: fresh/current CPU14 HOST_CENSUS_V143 plus recalculated host delta/target-inclusive resources; reviewed V1 failure backup, V61 dependency result, exact original baseline, release manifests and immutable dependency lock. Outputs: fresh field-transaction-v2 private admission, two descriptors, transaction/state/prepared files, five per-case receipts and aggregate result, actual resource/closure evidence and independent backup. No audio/weights/runtime/release tree copies. Same fresh8MiB combined/4MiB target/4MiB host envelope,768MiB AS/1MiB stack/sharedCPU2,3/200%/Tasks64/300s/60sStop/8MiB file and sampled memory guards. Fixed32GB/5GiB free floors remain.

PowerShell, fresh run only:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_transaction_v2.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V143.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_transaction_v2.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_transaction_v2.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V143.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_transaction_v2.py
```

Never overwrite or repeat completed run/backup paths. The dispatcher requires a census younger than15minutes and fresh native owner/lease/baseline/resource gates; all prior data remain counted. This is not a launcher, original rc5 activation, GUI/capture/model, endurance or field-release qualification.
