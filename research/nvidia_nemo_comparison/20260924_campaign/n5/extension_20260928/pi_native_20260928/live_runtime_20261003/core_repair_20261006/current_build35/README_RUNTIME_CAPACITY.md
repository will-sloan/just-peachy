# Runtime metadata capacity

Purpose: remove duration-derived cumulative metadata quotas that can mask the
actual caption/Mode failure or prevent normal Stop completion, while preserving
bounded RAM/I/O and actual physical storage pressure checks.

`runtime_support.py` starts from exact immutable build28 source SHA256
`67bced57a5a0c5fb96cc90479ec1fa557e3a01c7f4abec6d54c94d48f0aee1a2`,
package manifest
`e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b`.
Its lease/source pin/resource helpers are unchanged. `DiskBudget.maximum` and
`SegmentedText.maximum` remain compatible numeric planning estimates, and accepted
bytes remain exact monotone accounting. Neither estimate refuses accumulated
valid metadata. The actual filesystem free space must cover each append plus
the StoragePolicy byte/fraction reserve, using the same ceiling rounding. Engine
writers receive the actual store reserve policy. Used-gallery copies also check
physical headroom before copying each bounded file and its manifest.

Inputs: owned writer paths, initial planning estimate, text records, bounded
record/segment/queue sizes, actual filesystem measurements and byte/fraction
reserve policy. Outputs: append-only text segments and an exact completion/index
receipt, accepted/completed/pending counts, explicit physical I/O errors or RAM
queue/individual-record errors. Segment files do not grow without a per-file
bound; full history is preserved in successive segments. The existing 1 MiB
individual serialized record ceiling, 4 MiB pending byte queue, finite item queue,
Stop join/drain and file durability remain. These protect actual working memory;
they are not a total recording or metadata quota. No event is silently dropped.

The actual filesystem-wide per-file ceiling and expanding SQLite file allowance
are handled by the candidate storage/native-scope helpers described in
`README_STORAGE_RECOVERY.md`; this patch does not relax process address-space,
stack or source queue limits. Genuine disk pressure still stops capture safely.

`test_runtime_capacity.py` is standard-library-only and loads no model, device,
native owner or SSH client. Input fixtures use tiny estimates, temporary owned
directories and controlled disk-usage values. Outputs are unittest results and
temporary completion receipts removed after each check. It verifies that valid
records beyond both old estimates drain/close completely, real reserve failure
still refuses writes, and an oversized individual record still reports the RAM
boundary and closes its owner thread.

Run only after the current guarded native preread permits Python work, and do
not run concurrently with a native owner experiment.

PowerShell:

```powershell
$repairDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
Set-Location -LiteralPath $repairDir
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -m unittest -v test_runtime_capacity
```

CMD or Anaconda Prompt (existing interpreter; no new package install):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -m unittest -v test_runtime_capacity
```

Runtime helpers are loaded by the separately staged versioned launcher, not run
individually. Include this candidate `runtime_support.py` in the build replacement
manifest. Do not modify the activated build28 package in place. Follow
`README_CORE_REPAIR.md` for the full repair and native validation sequence. Fixture
success does not establish sustained native I/O, recognition or sensor quality.

Validation on 2026-10-06 passed all four capacity cases in the registered
24-test contracts process, with no skips. The check preserved source backups
and independent restores, confirmed source stability and fixture cleanup, and
the caller verified exact process closure after natural return code zero.
Receipts are in the private runtime root's
`audit-preparation/identity-host-contracts-20261006-a00bee7bd3784ea4981d549c13a1535d`.
