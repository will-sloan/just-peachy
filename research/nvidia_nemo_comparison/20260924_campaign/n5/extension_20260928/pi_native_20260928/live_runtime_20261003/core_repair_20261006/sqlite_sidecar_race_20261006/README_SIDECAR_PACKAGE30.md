# Build30 sidecar repair package preparation

`build_sidecar_package30.py` prepares a source review or a new immutable build30
package from exact frozen build29. Its only runtime replacements are
`storage_support.py` and `README_SQLITE_SIDECAR_RACE.md` in this iteration. See
that README for the diagnostic boundary, native37 uncertainty, and final17
focused fixture results. This builder performs host-only work; root coordinates
the host slot and subsequently performs native backup, staging and qualification.

## Pinned inputs and preservation

The base is
`Q/audit-preparation/core-package-v1-389154acb3e04317b614c4311bb6de02/package`,
PACKAGE_MANIFEST SHA256
`331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b`.
Q is
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003`.
The old/new native targets are exactly
`/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-29`
and `field-runtime-v29-build-30` under the same parent.

The builder derives from the reviewed build29 wrapper and reuses the immutable
`ui_restore_20261004/build_classic_package.py` core, SHA256
`bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5`.
The historical core's single paired-frontend condition is verified by its exact
AST and replaced in memory with a stricter complete two-file replacement-set
condition. Its main function has exactly one archive basename literal changed
to `field-runtime-v29-build-30-prepared.tar.gz`. The original source is preserved.
Inventory, finite outputs, package construction, independent archive restore,
and member validators are reused. No installed runtime or model is imported.

Ten source/evidence inputs receive separate backups and independent restores:
the two runtime replacements, this builder/README, the pinned packaging core,
focused test/runner sources, and three successful focused host receipts.
The final17 test must match exact PID26244/FILETIME134357830840231905,
natural0, independently absent, all fixtures closed, no failures/errors/skips.
Runtime and test code must match those tested hashes. Its README was updated
after the test with actual evidence and is pinned afresh for review/build.

All base package members are independently inventoried. Unchanged modules,
assets, model files, galleries, profiles, calibration, acceptance resource
limits, external data-root binding, and raw proof/source bytes must remain
byte-identical. Only the two selected replacements, their source backup/restore,
and derived binding/acceptance/provenance control files may differ. The raw
proof binding's package-local path moves from29 to30; its content is unchanged.
The package manifest is regenerated as a separate derived control. The README
is one new member. No member may be removed. `BUILD29_MEMBER_PRESERVATION.json`
reports exact changed/added members and unchanged counts.

Physical capacity and the existing logical-quota policy are retained. New
provenance identifies sidecar inspection changes and states that the original
native37 race is unproven. Prior29 native passes remain evidence for frozen29;
they cannot authorize changed30. All246 ordinary selections remain admissions
for guarded validation, not independent qualification of every combination.

## CLI inputs and outputs

- `--review-only`: registers one CPU14 Windows process before package reads,
  backs/restores all inputs, verifies final17 evidence, and emits
  `SOURCE_DIFF_REVIEW.json` with SHA pins, individual function AST differences,
  static local-import closure, constraints, and packaging-core adaptations.
  It creates no package or archive.
- Build requires `--review-manifest PATH`, `--review-sha256 SHA256`, and
  `--reviewer TEXT` (1–128 characters). Root must inspect the concrete review and
  explicitly approve it before build. Sources must match the reviewed inventory.
- Output is always a fresh private
  `Q/audit-preparation/sidecar-package30-UUID` directory. Review emits early
  owner/scope and source-closure receipts. Build additionally emits `package/`,
  the exact build30 archive, independent restored members, preservation report,
  and result pins using the existing core. Root records independent exact
  PID/creation-FILETIME absence after natural return.

The existing core bounds preparation to600 seconds/16 MiB, package contents to
16 MiB/512 members, and archive to2 MiB, with C:50 GiB/G:75 GiB free floors plus
headroom. These bound this known package's working set and preserve reviewed
admission; they are not recording corpus limits. Existing output is never reused.

## PowerShell: review first

Run only in the root-approved host slot. The existing project interpreter is
used directly; the WindowsApps `python` alias is unsuitable.

```powershell
$iteration = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/sqlite_sidecar_race_20261006'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' (Join-Path $iteration 'build_sidecar_package30.py') --review-only
```

Read the printed private output's `SOURCE_DIFF_REVIEW.json`, verify its SHA256,
and obtain root's concrete source approval. Root's external host guard must
close the exact owner before releasing the slot. Preserve the review sources.

After actual root approval, replace placeholders with the exact review path,
SHA, and reviewer. This command is not an instruction to build before review.

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' (Join-Path $iteration 'build_sidecar_package30.py') --review-manifest 'EXACT_REVIEW_DIRECTORY/SOURCE_DIFF_REVIEW.json' --review-sha256 'ROOT_ACCEPTED_SHA256' --reviewer 'ROOT_ACCEPTED_REVIEWER'
```

## CMD / Anaconda Prompt

Use the same existing interpreter without environment installation or activation.

```bat
set "ITERATION=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/sqlite_sidecar_race_20261006"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" "%ITERATION%/build_sidecar_package30.py" --review-only
```

Only after actual root review, use the exact values:

```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" "%ITERATION%/build_sidecar_package30.py" --review-manifest "EXACT_REVIEW_DIRECTORY/SOURCE_DIFF_REVIEW.json" --review-sha256 "ROOT_ACCEPTED_SHA256" --reviewer "ROOT_ACCEPTED_REVIEWER"
```

## Current status

Prepared source. Root authorized review-only execution; its actual receipt and
pins will be reported separately and preserved. No build30 package has been
built, staged, activated or qualified by this builder. Keep this README frozen
once used in a source review; record later outcomes in a separate evidence note
so review/build source hashes remain identical. Native staging must require the
accepted final production-backup13 closure and a fresh explicit stage procedure.
