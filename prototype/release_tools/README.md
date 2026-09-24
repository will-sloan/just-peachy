# Release tools: purpose, inputs and outputs

Current CM5 deployment: see `../docs/CM5_I2S_MIGRATION.md` and
`../app/README_IMU.md`. The current UI supports saved microphone permission and
optional one-shot listening on launch. Unset permission still opens stopped.
Source releases now include native C/H sensor sources and licences; compiled
architecture-specific helpers stay outside the immutable release. Older
hardware-pending statements below are historical PROTO1/task08 results.

These Python standard-library tools build immutable Just-Peachy source releases, verify and stage them, switch a portable `current.json` pointer, roll back code, and collect small privacy-limited diagnostics. They never start recording, flash firmware, modify the OS audio default or delete personal data. A stopped application is required for activation: application and updater acquire the same external `runtime.lock` atomically. Linux locks with proven dead owners or a different boot ID are safely recovered; active and uncertain owners remain protected. See README_STARTUP.md.

Inputs: `prototype/` source, explicit version, separate `config/assets.json` content identities, external shared model directory, an explicit install/data directory, and optionally an offline ARM64 wheelhouse. Outputs: versioned ZIP plus SHA256 receipt; immutable `releases/<version>`; `current.json`, `previous.json` and small activation history; optional diagnostics JSON. People, vectors, recordings, models and research evidence are excluded from source ZIPs. Source hashes are rechecked during build. Checksums establish integrity, **not publisher authentication**: accept only an archive from a trusted source.

## Windows PowerShell

Use the existing project environment; no installation or environment activation is needed:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -m unittest discover -s .\release_tools\tests -v
& $py .\release_tools\release.py build --source . --output 'G:\Just_Peachy_PROTO1\releases' --version proto1-20260919-01
```

Versions are immutable; choose a new version after edits. Do not rebuild an existing version in place. Before final build, complete fast tests and the physical portrait/live check recorded by the main application report.

## CMD / Anaconda Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m unittest discover -s release_tools\tests -v
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" release_tools\release.py build --source . --output "G:\Just_Peachy_PROTO1\releases" --version proto1-20260919-01
```

## Local staging and rollback rehearsal

The `release.py` commands work on Windows and Linux. The following is a **local sandbox**, not Pi deployment. Replace the archive version with the newly built version and SHA256 with the build receipt. Use separate external test data, never the live personal data directory for experiments.

```powershell
& $py .\release_tools\release.py stage --archive 'G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-20260919-01.zip' --root 'G:\Just_Peachy_PROTO1\release sandbox' --sha256 '<receipt SHA256>'
& $py .\release_tools\release.py activate --root 'G:\Just_Peachy_PROTO1\release sandbox' --data-root 'G:\Just_Peachy_PROTO1\release test data' --version proto1-20260919-01
& $py .\release_tools\release.py healthcheck --root 'G:\Just_Peachy_PROTO1\release sandbox' --data-root 'G:\Just_Peachy_PROTO1\release test data'
& $py .\release_tools\release.py collect-diagnostics --root 'G:\Just_Peachy_PROTO1\release sandbox' --data-root 'G:\Just_Peachy_PROTO1\release test data' --output 'G:\Just_Peachy_PROTO1\release-diagnostics.json'
```

Activate a second staged version, then `rollback --root ... --data-root ...`. Code/config and the version-specific dependency environment switch; people/settings remain unchanged. Schema 1 is supported. Existing data without a schema or a future schema is refused. No destructive automatic migration exists. A live or uncertain runtime lock blocks activation. Linux crash/reboot recovery follows README_STARTUP.md; age alone never permits recovery.

`healthcheck --models --imports` additionally verifies every shared model hash and imports the selected native runtime libraries without opening a microphone. It does not prove successful neural inference, device routing or GUI operation; those have separate application acceptance checks.

