# Independent first-use E0 failure review

Purpose: verify the closed native B01 lazy-load attempt against exact owners,
source/admission hashes, systemd natural exit1, actual event failure and drained
worker/archive/controller receipts. It does not rerun models or accept B01.

Input: private b01-lazy-e0-v1-evidence launch result and immutable target run.
Output: private REVIEW_INPUTS.json and REVIEW.json on host and REVIEW.json on Pi.
Raw text, vectors, smaps and audio remain private. The reader requires failed E0
model loading, zero embeddings, one observed1201-frame D1 update and failed-session
closure. Those observed frames do not imply completed named-speaker passage.

From G:\Just_Peachy_N1\20260924_campaign\worktree, PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_lazy_e0_v1.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_lazy_e0_v1.py
```

Run once after service and dispatch owners close. Existing receipts are never overwritten.
A successful reader means the failure has been audited, not that the application passed.
