# Broker qualification V5 session identity correction

Selected parent V10 uses the exact broker-root basename plus slot (for example field-operator-sessions-v3-slot-01) as the independent Registry request ID. The Registry regex and all retained mode/asset/endpoint checks remain unchanged. Parent OWNER is now published after admission/CPU/AS/broker identity checks and before file/Registry validation, so a later validation failure has a recorded identity. The one ACK remains required before constructors or child launch. No rejected mutation is retried.

The earlier native field-operator-sessions-v2 attempt created the actual broker, acknowledged it and invoked one visible New control. A complete fresh first recording capsule and RESERVED/STAGED ledger records were written. The parent rejected seven-character slot-01 before publishing OWNER; no installed Field/UI child, source, model or capture started. Broker/gate cleanup and full 145-file, 956760-byte mirror passed. This whole attempt remains FAILED; the parent's exact PID/start ticks were not recorded, and are not fabricated from process termination. Its preserved incomplete slot blocks reuse.

Selected chain: build_field_operator_broker_bundle_v3 -> admit_field_operator_broker_v2 -> dispatch_field_operator_broker_v4 -> gate V5 -> entry V3 -> broker V4 -> parent V10 -> unchanged qualification child entry V8. Chooser V3, stage V2, two-session driver V1, child driver V3 and full receiver/exporter V2 remain. Capsule64/2MiB/member128KiB, independent slots, source/model ownership, ACK barriers, actual controls and all cleanup/resource limits are retained.

README V4 covers builder purpose/config correction; V3 covers measured single-attempt policy and private output/backup/restore; V1 covers quiet qualification and host partial-backup scope. Use these selected filenames in those commands.

PowerShell with $src as README V1:
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$src\build_field_operator_broker_bundle_v3.py" --plan 'G:\PATH\CLOSED-V123-PLAN.json' --projection 'G:\PATH\CLOSED-V126-PROJECTION.json' --owners 'G:\PATH\FRESH-EXTRA-CLOSURE.json' --output 'G:\PATH\FRESH-BUNDLE'
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$src\admit_field_operator_broker_v2.py" --bundle 'G:\PATH\BUNDLE.json' --census 'G:\PATH\HOST_CENSUS.json' --resources 'G:\PATH\NATIVE_RESOURCES.json' --closure 'G:\PATH\NATIVE_CLOSURE.json' --extra 'G:\PATH\EXTRA_OWNER_CLOSURE.json' --output 'G:\PATH\FRESH-ADMISSION' --root-name field-operator-sessions-vN
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$src\dispatch_field_operator_broker_v4.py" --plan 'G:\PATH\FRESH-ADMISSION\PLAN.json' --owner-receipt 'G:\PATH\FRESH-ADMISSION\DISPATCH_EARLY_OWNER.json'

Command Prompt / Anaconda Prompt in the source directory:
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B build_field_operator_broker_bundle_v3.py --plan G:\PATH\CLOSED-V123-PLAN.json --projection G:\PATH\CLOSED-V126-PROJECTION.json --owners G:\PATH\FRESH-EXTRA-CLOSURE.json --output G:\PATH\FRESH-BUNDLE
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B admit_field_operator_broker_v2.py --bundle G:\PATH\BUNDLE.json --census G:\PATH\HOST_CENSUS.json --resources G:\PATH\NATIVE_RESOURCES.json --closure G:\PATH\NATIVE_CLOSURE.json --extra G:\PATH\EXTRA_OWNER_CLOSURE.json --output G:\PATH\FRESH-ADMISSION --root-name field-operator-sessions-vN
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_operator_broker_v4.py --plan G:\PATH\FRESH-ADMISSION\PLAN.json --owner-receipt G:\PATH\FRESH-ADMISSION\DISPATCH_EARLY_OWNER.json

Replace placeholders with actual reviewed input paths and an unused positive integer. A new failed root is never reused. Native qualification is still OPEN until actual evidence passes; no source-only readiness or physical touch/accuracy/offline claim is made.
