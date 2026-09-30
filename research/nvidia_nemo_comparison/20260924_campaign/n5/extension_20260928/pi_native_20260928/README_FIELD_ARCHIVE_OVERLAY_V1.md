# Retained archive-policy overlay

Purpose: bind the V70 reserved archive-budget-v2 policy through the real installed v12 Controller and FieldArchiveStore before any epoch publication. This small versioned overlay pins the existing v12 release/entry/contract and the exact retained V70 sessions/helper files. It adds a config, effective contract and descriptor; it does not copy a release, catalogue, runtime, assets or audio. The additional contract delta is exactly `archive_budget`; the old compact dependency binding does not cover it. A transaction/guarded-launcher adapter remains separate work.

`field_archive_overlay_v1.verify` checks descriptor, module origins/hashes, exact fields, config hash/canonical policy and the single contract delta before creating private data. It imports the retained sessions module explicitly under `app.sessions` before installed consumers load. All other app modules and app.paths.ROOT remain installed v12. The installed FieldArchiveStore parent retains its history/quota behavior; the small subclass passes the exact policy into the real SessionStore constructor. Import and export are explicitly unavailable because extended archives lack the old SQLite member and have different size limits. No interchange acceptance is implied.

This entry only admits construction/health qualification. It blocks live capture and pipeline start, uses saved-audio-only controller configuration and exposes no GUI CLI. The protocol holds the existing private RuntimeLock through health, real ApplicationLock checks, the sole controller borrower, epoch closure and worker joins. Original root/schema/feature checks remain. Policy drift is checked before the epoch engine factory could run. No N2Engine is constructed here, and no model/source/audio/Tk path runs.

Inputs: immutable v12 manifest `274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0`, exact retained V70 sessions/helper/config, current authority, fresh CPU14 census and copied private live/n2_runtime configuration. Outputs: exclusive descriptor/config, eleven small prepublication rejection fixtures, changed installed health/Controller/store propagation receipts, policy-conflict and disabled-action rejections, and one empty no-audio epoch with zero submitted items. The empty epoch tests policy propagation, not the previously tested large writers or finalization stress cases. All fixtures and receipts remain private.

The dispatcher admits 4 MiB target plus 4 MiB host backup under unchanged WINDOW_V5, 52 GiB total, fixed 32 GB Pi and 5 GiB free reserve. Actual worker: CPU2,3/shared200%, one native model thread, 768 MiB AS, 1 MiB stack, Tasks64, 300s/60s Stop, 32 MiB per-file upper limit; whole-target limit is the stricter 4 MiB. Initial available RAM850MiB, sampled available192MiB/aggregate640MiB stops remain. No policy increase or capture admission. Read-only preflight checks exact owners, units, baseline, capture and leases. Failed runs stay preserved; never rerun a passed run root.

PowerShell:
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_archive_overlay_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V163.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_archive_overlay_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_archive_overlay_v1.py
```

CMD / Anaconda Prompt (existing explicit environment; no installation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_archive_overlay_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V163.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_archive_overlay_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_archive_overlay_v1.py
```

The five Python files named above (overlay, protocol, dispatcher, independent review and backup) are covered by this README. Run only with a fresh census and absent exclusive run root. Restoration is leaving the unused overlay unselected: no original release, baseline config, catalogue or candidate pointer is changed. Retained module paths are required; this is not a standalone field release, full pipeline, capture, GUI or endurance qualification.
