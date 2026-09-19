# Launcher preparation checks

Checks.py reads the generated CONFIG.json and constructs all four actual profiles and desktop windows without starting models/audio. It verifies disabled hardware/enrollment/workload-switch controls, exact selected roster, source integrity, malformed schema, absent assets/gallery, explicit M0 fallback, invalid selection/language/device and PCM format rejection. Small silent WAVs are header fixtures only and are never played or passed into models. Output CHECKS.json and check_fixtures are preserved; reruns into existing output are refused.

PowerShell:
~~~powershell
$Task = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z\application\prototype_v1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$Task\Checks.py"
~~~
Anaconda Prompt/CMD:
~~~bat
set "TASK=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z\application\prototype_v1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%TASK%\Checks.py"
~~~
No installation is needed. Actual native per-mode CLI/GUI smokes, resource guards, diagnostic rotation and clean-path relocation remain to be executed before qualification. Frozen README.md/PREPARATION.json retain build provenance; subsequent corrections need separately versioned source and receipts.

