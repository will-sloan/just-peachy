# Prepared v29 package and native envelope

`prepare_package.py` builds a fresh, reviewable package on Windows. It does not
contact the Pi, copy models or galleries, change the desktop, or run native code.
It registers its numeric process creation time on CPU 14 before reading project
inputs. Inputs are this source directory and the preserved v28 profile directory.
Outputs are a unique preparation directory, `package/`, a deterministic gzip tar archive, and
`BUILD_RESULT.json` containing archive, manifest, and candidate-content hashes.
The exact 66-file `COMMON_BUNDLE.json` is checked and extracted under
`reference-v28/`. Existing profile descriptors retain their model/gallery paths.
Each new runtime source also has independently read-back `.backup` and `.restore`
copies. The logical audio journal path is the session directory; processed audio
is stored in segments and read through `SessionSpool.read_processed`.

The package defaults to `native_launch_enabled=false`. A reviewed admission is
permission to test this exact candidate; it never labels it performance or quality
qualified. `native_qualified` remains false. Preparation, staging, qualification,
and desktop activation are separate operations.

Raw capture may be included only with the explicit successful source receipt,
its SHA256 and a complete independently read-back closed mirror. The candidate's
source module triplet, batching and factory must match that actual qualification.
See `README_RAW_RELEASE.md` for the three preparation arguments, exact checks,
PowerShell/Command/Anaconda commands, and frozen-admission workflow. This enables
the qualified raw adapter only; `native_qualified` remains false for the release.

## Host preparation

In PowerShell, use the existing environment; no package installation is needed:

```powershell
$N = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$B = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928'
$PY = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$N/test_package.py" --source $N --profiles "$B/field-runtime-v28-install/stage-backup/field-runtime-v28-profiles" --release-id field-runtime-v29-build-01 --output-root "$B/live-runtime-20261003/audit-preparation"
& $PY -B "$N/prepare_package.py" --source $N --profiles "$B/field-runtime-v28-install/stage-backup/field-runtime-v28-profiles" --release-id field-runtime-v29-build-01 --output-root "$B/live-runtime-20261003/audit-preparation"
```

