# Independent A2 A76 full/repeat reader V1

Purpose: independently check the fresh A76-only native ASR candidate against the immutable generic source, resource admission and exact owners. It runs no model or capture. A failed assertion is preserved as a reader failure; it never relaxes canonical event matching.

Inputs: a2-a76-full-v1 admission, binding, source/library hashes, live unit envelope, loaded mappings, source counts, events, result and dispatch sampling; original generic full/repeat events and parent library hashes. Only three CPU aliases may differ; A2 metadata/scheduler/cache/library/adapter stay unchanged. Check both full715127sample streams,87canonical events/86nonempty each, EOF/postfinish/reset, actual1536MiB/1MiB/CPU2,3/200%/Tasks64/600s limits,32MiB target bound, natural closure and untouched baseline/capture/leases.

Outputs: private immutable REVIEW.json plus receipts in a2-a76-full-v1-evidence. Reports elapsed time and RTF as observations; only exact generic canonical equality can accept the candidate. A model run that closes naturally with the explicit canonical-mismatch failure is reviewed as failure accounting only, with differing event/word field positions and final-event equality recorded. It does not change the original gate or mark the runtime accepted. This is not independent logits parity, accuracy, integrated B02, live/endurance or a general CPU-kernel qualification. Original rc5 is active; comparison uses earlier sequential runs under equal admitted resources.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_a2_a76_full_v1.py --run-id a2-a76-full-v1
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_a2_a76_full_v1.py --run-id a2-a76-full-v1
```
Run only after exact worker/gate closure. Private transcripts and weights never enter Git. Preserve prior generic and failed variants.
