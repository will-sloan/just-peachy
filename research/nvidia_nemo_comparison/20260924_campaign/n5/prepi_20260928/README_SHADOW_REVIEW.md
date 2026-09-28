# Independent paired shadow review

Purpose: qualify only a closed one-file shadow diagnostic. Inputs are the
PREPI_WINDOWS_SHADOW_V1 admission, code/assets, both phase/lifetime receipts,
SHADOW.json and separately reviewed ungated output for the same composition.
The reviewer checks exact process closure, source/sample/PCM hashes, unchanged
activity/text/timestamps, contiguous source intervals, proposal aggregation,
no actual skips and all original GUI/store/drain checks. No inference or GUI
is started. Output is a new compact review JSON; existing receipts are refused.

PowerShell from this directory:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$prePiRun='G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-shadow-v1'
& $prePiPython -B review_shadow_v1.py --run $prePiRun --output "$prePiRun-REVIEW.json"
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PREPI_RUN=G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-shadow-v1"
"%PREPI_PY%" -B review_shadow_v1.py --run "%PREPI_RUN%" --output "%PREPI_RUN%-REVIEW.json"
```

Use the separately closed A0 path for its review. A pass is not speech-loss
qualification, real-world savings, a Pi speed claim, or full-bank/N4/N5 acceptance.
It checks proposed intervals and unchanged operation; all model work still ran.
