# Compact dependency and overlay launcher adapter

Purpose: make an explicit deployment descriptor combine the immutable V68 compact binding with the V71 retained archive overlay. It binds the overlay source hash, overlay descriptor/config/module hashes, installed v12 base and current private DATA_SCHEMA/live_config/n2_runtime hashes. Missing, conflicting or unreviewed data rejects before candidate publication or installed entry. No catalogue entry overrides are allowed. The unchanged original7890-entry catalogue is verified through its qualified compact adapter; it is never recollected, copied or passed silently into the old full-catalogue interface.

`field_overlay_deployment_v1` validates the new schema and returns the reviewed descriptor/manifest/dependency check. `field_overlay_transaction_v1` is a fresh derivative of the V62 single-state transaction helper; its only changes are the README reference and explicit adapter import/check call. Old commit/preflight/fsync/immutable-history logic is byte-for-byte retained after those replacements. `OVERLAY_TRANSACTION_DERIVATION_V1.json` records hashes. The fresh candidate root first selects base v12, then the overlay, and explicitly rolls back to base. These pointers remain separate from original rc5. No old pointers, releases, dependency locks or ledgers change.

`field_overlay_launcher_v1` checks exact admission/expiry/resource limits/current state/configs, then holds the real RuntimeLock across full dependency verification and one actual V71 overlay controller entry. It retains ApplicationLock root/schema/feature checks by lending its sole borrower the same outer token. The launcher joins the controller before releasing ownership. Three bounded test barriers let the parent attempt real rollback before entry, with the controller active, and after its closure; every attempt must reject and leave candidate state/history exact. The entry has saved_audio_only=true and explicit capture/pipeline-start blocks. No epoch, N2Engine, model, source, microphone or GUI is created. After rollback, an overlay launch explicitly rejects rather than selecting a fallback. There is no base-health rerun.

Inputs: fresh CPU14 census, current authority, installed v12, retained V68 compact binding, original catalogue, retained V71 overlay/source, copied private live/n2_runtime config and fresh synthetic DATA_SCHEMA. Outputs: seven new malformed deployment fixtures, three successful immutable transaction records, four new launcher rejection cases, one successful installed controller launch, three update-contention receipts, actual resource envelope, exact config/ownership closure and private backup. The protocol does not repeat old descriptor-only, writer, archive, model or capture tests. Current short-run scope is not a production GUI/capturable launcher or original activation/rollback.

The dispatcher admits4MiB target+4MiB host under unchanged WINDOW_V5/52GiB total/fixed32GB Pi/5GiB free. CPU2,3/shared200%, one native model thread, Tasks64,768MiBAS per parent/child,1MiBstack,300s/60sStop,32MiBperfile. Parent launches at most one child at a time; each spec expires within90s, process wait<=90s, phase deadline60s, per-barrier8s. Initial850MiB available and sampled192MiB available/640MiB aggregate stops remain. Whole target guard is4MiB and managed JSON writes reserve1MiB. No policy increase or capture admission.

PowerShell:
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_overlay_launcher_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V164.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_overlay_launcher_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_overlay_launcher_v1.py
```

CMD / Anaconda Prompt (existing explicit environment, no install):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_overlay_launcher_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V164.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_overlay_launcher_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_overlay_launcher_v1.py
```

This README covers the adapter, transaction derivative, launcher, protocol, dispatcher, independent reader and backup. Execution roots and receipts are exclusive; preserve failures, never retry a rejected mutation or rerun a passed root. Only changed valid descriptors are separately published. Restoration consists of leaving the isolated candidate root unselected; original app/config/personal data are unchanged. Full live output allocation and any later capture admission remain separate.