`verify_actual_release.py` performs the actual source-release acceptance: build an unused version, stage into a path with spaces, verify separately supplied shared models, activate and roll back a clearly labelled metadata-only second-version fixture while preserving synthetic private bytes, execute one existing prepared C105 WAV natively, and launch both real Windows launchers with an external child-only test hook that hides Tk and invokes its normal Close callback after one second. It opens no microphone, contacts no host, and never uses existing personal data. The hidden launch check proves application startup/shutdown, not physical pixel dimensions or live speech. The synthetic source/privacy fixture and hook remain outside the source/release. Inputs and a PowerShell invocation:

```powershell
& $py .\release_tools\verify_actual_release.py --source . --version proto1-0.1.0 --output 'G:\Just_Peachy_PROTO1\releases' --root 'G:\Just_Peachy_PROTO1\Relocated Windows Application' --models 'C:\Users\amiri\JustPeachy\shared\models' --wav 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav' --evidence .\release_tools\evidence\actual_release
```

From CMD/Anaconda, replace `& $py` with the quoted full Python path from the earlier example. Use a fresh version and fresh external root for a new run; archives are immutable. Outputs include `ACTUAL_RELEASE_RESULTS.json`, archive/hash receipts, small launcher logs, the relocated native result and external closure receipts. The prepared O0 WAV is already gained and is read at unity by the normal application file adapter.

For the final release after an RC, add `--baseline-archive <RC ZIP> --receipt-name FINAL_RELEASE_RESULTS.json --focused-contracts`. The verifier writes exact changed-file hashes and `RC_TO_FINAL.patch` for changed Python runtime files, retaining the baseline archive unchanged. The focused option invokes `run_relocated_contracts.py` against the newly installed release. It copies only six model-free test modules into an external harness, replaces their source-root expressions with the installed release path, preserves their assertions, and records both test-source hashes and actual imported runtime paths/hashes. It loads no models and opens no microphone. The independent helper accepts `--release <installed version> --tests <source tests> --harness <new external folder> --output <JSON>`; run it with the same Python executable/PowerShell or CMD conventions above.

## ARM64 offline dependencies

Declared target: **Raspberry Pi OS 64-bit Bookworm, aarch64, CPython 3.11, glibc 2.36 or newer**. Do not install this CPython lock into a different interpreter/OS. A newer Raspberry Pi OS release requires a separately resolved and tested lock. The Windows venv must never be copied to a Pi.

The existing artifact set is `G:\Just_Peachy_PROTO1\arm64 cp311 wheels`: 13 downloaded wheels, 89,968,134 bytes, checked against official PyPI publication hashes. It includes the selected NumPy 2.2.6, SciPy 1.15.3, ONNX Runtime 1.29.0, Sherpa-ONNX/core 1.13.4, sounddevice 0.5.5, soundfile 0.13.1, psutil 7.2.2, CFFI 2.1.1 and resolved transitive dependencies. No global packages were installed or upgraded.

To deliberately refresh the wheelhouse and lock (networked desktop only):

```powershell
& $py .\release_tools\prepare_arm64.py --output 'G:\Just_Peachy_PROTO1\arm64 cp311 wheels'
```

The script downloads binaries for the declared target without installing them, verifies publisher SHA256 values, writes `requirements-arm64.lock`, `evidence/ARM64_WHEELS.json`, and copies exact third-party licence texts into `licenses/`. A refreshed resolver can change transitive versions: review the new lock and repeat target tests before deploying it. The frozen checked lock is the reproducibility authority.

An administrator must provision OS packages separately: `python3.11-venv`, `python3-tk`, `libportaudio2`, `libsndfile1`, `libusb-1.0-0`, and `libgomp1`. The installer does not call sudo/apt or change groups/rules. Use the normal desktop user's existing audio/session permissions. For XVF vendor control, inspect the actual USB VID/PID and create the narrowest user ACL/udev rule if necessary; do not run the GUI as root or grant all USB devices write permission.

