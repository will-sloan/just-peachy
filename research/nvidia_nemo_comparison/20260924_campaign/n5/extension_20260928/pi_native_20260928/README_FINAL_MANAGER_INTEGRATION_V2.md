# Final manager integration V2

F04 selected entry: [V1 purpose, inputs, outputs and PowerShell/CMD/Anaconda instructions](README_FINAL_MANAGER_INTEGRATION_V1.md). New current-boot broker backup derivatives are field_operator_broker_census_v3.py, field_operator_broker_export_v3.py and mirror_field_operator_broker_v3.py. Their exact previous census/export/stream/readback bodies remain; baseline checks bind1008/start476 and1124/start514 on the admission's observed boot. Hard deadline is16:14:58Z. These helpers are for this current-boot qualification, not a reboot-capable production launcher.

The receiver uses the explicit broker HostStore partition: metadata768KiB/per-file256KiB, failure256KiB/per-file128KiB, closure128KiB/per-file64KiB plus four64KiB directories and one lock byte=1441793 bytes, within the original shared4MiB host metadata allocation. The complete one-broker target mirror reservation remains151114284 bytes and its original155308588-byte host reservation is retained. The joint dispatcher must enforce all four partitions before using the remaining bytes for manager/master/closure; this receiver alone does not issue a new resource policy.

PowerShell (in the V1 directory):
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B mirror_field_operator_broker_v3.py --help
```
CMD and Anaconda Prompt:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B mirror_field_operator_broker_v3.py --help
```

Actual invocation requires --admission NEW_PINNED_ADMISSION --output NEW_PRIVATE_PATH --owner-receipt NEW_EARLY_OWNER_PATH. The admission must include current boot, exact entire native census, complete module pins including exporter3, full reservation and remaining cleanup time. The census and exporter are injected APIs, never directly invoked against expired/consumed roots. Native execution remains unqualified until an actual receipt exists. No new capture occurs merely by preparing this path.

