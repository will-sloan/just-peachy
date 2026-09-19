# Independent actual candidate support review

Purpose: independently reconcile the exact working_v2 candidate-support receipt, all 31 declared analysis receipts and COVERAGE.csv buffers, and the two compact exported support tables. It does not import the collector or read individual score/prediction/audio/native payloads. A single immediate-directory metadata observation looks for already COMPLETE core authorities omitted from the explicit specification; smoke coverage is reported separately.

Inputs are pinned working_v2 receipt e33667f01216763ddc05decf9b99eaef28462ebccbe341c66f103f59613d6c2c, explicit specification 769f201ae9d5f116028f0f94a50f35eca0e0324dd85e21dfdc9a97668a1eb244, actual source review 48536f4fd9aa7686f90257fb10c79669655ed212eb56ad1b1fe3f189df785733 and their exact metadata/coverage bindings. Existing alias disposition is bound without following native artifacts. Each byte buffer is hashed before parsing; at most128MiB per metadata file. No live process/model or payload scan is performed.

Output is one fresh independent JSON review receipt. It reconciles all240 identities (196 C +44 actual B),388 C routes plus88 B routes, all742 authority-route records and every route support field. It retains exact full-bank per-authority semantics, missing coverage, all-source bindings, immediate metadata observation, and explicit limits. Empty physical_inference_count cells remain unavailable, never zero. All240 source cases include reference-incomplete/empty populations; scored coverage is not universal metric eligibility. An alias does not silently become a scored/native child. Source-scope strings remain declared metadata rather than independent physical-run proof. New completed authorities after this run need a fresh snapshot.

PowerShell:
```powershell
$simTask='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$pyTask='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $pyTask -B "$simTask\scripts\s6c_candidate_support_review_v1.py" --output "$simTask\reports\S6C\20260910T123540Z\independent_review\CANDIDATE_SUPPORT_ACTUAL_REVIEW_V1.json"
```
Anaconda Prompt / CMD (no activation/install needed):
```bat
set "S6C_SUPPORT_REVIEW_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_SUPPORT_REVIEW_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6C_SUPPORT_REVIEW_PY%" -B "%S6C_SUPPORT_REVIEW_SIM%\scripts\s6c_candidate_support_review_v1.py" --output "%S6C_SUPPORT_REVIEW_SIM%\reports\S6C\20260910T123540Z\independent_review\CANDIDATE_SUPPORT_ACTUAL_REVIEW_CMD_V1.json"
```
Use a fresh output filename when reproducing. Existing source and review receipts are never overwritten. A failed check raises and does not publish a PASS. This is numerical coverage reconciliation, not a metric rescore, candidate ranking or final completion review.
