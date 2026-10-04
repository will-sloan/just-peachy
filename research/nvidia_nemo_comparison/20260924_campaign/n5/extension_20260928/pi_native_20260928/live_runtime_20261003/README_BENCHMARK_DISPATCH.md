# Native component dispatch

`launch_benchmark_action.py` is an injected action for `host_operations.py`, not
a standalone host script. It verifies every immutable staged package member,
the saved WAV, current boot, free storage and full current owner inspection,
then starts one finite user service. It does not launch the GUI, capture audio,
change desktop shortcuts, or qualify a complete pipeline.

Input is a private JSON payload with `boot_id`, `expires_unix` (fresh <=600s),
`package`, `package_manifest_sha256`, `input`, `input_sha256`, unique `label`,
`profile`, `maximum_output_bytes=8388608`, and explicit optional boolean
`experimental`/`wall_paced`. The ordinary short-test allocation is 8 MiB on the
Pi plus an independent 8 MiB PC copy. With explicit `native_timing=true`, set
`maximum_output_bytes=41943040`: the additional 32 MiB independently reserves
one combined C stdout/stderr log bounded by RLIMIT_FSIZE. OS file descriptors
capture the existing `NEMO_SPEECH_TIMING=1` phase diagnostics; Python stdout and
stderr still have separate 64 KiB bounds. All log bytes remain private and are
included in the complete closed-file mirror. Neither is an hour-soak admission.

The service has CPU2/3, aggregate 200%, Tasks64, 768 MiB AS, 1 MiB stack,
32 MiB per-file limit, 470s alarm, 480s unit lifetime and 15s stop grace.
The actual benchmark verifies its own unit membership and RAM/disk floors.
One process records early identity, holds research and hardware exclusion locks,
runs the pinned benchmark, and retains a durable `JOB_EXIT.json`. Output contains
bounded stdout/stderr, exact argument/admission/source provenance and benchmark
records. Natural completion still needs independent exact owner/cgroup closure
and a complete hash-verified PC copy. A returned launch receipt is not success.

PowerShell (set `$n` to this directory and use a freshly prepared payload):

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$n/host_operations.py" --label chunk52-launch-01 --action "$n/launch_benchmark_action.py" --payload 'G:/PRIVATE/FRESH_PAYLOAD.json' --writes
```

Command Prompt / Anaconda Prompt (set `N` to this directory):

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\host_operations.py" --label chunk52-launch-01 --action "%N%\launch_benchmark_action.py" --payload "G:\PRIVATE\FRESH_PAYLOAD.json" --writes
```

The wrapper registers the CPU14 host owner and verifies independent source
backup/restore before SSH. All labels and native output paths are single-use;
failed runs are preserved. Reuse the WAV bytes, not a consumed run directory.

For the separately reviewed two-thread build, add both `native_variant` and
`native_variant_sha256` to the payload with `profile=chunk52` and
`experimental=true`. The action verifies the isolated descriptor path/SHA and
passes both flags to the child, which checks complete source/build/dependency
provenance before loading. See [README_NATIVE_VARIANT](README_NATIVE_VARIANT.md).
Omitting both retains the ordinary pinned core; the UI is unchanged.
