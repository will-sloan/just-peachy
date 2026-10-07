# Owned native job monitor and full output mirror

The external monitor also accepts an explicitly reviewed optional live300
follow-up. Only `optional-followup-NN` with its exact matching unit,
`workflow=optional-followup-live-policy`, runtime840, duration300, 256 files and
an interval of at most885 seconds can use its computed output reservation.
`JOB.output_plan` must match the complete default StoragePolicy calculation,
including primary, optional and outer trace allocations; the independent PC
copy must equal that total. Raw+processed requires330,610,984 bytes. The external
limit is512 MiB; all ordinary jobs retain their256 MiB ceiling. This gate does
not issue an admission or modify the frozen runtime package. Use the same
PowerShell/CMD/Anaconda monitor command below with the actual follow-up JOB and
a fresh output directory; inputs/outputs and closure rules are unchanged.

`monitor_native_job.py` monitors one explicitly launched job. It never starts,
renews, stops or kills a native model or service. It uses strict SSH with the
existing user key and known-host verification, hostname `raspberrypi.local`, and
the pinned address/host-key alias `192.168.2.57`. The only remote helper is the
read-only `native_job_probe.py`; it does not run the old full campaign inspector.

Inputs are a reviewed `JOB.json` and a fresh private host output directory under
`B/live-runtime-20261003`. The job schema is
`just-peachy.native-component-job.v1`, containing `boot_id`, exact `unit`,
`invocation_id`, original `control_group`, `owner` (actual PID/start ticks/boot,
or null pending recapture), `output_root`, `maximum_output_bytes`,
`package_manifest_sha256`, `issued_unix`, and `deadline_unix`.
The native output root must be a single fresh child of the current iteration's
`live-runtime-tests-20261003` directory. An absent job owner cannot be certified
until its actual early `OWNER.json` is recaptured. The optional durable
`JOB_EXIT.json` is retained and checked against the bound identity fields.

The host first pins CPU14 and writes numeric early registration. Before SSH it
saves and independently reads back two copies of the job, host runner, and native
probe. It preserves the existing C: 50 GiB and G: 75 GiB host free-space floors.
Each native probe pins CPU3, 128 MiB address space, 1 MiB stack, zero filesystem
write size, no core dump and a 15-second alarm, then emits its actual early owner
before project reads. Short directly owned `systemctl` utilities are naturally
reaped and their exact owners checked. The helper only queries the exact unit
and competing active project unit names; it does not stop anything.

While active, only status is copied. A full mirror requires the original cgroup
empty/absent and the exact actual owner gone on the same boot. It inventories all
regular single-link files, up to 256 files and the explicit byte reservation
(8 MiB is a useful first-job reservation; long-run jobs may explicitly reserve
256 MiB with `maximum_output_bytes:268435456`). No implicit reservation increase
occurs when a job exceeds its declared cap. Transfer frames carry at most 16 KiB
of source bytes. Every file's source inode/device/timestamps/extent and SHA256
are checked before and after transfer; membership is rechecked after the full
copy. A catalog hashes the closed source before transfer. Each read-only call
then transfers at most1 MiB from one pinned file at an explicit source offset;
the first segment is64 KiB and later sizes use measured successful SSH/reap
throughput, targeting6 seconds and capped at1 MiB. Every call retains the native
15-second alarm; it is never raised speculatively. Segment identity and digest
are checked with a separate PC readback. Each complete PC file is independently
rehashed, and a final complete source catalog must match the initial one. Thus a
large file does not need to fit in one native alarm. Catalog hashing itself must
still finish within15 seconds or fail closed. Truncation, missing
files, changed membership, cursor errors, and digest mismatches prevent a success
receipt. The mirror's explicitly declared scope is all regular output files;
empty directories are not copied or certified. Directory traversal is bounded
to 256 directories, and symlink/special output entries are rejected. A failed
copy remains as partial evidence and is never called complete.

The actual native `NATIVE_OWNER.json` is persisted as soon as the early frame
arrives, including when later status or transfer fails. Each SSH session has
bounded readers, a natural wait/reap requirement and bounded
stderr. After the probe's natural SSH exit, a separate read-only `/usr/bin/test`
checks that its actual PID is absent. PID reuse fails conservatively. A timed-out
host SSH child may be reaped, but that phase cannot certify closure. No native
target is signaled. The monitor is finite (1024 status probes and a finite copy
deadline, default1800 seconds after the later of host start/job deadline).
It never extends the native compute deadline. `--copy-deadline-seconds` explicitly
sets a60–7200 second closure/copy allowance; native calls remain15 seconds each.

