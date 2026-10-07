# Build30 validation, endurance and desktop helpers

Purpose: use the upcoming exact build30 package with the SQLite sidecar race
repair, while retaining frozen build29 and its helper sources. These are narrow
derivatives: the model weights, model math, source clock, calibration gates,
six ordinary backend rows and unit/resource limits are unchanged. Build30's
actual manifest SHA is
b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569,
from the independently closed 421-member package under private
`audit-preparation/sidecar-package30-99ab101518ce402a9a2c8d5f6ac96cc6/package`.
The sources are sealed to that pin and the actual activation action SHA.
No future Live41 proof has been invented.

Files and inputs/outputs:

- `prepare_core_native_validation_v3.py` takes the actual private package,
  manifest SHA, observed boot, kind live/saved, ordinary operator ID, fresh
  label and explicit Discard. Saved input also needs captured session metadata
  and its SHA. It reuses the exact frozen V2 native live/saved helpers, verifies
  full package membership, creates owner/source backup/independent restore,
  ACTION/PAYLOAD and preparation closure receipts. It targets build30 only.
- `prepare_core_endurance30.py` takes those package/boot inputs plus accepted
  backup12 census/COMPLETE hashes, the exact future c24 WAV path, hour label,
  reviewer and fresh private output. It performs the same lossless 966400-sample
  PCM join/independent readback and real verified pure imports as the build29
  preparer. It emits fresh stage and hour payloads; it never opens native data.
- `stage_c24_endurance_input30.py` is a root-injected PAYLOAD/BASELINE action
  with RESULT output. It requires the exact original c24 pins, current boot,
  staged WAV/PCM hashes and 8 MiB copy reservation; it takes existing nonblocking
  guard leases plus the c24 shared lease. It streams only to the fresh named
  input directory, rechecks original hashes/membership and reads back WAV/PCM.
  It never overwrites existing staging evidence or changes original recordings.
- `launch_core_full_app_hour30.py` is the sealed injected hour action. It
  delegates to the exact installed full_app_hour route with one continuously
  paced source/model session, inventoried imports, capacity-derived FSIZE and
  unchanged 3600-second source/4680-second service/complete-output reservations.
- `review_core_full_app_hour30.py` reads only a full independently closed PC
  mirror plus the exact build30 pure package. It emits numeric completion gates,
  59 wrap checks, one source/model session, layer counters, PnC/queue closure,
  quick_check, actual capacity evidence and descriptive memory/thermal bins.
- `prepare_core_activation30.py` requires the actual finalized Live41
  NATIVE_CHECK_V2.json, its complete independent mirror and finalizer receipt
  hashes, observed boot and build30 pin. It rehashes full mirrored membership
  and preserves the exact prior28 shortcut/disabled-autostart receipt. It emits
  backed ACTION/PAYLOAD and input/source review receipts, with no native writes.
- `activate_core_desktop_action30.py` is the root-injected activation action.
  It rechecks build30 inventory and actual finalized Live41 proof, backs up and
  independently restores the unchanged prior28 desktop entry, then uses the
  existing atomic compare-and-swap transaction for that single shortcut.
  Login startup, recordings, galleries and calibration remain unchanged.

The Windows preparers register CPU14 before project reads. Use only the
coordinated host slot and the existing interpreter; no installation is needed.

PowerShell examples (replace every ACTUAL input with verified evidence):

