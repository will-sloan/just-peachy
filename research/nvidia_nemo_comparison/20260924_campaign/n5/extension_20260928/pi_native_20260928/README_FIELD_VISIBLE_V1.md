# Installed visible GUI and private archive diagnostic

Purpose: execute the installed V2 candidate's actual `field_entry_v1.main gui` branch on the Pi display. The diagnostic schedules inherited PrototypeUI actions; application code and installed files stay byte-identical. It opens the GUI, cancels the Start consent page without starting capture, inventories mode/backend controls, verifies controller rejection, and exercises copied-archive Open, visible 40-row rendering, Rename, Save, text Export and Delete. Pre-delete copied evidence is retained in a private ZIP; the original archive is hash-checked unchanged. Conversation import is absent and remains a delivery gap. Screenshots establish visible rendering only, never physical touch.

Inputs: fresh WINDOW_V5 census, reviewed installed `field-package-v2/deployment/releases/b01-offline-20260930-v1a`, V50 saved conversation `94f197604c2049cd8503fca89ac64933`, current authority and baseline hashes. No models, capture, playback, enrollment or downloads. One diagnostic UI subclass only schedules actions after normal construction; it does not override rendering or commands. Unsupported buttons are observed as defects rather than treated as available. Stop is not tested against an active source.

Outputs: private `field-visible-v1` target and host evidence, admission, actual unit envelope, action log, full-display PNGs, copied archive/export evidence, observed availability/layout gaps and closure. Functional observations do not establish full GUI acceptance, installed live operation, import support or field release. Maximum300seconds plus60seconds orderly stop, main768MiB AS,1MiB stacks, sharedCPU2/3/200%,Tasks64, sampled aggregate640MiB/available192MiB guards.64MiB combined reservation split32MiB target/32MiB host. Existing Pi32GB/5GiB floor and host52GiB total/5GiB output policy apply. Fixed run refuses overwrite.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_visible_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V120.json
```

CMD or Anaconda Prompt (the explicit interpreter needs no environment activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_visible_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V120.json
```

Use a fresh unused census if V120 is older than15minutes. No direct unsupervised GUI launch. Independent review and exact private backup follow before readiness credit; preserve failures in fresh versions rather than editing bound files.
