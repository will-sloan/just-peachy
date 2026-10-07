# Bind an actually qualified raw source into a fresh release

`prepare_package.py` defaults to processed capture with raw disabled. Its three
raw qualification arguments require the exact native receipt path, that receipt's
SHA256, and an independently complete local closed-output mirror. The builder
reads every mirrored file back, checks membership and hashes, and requires the
actual job owner/unit/invocation, empty cgroup, natural success, physical stream
closure, route restoration, released leases, and exact raw/processed sample counts.
The success status is `RAW_NATIVE_QUALIFICATION_PASSED`.

The actual `installed_source.py`, `raw_capture.py`, and `source_batch.py` hashes
must match the new candidate bytes. Batch duration and retained factory hash must
also match. A receipt for a different source revision cannot enable raw. Five
seconds of source qualification does not certify a full application, ASR quality,
or sustained operation. Full application limits and admission remain independent.

Inputs are the source/profile directories, explicit raw receipt path/SHA, complete
local mirror, and the batch/native variant options selected for this candidate.
Outputs are the normal fresh package plus four small receipt documents and an
immutable raw reference in `BUILD_OPTIONS.json`. No audio, gallery or model is
copied into the package. `BINDING.json` records enabled raw capture with the exact
external native receipt and its hash; runtime verifies that receipt again.

First set `N`, `B`, and `PY` to the full paths shown in `README_PACKAGE.md`.
Replace every capital placeholder below with actual reviewed evidence. A fresh
candidate command in PowerShell is:

```powershell
& $PY -B "$N/prepare_package.py" --source $N --profiles "$B/field-runtime-v28-install/stage-backup/field-runtime-v28-profiles" --release-id field-runtime-v29-build-08 --source-batch-ms 100 --raw-qualification-reference '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/raw-qualification-NN/qualification/RAW_QUALIFICATION.json' --raw-qualification-sha256 ACTUAL_PROOF_SHA256 --raw-qualification-mirror 'FULL_LOCAL_MONITOR_DIRECTORY' --output-root "$B/live-runtime-20261003/audit-preparation"
```

In Command Prompt or Anaconda Prompt, use the same environment paths:

```bat
"%PY%" -B "%N%\prepare_package.py" --source "%N%" --profiles "%B%\field-runtime-v28-install\stage-backup\field-runtime-v28-profiles" --release-id field-runtime-v29-build-08 --source-batch-ms 100 --raw-qualification-reference "/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/raw-qualification-NN/qualification/RAW_QUALIFICATION.json" --raw-qualification-sha256 ACTUAL_PROOF_SHA256 --raw-qualification-mirror "FULL_LOCAL_MONITOR_DIRECTORY" --output-root "%B%\live-runtime-20261003\audit-preparation"
```

Append the paired `--native-variant` and `--native-variant-sha256` options from
`README_PACKAGE.md` when the reviewed candidate includes that native variant.
They are separate from raw qualification. All options must be chosen before
reviewing the candidate-content hash.

To admit a frozen candidate, use its `package` directory and exact manifest pin
with `--source-snapshot-manifest-sha256` and the explicit fresh reviewed admission,
as documented in `README_PACKAGE.md`. Omit the three raw arguments: the frozen
proof and operational raw options are inherited and revalidated. Qualification
and production authorization can change only the existing authorization fields;
they cannot replace raw evidence or change source geometry. Existing native
release directories are never overwritten by this tool.

Focused tests use only private synthetic files, register CPU14 and the numeric
host owner before project imports, and do not build or enable a package:

```powershell
& $PY -B "$N/test_raw_release.py" --output-root "$B/live-runtime-20261003/audit-preparation"
```

```bat
"%PY%" -B "%N%\test_raw_release.py" --output-root "%B%\live-runtime-20261003\audit-preparation"
```

The result is a fresh `raw-release-checks-.../TEST_RESULT.json`. An optional
`--closed-mirror FULL_LOCAL_MONITOR_DIRECTORY` reads back one explicitly named
historical raw mirror to check the reader protocol. That check never substitutes
receipt hashes for new candidate source bytes and never claims a new native pass.
