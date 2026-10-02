# Conditional recovery for the current microphone startup fault

Purpose: F08/F09 reuse the previously exercised XVF recovery sequence for the actual candidate5 AEC_MIC_ARRAY_TYPE255 failure while the audio loop was active. This is one conditional maintenance operation, not a periodic reset. No playback, recording, model inference, downloads or personal-data changes occur in this helper.

Before use, preserve candidate5 completely and restore the baseline. Supply its exact installation, preserved failure and a fresh read-only recovery inspection. The helper reads all registered historical/current owners, units, leases and lifetimes, binds the current boot and two baseline identities, and checks the saved270display and capture-off state. It makes two independent PC copies of the existing exact control tool/current/live configuration and verifies full readback before device access. It verifies those bytes on the Pi again before any maintenance command. Unreadable old volatile firmware state cannot be backed up or claimed restored.

Only a fresh matching AEC255 response permits one TEST_CORE_BURN0 command. An uncertain/nonzero send is final and is never repeated. If AEC is readable, no command is sent. Firmware VERSION3.2.1/build readback must match after2seconds. This does not qualify microphone function; a fresh runtime recording remains necessary.

Limits: CPU14 host; native CPU3 inside an actual systemd CPU2,3/shared200%/Tasks64 unit;128MiBAS/1MiBstack/FSIZE0/80s alarm/90s unit/10s Stop.850MiB initial available RAM,192MiB stop, Pi5GiB/C50GiB/G75GiB free. No project payload writes. Prospective measured10MiB reservation includes2MiB target/system-control allowance and8MiB independent PC backup/metadata. Old WINDOW and all retained usage remain unchanged. Native early owner and command/intent events are retained; natural SSH and independent exact process absence are required.

Inputs: local/private roots, prior binding, fresh previous inspection, actual candidate5 installation, fresh host scope, unused output directly under the private root. Output: exact before/restore copies, measured policy, raw command events/result and process closure. Never reuse the output or unit after an attempt.

PowerShell:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\recover_runtime_source_v1.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection FRESH_RECOVERY_INSPECTION --candidate-install CANDIDATE5_INSTALL --scope CURRENT_SCOPE --output NEW_PRIVATE_OUTPUT
~~~
Command Prompt / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B recover_runtime_source_v1.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection FRESH_RECOVERY_INSPECTION --candidate-install CANDIDATE5_INSTALL --scope CURRENT_SCOPE --output NEW_PRIVATE_OUTPUT
~~~

Source backup plus independent restore must close before execution. The first version binds the candidate5 failed source and a unique jp-runtime-source-recovery-v1.service. Old xvf_recovery_protocol_v4.py is the conditional-command precedent; its expired dispatcher is not invoked.
