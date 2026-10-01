# Changed runtime startup checks

Purpose: check the new F04 manager/broker startup ordering and the manager's stdout/stderr completion barrier. Inputs are the actual selected capsule V2 COMMON source and manager V1 poll method, extracted by AST. Native process identities/systemd output/backup callback are explicit fixtures. No native graph, systemd command, recording, physical closure or copy is executed.

Outputs: early CPU14 REGISTERED_OWNER.json and a bounded RESULT.json in a fresh private directory. The cases exercise manager-only staging, an active broker before OWNER publication, a published owner, and rejection of foreign/stale identities, wrong memory/slice/CPU/task limits and an unrelated active service. The actual poll method must consume both pipe EOFs before publishing helper EXIT or accepting a copy callback even if the child has already returned.

PowerShell from this README's directory:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./check_field_runtime_startup_v1.py --output 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/deployable-runtime-resume-v1/startup-check-v1'
```

CMD / Anaconda Prompt:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B check_field_runtime_startup_v1.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\deployable-runtime-resume-v1\startup-check-v1
```

Back up and independently restore selected sources before running. Use a fresh output once. This test does not rerun the old transport/mirror suites and does not make the runtime deployable.

