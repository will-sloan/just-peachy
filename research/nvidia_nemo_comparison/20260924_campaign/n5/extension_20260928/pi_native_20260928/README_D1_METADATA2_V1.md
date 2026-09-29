# D1 metadata reservation candidate

Purpose: investigate B01's native metadata allocation failure without raising the hard 768 MiB virtual-address cap. The previous D1 runtime reserves 8 MiB per metadata arena; tested graphs have at most 870 nodes. This fresh candidate reduces model/state and graph-probe metadata reservations to 2 MiB each and logs actual metadata usage. It retains allocation assertions, scheduler capacity 2,048 and its 95% guard, eight-entry executable-graph LRU, weights, kernels, speaker history and numerical computation. Capacity is a candidate until independently reviewed numerical and resource evidence exists. It is D1-only and must not be reused for A2 ASR.

Inputs: preserved metadata-native-v1 session source/runtime archive and manifest, d1-lru-build-v1 Sortformer object, original ARM64 objects/headers and source hashes. Outputs: a fresh native session.cpp, object/archive/library, compiler/link logs, BUILD_OWNER, BUILD_RESULT and stage-specific admission. No prior source or artifact is overwritten. Logging reports model, state template, session-state and graph-probe arena use; it does not log audio or identities.

`dispatch_d1_metadata2_build_v1.py` checks the research window, fresh comprehensive host census, exact closed host/Pi ownership, boot ID, original app identity, disk/RAM and combined output allowance. It stages `build_d1_metadata2_v1.py` and this README through strict SSH stdin, then runs a bounded systemd unit. Build success is not inference or application acceptance. Review the exact source diff and retained hashes, then use fresh full-source/repeat/EOF/reference checks before integrated trials.

## PowerShell

From this report directory, with a host census less than 15 minutes old:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_d1_metadata2_build_v1.py --run-id d1-metadata2-build-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V10.json'
```

## CMD / Anaconda Prompt

Use `cd /d` to this directory. Run the same explicit Python path in double quotes, omit `&`, and retain the arguments. No activation, installation or download is needed. Existing run names are refused, not overwritten. On the Pi the dispatcher uses the installed rc5 Python under systemd-run and taskset; do not run the build outside its bound admission.

Limits remain CPUs 2/3, total CPU 200%, one compiler at a time, 64 tasks, 600 seconds, hard 768 MiB virtual space, at least 850 MiB available RAM and 5 GiB disk before dispatch. The 16 MiB output reservation counts against the shared 1 GiB allowance. The pending 1 GiB application virtual-cap request is not authorization for this or any larger limit. Original rc5 app/install, OS, swap and personal data remain unchanged. No capture, playback, training, enrollment or accuracy scoring.