In Anaconda Prompt or Command Prompt, set the same paths with `set` and invoke
the pinned interpreter directly. This avoids changing the active environment:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "B=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%N%\test_package.py" --source "%N%" --profiles "%B%\field-runtime-v28-install\stage-backup\field-runtime-v28-profiles" --release-id field-runtime-v29-build-01 --output-root "%B%\live-runtime-20261003\audit-preparation"
"%PY%" -B "%N%\prepare_package.py" --source "%N%" --profiles "%B%\field-runtime-v28-install\stage-backup\field-runtime-v28-profiles" --release-id field-runtime-v29-build-01 --output-root "%B%\live-runtime-20261003\audit-preparation"
```

Only after an explicit native review, a fresh build may additionally receive
`--reviewed-native-admission PATH`. That bounded JSON must have schema
`just-peachy.v29-reviewed-native-admission.v1`, `reviewed: true`,
`native_launch_enabled: true`, the exact `candidate_content_sha256` from the
disabled build, the exact `target` below, a nonempty `reviewer`, the current Pi
`boot_id`, the reviewed baseline's `baseline_sha256`, and future `expires_unix`.
Any source or README change changes the content hash and invalidates admission.
The builder does not create or infer that admission.

To admit previously frozen bytes while current sources continue changing, use
`--source SNAPSHOT/package --profiles SNAPSHOT/package/profiles
--source-snapshot-manifest-sha256 SNAPSHOT_MANIFEST_SHA256` together with the
reviewed admission and intended fresh release ID. The builder first verifies
every snapshot member and uses its retained `reference-v28/COMMON_BUNDLE.json`.
It does not reread mutable runtime files. For example, with `$S`/`%S%` set to the
actual frozen `package` directory, PowerShell uses:

```powershell
& $PY -B "$N/prepare_package.py" --source $S --profiles "$S/profiles" --source-snapshot-manifest-sha256 REVIEWED_SNAPSHOT_SHA256 --reviewed-native-admission 'FRESH_ADMISSION.json' --release-id field-runtime-v29-build-03 --output-root "$B/live-runtime-20261003/audit-preparation"
```

Command Prompt or Anaconda Prompt uses:

```bat
"%PY%" -B "%N%\prepare_package.py" --source "%S%" --profiles "%S%\profiles" --source-snapshot-manifest-sha256 REVIEWED_SNAPSHOT_SHA256 --reviewed-native-admission "FRESH_ADMISSION.json" --release-id field-runtime-v29-build-03 --output-root "%B%\live-runtime-20261003\audit-preparation"
```

Placeholder hashes/paths must be replaced by actual review evidence. A disabled
preview and enabled package may share runtime source content, but they have
different package manifests. Once either is staged at a native root, that root
cannot be overwritten; a later variant requires a fresh build ID.

For a fresh explicitly batched candidate, append `--source-batch-ms 100` to the
PowerShell or Command/Anaconda Prompt preparation command. This writes a
`BUILD_OPTIONS.json` covered by the candidate-content hash and sets the same
binding option. Omission preserves the default unbatched path. Admission from
an existing snapshot inherits its pinned options automatically; an override
that differs from the snapshot is rejected. Batching still needs its own fresh
native qualification, including the exact `source_batch.py` hash.
Batch bindings also explicitly set `live_config.block_frames:480`, matching the
pinned installed default. If the retained template declares another geometry,
preparation fails. The strict source guard remains in force. Frozen build05
omitted this explicit binding and its batch trial refused before capture;
preserve that candidate and use a fresh build ID containing this correction.

The experimental integrated thread-two option additionally uses paired
`--native-variant PATH --native-variant-sha256 SHA256` preparation arguments.
They populate the exact `native_variants.chunk52_threads2` binding and hashed
build options. The builder includes the bounded
`component_evidence/chunk52_threads2_review.json` receipt and requires it when
this option is selected. Frozen-snapshot admission inherits the exact pair and
cannot replace it. These CLI arguments work identically in all prompts above;
use the reviewed native descriptor path and digest, never a host library path.
Frozen-snapshot admission preserves the original live configuration and checks
the complete operational binding. Only authorization fields may change. A later
builder correction cannot silently repair or relabel a preserved failed build;
prepare a new preview with its own release ID and content review first.

Production uses the separate `--production-acceptance PATH` interface described
in `README_RELEASE_AUTHORIZATION.md`; it cannot be combined with temporary
qualification admission. Its exact-content selection/asset/full-backup receipt
remains usable after reboot and across sessions. Static local imports, including
late-label, sparse-embedding and raw modules when used, must all be packaged;
the builder rejects a missing local dependency before creating the snapshot.
When present, the separately admitted native variant and GUI qualification
drivers are included with their instructions and independent source backups.
Their presence does not enable either entry point or claim qualification.

## Prepared native staging interface

These are interfaces for the separately guarded native dispatcher. They were
prepared on the host; writing them does not execute them. The dispatcher must
register its actual early owner and check the current native baseline first.

```python
# Execute the verified install_candidate.py definitions in the owned inspector.
RESULT = stage_archive(PAYLOAD['archive_base64'], PAYLOAD['archive_sha256'],
                       PAYLOAD['manifest_sha256'])
