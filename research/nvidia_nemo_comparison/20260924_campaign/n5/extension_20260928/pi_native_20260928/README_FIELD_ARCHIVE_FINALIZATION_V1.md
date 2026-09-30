# Reserved archive finalization

Purpose: close the V69 initial-versus-final control-size gap using a fresh versioned archive derivative. The v2 archive budget explicitly partitions64KiB control files: initial metadata <=32KiB and runtime fields <=24KiB, leaving serialization margin. Initial admission runs before creating the epoch/thread. Existing16MiB raw metadata,16MiB journals,130s PCM and queue/record/floor limits remain. The2MiB auxiliary allowance now reserves1MiB for diagnostic files; ordinary resources/windows/transforms share the remaining1MiB. This is not a larger allocation.

Full first failure text up to256KiB is retained exactly in failure.txt; the primary JSON contains a bounded UTF-8 preview and exact byte/hash reference. Late metadata exceeding the24KiB runtime reservation is preserved in checkpoint-detail.json when it fits256KiB, while the primary publishes essential counts, PARTIAL, explicit overflow and joined-worker state. Count old+temporary checkpoint details (512KiB) and failure.txt (256KiB) within the1MiB reserve. The live diagnostic detail is a current checkpoint, not an immutable history of every metadata update. Original errors/counts are not cleared. If diagnostic text exceeds its declared retention cap, the primary records the full byte count/hash and retention failure, and close raises after joining/publishing PARTIAL. This is an explicit unsupported-diagnostic failure, not full-detail retention. The test harness separately preserves that complete synthetic input. Hardware I/O failure, power loss, arbitrary corrupted/nonfinite runtime fields and all possible external metadata are not qualified by this protocol.

Inputs: exact V69 source hash, installed v12's unchanged adapters/runtime, ARCHIVE_BUDGET_V2.json, authority and fresh CPU14 census. Outputs: six fresh reserve/prepublication rejection cases and four native closure cases: normal reserved close, near32KiB initial metadata plus long Unicode/escaped failure, oversized late metadata, and diagnostic-retention overflow. Each has one harmless synthetic event; there is no generated audio, microphone, models, Controller, GUI, archive copy or full-size journal rewrite. No unchanged V69/V66/V67 cases rerun. Receipts, entire synthetic failure inputs, output/error files, live envelope and exact backup remain private.

The dispatcher admits4MiB target+4MiB host under unchanged WINDOW_V5,52GiB total and fixed32GB Pi/5GiB free. Actual worker request CPU2,3/shared200%,one thread,768MiBAS/1MiBstack/Tasks64/300s/60sStop/32MiBfile, initial850MiB and sampled192MiB available/640MiB aggregate stops. The stricter whole-target guard stays4MiB. No allowance revision or capture admission. Production field-contract/health/store/launcher integration is still separate. The v2 contract is not interchangeable with old v1; do not edit bound releases or feed it silently to old validators.

PowerShell:
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_archive_finalization_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V162.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_archive_finalization_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_archive_finalization_v1.py
```

CMD / Anaconda Prompt (existing explicit Python; no environment installation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_archive_finalization_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V162.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_archive_finalization_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_archive_finalization_v1.py
```

The run root and review/backup outputs are exclusive. Preserve failures and do not repeat a successful run. `field_archive_budget_v2.validate/digest` consume the exact v2 config; the archive/store policy key is archive_budget, the same explicit opt-in API as V69. The helper, overlay, protocol, dispatch, independent reader and backup are all covered here. No external import/export or live/endurance acceptance follows.
