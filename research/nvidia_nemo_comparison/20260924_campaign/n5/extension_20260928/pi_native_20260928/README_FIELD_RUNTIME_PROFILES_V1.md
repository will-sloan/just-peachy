# Runtime ReDimNet/TitaNet profile binding V1

Purpose: F06/F07/F12. Reuse the existing application backend routes and local TitaNet ONNX export, with explicit ReDimNet or TitaNet selection, correct retained D1 mode libraries, model-specific namespaces and one prepared desktop entry per supported combination. No NeMo/PyTorch installation, model download, export, training or enrollment is needed.

Status: prepared host configuration API. It does not install a release, construct an encoder, start a microphone or certify Pi availability. The delivery controller, storage paths, profile capsules and installed launch-profile entry must consume these bindings before shortcuts are deployed. Saved Streaming/Chunk52 profiles remain saved-input profiles; this code does not qualify them for microphone input. Anonymous D1 uses the existing native-slot path; its E0 resident identifier does not imply an embedding inference.

Inputs: the retained installed config/backends.json; exact D1_MODE_CATALOG_V1.json; prior n2_runtime document; existing local titanet_manifest.json, titanet_embedding.onnx and titanet_frontend.npz. The TitaNet verifier checks full source/export/frontend hashes and unchanged real-file identities using16KiB reads and a caller-provided resource/deadline guard. Outputs: a mode-specific backend composition/digest, runtime binding, separated embedding namespace, local asset receipt and prepared .desktop bytes.

API:
- select(profile): exact configured route; unknown profiles fail without fallback.
- backend_manifest(catalog_bytes,profile): derive the selected existing composition, retain Sherpa ASR and both model/export pins. Native availability remains NOT_YET_QUALIFIED.
- verify_titanet(directory,deadline=time.monotonic()+60,guard=resource_guard): read/hash existing files only, no inference.
- runtime_document(existing,profile,d1_catalog_raw=...,native_titanet_manifest=...,titanet_manifest_raw=...): returns a proposed immutable binding. E0 forbids an E1 dependency; E1 requires the exact previous namespace/export. All D1 library paths/hashes come from the retained catalogue, not merely a changed mode label.
- desktop_entry(profile,release_id,label): returns content for the future installed release's bin/launch-profile. That entry must verify policy/profile pins and open idle. No shortcut is installed by this module.

Profile IDs: baseline, baseline-titanet, d1-delayed, d1-delayed-titanet, d1-streaming-saved, d1-streaming-titanet-saved, d1-chunk52-saved, d1-chunk52-titanet-saved, d1-anonymous, baseline-anonymous. Non-spatial user naming modes remain a separate UI choice; unsupported spatial/hardware paths must remain explicit. Native functionality of each selected composition still needs focused acceptance. This table is not a new research sweep.

PowerShell syntax-only review from this directory:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; compile(Path('field_runtime_profiles_v1.py').read_bytes(),'field_runtime_profiles_v1.py','exec')"
```

CMD / Anaconda Prompt:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; compile(Path('field_runtime_profiles_v1.py').read_bytes(),'field_runtime_profiles_v1.py','exec')"
```

These commands compile only. The selected finite host reviewer must register its owner before source reads, obey the current allocation and back up/independently restore source before running the API. There is no admitted bare deployment/recording CLI here; final installer/run commands are F17/F23. Do not point desktop entries at old research dispatchers or a root lacking the installed launcher. Model weights and private galleries stay outside Git.
