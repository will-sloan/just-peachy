# Sustained-run failure reader V5

Purpose: independently account for failed field-sustained-v4 without rerunning capture/models or rewriting its admission. Planned V1-V4 success readers were not executed on this known partial run.

Inputs: immutable admission, exact owners, measured envelope, source ACK/route snapshots, failed journal/epoch records, saved float/PCM prefix, TRACE, dependency derivative, installed manifests and live resource series. Outputs: private REVIEW.json, failure/prefix/coverage accounting and separate hash-verified backup through backup_field_sustained_v4.py. CPU14 host; native read-only CPU3/512MiB, no bytecode.

Require natural main1/child0 and closed owners/controller/Tk/outer lease. Preserve failed logical event-handle closure, journal accepted/completed mismatch, incomplete D1 coverage and absent EOF. Verify only saved960000sample/60second float/PCM prefix against6000 traced block hashes. Report transport1843200, journal1842720, timeline1842880 and480 uncredited transport samples separately. No complete115s recording,120s passage, new model reference, quality, full endurance or release. Failure footer is BYTE_LIMIT/native and SOURCE_FAILURE/archive; narrow event-only decoder rejects other formats.

Static review: CompactJournal still caps8MiB and PCM16Writer/sessions metadata cap960000frames independently of systemd32MiB and GUI125seconds. No guard is removed. Fix those explicit contracts and test boundaries without capture before any fresh longer-run admission.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_sustained_v5.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_sustained_v4.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_sustained_v5.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_sustained_v4.py
```

Run only once into fresh review/backup destinations. Preserve all failures, partial data, hashes and raw receipts. Process exit closing OS handles does not establish clean logical finalization.
