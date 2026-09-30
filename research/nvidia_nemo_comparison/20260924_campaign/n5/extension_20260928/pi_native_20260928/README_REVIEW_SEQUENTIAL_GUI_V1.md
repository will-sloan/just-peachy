# Independent sequential controller/GUI reader

Purpose: review the preserved V1 widget failure or the V2 saved-source controller/GUI protocol without rerunning any model. The standard-library target reader compares actual canonical events, source hashes, cooperative cancellation prefix, three nonoverlapping model lifetimes, immutable primary/save manifests and GUI text. It checks live resource properties, natural exits, original app/config identities, closed capture and free leases. V1 is failure accounting only and must have no model child.

Inputs: existing immutable sequential-gui-v1 or sequential-gui-v2 target receipts, original reference events/assets and host launch receipt. Outputs: private REVIEW.json, BACKUP.json and hash-verified target/ files, with all target originals retained. No transcript is printed or committed. The reader uses host CPU14, target CPU3, 256 MiB virtual memory and 110-second alarm. It opens no model, GUI, microphone or playback. GUI acceptance is actual withdrawn widgets only; no physical touch, arbitrary source picker, live mode, accuracy or endurance acceptance. Child ru_maxrss is reported without treating inherited pre-exec high-water values as measured post-exec peaks; sampled aggregate RSS is separate.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_sequential_gui_v1.py --run sequential-gui-v2
```

CMD / Anaconda Prompt (explicit interpreter):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_sequential_gui_v1.py --run sequential-gui-v2
```

Use `--run sequential-gui-v1` to preserve and review its pre-model widget failure. Run only after the owned unit and exact processes have closed. Review and backup outputs are exclusive: never overwrite them or change the bound run to satisfy this reader. The small failed run and each successful stage backup count against their original 32 MiB combined admissions.
