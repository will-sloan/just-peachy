# Native failed-start cleanup repair and B01 V3

The native B01 V2 app passed Sherpa loading with process-local MALLOC_ARENA_MAX=2 but approached the hard768MiB virtual-address limit and failed to create a worker. The failure path tried to create another cleanup thread under the same exhausted limit. It left an unstarted finalizer reference and live journal/policy workers. RESULT recorded controller_closed=false; the exact failed job was then stopped through its systemd unit. Preserve V1/V2 evidence. The original installed app was not stopped.

`prepare_startup_cleanup_v1.py` verifies the exact reviewed app/controller.py parent hash and emits a separate controller.py plus PATCH.json. It changes only the partial-start cleanup boundary: when the finalizer is absent or never started, retain all actually started workers, omit never-started Thread objects from joins, and execute the normal finalizer synchronously on the existing controller command worker. This avoids needing an extra thread to recover from thread exhaustion. It does not bypass finalization, declare live workers closed, drop audio, change inference/drain gates, or increase resources. All success-path code stays unchanged.

Inputs: original immutable controller.py; new empty output path. Outputs: patched controller.py and hashes. Apply only to a fresh copy/overlay of shared-app-v1, replacing the new controller inode so hard-linked parent files stay unchanged. Bind all resulting source hashes in a fresh admission. Retain previous failures. Test native failed-start cleanup using the same B01 V2 memory/allocator conditions; a cleanly closed failure is a shutdown regression result, not a functioning integrated mode.

## PowerShell / Anaconda PowerShell

From this README's directory:

```powershell
& C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B prepare_startup_cleanup_v1.py --parent G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\derivatives\panel-journal-v1\prototype\app\controller.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\startup-cleanup-v1
```

Use the strict identity in README.md to stage `shared-app-v2` with this overlay. The V3 harness is the V2 harness with versioned documentation only; use fresh `b01-short-v3` data/admission, the identical prefix/model/runtime inputs, prototype pointing at shared-app-v2/prototype, all prior exact owners closed and fresh memory/disk checks. No personal data/gallery is copied. Then:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-b01-short-v3 --wait --pipe --setenv=MALLOC_ARENA_MAX=2 -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-short-v3/b01_native_short_v3.py'
```

## CMD / Anaconda Prompt / Linux

Omit the leading `&` for the local Python command; use double quotes around the SSH remote command. No activation/install/download. On Pi use systemd-run directly. Preserve CPUs2/3, one thread/model, hard768MiB address space, >=850MiB available RAM, >=5GiB disk, no capture/playback and the original app. Outputs remain the V2-style private owner/result/snapshots/journals, including source-bound finalization receipts. Verify exact owner closure and actual writer closure; do not treat source preparation as acceptance. Later memory-fit and real app/GUI/paced/endurance tests remain required.
