# Independent structural-guard review

Purpose: narrowly review the held canonical and C-long fast_v2 protection guard, preserving all original native/scanner/timer code and the failed v1 evidence. `test_s6c_guard_v2_component_review.py` pins the held L/C sources, reuses the owner's focused metadata/code fixtures into a separate output, and independently checks native/coordinator AST identity, retained function/code references, whole-source six-function policy and structural field projection. It imports only wrapper/test utilities; it does not import or execute the original native module, APP or models.

Inputs: the exact pinned fast_v2 sources, prior fast_v1 sources, their READMEs, the owner's guard test/README and original source bytes compiled without execution. No PCM, event, process trajectory, prediction or model assets are read. Outputs: fresh `REPRODUCED_GUARD_CHECKS.json` and `REVIEW_RECEIPT.json`, recording exact source bytes, test counts and review scope. Existing output is refused. This is source review, not authorization or proof of a native retry.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_s6c_guard_v2_component_review.py --output '..\reports\S6C\20260910T123540Z\independent_review\guard_v2_component_v1'
```

Anaconda Prompt / CMD (no installation or environment activation needed):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_guard_v2_component_review.py --output "..\reports\S6C\20260910T123540Z\independent_review\guard_v2_component_v1"
```

For reproduction, use a new output directory. The owner's output constant is changed only in this private review process; its source and original output are untouched. No resource census, native prepare, quiet lease or worker is launched.
