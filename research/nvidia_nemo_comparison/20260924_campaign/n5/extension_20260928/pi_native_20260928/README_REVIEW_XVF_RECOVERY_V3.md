# Independent one-shot recovery reader

Purpose: verify existing xvf-recovery-v3 receipts without sending hardware commands. It independently checks the bound prior active-stream fault, current closed-stream failure, literal single restart0 command, intent chronology,2-second delay, unchanged firmware readbacks, live768MiB/stack/CPU/quota/unit limits, natural owners, baseline/capture/lease closure, pre-send backups and fresh hash backup. It never infers microphone function, restored volatile state or live B01 from command success.

Inputs: immutable target admission,6 command receipts, intent, outcome and live envelope, plus private host pre-send backups and launch receipt. Outputs: private REVIEW.json, BACKUP.json and byte-verified target/ backup; target originals remain. Host CPU14; target CPU3,128MiB virtual,60s alarm. No capture/models/playback or maintenance operation runs. Combined backup/output remains under the16MiB admission.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_xvf_recovery_v3.py
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_xvf_recovery_v3.py
```

This reader expects the single-send branch. A readable-current-control/no-send or uncertain-command result requires a separate failure/branch review, never another maintenance attempt to satisfy this reader. Outputs are exclusive. Preserve all prior evidence; do not overwrite or rerun passed checks.
