# Reviewed analysis-first handoff packager

Purpose: replace the early checkpoint builder's hard-coded, now historical
stage counts with an explicit current status and reviewed file selection.
`package_reviewed_handoff_v2.py` creates a fresh private ZIP and a separate
SHA256/readback receipt. It never updates the shared ledger, rewrites earlier
archives, guesses stage completion, or installs/runs application models.

Inputs are a selection JSON (`files` and `current_status`, campaign-relative paths), an explicitly
chosen matching current N5 status JSON, and fresh private output/receipt paths beneath
campaign `local/n5`. Every selected file, selection itself and status must
match the current Git commit byte-for-byte. The current authorized branch and
remote are checked, and `git ls-remote` must match local HEAD. Commit/push the
reviewed changes before invoking the builder. A local commit alone cannot pass.

The ZIP contains the selected readable reports/tools with their campaign-relative
paths, the exact current status, a generated GITHUB_BACKUP_RECEIPT.json, and
HANDOFF_MANIFEST.json with hashes. The manifest excludes its own hash. All
members are read back and compared. Target is at most 10 MiB, hard maximum
20 MiB and 30–60 readable files. Individual selected files are limited to
2 MiB. Unsafe, duplicate, untracked, changed or oversized files are refused.
Only the explicit allowlisted text extensions can enter; review the selection
for privacy before committing. An extension check alone is not a privacy audit.

This version intentionally accepts only a PARTIAL checkpoint with zero newly
accepted N4 release profiles. It does not label N4/N5 complete, stop scheduled
work or claim physical CM5 checks. Large private release archives and all raw
audio/models/profiles/transcripts stay outside the handoff; selected public
reports may reference omitted private evidence by path and hash. Installation
instructions and model-fetch/build manifests describe the separately retained
software. GitHub visibility and main remain unchanged.

## PowerShell

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -m unittest test_reviewed_handoff_v2 -v
# Use the current committed status and fresh versioned paths:
& $py -B package_reviewed_handoff_v2.py --selection HANDOFF_SELECTION_V2.json --status N5_STATUS_20260927_V14.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260927_v2.zip --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260927_V2_RECEIPT.json
```

## CMD / Anaconda Prompt

The qualified interpreter needs no environment activation. Both commands use
stdlib only (Git must already be available and authenticated for ref reads).

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_reviewed_handoff_v2 -v
"%JP_PY%" -B package_reviewed_handoff_v2.py --selection HANDOFF_SELECTION_V2.json --status N5_STATUS_20260927_V14.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260927_v2.zip --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260927_V2_RECEIPT.json
```

Repeat with new output and receipt names after reviewing/committing a later
status. Failed/incomplete ZIPs remain preserved. No blanket directory scan is
used to choose files, and the earlier package_checkpoint.py is not re-run.
