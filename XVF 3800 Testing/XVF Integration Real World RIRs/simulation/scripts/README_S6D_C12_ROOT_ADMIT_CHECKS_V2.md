# Focused N6g C12 metadata/admission fixtures

Purpose: verify the additive C12 queue transformation and admission publication boundary. Inputs are the held helper/README plus the exact bounded original/adopted metadata graph. The suite reads the twelve literal queue rows, source files and saved old closure once, and tests source replacement, all three journal predicates, immutable science/limits, prior failure handling, fake process inventories and final validation order. It invokes the existing V4 validator on an in-memory twelve-row approval; it never invokes runner execution. Synthetic transaction reviews are explicitly named `SYNTHETIC_REVIEW_NEVER_EXECUTE.json`, and actual approval/admission writes are intercepted in memory.

No process census, audio/model/vector/journal scan, inference, device access, production preparation, actual admission or launch occurs. All fixture output goes to the supplied fresh G directory. The input helper and README hashes are verified before and after. A copied source directory is supported; canonical campaign inputs remain pinned to the repository.

Outputs: `RECEIPT.json`, a test-by-test count and binding receipt, plus small synthetic unapproved metadata folders. Checks include actual prepare orchestration and injected scope, allocation, source-guard and final-validator failures before authority publication. Success captures writes in memory and verifies approval is last and exactly bound. A failing run remains preserved; choose a fresh suffix for a corrected run.

Development receipts remain in checks_v1–v3: initial unpublished parser typo, success-stub readback mismatch, and a synthetic scope mutation that accidentally aliased the expected object. The last fixture now deep-copies its serialized preparation before mutation, matching separate production JSON reads. Final held-source checks use checks_v4; no production phase was invoked in any development run.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6d_C12_root_admit_checks_v2.py" --source-root "$sim\scripts" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\C12_queue_n6g_v1\checks_v4'
```

Anaconda Prompt or Command Prompt:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\s6d_C12_root_admit_checks_v2.py" --source-root "%SIM%\scripts" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\C12_queue_n6g_v1\checks_v4"
```

These are source fixtures only. Root must independently review and invoke the production helper's two phases; the fixture never creates campaign authority.
