# First CM5 setup from this Windows desktop

Purpose: provision the assembled CM5 and establish wired access before deploying
the current Just Peachy source. This is a guided procedure, not an automated disk
writer. Last checked: 2026-09-22.

## Confirmed by the user

- CM5 on a CM5 IO board, 32 GB eMMC, no wireless.
- Official Raspberry Pi USB-C power supply; exact output rating not yet read.
- Freenove 7-inch IPS 800x480, five-point touchscreen, ribbon at display port 0.
  The description matches the FNK0078 family; board revision/power arrangement
  still needs visual verification. Do not apply Touch Display 2 overlays.
- Screen is blank; user reports no OS installed. Storage contents have not been
  read or erased by this task.

The earlier 2 GB RAM plan remains unconfirmed for the assembled module.

## Windows tools and first checkpoint

Raspberry Pi Imager v2.0.7 is installed at
`C:\Program Files\Raspberry Pi Ltd\Imager\rpi-imager.exe`.

Official rpiboot installer downloaded to
`C:\Users\amiri\Downloads\rpiboot_setup_windows-v1.1.exe`.
SHA256 verified against the official release asset:
`4f700ef27909a543051270153ac238f48dee91736ecfa558b6c94f1184d66c15`.
The installer has not been executed by this task.

1. Run that installer, allow its driver installation to finish, and restart
   Windows as directed by Raspberry Pi's instructions. Save work first.
2. With the CM5 assembly disconnected from power, fit the J2 jumper specifically
   labelled **disable eMMC Boot / nRPI_BOOT**. Do not bridge unrelated J2 pins.
3. While unpowered, temporarily disconnect nonessential USB peripherals/HATs
   from the CM5IO for imaging. The official CM5IO has **one USB-C connector,
   J11, shared by power and USB data**. The earlier separate-power-connector
   instruction was incorrect and is superseded by this correction.
4. Connect J11 directly to a PC USB 3 port capable of at least 900 mA, using a
   good data-capable cable. For this reduced-load imaging setup the PC supplies
   both power and data; leave the official wall supply disconnected. Do not
   improvise a splitter or GPIO power connection. If it does not boot reliably,
   inspect the cable, power budget and remaining peripherals before writing.
   Raspberry Pi's CM5 troubleshooting also recommends holding the power button
   while connecting power and releasing it immediately afterward if needed.
5. Run **rpiboot - Mass Storage Gadget** from the Windows Start menu.
6. Stop at the storage-identification checkpoint: the CM5 eMMC must appear with
   its expected capacity (roughly 29-30 GiB). A zero-byte/no-media device is not
   a usable target. Decline Windows prompts to format a disk.

Initial Windows disk inventory had two 2 TB internal disks and a zero-byte USB
no-media device. Neither internal disk is the intended imaging target. Device
numbers can change; never use an old number as identification.

## OS selection, after identifying the actual eMMC

Use Raspberry Pi Imager with **Raspberry Pi OS (Legacy), 64-bit, Bookworm,
with desktop**. Avoid Lite (no desktop) and the much larger Full package.
This matches the prepared application dependency target: aarch64, Python 3.11.
Do not apply the existing cp311 wheel lock to a newer Python interpreter.

Before writing, explicitly verify the selected disk is the CM5 eMMC and that its
contents may be erased. Set a hostname (suggested `justpeachy`), an ordinary
username and private password, local timezone, and SSH access. Do not post
passwords/private keys in chat. No Wi-Fi configuration is needed.

After Imager finishes writing and verification, safely eject the storage and
disconnect the PC cable to power off. Remove the eMMC-boot disable jumper,
reconnect verified peripherals while unpowered, and connect Ethernet to the same
router or switch as the PC. Connect the official Raspberry Pi supply to the same
J11 USB-C port for normal operation. Wired SSH allows display troubleshooting even
if the panel remains blank. Verify the SSH host identity before storing it.

## Display and wiring checkpoint

### Follow-up: image written, first login not configured