```powershell
$repairDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
Set-Location -LiteralPath $repairDir
$pythonExe = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $pythonExe -B prepare_core_native_validation_v3.py --package 'ACTUAL_BUILD30_PC_PACKAGE' --manifest-sha256 ACTUAL_BUILD30_SHA --boot-id ACTUAL_CURRENT_BOOT --kind live --operator-id pyannote_redimnet --label classic-ui-check-41 --discard-session
& $pythonExe -B prepare_core_endurance30.py --package 'ACTUAL_BUILD30_PC_PACKAGE' --manifest-sha256 ACTUAL_BUILD30_SHA --backup-root 'ACTUAL_ACCEPTED_BACKUP12' --census-sha256 c827fad465bb6a1307de9157d13b55d31115476f7354868963cbe5b19a2444ac --complete-sha256 03ffc85b2e2f3046c707879c3059f3c2e1194626f4ece11a7d385975c924bdfb --boot-id ACTUAL_CURRENT_BOOT --native-input-path '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/core-c24-endurance-input-02/c24-processed.wav' --operator-id delayed_redimnet --label full-app-hour-01 --reviewer ACTUAL_REVIEWER --output 'ACTUAL_PRIVATE_PARENT/FRESH_HOUR_PREP'
& $pythonExe -B prepare_core_activation30.py --native-check-file 'ACTUAL_LIVE41_MIRROR/closed-output/NATIVE_CHECK_V2.json' --finalizer-result 'ACTUAL_LIVE41_FINALIZER_RESULT' --boot-id ACTUAL_CURRENT_BOOT --manifest-sha256 ACTUAL_BUILD30_SHA --mirror-complete-sha256 ACTUAL_COMPLETE_SHA --finalizer-result-sha256 ACTUAL_FINALIZER_SHA
```

CMD/Anaconda Prompt run the same scripts and arguments after selecting the
directory; replace the PowerShell `& $pythonExe` prefix with the interpreter:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B prepare_core_native_validation_v3.py --package ACTUAL_BUILD30_PC_PACKAGE --manifest-sha256 ACTUAL_BUILD30_SHA --boot-id ACTUAL_CURRENT_BOOT --kind live --operator-id pyannote_redimnet --label classic-ui-check-41 --discard-session
```

For saved checks, use `--kind saved` and add
`--saved-metadata-file ACTUAL_C24_SESSION_JSON --saved-metadata-sha256 7da45b76193d3ddd1e2aa29bbc6792b019643c8a945edd3959d9458db4fc6c69`.
After each actual unit closes, rerun the same preparation with
`--operation finalize`. Keep row/label/source pins identical. Root alone
dispatches native ACTION/PAYLOAD; preparers never run SSH or native models.
For the hour review, run `review_core_full_app_hour30.py --mirror
ACTUAL_FULL_CLOSED_HOUR_MIRROR --package ACTUAL_BUILD30_PC_PACKAGE
--manifest-sha256 ACTUAL_BUILD30_SHA --output-root ACTUAL_PRIVATE_REVIEW_PARENT`
with the same interpreter prefix. Activation preparation requires Live41 PASS
and full mirror closure first; it cannot run against a partial or future proof.

The staged 1,932,844-byte WAV must match SHA
9a83534025736c2f057f20068f3c0584b45770815289a7842a501fcae52b65c8 and PCM SHA
0f13e54972e4140f5797b996bdeb48d802acd4dcbb9407065d46190bda887e97.
The source-only active Delayed chain derives 57,600,000 samples, 360,001 frame
rows and an 11,520,032-byte float32 workspace from the hour SessionPolicy.
Old reference13001-frame guards belong to the uninvoked reference operator
composition; actual InstalledSession uses nemotron_binding.bind. This is
source evidence, not a native hour pass. Repeated speech does not establish
natural-conversation quality, GUI endurance, microphone or spatial behavior.

Host status: preparation against the actual 421-member build30 package passed,
with all seven derivative sources compiled, exact source backups/independent
restores, unchanged backup12 source, lossless WAV/PCM readback and real pinned
profiles/storage/storage_support import binding. Private receipts are under
`audit-preparation/core-endurance30-20261006-1b1dbf93a3e04713878364140e7fb309`.
CPU14 PID42608/creation FILETIME134357834535718902 closed naturally with exit 0
and was independently absent. Frozen input-02 staging action SHA is
5ebb8550edfc83298eb21fa747e8b1aefaa50bffe6706731c085905e95bcf332;
hour launch action SHA is
b31b3a0bbdbf8746c14fedb6d7934dd25941cce7b32862498f74329f92d0cec2.
Live41 validation preparation itself, activation preparation/proof, native
staging/replay and hour mirror review remain unexecuted. Keep this README
current with the actual host closure and native evidence when available.
