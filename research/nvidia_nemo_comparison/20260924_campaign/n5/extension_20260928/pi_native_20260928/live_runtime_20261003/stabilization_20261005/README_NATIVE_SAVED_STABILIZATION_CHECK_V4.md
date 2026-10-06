# Complete kept-recording replay with repaired storage

Purpose: exercise one selected backend through the retained six-profile chooser
and portrait application using one complete, pinned kept recording. V4 is a fresh
external check helper; V1–V3 remain immutable. It starts no physical microphone,
current BMI270, enrollment, playback or optional parallel refiner.

The common workflow, input fields and evidence meanings are documented in
[the V3 guide](README_NATIVE_SAVED_STABILIZATION_CHECK_V3.md). V4 preserves
actual History → Replay with selected backend, EOF/drain, Save or explicit
output-only Discard, exact shared source lease, original whole-tree pins, sample
count and final source verification. It supports the same six backend rows and
named/recorded-spatial Modes. An actual kept UUID and raw session.json SHA are
required; plain WAV input cannot substitute for rich recorded beam/BMI evidence.
No source samples are trimmed. Historical pose/beam/audio-callback anchors are
used in spatial Modes; current motion must remain false. Calibration/reference
changes, stale poses or missing anchors cannot invent a stationary speaker.

## Fresh admission

The source limit remains70s at16kHz and the UI driver remains240s. The actual
SessionPolicy total is370s; its unchanged150s reserve requires520s remaining
inside the540s shared unit. Stop remains30s. These are external check limits;
normal operator manual Stop is unchanged.

The selected build25 worker and helper now use an explicitly larger reserve:

```python
metadata_reserve_bytes = 2 * (16 * 1024**2 + seconds * 256 * 1024)
metadata_split = 'text1_sqlite1_v2'
terminal_metadata_reserve_bytes = 256 * 1024
```

At70s this gives35,127,296B text,36,175,872B SQLite and a separate262,144B
terminal pool. Complete processed/replay storage is78,371,636B; the retained
32MiB helper margin makes111,926,068B. Raw is not recaptured by Saved replay.
This repairs allocation planning; it is not native speech or quality proof.

Both `maximum_output_bytes` and `independent_pc_copy_bytes` must now be exactly
**268435456**, independently reserved256MiB each. Source tree readback is at
most256MiB, with the retained512 regular files/768 entries and32MiB per-file
ceilings. All other owner, resource, floor and membership checks remain.

Before creating a job, launch invokes the exact hash-pinned worker's unchanged
`file_size_plan` against current `recordings/history.sqlite3`. At70s its hard
per-file allowance is existing history bytes +151,519,232B. Existing history
must therefore be at most116,916,224B under this256MiB check. A larger current
history safely rejects and requires a separately measured fresh allocation;
no history is reset, deleted or granted unused-slot credit. Worker Start
rechecks its file plan. The admission records the observed current plan and
new storage spec, separately from later physical process/unit closure.

## Running and outputs

Do not run this helper directly or use bare SSH to activate it. Prepare a fresh
payload through `prepare_saved_stabilization_payload_v4.py`; see
[the preparer guide](README_PREPARE_SAVED_STABILIZATION_V4.md) for PowerShell,
CMD and Anaconda inputs. Native dispatch uses its emitted `command_argv` with
the selected `host_stabilization_operations_v2.py --writes` wrapper. Each
backend gets a fresh sequential admission after the preceding owners close.

For host source/pin/AST review, use a fresh directory:

```powershell
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$s/check_saved_stabilization_v4_source.py" --source $s --package-dir 'ACTUAL_HOST_BUILD25_PACKAGE' --package-manifest-sha256 ACTUAL_BUILD25_MANIFEST_SHA --output 'FRESH_PRIVATE_REVIEW_DIRECTORY'
```

CMD and Anaconda Prompt:

```cmd
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/check_saved_stabilization_v4_source.py" --source "%S%" --package-dir "ACTUAL_HOST_BUILD25_PACKAGE" --package-manifest-sha256 ACTUAL_BUILD25_MANIFEST_SHA --output "FRESH_PRIVATE_REVIEW_DIRECTORY"
```

The review registers CPU14/actual owner and backs/restores source bytes before
AST/pure calculators. It executes no GUI, microphone, native source or model.
Native output is the existing asynchronous JOB, private action/processing and
source-closing receipts, then independently finalized closure. Actual captions,
ASR/diarizer/embedding calls and cost are reported separately; an unlabeled
recording does not establish accuracy or sustainable real time. Complete
private PC hash/readback is required after each native job.
