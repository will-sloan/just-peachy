# TitaNet memory binding v1

Purpose: close F06/F12 integrated speech memory failure using the existing pinned NeMo TitaNet model and frontend. Disable only ONNX Runtime CPU memory arena and memory-pattern caching. Keep one thread, CPU, 768 MiB hard address-space limit and all existing storage/lifetime guards.

Input: exact saved-modes3 COMMON_BUNDLE bytes (SHA b0422b395e4dedb01342c514a9d1ca23e5bb681c857dc125a97097aff4102b2a). The installed adapter must retain SHA b765ec7cfd725a39f8d1542e76eeb71fcdc083989b421269fea119606afc6caa and its original constructor origin. Output: new complete 64-code-member capsule and derivation review. The installed adapter file, model, preprocessing, embedding calculation and gallery namespace remain unchanged. Runtime derives its constructor in memory, verifies actual session options and records successful embedding count in the existing RESULT metadata. This is not an accuracy claim.

API: `updated_bytes, review = field_runtime_titanet_memory_v1.derive(original_bytes)`. Use the versioned installer after exact backup/readback and fresh native preflight; do not overwrite any consumed capsule/root. No standalone model launch is provided.

PowerShell from the native reports directory:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); import ast,pathlib; ast.parse(pathlib.Path('field_runtime_titanet_memory_v1.py').read_text()); print('syntax only')"
```
CMD or Anaconda Prompt from the same directory:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import ast,pathlib; ast.parse(pathlib.Path('field_runtime_titanet_memory_v1.py').read_text()); print('syntax only')"
```
Compilation is not a native runtime pass. Focused host derivation checks and the next fresh integrated speech operation establish the result; failed previous candidates remain preserved.
