# Native closure V6

Purpose: retain V5 exact typed process-versus-ownership-closure logic while reporting cumulative output against one explicitly measured recovery policy. Old WINDOW_V5 is read and its cap retained; no retained usage is removed. This reader cannot authorize another job.

Inputs: fresh version, exact RECOVERY_RESOURCE_POLICY_V1 hash, fresh HOST_CENSUS receipt, exclusive host owner-receipt path. Output: NATIVE_CLOSURE/RESOURCES version with current identities, baseline/leases/capture, original and new caps, target-inclusive payload, and a resource-bounded recorded read-only Pi utility.

PowerShell, from the native report directory:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./collect_native_closure_v6.py --version 258 --resource-policy ./RECOVERY_RESOURCE_POLICY_V1.json --policy-sha256 VERIFIED_SHA256 --census ABSOLUTE_FRESH_CENSUS.json --owner-receipt NEW_ABSOLUTE_OWNER.json
```

CMD / Anaconda Prompt:
```bat
C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe -B collect_native_closure_v6.py --version 258 --resource-policy RECOVERY_RESOURCE_POLICY_V1.json --policy-sha256 VERIFIED_SHA256 --census ABSOLUTE_FRESH_CENSUS.json --owner-receipt NEW_ABSOLUTE_OWNER.json
```

Do not reuse the example receipt number if it exists. This is read-only evidence and a policy-bound ceiling check, not a reset or a new dispatch admission. Host CPU14; Pi utility CPU3/128MiB AS/1MiB stack/FSIZE0/45s alarm. All other V5 hardware/baseline and typed-closure checks remain.
