# Display reconnection and orientation V1

Purpose: retain the requested working portrait display upside down relative to its previous position, with a verified rollback. Inputs are the existing DSI-1 output, ~/.config/kanshi/config and labwc touch mapping. Output is transform270 instead of90 (180 degrees relative rotation), still480x800 logical /800x480 panel at60.029Hz, and a saved kanshi configuration.

September30: after reconnection, the output/backlight reported on but the touchscreen emitted repeated I2C -121 errors. A single display-only off/on cycle reinitialized DSI and a private compositor capture showed Just Peachy. No fresh errors appeared in the next54seconds. The user confirmed physical operation and reported a shifted ribbon. This does not establish that the software action alone repaired the hardware connection. No firmware reset or Pi/app reboot occurred. DSI cables should be connected with power disconnected: https://www.raspberrypi.com/documentation/accessories/display.html

The subsequent explicit user orientation request changed only the kanshi line transform90 to transform270. Original84-byte configSHA c4c576201cca88b6891e95ec4c9f6e6c5474967206a0c243dacf5ee817a265bc; new85-byte configSHA c4e12bb19373d607a7ca1e52a0c007e082e17a18eb5af7b8a60384ca82aae23b. Exact native and private host backups and a separate restoration copy were read back before atomic replacement. Actual running kanshi PID1001/start568 was verified before its documented SIGHUP reload. Live output transform270 and saved hash rechecked afterward. Restart persistence is configured, not tested by rebooting. The touch device remains mapped to DSI-1; no physical touch accuracy test is claimed.

Native backup: /home/peachyprototype/JustPeachy/research/nemotron-20260928/display-orientation-20260930-v1/KANSHi_CONFIG_BEFORE. Alongside it are RESTORE_VERIFIED_COPY, TOUCH_MAPPING_BEFORE and CHANGE_RECEIPT.json. Private host receipts are in local/n5/research-extension-20260928/pi-native-20260928/display-orientation-20260930-v1. Reconnection logs and screenshot remain separately private. Original app boot/PIDs/startticks/install/live_config unchanged; no capture or model launched by display maintenance.

## PowerShell verification

```powershell
ssh -i 'C:\Users\amiri\.ssh\just_peachy_cm5_ed25519' -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'env XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 wlr-randr'
ssh -i 'C:\Users\amiri\.ssh\just_peachy_cm5_ed25519' -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'sha256sum ~/.config/kanshi/config'
```

## Command Prompt / Anaconda Prompt verification

No Python environment is needed for these OpenSSH commands.

```bat
ssh -i "C:\Users\amiri\.ssh\just_peachy_cm5_ed25519" -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local "env XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 wlr-randr"
ssh -i "C:\Users\amiri\.ssh\just_peachy_cm5_ed25519" -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local "sha256sum ~/.config/kanshi/config"
```

Expected Transform:270 and new SHA above. No periodic off/on or automatic rollback. If a rollback is specifically requested, first verify the current new hash and original backup hash; copy the original backup to ~/.config/kanshi/config, reload the exact current kanshi process with SIGHUP, then verify Transform:90 and the original hash. Preserve any later user changes instead of overwriting them. The saved orientation is part of the current user preference for subsequent development.
