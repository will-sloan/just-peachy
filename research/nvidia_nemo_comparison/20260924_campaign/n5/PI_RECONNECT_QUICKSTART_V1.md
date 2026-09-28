# Reconnect and stage the preserved baseline on the Pi

Purpose: put the existing baseline, storage preflight and install/rollback
instructions in one transfer workflow. This is a later, user-operated procedure;
the offline campaign has not contacted or installed anything on the Pi.

Inputs: the two archives below, an actual transfer directory, a Raspberry Pi OS
64-bit Bookworm installation with CPython 3.11, and separate install/data roots.
Outputs: a preflight JSON report, an immutable staged baseline and its runtime,
then an explicitly activated version pointer if the later checks pass. Personal
profiles and transcripts stay in the external data root. No OS/eMMC/XVF flashing
or automatic microphone capture is part of this procedure.

This bundle contains the preserved N1 baseline. New Nemotron combinations are
engineering candidates, not validated Pi GUI choices in this bundle. Baseline
Sherpa ASR passed its emulated ARM64 C-API protocol; the complete ARM64 Python,
Tk, speaker, punctuation and GUI path remains unverified. Short A2/A3 emulated
checks do not clear the longer A2 timeout. N4/N5 remain partial.

## 1. Transfer these two files later

| File | Windows source |
| --- | --- |
| Baseline core, 310,867,595 bytes | `G:\Just_Peachy_N1\20260924_campaign\local\n5\releases\just-peachy-baseline-cm5-offline-v1.zip` |
| Small companion | `G:\Just_Peachy_N1\20260924_campaign\local\n5\pi-reconnect-companion-v1\just-peachy-pi-reconnect-companion-v1.zip` |

Copy both into a new folder on your chosen USB drive or authenticated transfer
location. Keep the original archives. The companion contains these instructions,
the preflight script, a baseline inventory and supporting notes; it does not
duplicate models. The report handoff ZIP is a separate analysis artifact, not an
installer. Do not infer a device IP or storage capacity from an old guide.

Verify both files against the separately trusted Git-backed
`RECONNECT_COMPANION_CHECK_V1.json` and `ARTIFACT_INDEX.json`. The manifest inside
an archive alone is not an independent trust source. The baseline SHA256 is:

```text
913e0a082e2de5f28e62f30503097cfb12f9008ed6d26fd1a803a7a2e8d32bbf
```

PowerShell, before transfer (repeat on the copied files using their actual paths):

```powershell
$jpCore='G:\Just_Peachy_N1\20260924_campaign\local\n5\releases\just-peachy-baseline-cm5-offline-v1.zip'
$jpCompanion='G:\Just_Peachy_N1\20260924_campaign\local\n5\pi-reconnect-companion-v1\just-peachy-pi-reconnect-companion-v1.zip'
Get-FileHash -LiteralPath $jpCore -Algorithm SHA256
Get-FileHash -LiteralPath $jpCompanion -Algorithm SHA256
```

CMD / Anaconda Prompt, with no environment activation required:

```bat
certutil -hashfile "G:\Just_Peachy_N1\20260924_campaign\local\n5\releases\just-peachy-baseline-cm5-offline-v1.zip" SHA256
certutil -hashfile "G:\Just_Peachy_N1\20260924_campaign\local\n5\pi-reconnect-companion-v1\just-peachy-pi-reconnect-companion-v1.zip" SHA256
```

## 2. Check the actual Pi before installing

Run the following only later on the reconnected Pi, as the ordinary user.
The existing OS must supply `python3.11-venv`, `python3-tk`, `libportaudio2`,
`libsndfile1`, `libusb-1.0-0`, `libgomp1`, `libstdc++6`, `libgcc-s1` and `zlib1g`.
The target must be Linux aarch64 with glibc >=2.36. Resolve missing OS packages
before an offline install; these archives contain no OS or apt repository.

Substitute your real transfer path for `/ACTUAL/TRANSFER/DIRECTORY`. All names
below must be fresh, except existing install/data roots which are retained.
Use a terminal on the Pi; do not paste Linux commands into Anaconda Prompt.

```bash
set -e
JP_TRANSFER='/ACTUAL/TRANSFER/DIRECTORY'
JP_ROOT="$HOME/.local/share/just-peachy"
JP_DATA="$HOME/.local/share/just-peachy-data"
JP_PREFLIGHT="$HOME/just-peachy-preflight-v1.json"
cd "$JP_TRANSFER"
sha256sum just-peachy-baseline-cm5-offline-v1.zip just-peachy-pi-reconnect-companion-v1.zip
```

