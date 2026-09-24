# Task08 — consolidated CM5 source release and wiring plan

20 September 2026. Release **proto1-0.2.0** consolidates implemented tasks01–07
and task08. Windows desktop and future Linux ARM64 use the same source and
unchanged S6/S7/PROTO1 models/recipes. No research sweep, model refresh, training,
new dependency, firmware flash, eMMC imaging, remote deployment, automatic
commit/push or production-profile mutation. Stop after08; optional09–12 remain
pending. The master Word workbook was not edited.

## Deliverables and use

- Release: `G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.2.0.zip` and
  adjacent `.receipt.json`. File hashes are inside `RELEASE_MANIFEST.json`.
  Hashes provide integrity; this is not a publisher signature. No private audio,
  enrollment vectors, duplicate models or research corpus is included.
- [Exact Windows/CMD/Anaconda and Linux commands](CM5_RELEASE_QUICKSTART.md).
  Normal GUI launch is idle/mic Off; live use is explicit XVF Start/consent.
  Native file replay can run headlessly. Windows does not require a Pi.
- [Update/rollback workflow](PI_DEPLOYMENT_WORKFLOW.md),
  [fill-in wiring and hardware-arrival checklist](CM5_WIRING_AND_BRINGUP.md),
  [disabled/null hardware template](HARDWARE_PENDING.json),
  [mode guide](../MODE_GUIDE.md), and
  [dependency/source ledger](UIITER2_08_DEPENDENCIES.json).
- Local verification/checkpoint: repository `Resumes/.uiiter2_08/`.
  Relocated installation: `G:\Just_Peachy_PROTO1\UIITER2 08 Relocated Application`.
  Final export execution receipt: `Resumes/.uiiter2_08/export/FINAL_RELEASE_RESULTS.json`.
  It is separate from the immutable payload to avoid a self-hashing manifest.

## Evidence status

| Status | Scope |
|---|---|
| **software-prepared** | Cumulative source, hashed manifest, shared models, external private data, staged update/rollback, feature flags, bounded storage, disabled peripheral interfaces, wiring worksheet |
| **Windows-tested** | 257 application tests; 22 packaging tests; actual native short-file portrait/archive session. Export-specific relocation, actual PS1/CMD idle launches, injected startup failure and fixture rollback are bound separately in the final export receipt |
| **Linux x86-64 tested** | Existing Ubuntu WSL, Python3.14.4, glibc2.43: 22 stdlib packaging tests, shell syntax/architecture guard. This is neither the selected Python3.11 target nor ARM64 inference |
| **ARM64-tested: NO** | Thirteen existing CPython3.11 aarch64/pure wheels rehashed (89,968,134 bytes); no new downloads. Artifact preparation does not establish native execution |
| **hardware-pending** | Actual CM5 2 GB/32 GB/no-wireless system, thermal/memory/latency/storage qualification, display/touch wiring, native ARM64 XVF control, BMI270/camera/GPIO drivers and fresh live participant checks |

The final export verifier checks actual immutable installed code with the expanded
13-module portable contract suite, a native caption file, Windows launchers and
safe rollback. It uses an external hidden-Tk close hook only for the two launcher
smoke tests; those do not claim pixel accuracy. Separate real portrait screenshots
from the native session were inspected. The rollback second version changes
manifest/version metadata only; application bytes stay identical. Prepared CMU
fixture people, if supplied, and a synthetic sentinel are hashed before/after;
no human/production enrollment is used.

## Integrated desktop result

`native_session_v2/SESSION_ARCHIVE_CHECK.json`: PASS. One previously prepared
12-second CMU mono16k fixture, 192,000 samples. Exact float32 archive bytes equal
the source (no second gain); 70 analysis-window records and 14 resource samples;
clean CLOSED epoch with no archive error. Save, annotation/export, close,
restart and reopen passed. Playback used an explicit fake sink, not speakers.
Anonymous/Balanced → Captions/Fast switch reused one ASR and one speaker-model
load; reopen loaded no models. No source-gap, queue-overflow or device error was
reported on this native file path. Real microphone gap/disconnect behavior is
covered here by deterministic fixtures, not a fresh hardware recording.

