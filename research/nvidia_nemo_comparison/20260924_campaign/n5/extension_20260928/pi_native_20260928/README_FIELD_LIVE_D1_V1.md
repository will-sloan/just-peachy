# Installed live D1 binding and field controller V2

Purpose: connect the actual installed v12 `N2ResidentModels.acquire_diarizer` and
`NemotronDiarizer` to the explicit delayed Nemotron-3 method. The original resident
acquisition still constructs the model. A checked subclass enforces one acquisition,
one construction and the constructor's one initial reset per process. This is
prepared production code, **not an accepted live launcher or a native test receipt**.

Files: `field_live_d1_v1.py` and `field_live_controller_v2.py`. V2 derives V1 without
changing its field restrictions, archive/source/native writer composition or command
whitelist. Existing V1 sources and saved-input contracts remain immutable.

## Inputs and outputs

The future admitted Pi entry calls `field_live_controller_v2.create(config_path)`.
The existing source CONFIG and ADMISSION must satisfy
`README_FIELD_LIVE_SOURCE_V1.md` and `README_FIELD_LIVE_CONTROLLER_V1.md`, including
CPU 2/3, 768 MiB AS, 1 MiB stacks, one native thread, genuine quiet-recording
authority, ownership and deadlines. This module does not grant that authority.

ADMISSION additionally requires `d1_binding` with exactly:

```json
{
  "mode": "delayed",
  "campaign": "/home/peachyprototype/JustPeachy/research/nemotron-20260928",
  "method_contract": "<admitted code directory>/D1_METHOD_CONTRACT_V1.json",
  "method_evidence": "<existing pinned METHOD_EVIDENCE_V1.json>",
  "maximum_samples": 2080000
}
```

Pin all imported new/retained helpers and the mode/method/endpoint JSON files in
ADMISSION.files. Reuse the existing compact method evidence; do not recopy the
dependency catalogue, models, or native build products. `n2_runtime.json` must
explicitly select `native_v3_delayed`, CPU -1 and the retained LRU1 runtime. Exact
installed origins and release-manifest digests are mandatory.

At actual acquisition, the adapter verifies all selected assets, the actual model
alias, and the retained source/object/build/link/header endpoint lineage. At native
creation it checks the actual C configuration: 264/1/1/0/264/188,
`v3-offline`, GPU -1 and the model path. Mapped native dependencies are checked at
creation and after construction. The selected method requires LRU1 and the 2 MiB
metadata arena; these are fixed profiles, not new performance measurements.

The controller returns its usual context plus `d1_binding`, a bounded in-memory
state record for the caller's admitted receipt writer. No model output, audio,
probabilities or private profile is printed. First D1 failure signals the real
controller's nonblocking Stop callback before the existing native diagnostic slot.
The latch survives Close within this process; it is not durable crash recovery.

Accepted audio is capped at 2,080,000 samples before native push. Native-reported
frame rows are bounded at 13,001 before the installed NumPy allocation. On finish,
actual counts must satisfy empty=0, otherwise floor(samples/160)+1. This is a new
bounded application of the retained source-derived rule. The old endpoint helper's
352,127-sample limit is unchanged. Larger-input native EOF, empty-input behavior,
accuracy, failure stress and live operation remain unqualified until observed.

## Host source checks

These commands only compile source in memory, with CPU14 set before project reads.
They do not import the installed app, create native models or capture audio. Use the
existing environment; no package installation is needed.

PowerShell, from the native reports directory:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; names=('field_live_d1_v1.py','field_live_controller_v2.py'); [compile(Path(n).read_bytes(),n,'exec') for n in names]; print('source compilation only')"
```

Command Prompt or Anaconda Prompt, from that same directory:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; names=('field_live_d1_v1.py','field_live_controller_v2.py'); [compile(Path(n).read_bytes(),n,'exec') for n in names]; print('source compilation only')"
```

For the Pi, the caller uses the installed rc5 Python and the genuine bounded entry:

```python
from field_live_controller_v2 import create
controller, context = create(admitted_config_path)
# The admitted entry owns GUI/Start/Stop/Save/Open/Close, closure and backup.
```

There is deliberately no standalone capture CLI here: complete physical writer
enforcement, full entry admission, owner ACK, visible lifecycle and closed-tree
mirror binding must be completed before that entry can run. Required delete,
import/export, gallery compatibility, repeated operator starts, physical touch and
offline acceptance remain open. No module here activates or replaces the baseline.
