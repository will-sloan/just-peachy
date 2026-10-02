# Ten-profile manager preparation

Purpose: retain the persistent manager, four independent recording slots, local copy before the next slot, fresh process ownership and shared resource limits, while adding the four saved Streaming/Chunk52 E0/E1 routes. Microphone and saved inputs have explicit, distinct capture flags. The selected profile drives the D1 mode/parent binding and immutable runtime document. The existing scrollable chooser labels input and embedding choices.

Inputs: an installed versioned manager root, exact release policy SHA, selected profile, and independently pinned profile descriptors/common capsule. Outputs: the existing immutable launch/recording journal, broker operation, local backup and UI. No automatic recording or downloads. This source is PREPARED; use only with a fresh controlled installer and backed complete manager capsule. Do not launch it against a consumed candidate.

PowerShell syntax check from this directory:

~~~powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; p=Path('field_runtime_manager_v7.py'); compile(p.read_bytes(),str(p),'exec')"
~~~

CMD / Anaconda Prompt:

~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; p=Path('field_runtime_manager_v7.py'); compile(p.read_bytes(),str(p),'exec')"
~~~

Native command shape, supplied by the controlled installer and its pinned systemd wrapper:

~~~text
PYTHON -B VERSIONED_ROOT/code/field_runtime_manager_v7.py --root VERSIONED_ROOT --policy-sha256 EXACT_POLICY_SHA --profile SELECTED_PROFILE
~~~

Do not run that command bare: the wrapper supplies the shared CPU slice, AS/stack/task limits, offline environment, rollback unit and exact policy. Inputs and launch assets are backed with independent restored copies before activation. Native processing and final offline readiness require separate actual receipts.

