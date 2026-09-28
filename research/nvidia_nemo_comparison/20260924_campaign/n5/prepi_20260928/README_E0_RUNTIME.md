# ReDimNet without the retired TitaNet dependency

Purpose: fix a portability blocker in E0 backend selection. The previous common
loader unconditionally opened and hashed a TitaNet manifest, even when selecting
ReDimNet. The derivative passes the actual selected embedding component to the
loader. E0 retains all native D1/runtime/device checks but needs no TitaNet fields
or files. Existing E1/default callers retain the original strict manifest check.
This preserves retired code/evidence without new TitaNet inference or training.

Inputs: hash-verified prepi-shutdown-v1 source receipt and fresh private output.
Outputs: immutable source, exact diff, source receipt, included tests and README.
Only controller selection and the dependency loader change; models, streaming,
shutdown repair, inference gates and all historical releases remain unchanged.
Preparation is not acceptance. Actual saved-file tests must use fresh E0-only
runtime copies with all TitaNet keys removed and compare with reviewed parents.

PowerShell from this directory:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$prePiE0='G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\derivatives\e0-runtime-v1'
& $prePiPython -B prepare_e0_runtime_v1.py --parent-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\releases\prepi-shutdown-v1\DERIVATIVE.json' --output $prePiE0
Set-Location "$prePiE0\prototype"
& $prePiPython -B -m unittest discover -s tests -p test_e0_runtime_v1.py -v
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PREPI_E0=G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\derivatives\e0-runtime-v1"
"%PREPI_PY%" -B prepare_e0_runtime_v1.py --parent-receipt "G:\Just_Peachy_N1\20260924_campaign\local\releases\prepi-shutdown-v1\DERIVATIVE.json" --output "%PREPI_E0%"
cd /d "%PREPI_E0%\prototype"
"%PREPI_PY%" -B -m unittest discover -s tests -p test_e0_runtime_v1.py -v
```

Tests use inert dependency files in isolated temporary stores, no models/devices.
The test process pins CPU14, one native thread and GPU off. Use private TEMP/TMP
roots during the campaign. Never overwrite a derivative or edit an active run.
An E0-only dependency fix is not proof of ARM64 Python/Tk/GUI or native Pi operation.
