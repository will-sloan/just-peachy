# Expanded handoff builder

Purpose: `build_handoff_v2.py` retains the original bounded documentation pack and adds the RAM/model report, shortcut/audio requirements, this README and the new builder. It makes no Pi, model or capture changes.

Inputs: the original 12 guide/tool files, these four additions, selected `CHECK_SUMMARY_V<number>.json` and D1 method findings. Summary 135 remains the latest native/research evidence; this report adds no model measurement. Requires the existing Python environment and psutil; no installation or conda activation is needed.

Outputs: a fresh private `completion-20261001-backups/<label>` directory with ZIP, BUNDLE_MANIFEST.json and BACKUP_RECEIPT.json, plus a separate early host-owner receipt. Every member/archive receives exact readback. There are 16 documentation files, two evidence files and one manifest: 19 ZIP members. Old packs are immutable.

The original 256 KiB/member, 2 MiB input/archive, 4 MiB cumulative retained handoff budget and C: 50 GiB/G: 75 GiB floors are unchanged. CPU 14 is set before project reads. The owner receipt must be a new path in an existing private evidence directory. Existing labels/receipts reject; preserve partial failures.

PowerShell:
~~~powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\completion_20261001'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B build_handoff_v2.py --label ram-model-report-v44 --summary-version 135 --owner-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\ram-model-report-v1-publication\HANDOFF_OWNER_V1.json'
~~~

CMD or Anaconda Prompt:
~~~bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\completion_20261001
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B build_handoff_v2.py --label ram-model-report-v44 --summary-version 135 --owner-receipt "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\ram-model-report-v1-publication\HANDOFF_OWNER_V1.json"
~~~

The example label is one use. Later changed snapshots need a new label, new owner receipt and verified summary version. Extract into an empty directory and read START_HERE, the RAM report and operator requirements. They document recommendations and required work, not active release readiness.
