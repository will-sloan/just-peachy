# Read-only first capture review

Purpose: independently reconstruct the transmitted whole unity-gain four-MIC source with guards, decode original PCM24 capture bytes, compare all six saved mono derivatives, and verify every active MIC sample at one recorded common offset. It also validates actual source/owner/restoration closure. No device query, playback, model call, artifact overwrite or source change occurs.

Inputs: exact first_capture_queue_v1 authority/protocol/closure, physical ledger and saved tagged_C_sentinel/P_INPUT_QA6/QA_QUAL_MAIN_PRE evidence. Output: fresh reports/S6D/20260913T195357Z/physical_first_QA_review_v1/ROOT_ACCEPTANCE.json.

The first root queue incorrectly expected progress_count=1. The bridge correctly reports17 durable file-progress changes; its physical semantic attempt_count is1. The helper permits only this exact documented mismatch after every other predicate passes. It preserves the original queue and REPORT_BLOCKED closure, verifies actual restoration, and never repeats the capture. Future queues must use semantic_checks.attempt_count, not the file progress counter, for capture counts. Auto PP has15 rail samples and remains LIMITED; optional AGC/slow telemetry loss and pending beam/tail qualification remain explicit.

PowerShell (existing Edge environment provides NumPy and SoundFile):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_first_capture_review_v1.py'
```

Anaconda Prompt / CMD:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_first_capture_review_v1.py"
```

An existing review output causes refusal. This receipt supports only this first QA pass and readiness for separately reviewed qualification controls; it does not qualify all240 scenes, beam routes, gain reliability, direction identity or S6D completion.
