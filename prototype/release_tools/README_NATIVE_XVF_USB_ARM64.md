# Native XVF USB and I2C control on CM5

Purpose: build the existing XMOS host control 3.0.0 and firmware-matched 3.2.1
command map for 64-bit Raspberry Pi OS. This is a host-side build, not a firmware
update. It builds the existing Linux i2c-dev transport as well as USB control;
it adds no SPI, DFU or audio playback implementation.

Inputs are the existing vendor archives `host_xvf_control---application-source-code_v3_0_0.zip`
and `XVF3800-Software_v3_2_1.zip`. Their hashes and the extracted paths are in
`source-receipt.json` in the prepared source bundle. Vendor sources/licences are
retained. `command-map-aarch64.patch` adds only an aarch64 Linux platform branch
to the map CMake file, with its own output directory. Command definitions and
C/C++ sources are unchanged. `host/cm5_i2c.cmake` exposes the existing I2C
driver on aarch64 without linking the vendor's ARM32-only SPI library.

Outputs: native `xvf_host`, `libdevice_usb.so`, `libdevice_i2c.so`, and `libcommand_map.so` together
under `~/JustPeachy/tools/native_xvf_usb/bin`; build logs, source patch, hashes,
and qualification receipts remain beside the sources. A successful build is
not proof of physical capture, correct firmware or permissions.

## Transfer from Windows

The prepared archive is
`G:\Just_Peachy_PROTO1\cm5_bringup_20260922\native-xvf-usb-src.tar.gz`.
Use PowerShell; no Conda environment needs activation:

```powershell
$jpKey = "$env:USERPROFILE\.ssh\just_peachy_cm5_ed25519"
scp.exe -i $jpKey -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 'G:\Just_Peachy_PROTO1\cm5_bringup_20260922\native-xvf-usb-src.tar.gz' peachyprototype@raspberrypi.local:/home/peachyprototype/JustPeachy/
ssh.exe -i $jpKey -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local
```

For CMD/Anaconda Prompt:

```bat
scp.exe -i "%USERPROFILE%\.ssh\just_peachy_cm5_ed25519" -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 "G:\Just_Peachy_PROTO1\cm5_bringup_20260922\native-xvf-usb-src.tar.gz" peachyprototype@raspberrypi.local:/home/peachyprototype/JustPeachy/
ssh.exe -i "%USERPROFILE%\.ssh\just_peachy_cm5_ed25519" -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local
```

`HostKeyAlias` verifies the already trusted Pi key under its original address;
it does not disable verification. Use the explicit IPv4 address if local-name
resolution is unavailable.

## Build on the Pi

Prerequisites already installed for this deployment: cmake, build-essential,
pkg-config, libusb-1.0-0-dev, python3, python3-yaml and python3-jinja2. Use the
ordinary Pi account, not root. If rebuilding an existing installation, stop
live sessions first and use a separate destination for candidate binaries.

```bash
mkdir -p "$HOME/JustPeachy/tools"
tar -xzf "$HOME/JustPeachy/native-xvf-usb-src.tar.gz" -C "$HOME/JustPeachy/tools"
cd "$HOME/JustPeachy/tools/native_xvf_usb"
cmake -S host -B build-host
cmake --build build-host --parallel 2
export PYTHONPATH="$PWD/firmware/sources/modules/fwk_xvf/modules/yaml_autogen/src"
cmake -S firmware/sources/modules/fwk_xvf/modules/host_cmd_map -B build-map -DPython3_EXECUTABLE=/usr/bin/python3
cmake --build build-map --parallel 2
mkdir -p bin
cp build-host/xvf_host build-host/libdevice_usb.so build-host/libdevice_i2c.so build-map/libcommand_map.so bin/
file bin/xvf_host bin/*.so
ldd bin/xvf_host
ldd bin/libdevice_usb.so
ldd bin/libdevice_i2c.so
ldd bin/libcommand_map.so
bin/xvf_host --version
bin/xvf_host --help
bin/xvf_host --list-commands > command-list.txt
sha256sum bin/xvf_host bin/*.so > binary-sha256.txt
```

Expect ELF64 AArch64 files and no missing shared libraries. Inspect the command
list for the firmware, array, audio-routing and beam parameters used by the
existing adapter before binding this helper into `~/JustPeachy/data/live_config.json`.
Do not copy Windows endpoint IDs or integer device indices. Enumerate the actual
ALSA XVF endpoint and qualify readback and bounded input Start/Stop on the Pi.
For I2C use `-u i2c` with INT firmware and `/dev/i2c-1`; the USB firmware
does not expose this control interface. Keep Pi I2S clocks disabled until the
XVF has the matching INT slave firmware. See `../docs/CM5_I2S_MIGRATION.md`.
DSP reads may need the existing adapter's input-clock priming; do not add output
playback to work around that. Keep personal data outside the immutable release.

Status at preparation: native build/physical qualification pending. The current
bring-up record is `../docs/CM5_INSTALL_20260922.md`.
