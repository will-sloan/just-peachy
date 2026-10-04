# Explicit continuous saved-component hour soak

`launch_soak_action.py` is injected through the separately guarded
`host_operations.py`; it is not a standalone host or native program. It prepares
one explicitly reviewed native Nemotron component run, using one native instance
and continuous sample offsets for at least3600 seconds of replayed saved audio.
Repetitions have recorded provenance and do not reset native state. This measures
the diarizer component. It does not run ASR, embeddings, capture, GUI or a combined
pipeline, and launch/completion alone does not establish quality qualification.

Inputs: schema `just-peachy.v29.saved-component-soak-admission.v1`, `reviewed:true`,
nonempty `reviewer`, current `boot_id`, `expires_unix` within600 seconds, immutable
`package` and `package_manifest_sha256`, exact `input`/`input_sha256`, unique simple
`label`, selected `profile`, explicit boolean `experimental`, `developer_soak:true`,
`wall_paced:true`, `duration_seconds`, equal `repeat_seconds`, `block_samples`,
`drain_seconds`, `backlog_seconds`, `maximum_output_bytes:268435456`, and
`independent_pc_copy_bytes:268435456`. Input is an existing mono PCM16/16kHz WAV
under the current native campaign, at most32 MiB; no implicit conversion occurs.

