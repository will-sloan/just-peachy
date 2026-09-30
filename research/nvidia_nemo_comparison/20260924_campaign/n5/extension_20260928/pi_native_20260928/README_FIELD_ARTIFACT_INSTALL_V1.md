# Installed artifact contract and native factory binding

Purpose: finish the missing installed configuration boundary after V66 passed the native writer/archive components. The actual controller constructs N2Engine before creating/attaching its archive. Merely teaching PrototypeEngine to inspect an archive constructor argument would leave production's native journal at the legacy default. A fresh controller derivative extracts the existing engine construction into `_create_epoch_engine` and passes validated artifact options there. Production `_start_session` calls this same helper. No source/inference start is needed to test it.

`prepare_field_artifact_install_v1.py` creates fresh controller, entry and FieldArchiveStore derivatives from privately backed-up immutable v10 source, with original/new hashes in ARTIFACT_INSTALL_DERIVATION_V1.json. It refuses existing outputs. `field_artifact_binding_v1.py` checks the exact installed config path, file/canonical hashes, declared byte accounting, recording duration and Start reservation. New entry health and create_controller use it; the latter rejects bad config before private-directory creation. FieldArchiveStore validates the same hash and passes the same limits into its policy; each native engine construction checks policy equality again. V66's writer modules remain byte-identical.

`field_artifact_install_v1.py` builds/stages code-only b01-offline-20260930-v11, adding the artifact config/helper and binding through field_contract.json and RELEASE_MANIFEST. Shared models/runtime/research dependencies stay in place. No candidate-pointer activation, dependency catalogue re-extraction or 5.5MB lock copy occurs. An actual outer RuntimeLock spans installed health, real controller, actual N2Engine constructor/native event-writer factory and actual FieldArchiveStore/EpochArchive creation/closure. Existing ApplicationLock still performs root/schema/feature checks, borrowing exactly one outer lease with the same token. Original live/N2 config copies remain exact; fresh empty store metadata is expected.

Seven tiny config-only fixtures enter actual installed create_controller preflight and reject missing binding/file, changed file/canonical hashes, wrong path, too-short audio frames and insufficient reservation before data publication. They are not complete alternative releases or independent asset-health tests. An eighth case changes only the in-memory store policy and rejects before engine creation; it is restored immediately. The valid path constructs the actual N2Engine without calling begin/start_xvf/start_file, writes one harmless event through its real `_open_journal_text` factory, and creates/closes one empty private audio epoch through the real store. Its WAV is only a44byte header, not a recording; no waveform, model, capture, playback, Tk or UI runs. The test checks effective16MiB journal and2080000-frame bounds, zero model loads, ownership/worker closure and source receipts absent. It does not repeat V66's large synthetic fixtures or qualify full pipeline start, live Stop, endurance, GUI or extended import/export.

Inputs: fresh CPU14 census, V66 independent pass/backup, exact v10 source/manifest and artifact derivatives, current authority, original baseline/config and copied N2 runtime configuration. Outputs: fresh field-artifact-install-v1 admission/source/codeZIP/stagedv11, malformed tiny config fixtures, installed health/factory/epoch/closure receipts, independent review and exact private backup. Target16MiB+host16MiB under unchanged WINDOW_V5, fixed32GB/5GiBfree. Actual Pi768MiBAS/1MiBstack/CPU2,3/shared200%/Tasks64/300s/60sStop/32MiBfile; initial850MiB and sampled192MiBavailable/640MiBaggregate guards. Full code/backup bytes count. Each extra capture requires a separate measured admission.

PowerShell, fresh preparation/run only:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B prepare_field_artifact_install_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_artifact_install_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V158.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_artifact_install_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_artifact_install_v1.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_field_artifact_install_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_artifact_install_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V158.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_artifact_install_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_artifact_install_v1.py
```

Preparation has already run when the new derivative files exist. Do not rerun completed paths. Dispatcher rejects a census older than15minutes and refreshes owner/lease/baseline/target-inclusive resource gates. Review reads existing files without importing the tested implementation; backup validates every byte/hash. Preserve all rejected fixtures and failures. No generated private data/audio/weights/profiles enter Git.
