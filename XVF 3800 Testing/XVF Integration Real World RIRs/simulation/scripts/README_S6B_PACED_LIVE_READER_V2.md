# S6B paced LIVE observer v2 and model-free fixtures

`s6b_paced_live_reader_v2.py` is a separately bound coordinator-only status reader. `test_s6b_paced_live_reader_v2.py` runs its isolated fault fixtures. Neither changes the frozen `s6b_paced.py` driver, native child entry point, APP, model weights, profiles, source pacing, dispatch, or final measurement checks. The pinned v1 helper supplies the original driver loader, strict run argument guard and PermissionError-only behavior for non-LIVE JSON reads.

The second interruption was `JSONDecodeError: Extra data` while reading a worker LIVE file. The exact failed input bytes were not retained by the former reader. Its later closed file is valid, and the original worker publisher already uses a unique temporary file, fsync and replace. The cause remains unproven. This observer improves read consistency and retains diagnostic evidence; it does not establish a publication defect.

## Inputs and boundary

Supply a prepared original-driver manifest, its externally verified SHA-256, a fresh observer event directory, and exact original `--mode run` arguments after `--`. The explicit output must equal the manifest parent and its declared output root. Only exact LIVE paths derived from the admitted manifest job IDs receive snapshot treatment. Their lexical and resolved paths must agree at admission and each snapshot; aliases and retargeted reparse paths fail. Same-named unlisted LIVE files remain strict. This is an invocation/read boundary guard, not filesystem isolation against a malicious concurrent path substitution inside an OS call.

Each admitted LIVE read uses one shared one-second deadline and at most 20 individual snapshot attempts, including both reads in a pair. Every actual binary read is preceded by a deadline check. A snapshot retains before/after size, timestamps, device/inode metadata when available; acceptance requires two identical byte strings and equal metadata across both snapshots. Text decoding remains UTF-8 with optional BOM. Changed pairs and PermissionError/errno EACCES trigger bounded 50 ms backoffs. A malformed identical pair fails immediately even if metadata changed. Missing files, oversized files, decoding errors and stable malformed JSON propagate. Valid JSON is returned without semantic coercion, so original caller errors remain errors.

One snapshot reads at most 65,537 bytes. More than 64 KiB fails with an explicitly truncated prefix. Anomalous bytes are preserved exactly in unique `.bin` files, with SHA-256/length and before/after metadata in the event log. Anomaly storage is bounded to 16 MiB; a read starts only with enough remaining capacity for its worst-case 20 snapshots. Capacity exhaustion fails closed. OS calls and durable diagnostic writes cannot be preempted; the deadline bounds when a subsequent byte read may start, not total wall time of an unpreemptible operation. Logging or sleep overshoot does not authorize another read.

## Outputs

The fresh observer directory contains `LAUNCH.json` (source, pinned helper, driver, manifest, PID/creation and exact allowed paths), `OBSERVER_EVENTS.jsonl`, `rejected_snapshots/*.bin` only for anomalies, and `COMPLETION.json` with read counts, attempts, changed pairs, failures, scheduled/measured waits and final event binding. The unchanged driver creates all native artifacts, trajectory samples, completion receipts and summary in the supplied paced namespace. No previous output is deleted or overwritten by this wrapper.

The fixtures create a fresh isolated directory with raw test bytes, retained snapshots, `FIXTURE_EVENTS.json` and `CHECK_RECEIPT.json`. They launch zero models. The tests cover actual stable binary/BOM reading, changed and malformed snapshots, exact retained bytes, metadata change, permission between snapshots, shared deadlines, delayed retries, the 20-read cap, vanished files, non-LIVE strictness, semantic errors, path resolution, oversized status, manifest/argument guards and original child entry point.

## PowerShell

Run from any directory; use a fresh fixture or event suffix for each intentional new run. The v3 manifest must already have passed the separately recorded 24-cell complete-only admission and independent review. Do not derive trust in a changed manifest merely by updating its SHA below: use the reviewed receipt's expected value.

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$report = "$sim\reports\S6B\20260909T230840Z"
$out = 'G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v3'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\test_s6b_paced_live_reader_v2.py" --root "$sim\staging\s6b\20260909T230840Z\paced_live_reader_checks_NEW"
# After independent review and a reserved quiet interval, use the bound v3 manifest SHA:
$expectedManifestSha = 'db125f67e26e2e5aa74fb9d806754c1a6a8d42b45c2e5002be5a964e3b8f5b60'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_live_reader_v2.py" --manifest "$out\MANIFEST.json" --manifest-sha256 $expectedManifestSha --events-root "$report\paced\live_reader_overlay_v2_run1" -- --mode run --epoch epoch2 --profiles B00,B36,B10,B17 --repetitions 2 --streams O0,O1 --report $report --output $out
```

## Anaconda Prompt / Windows CMD

The explicit project interpreter enforces the existing runtime; do not substitute the base Anaconda Python. Replace the reviewed SHA placeholder and use a fresh fixture suffix.

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "REPORT=%SIM%\reports\S6B\20260909T230840Z"
set "OUT=G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v3"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\test_s6b_paced_live_reader_v2.py" --root "%SIM%\staging\s6b\20260909T230840Z\paced_live_reader_checks_NEW"
set "EXPECTED_MANIFEST_SHA=db125f67e26e2e5aa74fb9d806754c1a6a8d42b45c2e5002be5a964e3b8f5b60"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_live_reader_v2.py" --manifest "%OUT%\MANIFEST.json" --manifest-sha256 "%EXPECTED_MANIFEST_SHA%" --events-root "%REPORT%\paced\live_reader_overlay_v2_run1" -- --mode run --epoch epoch2 --profiles B00,B36,B10,B17 --repetitions 2 --streams O0,O1 --report "%REPORT%" --output "%OUT%"
```

## Recovery and interpretation

The original namespace contains two completed physical cells and one interrupted cell. The v2 namespace references those two original completions, adds 22 completed physical cells and contains a second interrupted cell. The fresh v3 namespace will reuse all 24 exact COMPLETE/trajectory pairs, retaining their original absolute native artifact bindings through the earlier resume ledger; failed partials are not successes. Its remaining 40 cells use the original native children. Count physical attempts separately from logical cells and copied receipt references.

The 64-cell order, both taps, full source cases and two balanced repetitions remain as originally admitted. Successful resource traces now span three coordinator observer versions and two interruption gaps. Binary double reading and anomalous read retries add observer overhead and can delay or miss sampling opportunities; scheduled/measured delays are recorded without interpolation. Quiet model periods do not imply identical unrelated host activity or identical resource conditions. Preserve every repetition and fault; do not select a favorable repetition or retry for accuracy. The immutable pre-paced native/replay accounting stays separate from this paced closure.
