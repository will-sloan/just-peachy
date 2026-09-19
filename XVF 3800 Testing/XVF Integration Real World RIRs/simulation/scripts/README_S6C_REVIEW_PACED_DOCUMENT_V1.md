# Independently review the paced results document

Purpose: compare all72 rendered core rows and20 gallery rows in
PACED_NATIVE_RESULTS.md with original, hash-verified aggregate CSV files. Check
route/repetition, word/cp denominators, Unknown, returns, name samples and
observed/missing first-correct counts. The complete population definitions give
596 cells without pooling repetitions. This does not rerun scoring or inference.

Inputs: final_supplement_v1/PACED_NATIVE_RESULTS_SOURCE_BINDINGS.json, the bound
document,64 original score authorities and rendered-row CSV sources.
Output: independent_review/PACED_DOCUMENT_ROOT_REVIEW_V1.json.
An existing output rejects; a mismatch raises before a success receipt is written.

PowerShell:

~~~powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$s6cRepo\.edge-speech-env\python.exe" -B "$s6cSim\scripts\s6c_review_paced_document_v1.py"
~~~

Anaconda Prompt / CMD:

~~~bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%S6C_REPO%\.edge-speech-env\python.exe" -B "%S6C_SIM%\scripts\s6c_review_paced_document_v1.py"
~~~

The receipt records the review's scope and limits, not campaign acceptance.
Source tables and the document remain unchanged.

The initial invocation completed the numerical assertions, then rejected a prose
substring check because the document uses the exact metric identifier
cp_first_display_label_final_words. The check now requires that original field
name. No failed invocation wrote a success receipt or changed scientific data.
