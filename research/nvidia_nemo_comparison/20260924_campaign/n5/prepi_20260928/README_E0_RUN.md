# Actual E0-only runtime checks

Purpose: qualify the dependency repair on each priority Windows composition.
Inputs: e0-runtime-v1 source derived from the reviewed shutdown source, accepted
assets, frozen 44.695-second saved PCM and matching ungated parent reviews.
The generator produces readable e0_lifecycle_v1.py, prepare_e0_lifecycle_v1.py
and review_e0_lifecycle_v1.py. It refuses existing destinations.

Each fresh admission copies runtime JSON into its private precheck and removes
only titanet_manifest, titanet_manifest_sha256 and the E1 embedding_namespace.
No original runtime or model is modified. All D1/native hashes are retained.
The actual application must select the requested backend, load/use ReDimNet,
consume every source sample, preserve exact parent caption/timestamp/activity
results, save/reopen/delete, and close normally. G01/G02/G03 remain shadow-only;
no samples are skipped. This is a one-file composition check, not stage acceptance.

Outputs: private immutable config copies, resource admission, phase/lifetime
receipts, shadow observations and a separate independent review. The same
600-second/two-CPU/GPU-off/128-MiB/saved-file/private-desktop limits apply.
Run sequentially after exact previous owner closure, never on the user's desktop.

PowerShell from this directory, after README_E0_RUNTIME.md preparation/tests:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$prePiBase='G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928'
& $prePiPython -B build_e0_harness_v1.py
& $prePiPython -B prepare_e0_lifecycle_v1.py --name a2-e0-runtime-v1 --backend nemotron_600m
# After the supervisor, coordinator and application all exit:
& $prePiPython -B review_e0_lifecycle_v1.py --run "$prePiBase\a2-e0-runtime-v1" --output "$prePiBase\a2-e0-runtime-v1-REVIEW.json"
# Repeat preparation/review for a0-e0-runtime-v1, backend nemotron_hybrid.
```

CMD / Anaconda Prompt:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PREPI_BASE=G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928"
"%PREPI_PY%" -B build_e0_harness_v1.py
"%PREPI_PY%" -B prepare_e0_lifecycle_v1.py --name a2-e0-runtime-v1 --backend nemotron_600m
rem After all exact owners exit:
"%PREPI_PY%" -B review_e0_lifecycle_v1.py --run "%PREPI_BASE%\a2-e0-runtime-v1" --output "%PREPI_BASE%\a2-e0-runtime-v1-REVIEW.json"
rem Repeat for a0-e0-runtime-v1 and nemotron_hybrid only after closed-run review.
```

No new TitaNet inference, enrollment, downloads, device access or Pi connection.
Passing here does not establish full ARM64 Python/Tk or native hardware readiness.
