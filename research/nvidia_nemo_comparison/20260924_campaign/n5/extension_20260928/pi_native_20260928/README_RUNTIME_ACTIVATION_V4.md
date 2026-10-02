# Ten-profile activation renderer

Purpose: render pinned desktop entries for six microphone profiles and four saved Streaming/Chunk52 profiles, with ReDimNet/TitaNet explicitly labelled. All entries select manager7 through the same versioned frontend, idle with capture off. Rollback2, shared CPU slice, systemd limits and offline environment remain.

Inputs: a fresh release ID, exact policy SHA and exact rollback binding SHA. Outputs:15 launch assets within the existing16-file/64KiB limit. The pure render API creates bytes only; a fresh controlled installer must reserve, back up, transfer, verify and activate them. Saved routes use WAV input and never silently fall back to live Delayed.

PowerShell, from this source directory:

~~~powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; p=Path('prepare_runtime_activation_v4.py'); compile(p.read_bytes(),str(p),'exec')"
~~~

CMD / Anaconda Prompt:

~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; p=Path('prepare_runtime_activation_v4.py'); compile(p.read_bytes(),str(p),'exec')"
~~~

Inside a registered CPU14 coordinator with a current bounded scope:

~~~python
from prepare_runtime_activation_v4 import render
files = render(fresh_release_id, exact_policy_sha256, exact_rollback_sha256)
~~~

No native success is claimed by rendering. Do not replace old launchers before verified preservation and final activation. Existing closed candidates and their evidence remain immutable.

