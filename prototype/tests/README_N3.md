# N3 component verification

`test_n3_components.py` checks the C ABI layout, explicit architecture rejection,
multiple/empty native finals, complete short-tail journal accounting, traceable
ITN, preserved names/negation and contextual WD-40/name mapping approvals. It uses
protocol fixtures only and never loads a neural model or opens devices. The
backend catalog test retains immutable baseline identity and admits the two N3
native compositions without permitting unimplemented seeds to fall back.

From the campaign worktree, PowerShell:

```powershell
$env:PYTHONPATH='prototype/vendor'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m unittest prototype.tests.test_n3_components prototype.tests.test_backend_catalog -v
```

CMD or Anaconda Prompt:

```bat
set PYTHONPATH=prototype/vendor
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m unittest prototype.tests.test_n3_components prototype.tests.test_backend_catalog -v
```

Inputs are the current source and synthetic protocol/text fixtures. Output is the
unittest result. These tests do not establish model accuracy, real GUI application,
source-speed latency or target performance. Actual audio/GUI commands and receipts
are separate in the N3 campaign. Do not modify the frozen N2 source for these tests.
