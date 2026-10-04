# Release acceptance and per-session authorization

`release_authorization.py` is imported by the verified launcher and worker. It
does not contact the Pi or start anything itself. Inputs are the immutable
release binding, selected pipeline, finite SessionPolicy, and explicit review
receipts. Output is a session authorization record; invalid pins, selections,
limits or supervisor time raise an exception before Start.

Qualification uses a SHA-pinned `NATIVE_ADMISSION.json` for one current boot and
finite expiry. Production uses a distinct SHA-pinned `PRODUCTION_ACCEPTANCE.json`
with schema `just-peachy.v29.production-acceptance.v1`. Production has no boot
expiry or global session count. It binds exact target/content/installed-release
hashes, reviewer/time, previous desktop hash, accepted profile/source/embedding
tuples, finite policy ceilings and an explicit native asset inventory. Each asset
pins path, resolved path, bytes and SHA256. The worker rehashes assets required by
the selected pipeline before importing the installed engine. Existing resource,
storage, lease and source guards still apply. Acceptance never claims native
qualification or creates an acceptance receipt itself.

Acceptance fields: `accepted: true`, `reviewer`, `accepted_unix`, `target`,
`candidate_content_sha256`, `installed_manifest_sha256`,
`previous_desktop_sha256`, `allowed_selections`, `limits`, `assets`, `full_backup`.
Each selection contains the complete `RuntimeSelection.validate()` result:
`diarizer`, `embedding`, `input_source`, `nemotron_profile`, `allow_experimental`,
`provisional_correction`, `refinement_profile`, `revision_window_seconds`,
`refinement_period_seconds`, `embedding_schedule`, `embedding_refresh_seconds`,
`speaker_attribution`, and `optional_d1_refiner`. Changing an algorithm/schedule/window/refresh requires
its own explicitly accepted selection; experimental opt-in cannot widen an
existing acceptance. Limits contain
`maximum_session_seconds` (at most300), `maximum_developer_seconds` (3600–86400),
`max_drain_seconds` and `max_backlog_seconds`. Long sessions still require an
explicit developer flag. Unsupported simultaneous provisional correction fails.

`full_backup` explicitly selects reviewed `selected-release-and-user-data`
scope and identifies the host backup root, manifest/completion paths and their
SHA256 pins. The builder checks those pins, closed-source proof, full membership,
and independent host file hashes. Only backup receipts enter the package; no
additional model/gallery copy is made. Scope completeness is a reviewer decision:
a benchmark mirror does not automatically become a full release/user-data backup.
Activation requires production acceptance and two independently read-back desktop
backups. Qualification admission alone cannot activate a desktop shortcut.

Headless supervisor lifetime is the complete policy deadline plus300 seconds.
GUI lifetime is at least7200 seconds, or the policy deadline plus450 if larger.
Start requires the complete session deadline plus150 seconds remaining. Otherwise
the user must reopen the launcher for a fresh finite envelope. The GUI exits
after300 idle seconds only without an active worker. Capture is off by default.

## Host-only checks and preparation

Selected standard model assets resolve through the release-manifest-pinned
`config/assets.json`, exactly as installed `app.paths.pipeline_config` does:
`models_root / sha256 / filename`. Deployment-relative labels are checked against
that catalog; they are not filesystem model locations. Changed catalog bytes or
a descriptor/catalog digest mismatch fail before asset use. Acceptance still
pins each actual resolved native path, extent and content hash.

For explicit `chunk52_threads2`, production checks the same sealed variant
descriptor as the engine and inventories its selected model, complete isolated
library set, descriptor/build/source receipts, source file, core build output,
owner/exit receipts and pinned component review. Its native fields replace only
the selected diarizer fields; ASR, punctuation, embedding namespace and gallery
descriptor bindings remain part of the original selection. A production-approved
single-thread profile never implicitly accepts this distinct profile.

No package installation is needed. PowerShell:

