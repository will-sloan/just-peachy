# Numerical/resource checks for the 2 MiB D1 metadata candidate

Purpose: requalify the independently reviewed metadata2 build before application use. Inputs are the immutable geometry harness, native-profiles-v2 adapter, original full saved file, D1 weights, lane-preserving A76 library, new D1 session library and same-geometry generic reference. The new session library SHA256 is `1639518a4de05caa1cf40feb3c9e4e2672cfe82fde87f79f707b115421cdb020`. See README_D1_METADATA2_V2.md for the build and preserved V1 compiler failure.

Outputs are a fresh private admission, input hashes, exact owner, call traces, probability arrays, metrics, RESULT and independent REVIEW. Full-source/repeat/reset/EOF, continuous source/frame mapping, finite probabilities, model closure and 1e-5 same-geometry parity remain unchanged. Inspect `[d1-metadata]` logs for actual metadata use; a build alone cannot qualify the smaller capacities. Only recipes actually reviewed qualify; these D1 capacities must not be applied to A2 ASR.

## PowerShell

From this report directory with a census less than 15 minutes old:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_d1_metadata2_geometry_v1.py --profile native_v3_delayed --kernel a76 --run-id d1-geometry-delayed-metadata2-v1 --reference d1-geometry-delayed-generic-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V10.json'
& $py review_geometry_v1.py --run-id d1-geometry-delayed-metadata2-v1
```

## CMD / Anaconda Prompt

Use `cd /d` to this directory, the same explicit quoted Python path, omit `&` and retain the arguments. No activation/install/download is needed. The dispatcher uses strict SSH stdin and the existing Pi Python under a fresh bounded systemd unit. Existing run paths are refused. The independent reader only runs after terminal closure; never edit bound inputs or shared ledgers.

Limits remain CPUs 2/3, total CPU 200%, one model thread, 64 tasks, 600 seconds, hard 768 MiB virtual space, 850 MiB available RAM and 5 GiB disk floors, plus 16 MiB reserved within the combined 1 GiB output allowance. Keep the original app/install and OS/swap unchanged. No capture/playback, training, enrollment, silence removal or accuracy scoring. Successful component evidence does not qualify an integrated mode or release.
