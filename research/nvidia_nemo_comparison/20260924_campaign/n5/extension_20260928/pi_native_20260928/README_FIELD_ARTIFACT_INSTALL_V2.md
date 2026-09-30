# Installed artifact integration: explicit UTF-8 repair

Purpose: execute the V1 installed contract/controller/native writer-factory boundary with source bytes that match the intended Unicode derivatives. V1 generated two files using Windows default CP1252. Its seven config preflights and installed health completed, then controller import rejected byte0x85 before controller construction. No models/capture/GUI ran. All V1 code, v11, admission, failure and backup stay immutable; it is not a passed integration.

`prepare_field_artifact_install_v2.py` decodes the two exact V1 derivative byte streams as CP1252 and encodes UTF-8. It requires each result to equal the intended UTF-8 SHA already recorded in ARTIFACT_INSTALL_DERIVATION_V1.json, parses and compiles the actual bytes, and writes fresh files plus ARTIFACT_INSTALL_DERIVATION_V2.json exclusively. No semantic controller/entry change is introduced by this repair. The FieldArchiveStore and V66 writer implementations remain byte-identical. The fresh protocol stages v12 and includes this addendum alongside the immutable V1 documentation. The entry's retained README reference points to that included V1 purpose description.

Inputs: verified V1 failure review/backup, V66 component pass/backup, exact immutable v10 code, artifact config, current authority/baseline/config, and a fresh CPU14 census. Outputs: new repaired source, admission, code-only v12 ZIP/release, seven tiny config negatives plus actual conflicting store-policy rejection, actual installed health/controller/N2Engine constructor/native writer factory/empty archive receipts, independent review and full private backup. There is no begin/start_file/start_xvf/model/capture/Tk call, audio recopy, pointer activation, dependency catalogue copy or large fixture. A header-only44byte WAV is not a recording.

Limits remain16MiB target plus16MiB host evidence under WINDOW_V5; Pi768MiBAS/1MiBstack/CPU2,3/200%/Tasks64/300s/60sStop/32MiB per file, initial850MiB and sampled192MiB available/640MiB aggregate stops. Effective native/conversation16MiB and2080000-frame PCM bounds are tested at the installed construction/factory boundary. This does not qualify live propagation, sustained capture, new numeric model parity, GUI or extended interchange. All old releases and baseline remain unchanged. See README_FIELD_ARTIFACT_INSTALL_V1.md for the original implementation design and README_REVIEW_FIELD_ARTIFACT_INSTALL_V1.md for failure-aware independent review.

PowerShell (fresh paths only; preparation refuses existing outputs):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B prepare_field_artifact_install_v2.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_artifact_install_v2.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V159.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_artifact_install_v1.py --run field-artifact-install-v2
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_artifact_install_v1.py --run field-artifact-install-v2
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_field_artifact_install_v2.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_artifact_install_v2.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V159.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_artifact_install_v1.py --run field-artifact-install-v2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_artifact_install_v1.py --run field-artifact-install-v2
```

The V1 bound README omitted required `--run` arguments in its review/backup examples; the commands above and the separate review README correct those examples without editing old evidence. Do not rerun existing completed paths or silently reuse an expired census.
