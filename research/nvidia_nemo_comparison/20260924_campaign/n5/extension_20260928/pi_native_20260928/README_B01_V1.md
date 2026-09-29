# Native B01 shared-application preparation and short probe

Purpose: reuse the exact panel-journal-v1 shared application source on the Pi and test Sherpa ASR + Nemotron D1 + ReDimNet together through the actual controller. Existing separate-component passes do not prove simultaneous memory fit or worker drainage. This is a constructed 12-second saved-input diagnostic, not a real-world recording, accuracy score, GUI test or accepted release. No live capture or playback occurs. Keep the installed rc5 application/data/autostart unchanged.

`build_shared_app_bundle_v1.py` reads the pinned parent DERIVATIVE.json, verifies all392 source files (4,767,304bytes), and creates a fresh source-only tar.gz plus JSON hashes. No models, transcripts, profiles or unlisted directory contents enter the archive. Application code is unchanged. Run after the host census verifies the existing output reservation; it pins itself to host CPU14.

## PowerShell / Anaconda PowerShell: prepare source

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B build_shared_app_bundle_v1.py --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\derivatives\panel-journal-v1\DERIVATIVE.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\shared-app-v1\source.tar.gz
```

## CMD / Anaconda Prompt: prepare source

Use `cd /d` for the same working directory, then the same Python command without PowerShell's leading `&`. No activation/download/install is needed.

## Native bounded application check

First require independent V10 full-source/repeat/reference review and closed numerical owners. Transfer the source tar/manifest, verify archive paths and every source hash, and extract into fresh `~/JustPeachy/research/nemotron-20260928/shared-app-v1`. Stage `b01-short-v1` separately with this README, b01_native_short_v1.py, the exact first192000 PCM16 samples from the preserved source as prefix12.wav, and empty private data containing only a new n2_runtime.json. Bind the lane-preserving V4 native libraries and mixed-Q8 D1 weight by hashes; reuse existing installed Sherpa, ReDimNet and punctuation assets. No synthetic/personal gallery is copied. Caption/speaker evidence remains private.

Create a fresh ADMISSION.json with actual boot ID, expiry, prototype path and `files` rows of absolute path/SHA256 for the harness, README, prefix, runtime binding, all shared source files and every consumed model/library. Admit CPUs2/3, totalCPU200%, one native thread/model, 180seconds, hard768MiB virtual address space, tasks64, >=850MiB available RAM and >=5GiB disk before dispatch. Reserve16MiB new output within the existing combined cap. Do not remove the memory guard if the combined stack fails to fit; preserve that failure and design a bounded alternative. The code changes only its in-memory thread settings, selects explicit B01/anonymous_conversation/balanced, opens the saved file and retains original inference/drain gates. It imports tkinter but creates no Tk window and does not establish GUI behavior.

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-b01-short-v1 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-short-v1/b01_native_short_v1.py'
```

For CMD/Anaconda Prompt use double quotes around the remote command. For Linux terminal use the remote `systemd-run` portion directly. Outputs: OWNER.json, RESULT.json, FINAL_SNAPSHOT.json, PROGRESS.json and private application journals under data/. Success requires independent inspection of actual nonempty text, complete source/ASR/identity coverage, worker/drain/close behavior, explicit backend, model load counts and resource usage; a terminal success alone is insufficient. None of these saved-input checks yields WER/DER or establishes personal naming. Full-source integrated pacing, GUI modes/save/reopen/delete/error recovery and sustained native validation remain separate gates. This harness is not a user-ready application launcher.
