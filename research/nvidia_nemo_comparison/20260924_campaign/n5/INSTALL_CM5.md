# Install later on the offline CM5

Status: package preparation and static ARM64 verification only. Full target
installation/model/GUI/hardware checks are NOT_TESTED. Do not run deployment
during this campaign; the Pi is off. No OS/eMMC or XVF flashing is included.

Target is Raspberry Pi OS 64-bit Bookworm, aarch64, glibc ≥2.36, CPython 3.11.
The existing OS must provide python3.11-venv, python3-tk, libportaudio2,
libsndfile1, libusb-1.0-0, libgomp1, libstdc++6, libgcc-s1 and zlib1g. Provision
these OS packages before offline use; this bundle does not contain an OS or
apt repository. The wheel audit found libz.so.1 as an additional OS dependency.
All 13 Python wheels and eight baseline assets are prefetched; pip uses
`--no-index --require-hashes`. No training environment or CUDA is included.

From PowerShell, check the archive against ARTIFACT_INDEX.json and extract it
onto a USB drive or chosen transfer directory (substitute your actual path):

```powershell
Get-FileHash 'G:\Just_Peachy_N1\20260924_campaign\local\n5\releases\just-peachy-baseline-cm5-offline-v1.zip' -Algorithm SHA256
Expand-Archive -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\local\n5\releases\just-peachy-baseline-cm5-offline-v1.zip' -DestinationPath 'PATH_TO_NEW_BUNDLE_DIRECTORY'
```

CMD/Anaconda Prompt uses `certutil -hashfile "ARCHIVE_PATH" SHA256` and
`powershell.exe -NoProfile -Command "Expand-Archive -LiteralPath 'ARCHIVE_PATH' -DestinationPath 'PATH_TO_NEW_BUNDLE_DIRECTORY'"`.
The paths in capitals are explicit user-supplied values, not credentials.

On the connected CM5 later, ordinary user, from the extracted bundle:

```bash
python3.11 bootstrap/verify_bundle.py --root .
bash install-offline.sh "$HOME/.local/share/just-peachy" "$HOME/.local/share/just-peachy-data"
# After successful staged health checks, optionally activate the same version:
bash install-offline.sh "$HOME/.local/share/just-peachy" "$HOME/.local/share/just-peachy-data" --activate
python3.11 bootstrap/release.py healthcheck --root "$HOME/.local/share/just-peachy" --data-root "$HOME/.local/share/just-peachy-data"
```

Launch later from the graphical desktop with the installed runtime:

```bash
JP_ROOT="$HOME/.local/share/just-peachy"
"$JP_ROOT/runtimes/n1-common-20260924-v1/bin/python" "$JP_ROOT/releases/n1-common-20260924-v1/release_tools/launch_current.py" --root "$JP_ROOT" --data-root "$HOME/.local/share/just-peachy-data"
```

For wired SSH/SCP later, the current repository's
`prototype/release_tools/deploy_pi.ps1` takes `-PiHost`, `-UserName`,
`-IdentityFile`, `-Archive`, `-RemoteRoot`, `-RemoteDataRoot`, `-Wheelhouse`,
`-Models`, optional `-Activate` and `-DryRun`. Supply the actual verified host
and key; strict host-key checking stays enabled. A dry run only prints a plan.
The corrected helper transfers runtime_lock.py. Do not use historical example
IP addresses in older application docs as current device authority.

The wrapper verifies every bundle member before staging. The installer refuses
root, a non-aarch64 machine, wrong Python and missing runtime before activation.
Hashes provide integrity; separately trust the publisher/transfer source.
Personal data is external. Models with matching content hashes are reused.
