# Independent native A2 full-file review

Purpose: independently review closed a2-native-full-v1 evidence without running models. Require original715127samples in both resident sessions, nonempty text, identical canonical event arrays, monotone source sample publication positions, terminal final, exact source/end-time arithmetic, EOF/post-finish gates and model/stream/process closure. Verify complete source/asset hashes, live CPU/AS/stack/600second envelope, bounded files, baseline unchanged and capture/leases closed. Native word offsets remain model outputs, not reference phonetic alignment. No WER, forced-endpoint, generic-versus-modified probability parity, real-world quality, original1x pacing or integrated B02 acceptance.

Inputs: private target a2-native-full-v1 admissions, runtime/asset bindings, source WAV, exact owners, result/events/logs/resources. Outputs: private host a2-native-full-v1-evidence/REVIEW.json plus copies of small receipts/service log; no target mutation. The reader refuses overwrite; a failed reader needs a fresh version and preserved failure. Actual transcripts stay private.

PowerShell from G:\Just_Peachy_N1\20260924_campaign\worktree:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_a2_native_full_v1.py --run-id a2-native-full-v1
```
CMD / Anaconda Prompt (no activation needed):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_a2_native_full_v1.py --run-id a2-native-full-v1
```
Do not run against an active owner. Do not infer full campaign acceptance from the narrow reader status. Failure branches are deliberately restrictive; unexpected aborts retain evidence for a separate failure audit.
