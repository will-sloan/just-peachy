# Offline B01 candidate: package and installation boundary

Purpose: create a versioned source-only candidate from the V54 qualified application and isolated source components, using the existing integrity-checked release manager. Execute actual native build/stage/asset health/installed controller initialization, isolated candidate activation and rollback. No microphone, model inference, visible GUI, playback, enrollment, downloads or original-baseline activation occurs in this protocol. This is a new packaging boundary, not an unchanged model/capture rerun.

Inputs: immutable b01-isolated-quiet-v1 prototype and independent review, original installed runtime and hashed model store, current delayed D1 runtime/model paths, installed live configuration, authority and ALSA configuration. All source/model/config hashes are checked. The package contains code/config/notices only. Existing models/runtime are shared; D1 still uses recorded research asset paths. There is no asset relocation or self-contained model bundle claim. Missing/changed dependencies fail health explicitly; no download or silent backend fallback.

New field_entry_v1 is the installed main entry point. Health verifies the release, offline runtime and all assets. Controller-check initializes actual B01/Open with names/Balanced/O0 without loading models or opening capture, exposes unsupported backends, and rejects other recipes/spatial/enrollment explicitly. GUI code is prepared but not executed by this test; a future fresh launch admission must bind the release manifest/data root/quiet authority/expiry and native supervisor. It opens idle with original480x800 widgets, supplies isolated-source configuration, requests Stop at30seconds, and retains existing source Stop/drain semantics. Visible rendering, GUI controls, source limits and long-duration behavior of this new entry point require their own tests before use. Separate sequential ASR and B05 package integration remain unavailable; their older scoped tests are not transferred automatically.

Storage policy: fixed32GBPi/device31268536320bytes,>=5GiB free. Report unique asset inodes, shared runtime bytes, unpacked release sizes and two-version rollback storage. A proposed512MiB private-data quota with32MiB reserved before each session is enforced at Start; the current compact archive per-file/frame guards remain. No automatic deletion of old recordings or evidence. Float32 plusPCM16 for30seconds costs2880044bytes before events/metadata. The quota is not endurance acceptance. Real runtime/OS/shared asset use is already included in measured free space.

The native protocol builds v1a/v1b from identical candidate code, stages both under its fresh private research deployment, activates a then b and rolls back to a. It verifies synthetic private canary/config hashes and exact previous pointer. This tests the real release manager in an isolated installation, not switching or restoring the running rc5 app. It retains the deliberately damaged release used for a negative integrity check. Bad archive checksum and data-owner lock must reject before changing pointers. Models are referenced through one explicitly recorded deployment/models symlink; backups preserve the link target as metadata without copying weights or following the link.

Outputs: private source/release ZIPs/manifests, isolated installation/current/previous/history, exact source/config backups, dependency/storage census, installed health/controller stdout, child/worker owners and live resource envelope, RESULT and independent review/backup. Original source and baseline files remain unchanged. No field-release promotion follows from package PASS.

Envelope: WINDOW_V5,64MiB combined output reservation(32MiB target/32MiB host),52GiB total including target+2.5GiB reservations,5GiB combined window. Main/entrypoint child768MiB virtual,1MiB stack,CPU2/3 shared200%,Tasks64,one native thread/GPUoff. InitialRAM850MiB; aggregateRSS640MiB/availableRAM192MiB sampled stops. Service300s/Stop60s,entrypoint alarm60s/parent timeout70s,8MiB per-file. No OS/boot/swap or baseline pointer changes. No hardRSS/MEMCG claim.

PowerShell (fresh census under15minutes):
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_package_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V117.json
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_package_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V117.json
```

On the Pi, the installed candidate `main.py health` or `main.py controller-check --data-root PATH` must use the pinned offline Python and the same bounded supervisor; the protocol supplies exact commands and receipts. `main.py gui --data-root PATH --launch-admission FILE` is a prepared, unqualified path requiring a fresh admission; never invoke it using an old preview's flags. The internal package worker is not a standalone launcher. Run roots/admissions are exclusive; preserve failures and use fresh derivatives. Checkpoint October1 17:47:34UTC remains.
