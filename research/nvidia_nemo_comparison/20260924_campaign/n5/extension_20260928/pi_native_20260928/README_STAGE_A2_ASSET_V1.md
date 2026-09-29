# Stage the existing Nemotron English ASR asset on CM5

Purpose: copy the already-local, pinned 699,872,960-byte mixed-Q8 A2 model onto the Pi. This is asset staging only: no model load, transcription, microphone, playback, UI, download or original installation change. It does not qualify native A2 or B02. The unchanged source is SHA256 d9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d.

Inputs: fresh V2 host census, WINDOW_V2.json, pinned local asset, verified SSH identity, source/README hashes. Outputs: private target `a2-asset-stage-v1/A2.gguf`, admission/owner/result and host preflight/launch receipts. Failed transfers keep the partial file. The fixed run never overwrites an existing run.

The receiver holds the research and hardware leases while receiving, verifies exact boot/original app/owners/config/install, accepts precisely the expected bytes, checks SHA256 and atomically renames its own partial. It runs under systemd CPU200%, CPUs2/3, Tasks64, hard128MiB address space,1MiBstack,600s/10sstop; these are file-transfer limits, not model-inference limits. Reserve704MiB, count existing target bytes against both total/window ceilings, retain disk floors and at least850MiB available RAM. No original data or evidence is deleted.

PowerShell from the worktree, using a freshly recorded V2 host census:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/stage_a2_asset_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V35.json
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`, same command without `&`, double-quoted interpreter. Do not run `--receive` manually. The dispatcher supplies its target admission and service limits. An independent reader must rehash the staged file/source/admission, verify natural service exit, exact owner closure, both leases released, capture closed and original app/config/install unchanged before crediting staging. No numerical work should follow without a separate target-specific admission; D1-specific smaller runtime limits are not A2-qualified.
