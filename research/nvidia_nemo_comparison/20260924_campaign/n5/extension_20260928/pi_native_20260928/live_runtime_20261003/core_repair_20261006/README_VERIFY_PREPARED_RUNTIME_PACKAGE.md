# Independent prepared-runtime readback

Purpose: `verify_prepared_runtime_package.ps1` independently expands a pinned
prepared code archive on Windows, compares every byte and member with its
prepared tree, and checks each original source against both preservation copies.
It sets CPU14 and registers its actual host identity before project reads. It
does not contact the Pi, execute runtime code, open audio or change a release.

Inputs: a closed builder root under the private audit-preparation directory,
the actual two-digit build version, and exact manifest/archive/source-review
SHA256 values. Invoke only after observing that builder's natural exit zero;
the script separately checks that its PID is absent. Code-archive ceilings
(512 members, 2 MiB/member, 32 MiB expanded) bound this verification operation;
they are not recording or gallery limits. C:50 GiB and G:75 GiB floors remain.

Outputs: a fresh `independent-package-UUID`, its early owner, source backups and
independent restores, the expanded readback and `INDEPENDENT_CLOSURE.json`, also
published CreateNew into the original build root. An external owner-absence
receipt must follow successful validator exit. Failed outputs remain intact.

PowerShell:

```powershell
& 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/verify_prepared_runtime_package.ps1' -BuildRoot 'ACTUAL_BUILD_ROOT' -Version 34 -ManifestSha256 ACTUAL_MANIFEST_SHA -ArchiveSha256 ACTUAL_ARCHIVE_SHA -SourceReviewSha256 ACTUAL_REVIEW_SHA
```

Command Prompt and Anaconda Prompt (no environment/package installation):

```bat
pwsh -NoProfile -File "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\verify_prepared_runtime_package.ps1" -BuildRoot "ACTUAL_BUILD_ROOT" -Version 34 -ManifestSha256 ACTUAL_MANIFEST_SHA -ArchiveSha256 ACTUAL_ARCHIVE_SHA -SourceReviewSha256 ACTUAL_REVIEW_SHA
```

Use literal actual hashes from the accepted build result; placeholders are not
admissions. This is source/restore proof, not native runtime qualification.
