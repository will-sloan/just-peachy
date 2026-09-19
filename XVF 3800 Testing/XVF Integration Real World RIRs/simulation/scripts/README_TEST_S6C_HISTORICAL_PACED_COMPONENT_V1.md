# Historical paced converter independent synthetic review V1

`test_s6c_historical_paced_component_v1.py` is a model-free source-review fixture for the held historical paced converter SHA `7230d48b94ecdea4ab592f0c783b53d779a2f1b4b1cd3abadd06226ec5dc59f9`. It reads only the prepared B36 manifest and sealed original S6B epoch2 source/profile authorities. It imports the original tracker/scheduler without neural model construction and creates one explicitly synthetic 192-dimensional vector plus segmentation and ASR observations.

The original scheduler receives conservative native-style lane watermarks. The unchanged extractor/replay functions then process the same synthetic observations. The test retains exact decisions, final utterances and transcript-field differences, and demonstrates the expected current-source parity rejection caused solely by native release-watermark fields. Causal availability and source support are preserved. It does not read an actual cell, PCM, weights or live status, and does not imply that actual paced results have failed. It does not modify the converter.

Output is one fresh source-bound JSON receipt containing all synthetic inputs, both transcript sequences, exact code/metadata bindings and the observed strict-check outcome. The helper refuses changed converter bytes or an unexpected outcome; any later corrected converter requires a separate review version.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$repo\.edge-speech-env\python.exe" -B "$sim\scripts\test_s6c_historical_paced_component_v1.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\HISTORICAL_PACED_ROUNDTRIP_FINDING_V1.json"
```

Anaconda Prompt or CMD (the explicit interpreter selects the existing runtime):

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%REPO%\.edge-speech-env\python.exe" -B "%SIM%\scripts\test_s6c_historical_paced_component_v1.py" --output "%SIM%\reports\S6C\20260910T123540Z\independent_review\HISTORICAL_PACED_ROUNDTRIP_FINDING_V1_CMD.json"
```

Use a fresh output filename for reproduction. No cleanup, native launch, preparation of actual result inputs or completed-data analysis is performed.
