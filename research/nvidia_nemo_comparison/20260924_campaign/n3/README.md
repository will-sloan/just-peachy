# N3 streaming ASR and text components

This directory contains the N3 comparison implementation and receipts. N2 is
accepted with its final report, handoff ZIP and verified Git backup. Numerical
work respects the campaign's two CPU cores and sole GPU owner. Accepted and
running source, admission files and evidence remain immutable.

Status: ACCEPTED for offline N3 component comparison and N4 inputs. Read
REPORT_N3.md, N3_FINAL_METRICS.json, FINAL_CHECKS.json, N3_ACCEPTANCE.json and
N3_HANDOFF.md. All four 96-file screens, 32 regressions, 20 paced files and nine
new/native GUI cases are reviewed. The final A1-capable source suite passes
452 tests with two platform skips. A1's complete ONNX service is qualified on
Windows without Torch/NeMo in the deployed service. ARM64/CM5 remain separate.

The original A1 paced queue count defect and A3 single-core GUI failure remain
preserved. A separate census receipt admits the exact eight predeclared A1
files; A3's bounded two-core functional panel passes without a timeout change.
Neither is a general performance or model-quality claim. Earlier preparation
JSONs and failed attempts remain historical, not rewritten.

README_REVIEW.md and README_PACKAGE.md describe reproducible final review and
analysis packaging. README_GUI_TWOCORE.md documents the bounded resource
contrast. N4/N5 are not complete. The Pi remains off; no user desktop input,
focus, microphone, playback or personal-profile changes were used.

## Fetch exact official artifacts

`fetch_assets.py` downloads five pinned artifacts (about 6.28 GiB) from the
official NVIDIA Hugging Face repositories. It validates exact sizes/SHA-256,
preserves model cards and writes `FETCH_RESULT.json`. It executes no downloaded
model code, accepts no decoder defaults and changes no application environment.
The inputs are pins in this script and `--output`; outputs are private model
payloads, cards and the receipt. Existing mismatches fail rather than overwrite.
Partial HTTP downloads resume only if the server honors the exact byte range.

PowerShell:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& $py research/nvidia_nemo_comparison/20260924_campaign/n3/fetch_assets.py --output G:/Just_Peachy_N1/20260924_campaign/local/n3/assets
```

CMD or Anaconda Prompt (no environment activation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research/nvidia_nemo_comparison/20260924_campaign/n3/fetch_assets.py --output G:/Just_Peachy_N1/20260924_campaign/local/n3/assets
```

The fetch is sequential, uses CPU 4 at below-normal priority where psutil is
available, and reserves 75 GiB plus 16 GiB for N2 on the work drive, and 50 GiB
on C:. Downloads are not publicly committed. Ordinary commercial use is admitted
under the exact model terms; notices and source changes accompany distribution.
A1/A2 weights use NVIDIA Open Model License; A3 uses OpenMDW-1.1. These are
separate from the native runtime's Apache-2.0 code license.

Resume: inspect the N2 owner/CHAIN_RESULT before admitting numerical work. Read
this stage's receipts and run only missing cells. Do not duplicate N2 or N3.
The currently selected prototype and personal data remain the rollback path;
no candidate is enabled until its runtime/config binding passes validation.