Actual Tk portrait: 480×800 client pixels; 398 UI updates during processing,
largest measured update gap 0.475 s. RSS rose from 114.6 MiB before inference to
487.6 MiB sampled peak and 490.1 MiB after mode/control work; model loading is
included. Total check 16.83 s, last archived CPU total 7.70 s. This short check
observes memory use; it is not a long-run leak test or evidence that a whole
2 GB Pi meets deadlines. No unnecessary soak/all240 campaign ran.

Fault evidence: `test_sessions` covers bounded slow-writer exhaustion, full-disk
policy, interrupted/torn archive recovery, saved-session retention and no person
deletion. Lifecycle/source tests cover failed startup, callback overflow/stall,
disconnect, source closure and lock ownership. Release tests cover corrupt/hash-
mismatched archives, insufficient compatibility, active-app exclusion, missing
models, activation and rollback. The export check additionally injects malformed
JSON into isolated fixture settings: startup must fail and release its lock while
preserving enrollment bytes. It removes only the injected test bytes before
rollback; rollback itself does not repair corrupt personal settings.

One initial software-check pass exposed old minimal controller fixtures without
the new optional motion member; snapshot now defaults safely to hardware-pending.
The first expanded native harness also attempted to close a controller already
closed by the GUI; the harness now respects completed closure. Final receipts
supersede these retained diagnostic runs. Neither issue required changing the
speech engine, embeddings or capture logic.

## New motion and release safety

`app/motion.py` provides bounded timestamped stationary/moving/settling events,
quality, simulated provenance, host-clock validation and explicit uncertainty.
No hardware driver or poller is enabled. Moving/settling, unreliable/stale events
or unknown translation/range invalidate assigned-seat trust and show manual
re-anchor guidance. Fresh stationary evidence never proves identity or restores
an anchor automatically. Tests confirm enrollment file hashes are unchanged.
No absolute position/yaw, mock room tracking or relative-angle correction is
claimed; the linear array's front/back ambiguity remains. Manual movement
controls work without a sensor. Automatic IMU support for the other spatial
modes remains pending.

`config/release_capabilities.json` declares supported data features and pending
features. The updater and activated launcher check schema1 **and** paragraph
reader compatibility. Older releases cannot read task06 paragraph references;
the current updater refuses such a downgrade before switching pointers. It never
deletes/rewrites references to make rollback succeed. Use a compatible previous
release and the current updater; an old updater lacks this guard. No data migration
is run. External data/models remain separate from replaceable code/runtimes.

## CM5 bring-up boundary

Initial target: Raspberry Pi OS64 Bookworm, aarch64, CPython3.11, glibc≥2.36.
Native libraries and optional drivers remain target-specific. The supplied
firmware-v3.2.1/v3.0.0-host `rpi` executable and USB/command-map libraries were
rechecked as **ARM32**, not ARM64. Matching source and vendor guide are retained;
build/qualify native host + firmware-matched generated command map on the CM5,
then read-only version/routing queries before live activation. No claim that a
native ARM64 build will succeed without bring-up work. Do not flash firmware as
an application-update shortcut.

Wired SSH/SCP or trusted USB import supports stage → hash/space/import/model
healthcheck → stop app → activate → desktop test → compatible rollback. No
remote host/user/key was supplied or contacted. OS provisioning is separate.
Camera stays optional/on-demand; autofocus/driver pending. GPIO buttons are
logical actions until pins/mux/pulls/debounce are verified. Display/touch failure
does not block headless replay. All unknown connector/pin/bus/address/axes/rate/
interrupt/clock-offset fields remain null and disabled.

Acoustic enrolled-name bias remains unavailable without matching qualified ASR
BPE assets. Default-off text assistance remains separate from identity. Fresh
human enrollment, physical touch, real IMU/camera/buttons and complete-system CM5
performance remain the next hardware checks, not unreported software successes.

## Source rollback

Before08 checkpoint: `Resumes/.uiiter2_08/prototype_before_08.zip`, preserving
all local tasks01–07. `restore_before_08.py` is dry-run by default, checks hashes
and refuses later edits. See its local README; applying it rolls back source only,
never private people/models or historical release archives. Task08 changes remain
local and uncommitted. `UIITER2_08_CHECKS.json` binds current source/checks; earlier
task receipts remain historical evidence for their own source epochs.
