# Offline runtime policy V2

Purpose: connect the F04 production broker to the actual persistent F05 policy and immutable recording reservation. Every V1 function is retained with identical AST. See README_FIELD_RUNTIME_V1.md for original purpose, profiles, input/output fields and finite resource/storage rules.

New pure API `validate_broker_policy(value, runtime, operation, now=...)` requires an exact production schema, complete independent allocation, the runtime and operation SHA256s, selected profile, source root, boot owner and600-second interval. `load_broker_policy(value, now=...)` reads the actual pinned runtime control/RELEASE.json and recordings/recording-NN/RESERVED.json with exact membership/type/link/size checks, strict JSON, stable file identity and canonical real ancestors. It does not issue an admission, write a file, refresh old expiry or turn saved-only modes into live ones.

The production capsule adapter must replace the old broker's validate_policy function with `load_broker_policy`, retain the remaining source functions unchanged, include this module and its pinned dependencies within the original64-member/2MiB caps, and bind fresh current native state. No old source or consumed capsule is changed. The actual adapter/launcher is still under integration; this library is not independently deployable.

There is no direct Pi CLI. Host verification uses `check_field_runtime_broker_policy_v1.py --output NEW_PRIVATE_DIRECTORY` after complete source backup/independent restore. Its output is a bounded RESULT plus early CPU14 owner. It exercises only the new pure binding cases with explicit synthetic policy/identity facts; no native process or copy credit.

PowerShell (from this README's directory):
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./check_field_runtime_broker_policy_v1.py --output 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/deployable-runtime-resume-v1/broker-policy-check-v1'
```

CMD / Anaconda Prompt:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B check_field_runtime_broker_policy_v1.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\deployable-runtime-resume-v1\broker-policy-check-v1
```

Use a fresh output once; failed outputs and all V1 sources/results remain immutable. Do not rerun the passed V1 policy suite just because V2 exists.