The user completed imaging, chose hostname `PeachyPrototype`, and subsequently
reported no username and likely no SSH setting. The display remains blank.
On returning to rpiboot, the verified mmcblk0 device has a 512 MiB FAT32 bootfs
partition at E: and a Linux root partition. A read-only filesystem check reported
no problems; Windows also reports a dirty/repair-needed status, so no Windows
repair or format is being applied. Complete a clean Linux shutdown when access
is available and recheck if the flag persists.

Use the official first-login `userconf.txt` plus empty `ssh` method through the
private local prompt documented in
[README_PI_LOGIN.md](../release_tools/README_PI_LOGIN.md). The helper validates
the exact USB target and refuses existing provisioning files. A successful file
write prepares the next boot; it is not proof of a successful account login.
Do not reflash just to enable SSH. The Freenove display still needs independent
physical/configuration verification after remote access is established.

The user completed the local password prompt. The prepared account name is
`peachyprototype` (normalised from `PeachyPrototype` to meet the Linux setup
rule). `userconf.txt` and the empty `ssh` marker were verified on E:; the password
hash was preserved during the case correction and never included in logs.
The next normal boot successfully created the account. Password login was
completed privately and dedicated-key SSH access was then verified. The actual
hostname is `raspberrypi`, address `192.168.2.57`; the intended `PeachyPrototype`
hostname was not applied by Imager. Do not reflash. Current installation and
native test results are in [CM5_INSTALL_20260922.md](CM5_INSTALL_20260922.md).

### Physical display inspection

Request clear photographs of the complete unpowered assembly and screen rear,
showing labels, both ribbon ends, display power contacts/wires and any extender.
Freenove's instructions illustrate ordinary Pi 4/5 mounting, including contact
pins on some revisions; those pictures do not establish the CM5IO power wiring.
Verify the exact panel power and controller before choosing a display overlay.
The 800x480 panel can provide the app's intended 480x800 portrait area after
display and touch rotation are configured and tested together.

XVF live operation will use a CM5IO USB host port and the device's USB audio/control
connection. Confirm its actual port/cable and power arrangement during inspection.
Keep optional camera/IMU/button drivers disabled until each connection is verified.

## Software and first tests after OS boot

Reuse the existing release installer and model store described in
[release_tools/README.md](../release_tools/README.md). The old
`just-peachy-proto1-0.2.0.zip` contains tasks01-08 only. Build a new immutable
export from current source for tasks09-12 and the closed-group display fix.
Models and personal data stay outside versioned releases; Windows personal
recordings/profiles are not automatically included in deployment.

Sequence: verify OS/architecture/Python/storage; install native dependencies;
test saved-file inference; open idle GUI and verify touch; build and qualify
firmware-matched ARM64 XVF host control; configure the actual USB input; then
test captions, Stop/restart, enrollment and spatial modes. Measure combined
memory, latency and thermals before an extended session. ARM64 live operation
and full-system memory fit remain untested; the supplied vendor Raspberry Pi
host binaries are ARM32 and cannot be treated as qualified ARM64 helpers.

## Sources

- [Official CM5 imaging and connector procedure](https://www.raspberrypi.com/documentation/computers/compute-module.html#flash-an-image-to-a-compute-module)
- [CM5IO datasheet: J11 power/data schematic](https://datasheets.raspberrypi.com/cm5/cm5io-datasheet.pdf)
- [Official CM5 USB boot power troubleshooting](https://github.com/raspberrypi/usbboot/blob/master/docs/troubleshooting.md)
- [Official Windows rpiboot release](https://github.com/raspberrypi/usbboot/releases/tag/windows-v1.1)
- [Official OS choices](https://www.raspberrypi.com/software/operating-systems/)
- [Freenove 5/7-inch assembly instructions](https://docs.freenove.com/projects/fnk0078/en/latest/fnk0078/codes/tutorial/5_7_inch.html)
- [Raspberry Pi wired remote access](https://www.raspberrypi.com/documentation/computers/remote-access.html)
