# Broker qualification V2 execution index

Read README_FIELD_OPERATOR_BROKER_QUALIFICATION_V1.md for purpose, all module roles, inputs, outputs and safety limits. V1 sources and its host partial-backup check are closed and retained.

V2 selects field_operator_broker_gate_v4.py and dispatch_field_operator_broker_v3.py. Gate V3 still imported the former entry V7 utility module; V4 selects entry V8 so the actual capsule fits the unchanged 64-file ceiling. No native attempt occurred with Gate V3. Dispatcher V3 changes only the selected gate and its own exact pin. All other V1-selected modules remain unchanged.

build_field_operator_broker_bundle_v1.py builds a private, exact base64 capsule and manifest, config and child template from the retained V123 plan, V126 projection and a supplied closed-owner review. It does not issue a policy or contact the Pi. The output must be a fresh directory. It checks every original source pin, actual code membership, per-member/code/control byte ceilings, 51 child code files plus four data files, and explicit installed-package or Registry-only external imports. The template retains the mode registry and live D1 binding. Fresh measured admission, owners, census, expiry and full source/backup review are required before dispatch.

PowerShell (set $src as in README V1):
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$src\build_field_operator_broker_bundle_v1.py" --plan 'G:\PATH\TO\CLOSED-V123-PLAN.json' --projection 'G:\PATH\TO\CLOSED-V126-PROJECTION.json' --owners 'G:\PATH\TO\FRESH-EXTRA-OWNER-CLOSURE.json' --output 'G:\PATH\TO\FRESH-BUNDLE'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$src\dispatch_field_operator_broker_v3.py" --plan 'G:\PATH\TO\FRESH-ADMITTED-PLAN.json' --owner-receipt 'G:\PATH\TO\DISPATCH_EARLY_OWNER.json'
```

Command Prompt / Anaconda Prompt, from the source directory:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B build_field_operator_broker_bundle_v1.py --plan G:\PATH\TO\CLOSED-V123-PLAN.json --projection G:\PATH\TO\CLOSED-V126-PROJECTION.json --owners G:\PATH\TO\FRESH-EXTRA-OWNER-CLOSURE.json --output G:\PATH\TO\FRESH-BUNDLE
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_operator_broker_v3.py --plan G:\PATH\TO\FRESH-ADMITTED-PLAN.json --owner-receipt G:\PATH\TO\DISPATCH_EARLY_OWNER.json
```

Use literal existing input paths; output labels and the dispatcher owner path must match the reviewed allocation. The placeholder commands are not an admission. Outputs BUNDLE.json and REVIEW.json contain private configuration and source pins, never public media. Do not run the old closed dispatchers or call the native qualification entry manually. The two-session button driver is automatic and must only be selected by a fresh explicit quiet qualification admission; it is not a persistent user launcher.
