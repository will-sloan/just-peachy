# Root controls recovery review

Purpose: independently check the existing exact recovery documents and private inventory namespace before finite80-cell admission. This is no native rerun. Inputs are the fixed controls recovery result and its bound compact metadata chain; the namespace is the only argument. Output is reports/S6C/20260910T123540Z/independent_review/NAMESPACE/REVIEW_RECEIPT.json plus bounded source buffers. Existing output names are refused.

PowerShell:
~~~powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B s6c_controls_recovery_root_review_v1.py --namespace controls_recovery_root_v1
~~~

Anaconda Prompt / CMD:
~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_controls_recovery_root_review_v1.py --namespace controls_recovery_root_v1
~~~

Choose a fresh namespace only for a justified new review. The script checks actual bound documents, five rejection cases, unchanged collection code and absence of shared module mutation. It reads no native events/audio/models and changes no lease. The full finite admission and actual scientific analysis are separate.

