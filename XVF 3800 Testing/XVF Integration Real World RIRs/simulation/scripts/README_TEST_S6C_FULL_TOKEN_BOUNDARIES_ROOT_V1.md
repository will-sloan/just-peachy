# Independent full-token-boundary helper review

This finite review checks the new helper's mixed-population counting and original-CSV admission behavior. It uses tiny constructed rows, including two deleted boundary words, a missing one-word reference, empty input with insertions, and an incomplete reference. It also validates the exact finite draft's declared routes and pending sources against small existing metadata. It does not rerun the owner's 33 checks or rescan any actual score table.

Inputs are the SHA-pinned helper and its README, the inherited pure functions, and the existing draft SPEC.json. The output is a no-overwrite REVIEW_RECEIPT.json under REPORT/independent_review/full_token_boundary_root_v1. It proves only the stated source/fixture checks; the actual later table diagnostic still requires a complete admitted plan and result review. It performs no model, policy, audio, vector, prediction or native-event work.

## PowerShell

```powershell
$s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $s6cPython -B (Join-Path $s6cSim 'scripts\test_s6c_full_token_boundaries_root_v1.py')
```

## Anaconda Prompt or Windows CMD

```bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6C_PYTHON%" -B "%S6C_SIM%\scripts\test_s6c_full_token_boundaries_root_v1.py"
```

Use the explicit existing interpreter; no installation or activation is required. Run once because the output namespace is immutable. A changed helper or repeat review requires a new reviewed version/namespace; preserve this receipt and its source files. No deletion or mutation of source/results is part of the review.

