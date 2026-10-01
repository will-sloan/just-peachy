# Measured broker admission V3

The selected native/transport source set and base capsule builder are documented in README_FIELD_OPERATOR_BROKER_QUALIFICATION_V2.md and V1. This file adds admit_field_operator_broker_v1.py. Its purpose is to issue ONE fresh, measured two-session policy with all closed-owner identities and full target plus host reservations, then verify exact independent backup and restore copies before dispatch.

Inputs: the immutable BUNDLE.json from the builder, fresh HOST_CENSUS, matching NATIVE_RESOURCES/NATIVE_CLOSURE, ALL-owner EXTRA_OWNER_CLOSURE, an unused root name field-operator-sessions-vN, and a fresh private output directory. Outputs: RELEASE.json, INITIALIZER_REQUEST.json, PLAN.json, ADMISSION_REVIEW.json, registered issuer identity, and independent backup/restore copies. This preparation explicitly reserves 4MiB for these primary/copy files plus directory metadata. The new policy adds the unchanged 604,981,424-byte two-slot reservation and a declared 8MiB accounting margin: 4MiB preparation plus 4MiB operational accounting. It does not edit WINDOW_V5, delete retained usage or credit unused/failed slots.

The issuer refreshes compact owners in both config and child template, then recomputes the entire manifest. It verifies host owners dead and requires the supplied Pi closures at most 300 seconds old. The native initializer independently rechecks Pi identities, units, leases, physical device/RAM/disk, baseline and target-inclusive storage before writes. The policy expires in 600 seconds and cannot cross 2026-10-01T17:42:44Z. Run the already backed dispatcher V3 immediately after issuer exit; the dispatcher requires at least 590 seconds remaining. The issuer itself never contacts the Pi.

PowerShell, with $src set as in README V1:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$src\admit_field_operator_broker_v1.py" --bundle 'G:\PATH\BUNDLE.json' --census 'G:\PATH\HOST_CENSUS.json' --resources 'G:\PATH\NATIVE_RESOURCES.json' --closure 'G:\PATH\NATIVE_CLOSURE.json' --extra 'G:\PATH\EXTRA_OWNER_CLOSURE.json' --output 'G:\PATH\FRESH-ADMISSION' --root-name field-operator-sessions-vN
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$src\dispatch_field_operator_broker_v3.py" --plan 'G:\PATH\FRESH-ADMISSION\PLAN.json' --owner-receipt 'G:\PATH\FRESH-ADMISSION\DISPATCH_EARLY_OWNER.json'
```

Command Prompt / Anaconda Prompt from the source directory:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B admit_field_operator_broker_v1.py --bundle G:\PATH\BUNDLE.json --census G:\PATH\HOST_CENSUS.json --resources G:\PATH\NATIVE_RESOURCES.json --closure G:\PATH\NATIVE_CLOSURE.json --extra G:\PATH\EXTRA_OWNER_CLOSURE.json --output G:\PATH\FRESH-ADMISSION --root-name field-operator-sessions-vN
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_operator_broker_v3.py --plan G:\PATH\FRESH-ADMISSION\PLAN.json --owner-receipt G:\PATH\FRESH-ADMISSION\DISPATCH_EARLY_OWNER.json
```

Replace all placeholders with reviewed inputs and an unused positive integer N. Do not rerun a closed/failed admission. Before use, back up this source and verify its independent restore, refresh every required ownership/lifetime source, inspect source/cardinality/time allocations, and preserve all failed bytes. The automated native button driver remains a bounded quiet qualification. Neither the issuer nor a successful idle broker is an accepted persistent launcher or offline release.
