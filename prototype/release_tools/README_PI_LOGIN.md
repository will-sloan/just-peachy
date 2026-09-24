# Prepare the CM5's first login from Windows

Purpose: enable SSH and supply first-login credentials on an already imaged
Raspberry Pi OS Bookworm boot partition. For this user's fresh CM5 installation
with no account; not an existing-account password reset or a disk imaging tool.
The official mechanism is documented at
https://www.raspberrypi.com/documentation/computers/getting-started.html#manual-setup-for-ssh.

Inputs: the verified boot drive letter, expected whole-device byte capacity,
Git for Windows OpenSSL, and username/password entered interactively. Outputs:
`userconf.txt` (username and salted SHA-512 crypt hash) and empty `ssh` on the
Pi boot partition. No plaintext password, password hash, or account receipt is
printed or logged by the helper. The hash is sensitive and remains on the boot
partition until Raspberry Pi OS consumes the account file. It is never copied
into the repository. The script does not modify config.txt, cmdline.txt, OS
partitions, models or user recordings. The username defaults to `peachy` and
uppercase letters are normalised to lowercase for Raspberry Pi OS.

Prerequisites: Windows PowerShell, Git for Windows, a freshly imaged CM5 with
32 GB eMMC exposed via rpiboot, and an ordinary user who can write to bootfs.
Anaconda activation is unnecessary. As of 2026-09-22 this device is mmcblk0,
31,268,536,320 bytes, first partition E: (bootfs/FAT32). Drive letters may change;
inspect the actual disk before choosing arguments. USB/name/size/system-disk,
partition, filesystem and CM5 boot-file guards run both before input and before
writing. Existing userconf or other provisioning scripts cause refusal. All
new files use CreateNew so existing data is never overwritten. A failure after
one file was written requires inspection; do not bypass the guard on a retry.

PowerShell, from any directory (a visible interactive console is required):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype\release_tools\prepare_pi_login.ps1' -DriveLetter E -ExpectedDiskBytes 31268536320
```

CMD / Anaconda Prompt, or if PowerShell execution policy blocks the script:

```bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\amiri\Documents\GitHub\just-peachy\prototype\release_tools\prepare_pi_login.ps1" -DriveLetter E -ExpectedDiskBytes 31268536320
```

ExecutionPolicy Bypass applies only to that process. Enter a username and the
password twice in the local window. No password belongs in arguments or chat.
OpenSSL receives it through a private stdin pipe, not a command-line argument.
PowerShell necessarily holds it briefly in process memory during hashing.

Add `-CheckOnly` for a read-only target guard and synthetic OpenSSL hash check.
Wrong targets are refused before password input. This check does not test
account creation on ARM64. Native success is established only by booting and
logging in afterward.

After SUCCESS and boot-file verification, safely eject, disconnect PC USB,
remove the eMMC boot-disable jumper, keep Ethernet connected, and connect the
official supply to the same USB-C socket. Allow the account setup to complete.
Do not run Imager or format the drive again. See
../docs/CM5_FIRST_BOOT_WINDOWS.md for the full hardware sequence.