## Explicit Pi transfer — no host discovery

User-supplied host/user/key, a trusted SSH host key already in `known_hosts`, and modern OpenSSH/SCP with SFTP support are prerequisites. No target was supplied or contacted in PROTO1. Inspect a dry run first; remove `-DryRun` only when the user has supplied/authorized the actual Pi:

```powershell
.\release_tools\deploy_pi.ps1 -PiHost 'YOUR-PI-HOST' -UserName 'YOUR-USER' -IdentityFile 'C:\path\to\private-key' -Archive 'G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-20260919-01.zip' -RemoteRoot '/home/YOUR-USER/.local/share/just-peachy' -RemoteDataRoot '/home/YOUR-USER/.local/share/just-peachy-data' -Wheelhouse 'G:\Just_Peachy_PROTO1\arm64 cp311 wheels' -Models 'C:\path\to\content-addressed-models' -Activate -DryRun
```

Use actual lowercase Unix user values. No password or private-key content is saved. The deployment probes `aarch64`/Python 3.11/non-root status, stages only after integrity/free-space checks, installs offline wheels into `runtimes/<version>`, verifies imports/models, then optionally activates at a safe stopped-app boundary. An existing personal-data lock stops activation, not the running app. It does not force-kill processes or open the GUI from SSH. Source staging without models/wheels is possible, but activation via installer requires both a prepared runtime and verified model assets.

After the initial transfer, omit `-Models` when the new release uses the same model hashes: the existing shared store is verified and reused without retransferring weights. Each new version keeps its own environment for rollback; provide the offline wheelhouse again or reuse its already copied directory when running the installer directly. No Windows environment is copied.

## Removable USB uses the same archive

On the Pi, after copying the release tools, archive, wheelhouse and content-addressed models from trusted USB media:

```bash
bash /media/USER/USB/release_tools/install_pi.sh \
  --archive /media/USER/USB/just-peachy-proto1-20260919-01.zip \
  --sha256 RECEIPT_SHA256 \
  --root "$HOME/.local/share/just-peachy" \
  --data-root "$HOME/.local/share/just-peachy-data" \
  --wheelhouse /media/USER/USB/wheelhouse \
  --models /media/USER/USB/models --activate
```

For staging only, `python3.11 release.py usb-import --archive ... --sha256 ... --root ...` calls the same bounded extraction/hash verifier as SSH staging. `import-models --release <staged directory> --source-models <USB models> --target-models <install root>/models` copies only manifest-bound assets, verifies hashes, and reuses unchanged files. No personal profile export is part of deployment.

Launch **from the logged-in graphical desktop** (not a root/headless service):

```bash
python3.11 "$HOME/.local/share/just-peachy/releases/proto1-20260919-01/release_tools/launch_current.py" \
  --root "$HOME/.local/share/just-peachy" --data-root "$HOME/.local/share/just-peachy-data"
```

This reads the current pointer and selects its matching runtime/source. It preserves personal data and opens the app stopped; recording still requires the app's explicit consent. A desktop/autostart entry may invoke that command in the ordinary user session after hardware bring-up; no system service was installed here. `launch_current.py` intentionally refuses a Linux environment without DISPLAY/WAYLAND_DISPLAY.

## Tests, limitations and helper contracts

N5 transfer fix: wired deployment copies `runtime_lock.py` beside `release.py`
in the remote inbox. Without it, the standalone installer fails during Python
import before staging. The dry-run test now reconstructs the transferred helper
set in a fresh temporary directory and invokes its CLI help with the selected
Python, in addition to checking host-key flags. This performs no SSH or device
access. Run the existing `run_checks.py --output NEW_DIRECTORY --wsl` commands
below to reproduce; outputs include the helper-import result. Older immutable
archives remain untouched; use this current deploy helper for a future transfer.

