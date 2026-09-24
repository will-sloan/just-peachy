# Small task11 native check

Purpose: run the existing controller and frozen speech models on a few local CMU
Arctic recordings. Original enrollment (awb/bdl a0001,a0003), candidate (awb
a0016), fresh held-out query (awb a0017–a0019), outsider (clb a0001) and deliberate
two-speaker mixture have separate roles. No microphones, playback, downloads,
production profiles or sweep. Fixture confirmations use the known corpus speaker,
not a claim that a participating human approved production adaptation.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& .\.edge-speech-env\python.exe prototype/tools/check_adaptation_native.py --output Resumes/.uiiter2_11/native_fresh
```

Command Prompt / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
.edge-speech-env\python.exe prototype\tools\check_adaptation_native.py --output Resumes\.uiiter2_11\native_fresh
```

Inputs: existing models under `C:\Users\amiri\JustPeachy\shared\models` and the
repository CMU Arctic corpus; optional `--corpus` selects that corpus directory.
Output must be a **new** folder. It contains temporary private fixture profiles,
prepared PCM16 WAVs, real runtime logs and NATIVE_ADAPTATION_CHECK.json. The report
binds source/model audio hashes, original anchors, exact runtime files, per-run
wrong named segments/accepted segment coverage, candidate decisions and wall/CPU/
sampled RSS. Coverage is final caption segments, not time-aligned DER. Mixture
has no single true speaker. Initial short segments may remain Unknown normally.

Native comparison runs matching Off, On and after Undo with held-out audio.
Replaying the promoted source checks that saved audio cannot be collected twice.
It does not infer improved accuracy from equal results, train models, tune gates
or qualify CM5. Retain failed attempt receipts separately. Keep vectors, corpus
audio and full logs local; only compact aggregate results belong in the handoff.

Actual controller/widget check (no inference): replace the script above with
`prototype/tools/check_adaptation_ui.py --output Resumes/.uiiter2_11/ui_fresh`.
It uses isolated synthetic profiles and drives confirmation, selection, promotion,
matching and Undo; saves six screenshots and UI_CHECK.json. It briefly raises a
480×800 window for unobscured screenshots, then closes only its own window.
