# Broker qualification V4 config correction

Selected builder: build_field_operator_broker_bundle_v2.py. V1 omitted the native gate's required python and alsa_config keys. Actual field-operator-sessions-v1 initialized, then gate failed with KeyError: alsa_config BEFORE launching a broker/app/capture. Its exact closed tree was backed up (70 files, 518072 bytes, 76 measured chunks). No failed bytes are edited and V1 is not retried.

V2 adds only the actual retained installed Python path and installed release's pinned config/alsa_hw_only_v1.conf. All capsule/child membership, source pins, mode Registry and live D1 binding checks remain. The gate still verifies actual envelope and baseline. README_FIELD_OPERATOR_BROKER_QUALIFICATION_V3.md describes the fresh issuer and README V2 the builder inputs/outputs; substitute build_field_operator_broker_bundle_v2.py in BOTH PowerShell and Command Prompt/Anaconda commands.

PowerShell (source path as README V1):
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$src\build_field_operator_broker_bundle_v2.py" --plan 'G:\PATH\CLOSED-V123-PLAN.json' --projection 'G:\PATH\CLOSED-V126-PROJECTION.json' --owners 'G:\PATH\FRESH-EXTRA-CLOSURE.json' --output 'G:\PATH\FRESH-BUNDLE'

Command Prompt / Anaconda Prompt, in the source directory:
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B build_field_operator_broker_bundle_v2.py --plan G:\PATH\CLOSED-V123-PLAN.json --projection G:\PATH\CLOSED-V126-PROJECTION.json --owners G:\PATH\FRESH-EXTRA-CLOSURE.json --output G:\PATH\FRESH-BUNDLE

Then use the V3 issuer/dispatcher commands with a fresh measured admission and unused root. No source change alone passes native qualification. No healthy host partial-backup/transport/history suite is repeated for this config-only correction.
