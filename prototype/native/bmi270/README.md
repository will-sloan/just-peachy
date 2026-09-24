# Lightweight BMI270 native I2C adapter

Purpose: read acceleration (g) and angular velocity (degrees/second) without
Python package downloads, cloud processing, or a subprocess per sample.
The small Linux wrapper uses Bosch's unchanged BMI270 SensorAPI, including
its required sensor initialization data and gyro cross-axis handling.
Vendor commit: `41129fcfe39c583ee5462d79195741945d51c1fe` from
https://github.com/boschsensortec/BMI270_SensorAPI (BSD-3-Clause; licence retained).

Inputs: `/dev/i2c-1`, verified BMI270 at 0x68 (chip ID 0x24), these C sources.
No writes occur if chip identity differs. Initialization resets/configures only
the selected BMI270. Acceleration +/-4g, gyroscope +/-500 degrees/second,
both 50 Hz. Outputs: `libpeachy_bmi270.so`, six SI-related measurements per
successful sample; the Python motion adapter adds host monotonic timestamps.
This is relative inertial sensing, not an absolute position/heading sensor.

On the Pi, from this directory:

```bash
mkdir -p "$HOME/JustPeachy/tools/bmi270"
gcc -std=c11 -O2 -fPIC -shared -Wall -Wextra -I vendor \
  peachy_bmi270.c vendor/bmi2.c vendor/bmi270.c -lm \
  -o "$HOME/JustPeachy/tools/bmi270/libpeachy_bmi270.so"
file "$HOME/JustPeachy/tools/bmi270/libpeachy_bmi270.so"
```

For transfer from Windows PowerShell, or CMD/Anaconda Prompt, run:

```text
scp.exe -r -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o HostKeyAlias=192.168.2.57 prototype/native/bmi270 peachyprototype@raspberrypi.local:/home/peachyprototype/JustPeachy/tools/bmi270-source
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local
```

Then `cd ~/JustPeachy/tools/bmi270-source` and build as above. Use the normal
user with I2C group access, not a root GUI. Run only one sensor owner at a time.
See `../../app/README_MOTION.md` for application setup, calibration and limits.
There is no installation/download during routine offline operation.
