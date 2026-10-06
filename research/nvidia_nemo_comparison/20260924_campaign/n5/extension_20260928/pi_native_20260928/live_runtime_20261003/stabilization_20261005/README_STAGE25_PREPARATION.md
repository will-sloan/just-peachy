# Prepare build25 staging

Purpose: prepare a fresh build25 payload using the exact unchanged stage24
installer and stage action. This host utility stages nothing and activates
nothing. Existing runtime roots, recordings and shortcuts are preserved.

Inputs: the actual completed build25 package directory, its archive and exact
archive/manifest SHA256, and current boot
`0561d730-3cad-48e0-940a-fe3930c89665`. The preserved stage24 installer/action
are read back against their bound SHA256. Full archive members, expanded package
membership, bytes and hashes must agree under the original installer limits:
2 MiB compressed archive, 16 MiB expanded package, 512 regular members and 2 MiB
per member. No model downloads or gallery conversions occur.

Outputs: a fresh private CPU14 preparation containing ACTION.py, PAYLOAD.json,
installer, this preparer and README, each with exact backup and independent
restore. The original 8 MiB/600-second host scope and C50/G75 GiB floors apply.
Target reservation includes expanded files, retained archive bytes, each
directory plus root at 64 KiB, and a further 64 KiB control allowance. Preparation
is complete only after its owner exits and an exact host closure is checked.

PowerShell, from this directory, using the actual closed package builder output:

```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $py -B './prepare_stabilization_stage25.py' --package 'ACTUAL_BUILD25/package' --archive 'ACTUAL_BUILD25/field-runtime-v29-build-25-prepared.tar.gz' --archive-sha256 ACTUAL_ARCHIVE_SHA256 --manifest-sha256 ACTUAL_MANIFEST_SHA256 --boot-id 0561d730-3cad-48e0-940a-fe3930c89665
```

CMD / Anaconda Prompt use the same explicit Python and actual arguments:

```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B prepare_stabilization_stage25.py --package "ACTUAL_BUILD25/package" --archive "ACTUAL_BUILD25/field-runtime-v29-build-25-prepared.tar.gz" --archive-sha256 ACTUAL_ARCHIVE_SHA256 --manifest-sha256 ACTUAL_MANIFEST_SHA256 --boot-id 0561d730-3cad-48e0-940a-fe3930c89665
```

After host closure, the separately authorized native staging command is:

```powershell
& $py -B './host_stabilization_operations_v2.py' --label stabilization-stage25-01 --action 'ACTUAL_PREPARATION/ACTION.py' --payload 'ACTUAL_PREPARATION/PAYLOAD.json' --writes
```

CMD / Anaconda use the same quoted executable/arguments without PowerShell's
leading `&`. The complete current baseline/owner/lease/resource preread remains
mandatory. The unchanged installer refuses an existing target; failed roots and
admissions are never reused. Explicit `--writes` keeps the bounded native write
envelope. Staging produces PREPARED_PACKAGE_STAGED_FOR_NATIVE_COMPONENT_CHECKS;
it starts no microphone/model and does not change Desktop. Native functional
qualification, independent copies and activation are separate later actions.
