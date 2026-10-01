# Host broker transport boundary check

Purpose: run only three changed host subprocess cases for field_operator_broker_host_v2: exact20,480-byte echo,128-byte stdout quota with actual4096-byte output, and a50ms phase deadline. Each fixture writes its exact CPU14 PID/create-time owner before work; the runner checks reaping and reader completion. No Pi/GUI/audio/model is used. This does not validate native Stop, SSH loss, kernel quotas or full broker operation.

Inputs: a fresh absent private output path and a future UTC expiry within600seconds. Outputs: runner and three fixture owner records plus RESULT.json (<16KiB). Keep total within the containing2MiB host scope. Do not rerun the healthy cases merely for a version change.

PowerShell:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928\check_field_operator_broker_transport_v1.py' --output 'FRESH_PRIVATE_OUTPUT' --expires-utc 'FRESH_ISO_UTC_EXPIRY'
```

CMD / Anaconda Prompt:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928\check_field_operator_broker_transport_v1.py" --output "FRESH_PRIVATE_OUTPUT" --expires-utc "FRESH_ISO_UTC_EXPIRY"
```

The placeholders must come from a current bounded preparation scope. Source must have an exact backup and independent restore copy before use. See README_FIELD_OPERATOR_BROKER_DISPATCH_V2.md for the separate native dispatch design and open gates.