```powershell
$N = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$B = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928'
$PY = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$N/test_native_scope.py" --output-root "$B/live-runtime-20261003/audit-preparation"
# Only after explicit acceptance; select a fresh release ID.
& $PY -B "$N/prepare_package.py" --source $N --profiles "$B/field-runtime-v28-install/stage-backup/field-runtime-v28-profiles" --release-id field-runtime-v29-build-03 --production-acceptance 'REVIEWED_ACCEPTANCE.json' --output-root "$B/live-runtime-20261003/audit-preparation"
```

Command Prompt and Anaconda Prompt use the same existing interpreter:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "B=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%N%\test_native_scope.py" --output-root "%B%\live-runtime-20261003\audit-preparation"
"%PY%" -B "%N%\prepare_package.py" --source "%N%" --profiles "%B%\field-runtime-v28-install\stage-backup\field-runtime-v28-profiles" --release-id field-runtime-v29-build-03 --production-acceptance "REVIEWED_ACCEPTANCE.json" --output-root "%B%\live-runtime-20261003\audit-preparation"
```

Replace the placeholder acceptance path with the actual review receipt. Checks
write a fresh CPU14 owner before project imports and a `TEST_RESULT.json`. They
cover mocked policy/selection/lifetime gates without native execution, systemd,
SSH or activation. Production installation remains a separately reviewed action.

Build07 adds the explicit optional_d1_refiner Boolean to every selection key. False is the RuntimeSelection default. An old receipt missing this key is rejected, and cannot silently authorize the optional child. Production acceptance of true remains unavailable pending separately reviewed combined integration; the separate measured experimental admission is not a production acceptance. Run the existing test_native_scope.py host command with --checks test_production_optional_refiner_requires_explicit_new_key for this focused contract.

## Build08 optional experimental acceptance

The prior build07 blanket rejection is superseded only in the new candidate. `optional_d1_refiner=true` requires `optional_refiner_admissions` references with exact selection, policy, native proof path/SHA and selected asset-inventory SHA. The actual worker/UI validates the measured v2 experimental proof and canonical selected primary+child asset inventory; a qualification permit is rejected by this route. This is not sustained or quality qualification. Same-runtime first/follow-up permits and deliberate later acceptance are documented in [README_OPTIONAL_QUALIFICATION](README_OPTIONAL_QUALIFICATION.md). All raw, gallery, source and other operational binding fields remain pinned.

## Exact installed interpreter resolution (candidate12)

Every selection requires the interpreter asset; it is not omitted from accepted
inventories. The actual `selected-assets-01` census verified the binding's Python
alias under JustPeachy resolves to `/usr/bin/python3.11`, exactly6,616,896 bytes,
SHA256 `304aa87a76ebb13fd22d253ac157f14980ff2cdb23e6274f3b045571405e07dc`.
The validator permits only that exact alias/realpath/size/hash combination outside
the JustPeachy root. Every other asset keeps the original root restriction.
The worker still resolves and rehashes the selected actual file before native
imports. No generic `/usr` allowance, interpreter substitution, asset omission,
production acceptance or native qualification is created by this correction.

`test_interpreter_acceptance.py` runs host-only shape checks with the actual
closed inventory and exact frozen source; synthetic acceptance exists only in
memory and is never issued. Inputs are the exact source snapshot and inventory;
output is a private CPU14 owner/result receipt. No models or device calls run.

PowerShell:

```powershell
& $PY -B "$N/test_interpreter_acceptance.py" --source $S --assets $ASSETS --output-root "$B/live-runtime-20261003/audit-preparation"
```

CMD and Anaconda Prompt use the same qualified interpreter:

```bat
"%PY%" -B "%N%\test_interpreter_acceptance.py" --source "%S%" --assets "%ASSETS%" --output-root "%B%\live-runtime-20261003\audit-preparation"
```

Use exact `$S`/`%S%` from the disabled activity11 BUILD_RESULT and
`$ASSETS`/`%ASSETS%` pointing to the privately saved selected-assets-01 JSON.
This is a validator correction; it changes candidate content and therefore
requires a reviewed derivative. Build11 and all actual observations stay intact.
