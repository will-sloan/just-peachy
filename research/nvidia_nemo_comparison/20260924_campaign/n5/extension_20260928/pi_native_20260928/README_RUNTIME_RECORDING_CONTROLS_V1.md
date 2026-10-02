# Optional processed recording

Purpose: F13 adds Audio off / Processed before Start to the existing profile frontend. Off keeps transcript, events and timing metadata; the installed MemoryJournal retains working samples in RAM and EpochArchive omits both audio files. Processed requires explicit storage consent and preserves the existing lossless float32 model input plus PCM listening copy. Raw MIC0–MIC3 plus processed is visibly unavailable because simultaneous taps have not been qualified. This is not a hardware impossibility claim.

Inputs: the exact backed candidate8 COMMON_BUNDLE.json (SHA256 `7b6bf198c6d131e6e034f35f4cf07e1212d3b0c30e55046d9e20e592f6620e09`). The pure `derive(bytes)` API returns new capsule bytes and a change review. It does not issue a policy, install or start capture. A fresh installer must pin its output and use current owners, full independent reservations and verified backups. Never overwrite a consumed release.

Outputs: five changed existing capsule members, a new whole-capsule manifest and review. The 64-member / 2MiB / 128KiB-member and 1MiB-packed caps remain. Archive validation requires exactly five files for Off or seven for Processed, matching strict boolean consent and epoch metadata; source counts, complete event decoding, timestamps, import path guards, sizes and hashes remain. No allocation credit comes from choosing Off. Export remains a full private copy, never automatic deletion.

PowerShell (preparation API only):

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); import field_runtime_recording_controls_v1 as m; print(m.request(False, False))"
```

Command Prompt / Anaconda Prompt, from this source directory:

```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import field_runtime_recording_controls_v1 as m; print(m.request(False, False))"
```

These commands validate only the selector. Use the documented bounded checker for actual capsule/installed-schema verification with an early host owner receipt. Native recording-off behavior, UI geometry and final-entry history/export require the changed installed composition check. No native pass is claimed by this source.