Compare these two digests with the trusted Windows/Git receipts before proceeding.
Then extract only the small companion into a new directory:

```bash
test ! -e "$JP_TRANSFER/companion-v1"
mkdir "$JP_TRANSFER/companion-v1"
python3.11 -m zipfile -e "$JP_TRANSFER/just-peachy-pi-reconnect-companion-v1.zip" "$JP_TRANSFER/companion-v1"
python3.11 "$JP_TRANSFER/companion-v1/pi_storage_preflight_v1.py" \
  --bundle "$JP_TRANSFER/just-peachy-baseline-cm5-offline-v1.zip" \
  --sha256 913e0a082e2de5f28e62f30503097cfb12f9008ed6d26fd1a803a7a2e8d32bbf \
  --runtime-overhead-bytes 536870912 \
  --target-install-root "$JP_ROOT" --target-data-root "$JP_DATA" \
  --output "$JP_PREFLIGHT"
python3.11 -m json.tool "$JP_PREFLIGHT"
```

Require all three report values before continuing: `target_observation.status`
is `PREREQUISITE_METADATA_PASS_ONLY`, `space.space_status` is `ESTIMATED_FIT`,
and `available_space_source` is `ACTUAL_TARGET_FILESYSTEM`. Process exit zero
alone is insufficient. Resolve missing prerequisites or space first. The script
does not install, create either root, load models, open audio or launch a GUI.

The conservative baseline estimate is 3,009,905,316 additional available bytes
(about 2.80 GiB), including a 1-GiB reserve and an unmeasured 512-MiB overhead
allowance. It gives no credit for existing assets and retains previous rollback
versions. This is an estimate of storage need, not measured installed size or RAM.
Actual free space is checked on the target filesystem. Optional backends require
their own complete inventories and validation before being added.

## 3. Stage, check, then explicitly activate

After the three preflight checks pass, use a new extraction directory:

```bash
test ! -e "$JP_TRANSFER/baseline-v1"
mkdir "$JP_TRANSFER/baseline-v1"
python3.11 -m zipfile -e "$JP_TRANSFER/just-peachy-baseline-cm5-offline-v1.zip" "$JP_TRANSFER/baseline-v1"
cd "$JP_TRANSFER/baseline-v1"
python3.11 bootstrap/verify_bundle.py --root .
bash install-offline.sh "$JP_ROOT" "$JP_DATA"
```

The wrapper verifies every member. The installer stages an immutable application
and its pinned runtime using the bundled wheels and assets. Stop if staging or
health checks fail; preserve the report and failed attempt. If checks pass and
you want this version selected, stop any existing app using the data root, then:

```bash
bash install-offline.sh "$JP_ROOT" "$JP_DATA" --activate
python3.11 bootstrap/release.py healthcheck --root "$JP_ROOT" --data-root "$JP_DATA"
```

From a terminal in the Pi's graphical desktop, launch it later when ready:

```bash
"$JP_ROOT/runtimes/n1-common-20260924-v1/bin/python" \
  "$JP_ROOT/releases/n1-common-20260924-v1/release_tools/launch_current.py" \
  --root "$JP_ROOT" --data-root "$JP_DATA"
```

First validate with a chosen saved WAV: startup, backend selection, caption and
speaker behavior, save/reopen/delete and clean shutdown. Do not infer that these
checks have already passed on the Pi. Capture, device controls, hardware and
personal enrollment require their later authorized testing.

## 4. Preserve a working version

If a previous compatible version pointer exists, stop the app and, from the
extracted baseline directory, roll back without deleting profiles or code:

```bash
python3.11 bootstrap/release.py rollback --root "$JP_ROOT" --data-root "$JP_DATA"
python3.11 bootstrap/release.py healthcheck --root "$JP_ROOT" --data-root "$JP_DATA"
```

Do not delete an active/uncertain owner lock to force an update. Rollback cannot
invent a previous install and must refuse incompatible data. See
`UPDATE_ROLLBACK.md` and `INSTALL_CM5.md` for details, including a later wired
SSH/SCP route with the actual verified host, user and key.

Retain candidate Nemotron modes, component combinations, worker strategies and
silence gates for separate held-out real-world evaluation. Synthetic scenes can
contain excessive silence, so silence savings do not establish real conversation
or Pi speed. Use matched ungated controls, original source pacing and dense,
quiet/short, returning-speaker, overlap and noisy conversations. Native CPU/RAM,
backlog, temperature and 30/60-minute endurance remain later target checks.