An explicitly selected isolated thread variant additionally requires both
`native_variant` (the exact existing job's `RUNTIME_VARIANT.json` path) and
`native_variant_sha256`. The profile must be `chunk52` or `chunk52_threads2` with
`experimental:true`; the chosen immutable package must support that profile.
The action validates the descriptor path and hash, then forwards the exact pair
as `--native-variant PATH --native-variant-sha256 SHA256` to the benchmark.
The benchmark re-verifies the complete isolated build/library provenance before
loading any model. An incomplete pair, other profile or changed descriptor fails;
no supplied descriptor enables a general library-path override. The reviewed
payload and resulting plan retain both pins. CLI wrapper commands below remain
the same; add these fields to the separately reviewed JSON payload.

Recommended explicit hour geometry is duration/repeat3600, block3200 samples
(200 ms), drain600, backlog600, and profile `current_delayed`. Its benchmark plan
allows57,600,000 source samples,360,001 probability frames and18,001 push/finish
records, totaling161,081,376 reserved benchmark bytes. The action additionally
reserves a complete32 MiB C diagnostic file and2 MiB for bounded Python logs and
receipts, all within256 MiB. A100 ms block plan exceeds the allocation and fails;
it is never silently downsampled or truncated. Different durations/profiles need
their own exact explicit payload and must pass the same plan calculation.

The host dispatcher checks independent PC copy space above the existing C:50 GiB
and G:75 GiB floors before SSH. The native metadata helper remains CPU3/128 MiB.
It verifies every package/input byte and a full native256 MiB reservation above
the existing5 GiB disk floor. The model service is independently created with
AllowedCPUs2/3, aggregate200%, Tasks64, 768 MiB AS,1 MiB stack and32 MiB per-file
limit. Thread environment limits equal1. The actual main owner is recorded before
project reads, and model imports wait for external verification of exact owner,
unit, InvocationID, cgroup and resource properties. Research/hardware exclusion
leases are held for the continuous run; no hardware is opened.

RuntimeMaxSec is SessionPolicy.total_deadline_seconds plus150. The wrapper alarm
is30 seconds earlier, and systemd stop grace is30 seconds. Thus work, model load,
explicit drain, policy cleanup and wrapper closure are finite and separately
accounted. The benchmark retains its own RAM/disk/backlog/deadline checks. A hard
timeout preserves prefixes and cannot produce a successful completion claim.

Outputs are `ADMISSION.json`, pinned `wrapper.py`, early `OWNER.json`,
`UNIT_OWNERSHIP.json`, `LAUNCH_UTILITIES.json`, `JOB.json`, bounded Python/C logs,
segmented benchmark probabilities/timings, and durable `JOB_EXIT.json` on natural
wrapper exit. A returned job means launched, not completed. Use the existing
read-only monitor to prove actual owner/cgroup closure and independently mirror
all regular output files. The monitor accepts256 MiB and streams <=1 MiB segments
in16 KiB frames, with15-second native helpers. It never signals the job.

## Preparation and execution interfaces

PowerShell, using the existing environment and a fresh reviewed payload:

```powershell
$N = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$Q = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$N/test_native_scope.py" --output-root "$Q/audit-preparation"
# These two commands are execution interfaces, not actions performed by authoring.
& $PY -B "$N/host_operations.py" --label delayed-hour-launch-01 --action "$N/launch_soak_action.py" --payload 'REVIEWED_FRESH_SOAK_PAYLOAD.json' --writes
& $PY -B "$N/monitor_native_job.py" --job 'ACTUAL_RETURNED_JOB.json' --output "$Q/delayed-hour-monitor-01" --copy-deadline-seconds 3600
```

Command Prompt or Anaconda Prompt:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%N%\test_native_scope.py" --output-root "%Q%\audit-preparation"
"%PY%" -B "%N%\host_operations.py" --label delayed-hour-launch-01 --action "%N%\launch_soak_action.py" --payload "REVIEWED_FRESH_SOAK_PAYLOAD.json" --writes
"%PY%" -B "%N%\monitor_native_job.py" --job "ACTUAL_RETURNED_JOB.json" --output "%Q%\delayed-hour-monitor-01" --copy-deadline-seconds 3600
```

Use the actual reviewed payload and returned job paths; neither is fabricated by
this script. Host checks register CPU14 before imports and test pure plan bounds
and wrapper compilation only. They run no native model, service or SSH command.
Existing snapshot packages remain immutable; changed benchmark/source bytes need
a freshly staged build before they can be selected for the soak.

## Proposed hour comparison with the measured thread-two build

Use `profile:chunk52`, `experimental:true`, and the paired native variant below
for a component-only run on an existing reviewed package that supports the pair:

```json
{
  "native_variant": "/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/native-threads2-build-01/RUNTIME_VARIANT.json",
  "native_variant_sha256": "3fdb0a0699e06a0608ca6cf5676676e3416bf291398271ebd3fd9a5bca41bc57"
}
```

The exact44.6954375-second measured comparison completed715,127 samples and4,470
frames with zero maximum absolute difference from its same-geometry numerical
reference. That short result supports choosing this comparison; it does not
qualify an hour, combined ASR/embedding operation or diarization accuracy.

For duration/repeat3600, block3200, drain600 and backlog600, the existing plan
reserves161,081,376 benchmark bytes plus35,651,584 wrapper/log bytes, totaling
196,732,960 bytes. Native output and its independent PC mirror each reserve
268,435,456 bytes. Native free space must remain above5 GiB; the PC dispatcher
also preserves C:50 GiB and G:75 GiB. The input is repeated explicitly with one
continuous native state; it is not60 minutes of new speech material.

The complete policy deadline is4,380 seconds:3,600 source,120 model loading,600
drain and60 cleanup. Systemd has4,530 seconds, wrapper alarm4,500, and stop grace30
(at most4,560 seconds through the independent service stop boundary). The CPU
budget is8,760 seconds across the allowed two CPUs. AS remains768 MiB, stack1 MiB,
Tasks64 and aggregate CPU200%; the pre-exec allocator policy is restored. These
are finite resource ceilings, not predictions of actual memory or completion.

Current implemented physical-memory gates require at least850 MiB available RAM
before native loading and stop below192 MiB during guards. RSS/PSS, virtual peak,
swap and system available memory remain distinct recorded values. A stronger
proposal for review is `MemoryMax=768MiB`, `MemorySwapMax=0`, and admission available
RAM at least1,088 MiB (768 service +128 metadata helper +192 preserved floor).
Those additional cgroup/threshold settings are not implemented or authorized by
this document; the action must gain and verify them before an admission claims
they apply. Neither proposal raises RLIMIT_AS or assumes the device has spare RAM.

Do not turn a draft into an issued admission from historical measurements. First
obtain a fresh idle native ownership/resource baseline, exact boot, selected
immutable package/manifest, input and variant pins, and full native/PC reservation
evidence. Then supply `reviewed:true`, the reviewer, and expiration within600
seconds in the schema described above. Existing commands execute only that fresh
reviewed payload. A draft with null boot/time/package and `reviewed:false` must
fail and must never be submitted as a launch request.
