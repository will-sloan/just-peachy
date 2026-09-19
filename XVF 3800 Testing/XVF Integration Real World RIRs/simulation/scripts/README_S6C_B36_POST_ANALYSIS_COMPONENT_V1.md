# Independent B36 post-analysis context review

Purpose: review the held B36V2 post-analysis/normalization wrapper while preserving every native/scientific source. Inputs are exact pinned wrapper/README and their held A/N/inventory dependencies. Outputs are reproduced23 owner checks and nine independent private-context checks in a fresh directory. The test admits no actual batch, opens no runtime logs/PCM/models and starts no models. Its outer prepare call is mocked and records only arguments.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_s6c_b36_post_analysis_component_v1.py --output '..\reports\S6C\20260910T123540Z\independent_review\b36_post_analysis_component_NEW'
```

Anaconda Prompt / CMD (existing interpreter; no environment changes):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_b36_post_analysis_component_v1.py --output "..\reports\S6C\20260910T123540Z\independent_review\b36_post_analysis_component_NEW"
```

Use a new output directory. This review is not native completion, actual post-analysis, inventory or final scientific acceptance.