`tests/test_release.py` uses temporary fixtures and a path containing spaces. The checks exercise archive integrity/traversal/case/symlink refusal, idempotent staging, immutable versions, atomic owner exclusion, schema rejection, activation/rollback and unchanged private bytes, shared assets, and privacy-limited diagnostics. They contain no real voice data.

For one complete local release-tool check and machine-readable evidence, run `& $py .\release_tools\run_checks.py --output .\release_tools\evidence --wsl` from PowerShell, or the same Python invocation without `&` from CMD. Omit `--wsl` if no existing Ubuntu WSL installation is present. The harness runs the bounded tests, parses PowerShell, exercises an explicit **non-networked** deploy dry run with a fake key placeholder, checks Bash syntax and (when requested) runs the same installer library tests on actual Linux x86_64. It writes `RELEASE_TEST_RESULTS.json`, `DEPLOY_DRY_RUN.json` and short text logs. `tests/test_deploy.ps1` is a harness helper; it never invokes SSH in its DryRun call. No WSL distribution or system package is installed by the harness.

`hardware_adapters.py` contains disabled/null peripheral interfaces and an explicitly simulated test adapter. Neither opens GPIO, camera or an IMU. `docs/HARDWARE_PENDING.json` retains unknown buses, addresses, pins, touchscreen driver and transforms as null/disabled.

`audit_xmos_artifacts.py --binary-zip <vendor ZIP> --output <JSON>` reads ELF headers without extraction or device access. The actual supplied `rpi` host, USB library and command map are ARM32, not ARM64. See the native build prerequisite and first-boot checklist in `../docs/PI_DEPLOYMENT_WORKFLOW.md`.

Evidence labels: Windows release-tool tests and Linux x86_64 stdlib tests are executed; ARM64 wheel artifacts are prepared; native CM5 audio, GUI/touch, sensor support, sustained 2 GB memory/thermal fit and matched ARM64 XMOS control are **not tested**. Full `install_pi.sh` execution remains target-pending; shell syntax and its wrong-architecture refusal are tested locally. A model import is not a neural performance test.
# Task08 consolidated export — proto1-0.2.0

This version includes accepted iterations01–07 and the task08 release/motion
contracts. `config/release_capabilities.json` declares features, defaults and
pending hardware work. See `../docs/UIITER2_08_HANDOFF.md` for measured results,
`../docs/CM5_RELEASE_QUICKSTART.md` for exact commands, and
`../docs/CM5_WIRING_AND_BRINGUP.md` for the fill-in wiring/arrival checklist.
The older 0.1.4 archives remain historical.

Task08 `verify_actual_release.py` also accepts `--fixture-people PATH` for an
explicit nonproduction prepared-fixture store. It copies those files only to
the external test-data root and verifies every hash after an injected startup
failure and rollback. Invalid JSON is deliberately injected into that fixture's
settings, checked for clean lock release, then the injected bytes are removed.
Rollback itself does not fix corrupt user settings. The metadata-only rollback
archive lives in the evidence directory, not beside the user release. No
production data is modified. Test suites remain in the repository/external
harness; the portable payload's self-test is `release.py healthcheck`, with
`main.py file` for genuine native inference on a supplied WAV.

The updater and `launch_current.py` now check paragraph-enrollment reader
compatibility as well as schema1. They scan bounded per-person metadata and
refuse older manifests lacking `paragraph-enrollment-v1`. No profiles are
deleted or converted. Rollback to another compatible release is supported;
rollback to pre-task06 after paragraph enrollment is intentionally refused.
Use this current updater, not a historical updater that lacks this check.

`run_relocated_contracts.py` now covers 13 model-free test modules spanning
timing, source lifetime, profiles, roster, seats/motion, paragraph enrollment,
archives and text assistance. It rebinds source paths and two helper-import
names only; assertions are retained and imported release files are hash-bound.
Its inputs/outputs and invoking command remain those documented below.
