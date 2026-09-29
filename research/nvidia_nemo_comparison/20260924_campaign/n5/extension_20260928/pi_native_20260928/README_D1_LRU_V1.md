# D1 executable graph cache:48 to8 entries

Purpose: investigate the native streaming recipe's EOF allocation failure without increasing the768MiB virtual-address cap or shortening speaker history. Sortformer explicitly retained up to48 executable graphs, and the failed run accumulated42. This derivative changes only its `set_run_cache_capacity(48)` to8, using the runtime's existing LRU eviction, placement-generation checks and compute mutex. Model weights, speaker/FIFO caches, recipe, frontend and arithmetic stay unchanged. Eviction may add graph reconstruction cost, which must be measured.

`build_d1_lru_v1.py` rehashes the preserved source/object bundle, compiles only sortformer_model.cpp on CM5, and relinks27 retained ASR objects plus that new object. It reuses the qualified2048-node/8MiB metadata runtime archive and unchanged common/SentencePiece/ggml libraries. This is a D1-only partial rebuild; it does not qualify A2 or a new integrated release. It writes a fresh build directory and never edits retained inputs.

Inputs: pinned source revision97a15afa, source Sortformer SHA831d819e0a3986b7b6007987a67b4ccc5f2895d6d68247ca138ed4d9c3c3d2c9, original bundle manifest, metadata-native-v1 runtime.a and library, fresh host census/target admission. Outputs: patched source, new object/shared library, compiler/linker logs, source/output hashes, exact build OWNER and BUILD_RESULT. A successful build is not inference qualification. Keep all failures.

`dispatch_d1_lru_build_v1.py` applies the existing extension guard, fresh exact host/native owner and storage/RAM checks, strict SSH verification and a new stage receipt. It stages code/docs and starts one bounded unit: CPUs2/3,totalCPUquota200%,Tasks64,600seconds,hard768MiB RLIMIT_AS,>=850MiB available RAM,>=5GiB disk,16MiB new-output reservation within the combined1GiB allowance. Compilation is sequential; no parallel build, downloads, capture, playback or OS/current-app changes. The pending1GiB application trial is not authorized by this path.

## PowerShell

From this report folder, with a fresh comprehensive census:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' dispatch_d1_lru_build_v1.py --run-id d1-lru-build-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V7.json'
```

## CMD / Anaconda Prompt

Use `cd /d` to this folder, then the explicit existing interpreter:

```cmd
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" dispatch_d1_lru_build_v1.py --run-id d1-lru-build-v1 --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V7.json"
```

No activation/install is needed. Existing IDs refuse rerun. Following exact owner closure and build review, bind the new library into a fresh component derivative for full source/repeat/reset/EOF and unchanged1e-5 same-geometry generic/A76 parity. The prior48-entry streaming run has no complete reference because it aborted; do not claim full old/new-cache numerical equivalence without evidence. Scope any eventual pass to the actual tested geometry and input. Keep speaker quality and real-life validation separate.
