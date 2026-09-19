# Review a closed S6D capture stage

Purpose: independently reconstruct the transmitted whole unity-gain microphone input with its1s pre/3s post guards; verify actual native PCM24 markers, saved six-channel and mono derivatives, logical route/configuration, required payload, rails and exact four-MIC recovery for QA passes. Verify actual owner/telemetry/supervisor/census closure. This is read-only analysis with no device/model/process launch and no automatic scientific admission.

Inputs: one literal closed qualification QUEUE.json, all of its hash-bound plans, code, results, original WAVs, capture artifacts and actual completed supervisor/owner receipts. A supervisor must have finished normally; the exceptional first-QA root correction has its separate historical reviewer. Outputs: a new compact JSON review with checks and binding hashes, per-stream rail/equality/activity diagnostics, and explicit pending processed tail/route/observer interpretation. Existing output is refused. Original audio is never modified or normalized.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_closed_capture_review_v1.py" --queue "$sim\reports\S6D\20260913T195357Z\runner\qualification_stage_1_queue_v2\QUEUE.json" --output "$sim\reports\S6D\20260913T195357Z\physical_qualification_review_v1\MAIN_TRANSPORT_REVIEW.json"
```

Anaconda Prompt / CMD (explicit environment, no activation):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_closed_capture_review_v1.py" --queue "%SIM%\reports\S6D\20260913T195357Z\runner\qualification_stage_1_queue_v2\QUEUE.json" --output "%SIM%\reports\S6D\20260913T195357Z\physical_qualification_review_v1\MAIN_TRANSPORT_REVIEW.json"
```

Run only after the owner and supervisor close. For later stages supply their actual queue and a fresh output filename. Any failed check raises an error; inspect the source evidence instead of changing assertions to force passage. A processed-only pass has no exact microphone echo. Equal processed beams may be real. Last nonzero output and complete input submission alone do not prove useful processed speech survived; separate qualification diagnostics must assess the common measured delay, source support and retained tail before a bank is admitted.
