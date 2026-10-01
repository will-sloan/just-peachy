# Runtime profile manager V2

Purpose: connect the finite local manager to the shared live-profile capsule and separately pinned profile descriptors. Reuse the original app's Pyannote/Nemotron diarizers, Sherpa ASR and ReDimNet/TitaNet encoders. Each recording retains a fresh process and independent finite allocation. Startup is idle and a shortcut must name an exact profile; unavailable profiles remain explicit.

Selected new sources: field_runtime_manager_v2.py, field_runtime_journal_v3.py and field_runtime_backup_v2.py. Journal3 and backup2 retain their function bodies except dependency links to production policy3/journal3. The manager adds strict descriptor binding and selects a common code capsule rather than six duplicate code trees. Original service, early-owner, lifetime lock, full source/local/PC reservations, natural reap, Stop, backup and first-fault guards remain. Failed-source recovery and four saved-input profiles are still unfinished. These files are PREPARED, not a deployed runtime.

Inputs: an independently backed native release root with code/control/launches/recordings/backups, exact RELEASE.json SHA, a fresh current-boot ACTIVATION.json, and sibling root-profiles/ containing COMMON_BUNDLE.json plus PROFILE.json descriptors. Each descriptor has exactly schema, profile, template_sha256, runtime_profile and runtime_document. The policy profile pin binds the descriptor bytes; template_sha256 binds the common capsule. runtime_profile contains the exact backend definition and independently admitted read-only E0/E1 gallery snapshot descriptors. E1 requires its own TitaNet manifest/namespace; E0 must not depend on TitaNet. Installer must reserve and verify these sibling assets separately before final production accounting.

Outputs: unchanged immutable launch OWNER/EXIT/FAILURE records and recording RESERVED/STARTED/CLOSED/BACKUP records, one broker tree per recording and a complete independent local copy. A user closes the recording screen before another slot; the manager verifies the copy first. The optional later PC export copies all retained bytes without deletion.

Do not run the native manager directly in Windows or bare SSH. It requires a reviewed installed release, fresh native admission/activation, systemd shared resource limits and exact current baseline. The final installer supplies launch-profile desktop commands. Native API after that installation:
```text
python -B field_runtime_manager_v2.py --root /home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-vN --policy-sha256 EXACT_RELEASE_SHA256 --profile d1-delayed-titanet
```
This is the service entry contract, not permission to bypass the installer or launch a prepared source.

PowerShell static compilation (only after source backup/readback; no bytecode output):
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; [compile(Path(n).read_bytes(),n,'exec') for n in ['field_runtime_manager_v2.py','field_runtime_journal_v3.py','field_runtime_backup_v2.py']]"
```
CMD or Anaconda Prompt, from the native report directory:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; [compile(Path(n).read_bytes(),n,'exec') for n in ['field_runtime_manager_v2.py','field_runtime_journal_v3.py','field_runtime_backup_v2.py']]"
```
Compilation is not device execution or offline acceptance. See README_RUNTIME_PROFILE_CAPSULE_V1 and README_RUNTIME_CONTROLLER_PROFILE_V1 for the selected code and gallery bindings; final runtime assembly must include the changed ledger and policy from that common capsule.

