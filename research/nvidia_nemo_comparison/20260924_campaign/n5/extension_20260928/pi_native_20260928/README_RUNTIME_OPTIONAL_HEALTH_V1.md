# Manager closure for saved inputs and optional audio

Purpose: adapt the exact existing manager health consumer to both microphone and saved-source records, and to the explicit Off/Processed archive choice. Every started source still requires matching model/source sample counts, joined source/archive threads, a closed error-free archive and actual source integrity. Off requires exactly zero stored audio samples; Processed requires complete audio coverage. Saved input requires its actual file-context/thread closure and explicitly no microphone/source subprocess.

Input: the exact backed existing field_operator_health_v1.py bytes (SHA2724499e8ad9dc5275b50f7994c74d1fbd1478c52028650092c603d3f6ec62eb). Output: updated health bytes for the same existing manager member, so the16-module cap remains. The installer binds the complete modified manager manifest and independent backups. This derivation is prepared; actual native integration remains to be checked.

PowerShell:

~~~powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; p=Path('field_runtime_optional_health_v1.py'); compile(p.read_bytes(),str(p),'exec')"
~~~

CMD / Anaconda Prompt:

~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; p=Path('field_runtime_optional_health_v1.py'); compile(p.read_bytes(),str(p),'exec')"
~~~

API, within the registered bounded installer after source backup/independent restoration:

~~~python
from field_runtime_optional_health_v1 import derive
updated_health_bytes = derive(exact_original_health_bytes)
~~~

Old health modules and receipts are not rewritten. This is a new source binding for a fresh versioned runtime only.

