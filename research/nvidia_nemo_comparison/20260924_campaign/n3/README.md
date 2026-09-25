# N3 streaming ASR and text components

This directory contains the N3 comparison implementation and receipts. N2 is
accepted with its final report, handoff ZIP and verified Git backup. Numerical
work respects the campaign's two CPU cores and sole GPU owner. Accepted and
running source, admission files and evidence remain immutable.

Status: IN_PROGRESS. Stage acceptance and target performance remain unproven.
The v3 queue has finished with valid A0/A1 screen/regression/paced evidence,
but failed native initialization and A1 export checks prevent acceptance.
See README_REUSE.md for the bounded v4 recovery and its provenance rules.
RECOVERY_V4.md records the native recovery. V4 is terminal: 29 jobs complete,
three failed (A1 export checker and both GUI panels). A fresh reference
diagnostic then passed eight strict encoder/cache cases on the preserved graph.
The GUI failures were traced to two corrupted expected-label literals; all six
GUI cells rerun in numerical-guilabelsv1 using the exact frozen application.
README_A1_DIAGNOSTIC.md and README_GUI_RECOVERY.md describe these checks. A1
portable frontend/decoder/EOU and real-audio qualification remains outstanding.
Pi is powered off throughout. Use saved hash-bound audio only. Do not open a
microphone, enumerate input devices, play audio or change desktop focus.

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
