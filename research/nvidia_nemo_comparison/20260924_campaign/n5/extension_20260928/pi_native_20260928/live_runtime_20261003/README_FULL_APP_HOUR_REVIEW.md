# Closed full-application hour review

`review_full_app_hour.py` performs a read-only PC review after the existing native monitor reports a complete closed mirror. It starts on CPU14 and durably records the actual host owner before project reads. It imports the existing `review_soak.Stats` accumulator and the storage event decoder; it starts no models, capture, SSH or device process.

Inputs are one `full-app-hour-NN` monitor directory and a private output root. The mirror must contain its complete manifest, result/closure, every regular output file, one SQLite session and the bounded whole-unit memory trace. Every file is hashed with streaming reads and the complete directory membership is checked. SQLite is opened immutable, read-only and query-only. Limits remain2,048 files/3GiB,6,000 health or memory rows,16MiB memory trace, bounded metadata and a2MiB numeric report. Caption revisions are decoded one at a time; words and speaker labels are never included in the report or stdout.

Outputs: fresh private directory containing actual owner, reviewed source backups/readbacks and `REVIEW.json`. It includes ten-minute worker/whole-unit RSS/PSS/available RAM/backlog/rolling diarizer RTF/temperature/CPU summaries, descriptive slopes after warmup, sample gaps, final clocks and drain, indexed caption/revision counts and approximate first-publication latency, SQLite allocation use, and exact completion gates. Startup and final drain have separate time bins. The stored rolling RTF describes diarizer pushes only; paced application wall duration is not compute RTF. Whole-unit RSS may double-count shared pages; PSS, per-process virtual address space and physical available RAM are reported separately. Sampled maxima are not continuous peaks. Temperature alone cannot attribute throttling.

Only exact57,600,000 samples with all3600-second final clocks, zero final lag/drops, finite developer policy, successful logical cleanup, child reap, physical owner/cgroup closure, lease release and a completed engine can produce `COMPLETE_3600_SOURCE_AND_CLOSURE`. It does not automatically declare sustained realtime or acoustic quality. Missing/failing gates produce `FAILED_OR_INCOMPLETE_PREFIX`, allowing a preserved failed run to be reviewed without claiming success. A physical closure receipt does not substitute for logical/model cleanup.

Set `PY` to `C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe`, `N` to this source directory and `Q` to the private `live-runtime-20261003` evidence root. Wait for `MIRROR_COMPLETE.json` before running. The full hash pass can take time on a multi-gigabyte mirror; it does not load audio into RAM.

PowerShell:

```powershell
& $PY -B "$N/review_full_app_hour.py" --mirror "$Q/full-app-hour-04-monitor-01" --output-root "$Q/audit-preparation"
```

CMD or Anaconda Prompt (explicit qualified interpreter):

```bat
"%PY%" -B "%N%\review_full_app_hour.py" --mirror "%Q%\full-app-hour-04-monitor-01" --output-root "%Q%\audit-preparation"
```

For the preserved failed prefix, substitute `full-app-hour-02-monitor-01`. The approximate per-caption latency subtracts a source origin inferred from health elapsed time from the SQLite write timestamp, then subtracts that caption's source end; wall-clock adjustments can affect it. First caption/speaker latency in health uses the runtime's own monotonic clock and is retained separately. No transcript or labeled-quality comparison is performed.

A complete physical mirror may contain `job_exit: null` after an externally ended service. The reviewer explicitly treats this as missing natural-exit and lease-release proof; it reports `job_exit_recorded: false`, the actual service result, and physical owner/cgroup closure separately. It does not infer worker/model cleanup from a signal or an empty cgroup. Prior failed reviewer outputs and their registered owners remain preserved.
