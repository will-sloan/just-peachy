# N2 analysis handoff package

`package_handoff.py` packages a completed and reviewed N2 stage. It is not an
acceptance shortcut. Inputs are final `N2_METRICS.json` with status COMPLETE,
verified Git backup and hashes/byte counts for every selected report, passing
`evaluation/FINAL_CHECKS.json`, and an explicit30–59-file JSON allowlist.
It accepts only small Markdown, JSON and text analysis files inside N2.
Never add private logs, full transcripts, audio, profiles or model weights.

Output is a fresh ZIP, `PACKAGE_CONTENTS.json` inside it and a separate SHA-256
receipt. It checks every archived hash/CRC, targets10MiB and enforces20MiB.
An oversized failed artifact is retained with a FAILED_SIZE_LIMIT receipt.
The scripts needed to run the application remain available in the backed-up
campaign Git commit; the source release ZIP is a separate artifact.

PowerShell, after final acceptance and manual review of `HANDOFF_FILES.json`:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B research\nvidia_nemo_comparison\20260924_campaign\n2\package_handoff.py --file-list research\nvidia_nemo_comparison\20260924_campaign\n2\HANDOFF_FILES.json --output 'G:\Just_Peachy_N1\20260924_campaign\N2_HANDOFF.zip' --receipt research\nvidia_nemo_comparison\20260924_campaign\n2\HANDOFF_PACKAGE.json
```

Command Prompt / Anaconda Prompt (no environment activation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B research\nvidia_nemo_comparison\20260924_campaign\n2\package_handoff.py --file-list research\nvidia_nemo_comparison\20260924_campaign\n2\HANDOFF_FILES.json --output "G:\Just_Peachy_N1\20260924_campaign\N2_HANDOFF.zip" --receipt research\nvidia_nemo_comparison\20260924_campaign\n2\HANDOFF_PACKAGE.json
```

For revisions choose a new ZIP and receipt path. Missing/incomplete acceptance,
changed report bytes, path escapes or a pre-existing destination cause failure.
The package remains unavailable while the numerical campaign is running.
