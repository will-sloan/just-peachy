# Independent restart review

Purpose: independently check a closed PREPI_WINDOWS_RESTART_V1 run. Inputs are
the admission, bound source/assets and both private phase/lifetime receipts.
The reviewer verifies every source hash, exact PID creation identity closure,
both complete sample counts, equal speaker activity and stored text/timestamps,
one ASR/E0 load with two streams, GUI navigation, both saved-record deletions,
and normal process/job closure. It neither loads a model nor opens a GUI/device.

Output is a new compact review JSON; existing receipts are never overwritten.
A pass applies only to two EOF/Stop/Start cycles of the selected saved source.
It does not qualify early cancellation, twelve-pair switching, a full audio bank,
native ARM64/Pi, sustained real-time processing or N4/N5 acceptance.

PowerShell from this directory:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$prePiRun='G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-restart-v1'
& $prePiPython -B review_restart_v1.py --run $prePiRun --output "$prePiRun-REVIEW.json"
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PREPI_RUN=G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a2-restart-v1"
"%PREPI_PY%" -B review_restart_v1.py --run "%PREPI_RUN%" --output "%PREPI_RUN%-REVIEW.json"
```

Use the A0 run path for that separately closed run. Review only after all run
owners exit; a supervisor success alone is insufficient.
