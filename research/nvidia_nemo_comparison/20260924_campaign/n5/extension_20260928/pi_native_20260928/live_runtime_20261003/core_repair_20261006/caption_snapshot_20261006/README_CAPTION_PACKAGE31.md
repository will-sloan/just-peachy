# Build31 caption snapshot package preparation

`build_caption_package31.py` prepares a source review or an immutable build31
package from exact frozen build30. Its explicit replacement set is
`installed_engine.py`, `d1_spatial_policy.py`, `d1_caption_snapshot.py`, and
`README_D1_CAPTION_SNAPSHOT.md` in this directory. The first two are runtime
adapters; the helper copies canonical identity inputs without projecting
unrelated display rows, derives the pinned N2 revision method, and retires
obsolete span/revision cache entries. The installed adapter also records D1
revision wall time and separate source-lane health fields. See the helper README
for the exact interface and focused fixtures.

This is Windows host preparation only. It registers one CPU14 owner before
reading project/package files. It does not execute installed engine or model
code, open production recordings or databases, use SSH, stage an installation,
change the desktop, or activate a package. Root coordinates the host slot and
separate native actions. The commands below are prepared instructions; source
preparation does not mean they have been executed.

## Inputs and preservation

Q is
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003`.
The base is
`Q/audit-preparation/sidecar-package30-99ab101518ce402a9a2c8d5f6ac96cc6/package`.
Its `PACKAGE_MANIFEST.json` SHA256 must be
`b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569`.
The old/new targets are exactly
`/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-30`
and `field-runtime-v29-build-31` under the same parent.

The pinned packaging core is
`../../ui_restore_20261004/build_classic_package.py`, SHA256
`bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5`.
The wrapper reuses its inventory, finite output, derive, acceptance validator,
archive construction, and independent full member readback. It verifies the
historical paired-frontend AST condition and substitutes the exact four-file
set in memory. It changes exactly one core main archive literal to
`field-runtime-v29-build-31-prepared.tar.gz`. Neither frozen core nor build30 is
edited.

`--host-test-root` is required for both review and build. It must name an actual
ordinary directory directly under `Q/audit-preparation`. Admission requires:

- `RESULT.json`: actual PASS, exactly11 tests, zero failures/errors/skips,
  fixtures closed, sources unchanged, no native action, and no failure.
- `REGISTERED_OWNER.json`: CPU14/mask16384 and positive PID/creation FILETIME;
  its complete owner must match the result and independent closure.
- `HOST_CLOSED.json`: `natural_exit_code:0`, `os_process_absent:true`, and the
  same exact owner. This is written after natural return and independent OS
  absence inspection, not by the running test process.
- `SOURCE_CLOSED.json`: independently backed/restored source pins. All three
  runtime Python replacements and the focused check/runner must match their
  tested byte counts and SHA256 values. The helper README can receive actual
  evidence after testing and is pinned afresh for source review.

The actual admitted11-test root is
`Q/audit-preparation/caption-snapshot-host-b338043a6358469d86ace1a31bb53414`.
It reported PASS11, errors/failures/skips0, fixtures closed and sources unchanged.
Registered PID38760 / creation FILETIME134357877265399478 returned naturally0;
its independent closure records exact process absence. These are host fixtures,
not native qualification or an hour-long sustainability result.

Thirteen selected source/evidence inputs receive separate backups and
independent restores: the four replacements, this builder/README, the pinned
core, the check/runner, and four actual host receipts. Source and import review
includes the exact source hashes and nested-function AST changes; all replacement
Python modules must be statically reachable from native entrypoints. No model
graph is imported for this check.

Every base member is independently inventoried. Only the four replacements,
their Python source backup/restore members, and derived binding/acceptance/
provenance controls may change or be added. No member may be removed. All other
runtime modules, storage/audio durability, physical guards, ASR/embedding model
assets, gallery descriptors, modes, calibration, backend profiles, source/proof
bytes and external data-root location are preserved. The raw proof binding's
package-local path alone moves from30 to31. The manifest is a separate derived
control. `BUILD30_MEMBER_PRESERVATION.json` reports actual changed/added members
and the unchanged count.

## Outputs and approval boundary

Each invocation creates a fresh private
`Q/audit-preparation/caption-package31-UUID` directory. Review emits early
`REGISTERED_OWNER.json`, `HOST_SCOPE.json`,13 source backups/restores,
`PREPARED_SOURCE_CLOSED.json`, `SOURCE_DIFF_REVIEW.json`, and `SOURCE_CLOSED.json`.
It creates no package/archive. Root must review the concrete source/AST/import
inventory and approve its exact SHA256 before build.

Build additionally emits `package/`, the exact build31 archive,
`BUILD30_MEMBER_PRESERVATION.json`, and authoritative `BUILD_RESULT.json`.
The latter retains the core fields `package`, `archive`, `target`, `data_root`,
`manifest_sha256`, `archive_sha256`, `candidate_content_sha256`,
`parent_manifest_sha256`, `files`, `ordinary_selections`,
`source_backups_and_restores_exact`, and `archive_members_independently_restored`.
It declares no installation, desktop change or native qualification. The core
checks every archive member independently before returning.

Root performs an independent exact PID/FILETIME absence check after natural
return and records `INDEPENDENT_CLOSURE.json` with source/member readback. That
external receipt is a prerequisite for later staging; the builder cannot attest
its own process absence. There is no `RESULT.json` alias for `BUILD_RESULT.json`.

The unchanged host core bounds preparation to600 seconds/16 MiB, package
contents to16 MiB/512 members, and archive to2 MiB, with C:50 GiB/G:75 GiB free
floors and its existing available-RAM checks. These bound package preparation;
they do not introduce a recording-corpus quota. Runtime reserves, queue/memory
bounds, SQLite allowances, ownership and the maximum-backlog stop remain those
of frozen build30. Passing build30 or host11 cannot qualify changed build31.
The original hour01 failure remains evidence; the static copy/cache defects do
not establish an exclusive cause or sustainable realtime behavior.

## PowerShell commands

Use the known Windows interpreter; do not install or select a new environment.
Root must authorize the single host slot before executing either invocation.

```powershell
$py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$dir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/caption_snapshot_20261006'
$testRoot = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/caption-snapshot-host-b338043a6358469d86ace1a31bb53414'
& $py "$dir/build_caption_package31.py" --host-test-root $testRoot --review-only
if ($LASTEXITCODE -ne 0) { throw 'Source review failed; preserve its fresh output' }
```

Read the printed fresh output path and inspect its `SOURCE_DIFF_REVIEW.json`.
Record the review SHA using `Get-FileHash`; root approval applies only to that
exact review. After review-process closure and approval:

```powershell
$review = 'G:/replace/with/actual/caption-package31-UUID/SOURCE_DIFF_REVIEW.json'
$reviewSha = (Get-FileHash -LiteralPath $review -Algorithm SHA256).Hash.ToLower()
& $py "$dir/build_caption_package31.py" --host-test-root $testRoot --review-manifest $review --review-sha256 $reviewSha --reviewer 'REPLACE WITH ACTUAL ROOT REVIEWER'
if ($LASTEXITCODE -ne 0) { throw 'Build failed; preserve its fresh output' }
```

For an independent read-only exact-owner check after either natural return,
set `$out` to that invocation's actual fresh output and run:

```powershell
$out = 'G:/replace/with/actual/caption-package31-UUID'
$owner = Get-Content -LiteralPath "$out/REGISTERED_OWNER.json" -Raw | ConvertFrom-Json
$process = Get-Process -Id $owner.pid -ErrorAction SilentlyContinue
if ($process -and $process.StartTime.ToUniversalTime().ToFileTimeUtc() -eq $owner.creation_filetime) {
    throw 'The registered owner is still present; closure cannot be claimed'
}
$owner | Select-Object pid, creation_filetime, cpu, affinity_mask
```

A reused PID is distinguished by creation FILETIME. A failed/inaccessible
inspection does not authorize claiming closure. Root records the actual return
code, readbacks and this OS check in the independent closure receipt.

## CMD and Anaconda Prompt commands

The same known interpreter works from CMD or an already-open Anaconda Prompt.
No `conda create`, installation, environment migration or model download is
required. In either prompt, enter:

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "DIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\caption_snapshot_20261006"
set "TESTROOT=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\caption-snapshot-host-b338043a6358469d86ace1a31bb53414"
"%PY%" "%DIR%\build_caption_package31.py" --host-test-root "%TESTROOT%" --review-only
```

Stop on a nonzero exit code and preserve its output. After root review and
independent closure, substitute the actual reviewed path/hash/reviewer:

```bat
"%PY%" "%DIR%\build_caption_package31.py" --host-test-root "%TESTROOT%" --review-manifest "G:\ACTUAL\SOURCE_DIFF_REVIEW.json" --review-sha256 ACTUAL_REVIEW_SHA256 --reviewer "ACTUAL ROOT REVIEWER"
```

Use PowerShell for the independent PID/FILETIME and full source/member readback
receipt. No command above stages, launches or activates native build31.
