# Original-setting evidence parity

Purpose: compare actual S6B R0 neural output with accepted S6A journal-derived vectors and native anonymous labels. This checks whether B36's original-tracker control retained acoustic source spans and legacy decisions, separately from its changed scheduler. It performs no neural inference and does not overwrite evidence.

Inputs: bound INPUT_INDEX, completed R0 evidence and B36 predictions. Outputs: a new JSON receipt with each comparison, exact source/flag and legacy-label equality, finite/shape checks, vector bit equality and maximum numerical difference. Small observed float differences are reported rather than called exact equality. Missing outputs remain PARTIAL.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6b_r0_feature_parity.py" --epoch epoch2 --panel challenge --output R0_CHALLENGE_FEATURE_PARITY.json
```

Anaconda Prompt or Command Prompt:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_r0_feature_parity.py" --epoch epoch2 --panel challenge --output R0_CHALLENGE_FEATURE_PARITY.json
```

After full R0/B36 confirmation, use `--panel all --output R0_ALL_FEATURE_PARITY.json`. The receipt preserves prior versions. Original B00 versus B36 word/CER parity is independently checked by the core scorer; this script does not treat altered transcript attribution as a vector error.
