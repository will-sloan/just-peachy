# Runtime activation and local rollback, version 1

Purpose: support F04/F17/F18/F19 by installing a guarded startup transition from the existing idle baseline to the finite offline manager. This source set is PREPARED; it has not activated the Pi.

The rollback utility restores only the exact candidate autostart file from two independently verified original copies. It refuses unrelated edits, running candidate processes, active capture, changed personal settings, or a changed original launcher. It does not delete failed releases or recordings. Each attempt consumes one of sixteen separately allocated receipt slots. The original baseline is restored through a named local systemd service; this restores the existing application's resource behavior, while retaining two CPUs, 200% aggregate CPU and 64 tasks. This is not a new model qualification.

Manager4 retains manager3 and adds a maximum ten-second wait for the exact installer unit and boot/PID/start identity recorded in the pinned rollback binding. All other active research units reject startup. The original manager-only envelope is checked afterward. This avoids exempting a general family of helper processes.

## Inputs and outputs

- field_runtime_activation_v1.py: canonical activation tree, exact binding SHA256, original autostart backup plus independent restore, code SHA, current personal-settings/launcher pins, sixteen precreated receipt directories, and an 8 MiB independent activation reservation.
- field_runtime_manager_v4.py: existing manager CLI plus control/ROLLBACK.json pointing to the exact sibling activation binding.
- prepare_runtime_activation_v1.py: pure launch/service renderer, described by its function docstring; no native mutation.
- Outputs: immutable OWNER/RESULT or FAILURE for each rollback attempt; only a compare-before-replace restoration of the candidate autostart; the retained baseline opened idle.
- Source/host preparation does not constitute actual rollback, installation, service envelope, current owner closure, model execution or offline proof.

## Running

These are native Linux service entrypoints, not standalone Windows launchers. The installation issuer must first create a measured finite admission, inspect all owners, independently back up affected active files, and pin all generated assets. Do not substitute the old consumed asset policy or a preview SHA.

On the Pi, the installed rollback unit executes:

```sh
/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v1-activation/field_runtime_activation_v1.py --root /home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v1-activation --binding-sha256 ACTUAL_PIN
```

The issuer supplies ACTUAL_PIN and a fresh versioned root. Do not run this example directly.

PowerShell read-only syntax check after source backup:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); import ast,pathlib; ast.parse(pathlib.Path('field_runtime_activation_v1.py').read_text(encoding='utf-8')); print('syntax OK')"
```

Command Prompt / Anaconda Prompt, from this source directory:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import ast,pathlib; ast.parse(pathlib.Path('field_runtime_activation_v1.py').read_text(encoding='utf-8')); print('syntax OK')"
```

A production installer/issuer and local rollback exercise are still required. Failure receipts preserve incomplete startup and never assert the utility's own physical death.

