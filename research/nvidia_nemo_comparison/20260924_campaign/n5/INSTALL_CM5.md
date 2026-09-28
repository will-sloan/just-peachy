# Install later on the offline CM5

Status: baseline package preparation, static ARM64 verification and passing
emulated baseline Sherpa C-API ASR parity (four cases plus eight invalid WAVs).
See `BASELINE_ARM64_CPU_RETEST_V2.json`; explicit Cortex-A76 emulation was
required. Full target installation/Python/model-stack/GUI/hardware checks are
NOT_TESTED. Do not run deployment
during this campaign; the Pi is off. No OS/eMMC or XVF flashing is included.

Target is Raspberry Pi OS 64-bit Bookworm, aarch64, glibc ≥2.36, CPython 3.11.
The existing OS must provide python3.11-venv, python3-tk, libportaudio2,
libsndfile1, libusb-1.0-0, libgomp1, libstdc++6, libgcc-s1 and zlib1g. Provision
these OS packages before offline use; this bundle does not contain an OS or
apt repository. The wheel audit found libz.so.1 as an additional OS dependency.
All 13 Python wheels and eight baseline assets are prefetched; pip uses
`--no-index --require-hashes`. No training environment or CUDA is included.

Before extraction/installation on the Pi, transfer the original ZIP and the
separate Git-verified `pi_storage_preflight_v1.py` companion. Follow
`README_PI_STORAGE_PREFLIGHT_V1.md` with the actual archive path and separate
absolute install/data roots. It verifies the full archive and declared members,
checks prerequisite metadata and reads actual target free space without creating
those roots. Require `PREREQUISITE_METADATA_PASS_ONLY` and `ESTIMATED_FIT` in
the report before continuing; resolve failures first. A successful process exit
alone is not enough: the report contains the prerequisite and space outcomes.

The preserved baseline needs an estimated 2.80 GiB additional free space under
the documented conservative budget, including a 1-GiB reserve and an unmeasured
512-MiB overhead allowance. It gives no credit for existing files and preserves
existing rollback releases. This is not a measured installation size or RAM
result. Final optional backend bundles need their own matching inventory.
The companion and these updated instructions are outside the unchanged v1 ZIP;
the ZIP's older embedded instructions remain preserved for provenance.

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
