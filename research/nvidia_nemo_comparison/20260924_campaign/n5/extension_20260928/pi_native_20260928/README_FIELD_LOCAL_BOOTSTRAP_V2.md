# Manager bootstrap V2 execution index

Read [V1 purpose, inputs, outputs, API and native limits](README_FIELD_LOCAL_BOOTSTRAP_V1.md). Selected runtime preparations remain field_local_auxiliary_v1, field_local_manager_bootstrap_v1 and field_local_manager_export_v2. All are native-unexecuted. Current changed host check is check_field_local_bootstrap_v2.

The first host check correctly encountered the old ASCII-header receiver rejection, but its test harness omitted HostBudgetError from expected rejection types. The whole check therefore failed before RESULT. Preserve bootstrap-check-v1 and its owner; no native work occurred. V2 adds only the explicit expected HostBudgetError type/import and this README link, using a fresh output.

PowerShell:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\check_field_local_bootstrap_v2.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\operator-local-bootstrap-v1-preparation\bootstrap-check-v2'
```

CMD and Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B check_field_local_bootstrap_v2.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\operator-local-bootstrap-v1-preparation\bootstrap-check-v2
```

Do not rerun a consumed passing check. Input is the exact prepared source graph; output contains actual host process identity, graph pins, changed protocol results and explicit fixture/native limitations. No SSH or admission is issued. The current actual receiver/closure host wrapper and joint dispatcher still need implementation before any native use.

