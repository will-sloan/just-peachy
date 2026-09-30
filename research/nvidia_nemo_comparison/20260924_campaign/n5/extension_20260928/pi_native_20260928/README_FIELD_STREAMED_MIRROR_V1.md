# Streamed host mirror and concrete live path projection

Purpose: replace the one-MiB in-memory backup restriction for future closed live
run evidence with bounded streaming and exact readback. No native model, audio,
GUI, capture, deployment, deletion or network action is performed by these tools.
This is infrastructure preparation, not full field/runtime acceptance.

## Code and inputs/outputs

- `field_streamed_mirror_v1.py`: `publish(store, destination, source, pinned_files,
  deadline=monotonic_deadline, maximum_bytes=allowance)` copies a **local**, closed
  and independently pinned source tree. The caller establishes exact owner closure
  and source completeness. It accepts at most256files/64directories/32MiB per file,
  with at most80,106,028B logical files plus64KiB per directory. Reads, writes and
  readback use16KiB chunks; only the bounded manifest is held in memory. Source
  identities, exact membership, size and SHA256 are checked; links/reparse points,
  nonportable/case-aliased paths and changed source files reject. Original hidden
  guards and `.pending` files retain their names and bytes. This does not implement
  SSH transport; the full Pi-to-host route remains to be composed.
- The destination must never have existed. Exact filenames are written exclusively;
  a failed tree remains intact and is never retried or deleted. The separately
  reserved existing HostStore metadata writer publishes `BACKUP.json` only after
  streamed readback. A failed metadata publication is also retained by that writer.
  There is no crash-durability or malicious concurrent-filesystem guarantee.
- `field_live_paths_v1.py`: `project(session, conversation, epoch, runtime_token,
  code_files)` projects the selected V3 layout onto exact one-run IDs. It accounts
  for data/config replacements, native/archive controls, guard files, runtime-lock
  temporary names, code and sidecar pending files. Independent aggregate slices
  share their existing maxima; no allowance is increased. `check_inventory` checks
  an already enumerated tree. The IDs must be obtained from the admitted runtime.
  This checker is **not** a runtime interception layer or evidence that every
  transitive writer is bound. Live full-path census and producer enforcement remain
  open. Unused declared paths may be absent; unknown paths reject.
- `verify_field_streamed_mirror_v1.py` is a CPU14 local-copy entry point. Inputs are
  a closed evidence directory, its exact BACKUP.json files manifest, a fresh
  host-only admission and a unique output path. It creates a bounded HostStore at
  output and a sibling `output-mirror`, then prints only byte/count metadata.
  The small verifier allows1,600,000B including directory reserve; the reusable
  production mirror has the larger explicit ceiling above. This verifier is not
  a native/capture admission or a global allocation-policy editor.

## PowerShell

Use the existing environment; no installation or download. Obtain a **fresh**
target-inclusive ownership/census and host-only admission before running. The
recorded V108 preparation admission is closed/expired and cannot be reused.
Replace the placeholders with the new admission and a never-used output name.

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$b='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928'
& $py -B "$p\verify_field_streamed_mirror_v1.py" --source "$b\d1-visible-entry-v2-evidence\target" --manifest "$b\d1-visible-entry-v2-evidence\BACKUP.json" --admission '<fresh-admission.json>' --output '<fresh-private-output>'
```

## Command Prompt / Anaconda Prompt

The same absolute interpreter works in CMD and Anaconda Prompt; activating a
different environment is unnecessary. Replace both placeholders before execution.

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
set "B=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928"
"%PY%" -B "%P%\verify_field_streamed_mirror_v1.py" --source "%B%\d1-visible-entry-v2-evidence\target" --manifest "%B%\d1-visible-entry-v2-evidence\BACKUP.json" --admission "<fresh-admission.json>" --output "<fresh-private-output>"
```

Do not rerun the retained successful passage simply to refresh a version. New
failures preserve the complete destination and the missing/pending completion
receipt for review. Inspect the result before any new, differently admitted work.
Never publish private images, recordings or transcript contents in Git.

## V108 observations and limits

One actual local mirror of the retained V100 native evidence copied75files,
352,621B,14directories and14empty files with exact readback. Largest file45,633B
requires multiple16KiB reads.69data chunks are calculated from file sizes; the
returned counter was not retained after the initial review assertion failed.
That assertion incorrectly required chunks greater than file count, ignoring
empty files. The first review failure is preserved; a fresh independent review
uses the exact existing completion receipt, with **no positive copy rerun**.

A separate explicit fsync fault preserved the first copied empty guard file and
all created directories, with no completion receipt. Its zero-byte payload does
not establish nonempty partial-write preservation. Re-entry rejects before writes.
Four path rejects and three changed projection rejects passed. The full projection
retains80,106,028B target maximum; test IDs are a projection fixture, not actual
live session identities. No Pi job, source/model/GUI/capture or native live-path
qualification occurred. Full network mirror, runtime writer census and admission
remain open.