```

`PAYLOAD` contains the base64 bytes of `field-runtime-v29-build-01-prepared.tar.gz` and the
two hashes from `BUILD_RESULT.json`. Staging only accepts the independent target
`/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29`,
or a versioned field-runtime-v29-build-N root, which must not exist. It checks tar member types, relative paths, complete
inventory, every digest, source backups, bounded total bytes, and the existing 5 GiB free disk floor
before an atomic fresh-directory rename and full readback. A failed temporary
stage remains for inspection. No old source or launcher is overwritten.

`install_candidate.py activate` is a distinct, later operation. It requires the
exact package manifest hash, explicit production acceptance and current baseline,
one explicit existing Desktop `.desktop` file, and its expected previous hash.
It writes and reads back two independent copies of that launcher before replacing
it atomically. It creates no autostart entry and starts no process. Review those
exact inputs in the native dispatcher before invoking activation.

## Prepared runtime wrapper

The eventual launcher invokes the pinned native interpreter with:

```sh
PY=/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python
N=/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29
"$PY" -B "$N/native_scope.py" --binding "$N/BINDING.json" --manifest-sha256 REVIEWED_PACKAGE_MANIFEST_SHA256 --data-root "$HOME/JustPeachy/data/runtime-v29"
```

The external owner is on CPU 3 with 128 MiB address space, 1 MiB stack, 32 MiB
file size, and a finite alarm. It starts one independent uniquely named systemd
user service. The GUI, worker, source and their descendants share AllowedCPUs
2–3, CPUQuota 200%, TasksMax 64 and a finite RuntimeMaxSec. The GUI has a 256 MiB
soft/768 MiB hard address limit so the bounded model worker can set its explicit
768 MiB limit. Its initial file-size soft limit is 32 MiB; its hard ceiling is
actual free space minus the existing 5 GiB floor. The worker narrows that ceiling
to its admitted finite session/database allowance. This avoids inheriting an
unraisable 32 MiB hard limit. Python threads receive explicit 1 MiB stacks.

Both owners verify the supplied package manifest hash, every runtime member,
and the complete file inventory before project imports. Enabled qualification
bindings also require the exact reviewed admission to be unexpired on the current
boot. Production acceptance is a separate immutable mechanism; the wrapper never
infers it from qualification. Each production Start checks the accepted selection,
finite policy, selected asset hashes, and complete-session supervisor time.

The service gate records its actual PID/start ticks/boot before project imports,
waits for the external `UNIT_OWNERSHIP.json`, checks the actual systemd invocation,
main PID and cgroup, then imports the launcher. The ownership receipt fields are
`unit`, `invocation_id`, `control_group`, `main_pid`, and exact `owner`. The
launcher watchdog can target only that verified unit. RuntimeMaxSec is independent
of that watchdog. The outer owner writes `UNIT_CLOSURE.json` after the service
stops and checks the main and registered source identities. The service writes a
durable `SERVICE_EXIT.json` with its actual headless return code before exiting.
The outer owner can verify success even if systemd already removed the inactive
transient unit. It checks the exact cgroup's recursive `populated` flag or
disappearance. Process disappearance
does not substitute for the source's physical stream/lease closure receipt.

For an explicitly reviewed headless test, append `--headless` and the documented
launcher selection flags. A long soak additionally requires both
`--maximum-session-seconds 3600 --developer-soak`; those exact values are forwarded
to the launcher and used in the containing service deadline. Drain/backlog flags
are forwarded and included in policy validation. Headless lifetime is the full
policy deadline plus300 seconds, including separate startup and closure reserve.
GUI lifetime is at least7200 seconds, or the full policy deadline plus450 if
larger. The GUI exits after300 idle seconds only without an active worker. Start
requires the full session deadline plus150 seconds remaining; otherwise reopen
the launcher for a fresh finite envelope. This wrapper is not a
claim that a 60-minute recording has been qualified.

## Verification scope

`test_package.py` runs CPU14 host-only checks of exact retained-capsule extraction,
disabled native admission, all-file round-trip validation, archive corruption,
path traversal rejection, invalid admission rejection, and finite systemd time
parsing. It never invokes systemd, SSH, models, microphones, staging, or activation.
Native behavior remains unexecuted until the separate reviewed dispatcher runs it.

`test_native_scope.py` separately checks file-size limit inheritance, forwarding
of long-session policy, failed headless return codes, durable exit receipts, and
rejection of an unlisted runtime module. It uses mocks and a fresh CPU14 owner;
It also checks the actual mounted BMI270 `close()` contract: success requires
both a True return and a dead sensor thread; incomplete closure retains its
owner, and a stuck speech lane does not skip sensor cleanup or destroy its model.
it executes no systemd command or native process:

```powershell
& $PY -B "$N/test_native_scope.py" --output-root "$B/live-runtime-20261003/audit-preparation"
```

```bat
"%PY%" -B "%N%\test_native_scope.py" --output-root "%B%\live-runtime-20261003\audit-preparation"
```

For only the focused IMU closure checks, append
`--checks test_motion_close_requires_true_and_dead_thread test_motion_closes_while_stuck_speech_model_remains_owned`
to either command. No native sensor or model is imported by these fixtures.

Startup failures after engine `begin()` but before source launch now use the
installed finalizer to drain journal, transcript and trace writers. Model
ownership stays retained when the finite cleanup deadline cannot reap them;
finalizer errors propagate before a session can report successful closure.
Focused PowerShell checks use:

```powershell
& $PY -B "$N/test_native_scope.py" --output-root "$B/live-runtime-20261003/audit-preparation" --checks test_prelaunch_cleanup_drains_real_writers_once test_prelaunch_cleanup_timeout_retains_model_until_reaped test_production_assets_match_pinned_content_addressed_catalog test_raw_template_requires_source_batch_pin
```

Command Prompt or Anaconda Prompt uses:

```bat
"%PY%" -B "%N%\test_native_scope.py" --output-root "%B%\live-runtime-20261003\audit-preparation" --checks test_prelaunch_cleanup_drains_real_writers_once test_prelaunch_cleanup_timeout_retains_model_until_reaped test_production_assets_match_pinned_content_addressed_catalog test_raw_template_requires_source_batch_pin
```

The writer test extracts only the pinned installed stdlib finalizer methods and
drains real bounded text writers with synthetic records. It loads no models or
native libraries. Each run emits owner and test-result receipts in a fresh folder.

The preserved build-01 preview predates these wrapper corrections and remains
disabled for integrated native launch. Use a fresh later build ID to package
the corrections. Never overwrite a staged or failed candidate.

For the separately reviewed five-second raw-only harness, `native_scope.py`
accepts `--entrypoint raw_qualification.py --raw-admission-template PATH
--raw-admission-template-sha256 SHA256`. The exact bounded template has schema
`just-peachy.raw-qualification-template.v1`, `reviewed: true`, `duration_seconds:5`,
current `boot_id`/future `expires_unix`, target, binding/package manifest SHA256,
and exact installed_source/raw_capture/source_batch SHA256 pins. After verifying its unique
actual unit/main owner, the wrapper writes a fresh invocation-bound admission
and supplies it to the harness. It never enables ordinary raw capture or starts
models through this harness. No raw qualification is claimed by preparing it.


## Saved-source batching derivative inventory

The external builder includes `saved_source_metrics.py` when present in the
reviewed copied source. Static local-import closure prevents a source using
that helper from producing a package that omits it. The retained66-file reference
capsule is unchanged. Qualification13 is host-prepared from exact disabled12 plus only
the separately reviewed saved/repeat/kept-source batching files and their README;
production14 would be a later reviewed relocation. Existing frozen packages are
never edited. Copy/compile/hash review is host preparation, not a native hour pass.
Use the same PowerShell/CMD/Anaconda build and exact-snapshot admission commands
above with the actual resulting source path, content/manifest pins and fresh
reviewed admission. Do not substitute mutable N wholesale for a frozen snapshot.

The current exact snapshot, fresh admission shape and stage-only recipe are in [README_BUILD13_PREPARATION](README_BUILD13_PREPARATION.md). It creates no production acceptance and runs no native job automatically.

The qualification14 late-label derivative adds the pure admitted_identity.py
module to the explicit runtime inventory. Its ordinary static import is checked
by the existing local-import closure pass; a missing helper fails preparation.
This is the only builder-code change from the13 preparer. Frozen13 source,
models, raw/source modules, galleries and policies are unchanged. Use
[README_IDENTITY_DERIVATIVE](README_IDENTITY_DERIVATIVE.md) for the exact disabled
snapshot and later fresh-admission procedure; no native qualification is implied.