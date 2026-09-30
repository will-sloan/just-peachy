# Compact dependency-gate fixtures and prewrite output bound

Purpose: finish the dependency-guarded candidate activation/rollback boundary after the immutable V1 output-guard failure. Reuse the exact retained5,519,586-byte dependency lock and prior import/link observation; do not repeat collection, ldd commands, module imports, asset copies or model work. A fresh verification still checks all dependency bytes, identities, symlink targets and runtime membership before candidate pointer publication and after rollback.

`field_dependencies_v2.py` is a fresh derivative adding a one-time bound output root and prospective byte check to its exclusive JSON writer. It reserves1MiB of the4MiB target allowance for supervisor/other small receipts. Managed writes reject before opening a file when the current bytes plus new serialized bytes exceed that bound. A test may only lower the effective bound; it cannot enlarge it. Other supervisor/runtime-lock writes retain the sampled run-wide guard; this is not a hard whole-process filesystem quota.

`field_dependency_protocol_v2.py` uses new private candidate/data directories and two descriptors for the unchanged v5/v7 releases. It tests v5→v7→v5, exact current/previous pointers, dependency hashes/paths/targets, busy data, and prewrite quota. Three new compact malformed locks each contain one invalid dependency row and empty runtime membership, intentionally isolating rejection at that row; they are not otherwise complete valid runtime catalogues. They replace the three full5.5MB negative copies that caused V1's sampled16MiB target overrun. Original V1 files/failed admission/TERM/no RESULT/two pointer entries remain untouched. The new run uses the same52GiB/5GiB policy with a smaller fresh8MiB combined allowance, not a retroactive extension.

Inputs: fresh CPU14 host census plus current host delta/target-inclusive accounting, exact V60 release manifests, retained V1 lock/probe hashes, reviewed38-file private V1 backup and current baseline/leases/resources. Outputs: fresh `field-dependency-v2` admission, original config/install backups, two dependency-bound release descriptors, compact malformed fixtures, eight rejection receipts, storage record, natural-owner/resource result, and isolated candidate pointer history. No new audio/runtime/model/release tree copy. Retained dependency paths remain required; no relocation or original rc5 activation. The original installer does not consume this candidate pointer yet.

Same default native envelope as V1:768MiB AS/1MiBstacks/CPU2,3/shared200%/Tasks64/300s/60sStop/8MiBfile, initial850MiB RAM, sampled192MiB available floor/640MiB aggregate RSS stop, fixed Pi5GiB free plus planned512MiB private quota. Target4MiB plus host4MiB new output, original larger inventory remains already counted. No probe child, GUI, capture, playback, reset or download. The new prewrite fixture uses an injected lower allowance, not physical disk exhaustion.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_dependency_v2.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V140.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_dependency_v3.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_dependency_v2.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V140.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_dependency_v3.py
```

The dispatcher requires a census younger than15minutes and calculates current host changes/target bytes before admitting the run. Commands document fresh execution only; never rerun or overwrite completed paths. The V3 reader independently hashes retained dependencies, descriptors, pointer history, unchanged original sources, private canary/config/schema, guard rejection receipts and closed owners; it verifies every private backup file. It sets hostCPU14/PiCPU3/256MiB and disables bytecode, with no imports/model/capture/GUI work. V1 rejected reader and V2 failure-aware reader are separately preserved. Module inputs/outputs and retained-placement/ELF limitations are defined in README_FIELD_DEPENDENCIES_V1.md; V1's successful full-protocol claim was never accepted.
