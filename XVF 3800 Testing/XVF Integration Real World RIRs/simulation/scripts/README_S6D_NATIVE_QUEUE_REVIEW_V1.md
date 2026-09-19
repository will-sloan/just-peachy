# Independent exact native queue metadata review

`s6d_native_queue_review_v1.py` compares the final proposed native176/Tk8/HOST2 manifests and literal jobs to their preserved scientific declarations. It checks source, profile, gallery, reference and completion bindings, output freshness, exact owner, original deadline, affinity and thread declarations. It invokes only the accepted runner's pure `validate_queue` function, with a clearly temporary in-memory proposed-hash list; the real empty approval proposal must reject. It writes no approval and launches no supervisor, child process, native helper, model, scorer, Tk/UI or hardware.

Inputs: `--directory` containing the exact queue preparation, `--receipt-sha256` for its receipt, and `--output` naming a fresh directory under the declared G study root. The helper uses the existing edge Python and accepted V4 runner. Outputs: one compact `INDEPENDENT_QUEUE_REVIEW_V1.json`; redirect stdout/stderr to a separate fresh G log when desired. Existing code and manifests are read only. No audio payload is created or scored. Audio PCM metadata is compared to prior exact preparation; actual source/journal hashing remains the execution wrapper's responsibility.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_native_queue_review_v1.py" --directory "$sim\reports\S6D\20260913T195357Z\runner\native_execution_queue_preparation_v1" --receipt-sha256 '3bf8712c64c761997183103adc002fabe20f2f4a52f10d92d5e400f4de667017' --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_queue_independent_v1'
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_native_queue_review_v1.py" --directory "%SIM%\reports\S6D\20260913T195357Z\runner\native_execution_queue_preparation_v1" --receipt-sha256 "3bf8712c64c761997183103adc002fabe20f2f4a52f10d92d5e400f4de667017" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_queue_independent_v1"
```

Use a new output suffix if rechecking a reviewed change; never overwrite prior evidence. This acceptance covers metadata/source consistency only. Root separately owns actual queue approval, resource floors, owner isolation and launch; successful schema checking is not production authorization or whole-study completion.
