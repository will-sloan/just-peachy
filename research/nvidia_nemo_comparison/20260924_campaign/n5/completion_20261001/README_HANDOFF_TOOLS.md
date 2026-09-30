# Handoff packaging instructions

Purpose: `build_handoff.py` makes a small versioned documentation-only ChatGPT ZIP and exact readback manifest. It does not deploy software, start models, change Pi configuration, collect recordings or certify offline readiness.

Inputs: this folder's fixed12-file guide/tool allowlist, an explicitly selected `CHECK_SUMMARY_V<number>.json` and the V95 method-integration findings. The initial invocation uses V95. Update the guides/acceptance and select the newest verified summary for a later package; make a fresh builder derivative if its evidence allowlist must change after the source is bound into a closed pack.

Outputs: private `G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\completion-20261001-backups\<label>\` containing a ZIP, `BUNDLE_MANIFEST.json` and `BACKUP_RECEIPT.json`. Unique labels only; existing output roots reject. Partial output is preserved on failure. No deletion, overwrite or blind retry. A successful receipt verifies every ZIP member and exact archive readback; it is not a private-model/data backup.

The tool setsCPU14 before reads. It requires the existing `.edge-speech-env` Python and `psutil`; it downloads nothing. Input is<=256KiB/file and<=2MiB total, archive<=2MiB, all retained package outputs<=4MiB, C>=50GiB/G>=75GiB. These conservative package bounds fit within the campaign caps and do not reset them. The final N5 handoff limit remains20MiB, target10MiB. No personal media/transcripts/profiles/vectors/weights/credentials are included.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\completion_20261001'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B build_handoff.py --label draft-v1 --summary-version 95
```

## Command Prompt or Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\completion_20261001
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B build_handoff.py --label draft-v1 --summary-version 95
```

These commands create the first pack once. For another legitimate snapshot choose a new label (for example`final-v1`) and its verified summary version. Do not rerun the initial command against its existing directory. No conda environment activation is needed because the full interpreter path is explicit.

To use the handoff, extract into a new empty folder and open `START_HERE.md`, then `CHATGPT_HANDOFF.md`. JSON fields are status/evidence, not launch authorization. References under `evidence/` support the snapshot; the full research tree/private receipts remain at the indexed paths. Run operational tests only through their separately reviewed launchers/admissions, never by replaying a closed research dispatcher.
