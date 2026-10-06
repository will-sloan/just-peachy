# Read back the actual build26 desktop activation on the PC

Purpose: validate the real closed activation result, reconstruct its returned
before/restore/new desktop bytes with independent hash/readback copies, and change
the activation V4 README from pending to its actual result. No SSH, application,
capture or native mutation occurs. Immutable action V4 remains unchanged.

Inputs: `--result` must be the actual guarded activation26 `dispatch/RESULT.json`;
`--label` is a fresh private output label. Current boot, package26 manifest,
disabled-autostart SHA, one exact owned desktop path, prior build25 desktop SHA,
actual utility absence and all native transaction success fields must match.
The expected old desktop SHA is historical evidence; the native transaction
already freshly checked it before mutation. The reviewer does not invent a new
native observation or equate returned bytes with a complete native-tree mirror.

Outputs: fresh private CPU14/kernel-FILETIME owner and finite2MiB/600s scope,
including64KiB directory reserve; source/README/real receipt backups and independent
restores; before/restore/new desktop copies; updated public activation README;
compact RESULT and SOURCE_CLOSED. C50/G75GiB storage floors remain. Verify owner
absence after natural process exit. No private base64 or desktop content is printed.

PowerShell from this directory, only after the root activation wrapper is closed:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B './review_stabilization_activation26.py' --result 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/operation-stabilization-desktop26-01/dispatch/RESULT.json' --label activation26-pc-readback
```

CMD and Anaconda Prompt (same existing interpreter):

```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B review_stabilization_activation26.py --result "G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/operation-stabilization-desktop26-01/dispatch/RESULT.json" --label activation26-pc-readback
```

Use a fresh output label after any preserved failed review; do not rewrite closed
receipts. Source bytes and independent restore copies are saved before checks and
before the README update. This review adds no performance, accuracy or physical
testing claim.
