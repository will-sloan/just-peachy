# Prepared-CM5 runtime delivery kit

Purpose: create one private deployable overlay/backup for the existing prepared CM5 and PC. The current installation already contains all ten functional profiles. This kit includes exact current installed code and policy, local TitaNet assets, operator source lineage, prepared inputs, source receipts and current guides. Existing pinned baseline runtime/model assets and Nemotron libraries remain required. It is not an OS image or a portable clean-machine installer.

Inputs: source directory, completion guides, verified current installation, private base, fresh host-only512MiB package scope (<=600s), absent output. Outputs: ZIP, complete member/SHA manifest, a separately written ZIP copy and an expanded independent restore with every file read back. Up to3000source files/160MiB uncompressed/160MiB archive/512MiB total output. CPU14, C50GiB/G75GiB plus full new allocation, finite time and no overwrite are enforced. No SSH/model/capture/recording/galleries are used.

PowerShell:
    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B build_runtime_delivery_v1.py --private PRIVATE --sources SOURCE_DIRECTORY --docs COMPLETION_DIRECTORY --install CURRENT_INSTALL --output NEW_KIT_DIRECTORY --scope PACKAGE_SCOPE.json

Command Prompt / Anaconda Prompt:
    python -B build_runtime_delivery_v1.py --private PRIVATE --sources SOURCE_DIRECTORY --docs COMPLETION_DIRECTORY --install CURRENT_INSTALL --output NEW_KIT_DIRECTORY --scope PACKAGE_SCOPE.json

Replace uppercase arguments with the exact absolute paths in PATHS_AND_BACKUPS.md. Output must not exist. A failed output is retained, never reused. Runtime policies/old roots are never replayed as new installations: use Refresh-JustPeachy.ps1 on the prepared workstation to preserve the old batch and issue a newly measured higher version. To recover the source kit, extract into a NEW review directory, verify DEPLOYMENT_MANIFEST.json member sizes/SHA256, then use the documented fresh-version workflow; never overwrite a consumed native root.

Historical sources inside operator-sources are dependencies and provenance. Only the current mode table/entry commands describe user-supported choices; old research dispatchers are not user launchers. Keep this kit private: prepared paths/owner history are not the small ChatGPT handoff. Recordings, personal gallery vectors and SSH key material are excluded.

