# Offline runtime manager V1

Purpose: implement F04's persistent idle manager and its three native recording phases: initialize a fresh broker, run the guarded manual broker, and make the complete independently verified Pi-local backup. The real recording UI retains its explicit New/Start/Stop/Save/Return actions. The manager waits for natural process closure and a verified local copy before enabling another recording.

Status: PREPARED / NATIVE UNEXECUTED. This version implements only Delayed profile dispatch. The UI explicitly refuses other profiles even if an input policy incorrectly calls them available. It is not the completed all-mode deployable runtime. Production installer, activation/rollback, reboot lifecycle refresh, other profiles, failed-source recovery, shortcuts and offload integration remain required. There is no approved existing root to run this version against.

Inputs: an installed canonical field-runtime-vN root with the complete <=16-member manager code manifest and finite runtime policy; actual ACTIVATION.json; pinned profile BUNDLE.json under the sibling field-runtime-vN-profiles/d1-delayed directory; actual configured systemd manager service and shared slice. The runtime policy's profile manifest SHA pins the complete packed template bytes. ACTIVATION has schema, policy_sha256, settings_sha256, baseline_owners, baseline_expected, baseline, launch_slot. Baseline must be freshly observed on the current boot. V1 deliberately refuses an old-boot activation; offline boot refresh is not implemented by this file.

Outputs: bounded immutable launch/recording owner/start/closure/backup records, new source tree and independent local copy. Existing and failed trees are preserved. Helper HELLO is checked against actual PID/start/boot and persisted BEFORE its small input is sent and before project imports. The manager itself registers its owner before project imports while holding the same lifetime directory lock it passes into RuntimeJournal V2.

The actual manager and all broker services must share a slice with CPUQuota=200%, TasksMax=64 and AllowedCPUs=2,3. Manager AS128MiB, stack1MiB, FSIZE32MiB, RuntimeMax86400s; broker AS768MiB, stack1MiB and original finite operation/child/Stop guards remain. The manager opens capture off. No automatic capture, automatic retry, model download, playback or enrollment is added.

Failure handling requests Stop before diagnostics, drains bounded helper output, waits for the exact helper, and preserves failure/pending paths. It can close capture-off with RECOVERY_REQUIRED. This does not implement failed-source backup/recovery or certify an unsuccessful operation. The next recording remains fenced.

Host syntax review (does not execute Linux imports), PowerShell:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; compile(Path('field_runtime_manager_v1.py').read_bytes(),'field_runtime_manager_v1.py','exec')"
```

CMD / Anaconda Prompt from this README's directory:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; compile(Path('field_runtime_manager_v1.py').read_bytes(),'field_runtime_manager_v1.py','exec')"
```

Future native invocation is through the reviewed installed systemd service only. Its ExecStart will use the installed Python and code/field_runtime_manager_v1.py with --root CANONICAL_INSTALLED_ROOT --policy-sha256 EXACT_POLICY_SHA --profile d1-delayed. Do not substitute a consumed research root. The --helper stage/gate/copy interface is internal: it emits HELLO, then accepts one <=4096B owner/root/policy/slot request from the owning manager, and returns a <=256KiB result. It is not a manual capture command. Final PowerShell/CMD/Anaconda deployment and launch commands depend on the installer and fresh admission and will be added before this can be called deployable.