Outputs include `REGISTERED_OWNER.json`, source backups, per-probe actual owners,
status/SSH closure receipts, `closed-output/`, `MIRROR_MANIFEST.json`,
`MIRROR_COMPLETE.json`, and `RESULT.json`. Complete output copying is distinct
from model success; a nonzero or absent durable job exit remains visible.

## Host commands

In PowerShell, use the existing interpreter. Choose a fresh output name each run:

```powershell
$N = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$Q = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$N/test_job_monitor.py" --output-root "$Q/audit-preparation"
& $PY -B "$N/monitor_native_job.py" --job "$Q/chunk52-01-JOB.json" --output "$Q/chunk52-01-monitor-01"
```

In Anaconda Prompt or Command Prompt, no environment package changes are needed:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%N%\test_job_monitor.py" --output-root "%Q%\audit-preparation"
"%PY%" -B "%N%\monitor_native_job.py" --job "%Q%\chunk52-01-JOB.json" --output "%Q%\chunk52-01-monitor-01"
```

Append `--status-only` for one capped status probe without full output transfer.
`--poll-seconds` accepts 1–30 seconds (default 5). For a job already explicitly
reserved at256 MiB, a long-copy command may append `--copy-deadline-seconds 3600`.
Changing the allowance does not change the job's byte reservation.
These monitor commands perform
SSH only when explicitly run; authoring these scripts and running their synthetic
tests does not contact the Pi. `test_job_monitor.py` checks multi-chunk digest and
PC readback, segmented prefix offsets/readback, the explicit256 MiB ceiling,
catalog byte mismatches, traversal rejection, and bad cursor/hash refusal without SSH/native
execution. Its unique CPU14 receipt directory is printed at completion.

GUI qualification exception: only output root live-runtime-tests-20261003/gui-qualification-NN paired exactly with jp-v29-gui-qualification-NN.service, with a finite <=1545-second job interval, may reserve up to1GiB and1024 regular files/directories. The explicit GUI dispatcher computes490,353,232 bytes for processed-first plus replay, or567,398,992 with separately qualified raw. Catalog wire budget is2MiB for this bounded1024-entry case; each native helper remains15seconds and may safely refuse if storage cannot finish hashing within that bound.

Full-application hour exception: only exact `full-app-hour-NN` root/`jp-v29-full-app-hour-NN.service`, workflow `continuous-full-application-repeated-wav`, duration/repeat3600, maximum_output_files2048 and job interval<=4725s may use the3GiB ceiling. Actual bytes remain explicitly derived/admitted. Its catalog is identity-only (sha256:null, hash_mode:streamed_segments), with4MiB bounded catalog wire output. It avoids one multi-gigabyte full-tree hash under the15s helper alarm. Each contiguous segment still supplies native SHA and independent PC readback; the complete-file PC hash is recorded separately with honest provenance. Before/after source membership/identities and exact closure must match. All other jobs retain256MiB/256. See `README_FULL_APP_SOAK.md` for the independent reservations and commands. No native/SSH behavior runs during protocol tests.

## External sampled whole-unit memory

The optional `--sample-memory` flag is an external read-only monitoring derivative;
immutable build08 is unchanged. It samples only the exact verified service cgroup,
with at most64 processes/directories and bounded procfs reads. Each process binds
PID/start ticks before and after RSS/PSS/VM/VmPeak/swap reads; changed or unreadable
owners make `complete_process_sample=false`. System MemAvailable/MemTotal/swap and
temperature accompany the sample. No models, capture or native files are modified.
The existing CPU3/128MiB/1MiB stack/FSIZE0/15s helper envelope stays unchanged.

Polling becomes at least15seconds plus helper/SSH time. `SAMPLED_MEMORY.jsonl` is
an independently bounded1MiB host aggregate trace; full bounded per-process rows
remain in each probe's STATUS.json. Values are sampled observations, not a
continuous peak; a monitor started after launch misses earlier activity. Never
repeat a healthy session merely to erase this coverage limitation. Complete native
output mirroring and exact closure checks remain unchanged.

PowerShell (use actual existing JOB and a fresh output path):

    & $PY -B "$N/monitor_native_job.py" --job "$Q/gui-qualification-02-JOB.json" --output "$Q/gui-qualification-02-monitor-01" --sample-memory

CMD or Anaconda Prompt:

    "%PY%" -B "%N%\monitor_native_job.py" --job "%Q%\gui-qualification-02-JOB.json" --output "%Q%\gui-qualification-02-monitor-01" --sample-memory

Host-only focused owner/readback check, after the script's early CPU14 owner:

    & $PY -B "$N/test_job_monitor.py" --output-root "$Q/audit-preparation" --checks test_sampled_memory_exact_members_and_reused_owner_exclusion

Use the same quoted executable/paths and arguments in CMD or Anaconda Prompt.
