# Offline startup and ownership recovery

Purpose: start the installed current release automatically when the Pi logs into
its desktop, without Ethernet. Also provide a visible Just Peachy desktop icon
and an executable shell launcher. Desktop autologin must already be configured.
Inputs: an installed release/runtime, local models, saved settings and private
data. Outputs: GUI, existing session outputs, and ~/JustPeachy/startup.log.
No packages or models are downloaded at startup.

## Raspberry Pi terminal

Run as the normal desktop user, not root, after installing the release:

```sh
python3 ~/JustPeachy/install/releases/proto1-cm5-20260923-rc5/release_tools/install_autostart.py --root ~/JustPeachy/install --data-root ~/JustPeachy/data
```

Reboot to test automatic launch. To reopen manually, double-click **Just Peachy**
on the desktop, or open `~/JustPeachy/start-prototype.sh` and select Execute.
The equivalent terminal command is:

```sh
~/JustPeachy/start-prototype.sh
tail -n 50 ~/JustPeachy/startup.log
```

The launcher follows current.json, including future activated releases. Keep its
anchor release installed. The saved microphone permission/listening preference
controls recording; this installer does not change consent or sensor mounting.
Use normal OS shutdown before disconnecting power to flush recordings.

## Recovery rules

The old exclusive-create runtime.lock survived power loss and blocked startup.
App and updater now share an OS-owned guard plus the legacy ownership record.
On Linux a record is reclaimed only when its boot ID differs, or its PID no
longer exists. No wall-clock/age guess is used. Active, malformed and uncertain
records remain protected. Windows conservatively preserves stale legacy records.
PID reuse in a legacy record can conservatively require manual inspection.
The guard releases on process death; its file must never be manually deleted.
Complete metadata is atomically published so a crash cannot publish an empty
new ownership record. Older releases still respect runtime.lock.

## Developer checks (no microphone or inference)

PowerShell from repository root:

```powershell
$env:PYTHONPATH="$PWD\prototype"
& .\.edge-speech-env\python.exe -m unittest discover -s prototype/tests -p test_runtime_lock.py -v
```

CMD / Anaconda Prompt from repository root:

```bat
set PYTHONPATH=%CD%\prototype
.edge-speech-env\python.exe -m unittest discover -s prototype\tests -p test_runtime_lock.py -v
```

On Linux, with source and test file available:

```sh
PYTHONPATH=/path/to/prototype python3 /path/to/prototype/tests/test_runtime_lock.py -v
```

Tests cover live app/updater exclusion, uncertain legacy records, Linux boot
recovery, crash recovery and concurrent contenders. Linux-specific tests skip on
Windows; execute them on the Pi before claiming crash recovery verified.
