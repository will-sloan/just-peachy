# Explicit Nemotron diarizer modes V1

Purpose: make three already reviewed D1 component recipes selectable by exact name, geometry and runtime identity. The September30 user priority is diarizer modes and speed methods; Nemotron ASR is secondary. These files do not load an ASR model. Existing component receipts remain immutable, and the new selector does not confer full application or real-world accuracy acceptance.

| Mode | Chunk/right/left/FIFO/cache/refresh | Runtime | Retained unpaced work/audio |
| --- | --- | --- | --- |
| delayed | 264/1/1/0/264/188, v3-offline | A76, executable-graph LRU1, 2MiB metadata arena | 0.405 |
| streaming | 13/1/0/80/264/40, v3-streaming | A76, executable-graph LRU8 | 3.634 |
| chunk52 | 52/1/0/80/264/40, v3-streaming | A76, executable-graph LRU8, experimental recipe | 1.085 |

Frames in this table are80ms coarse frames; output probabilities use10ms frames. These are saved44.695s component observations with the original rc5 app concurrent. They are not fresh benchmarks or accuracy measurements. The delayed mode waits for roughly21.3s of input in the retained100ms-push test; related paced delayed checks first published around25.5s. Unpaced first-output wall time is not live latency. Streaming/chunk52 are not demonstrated sustained real-time modes on this device. Changing geometry can change diarization behavior, so cross-geometry probability equality is not a valid acceptance gate. Same-geometry generic/A76 and repeat gates remain1e-5.

The A76 kernel's same-geometry reductions in compute time were measured separately. The LRU reduces executable graph retention, not speaker/FIFO history; smaller LRU is not itself a guaranteed speedup. The metadata arena and1MiB stack changes are resource methods, not speaker-quality improvements. ONNX whole-waveform, applied ASR/VAD skipping and parallel diarizer pools remain explicitly unavailable here. The34-method catalogue retains its own evidence scopes.

## Inputs and outputs

D1_MODE_CATALOG_V1.json pins twelve retained CONFIG/INPUTS/RESULT/REVIEW receipts across the three recipes, all selected runtime-library aliases, the Q8 model and exact Python adapter. d1_modes_v1.py verifies the catalog hash and returns a detached selection with no default or silent fallback. Its CLI prints JSON and never starts inference. `--verify-assets` streams hashes from the retained Pi run directory, reusing inode identities for aliases; it does not copy weights or load the runtime.

The C-wrapper hash is identical across these builds, but the delayed LRU1/metadata2 main runtime hash differs from the LRU8 runtime. The selector binds the full library set, including the main library and CPU kernel. It rejects mismatched/omitted files, wrong presets, boolean integer fields, unavailable modes and an already mapped runtime. Runtime-path checks additionally reject dependencies loaded from another directory. A mode change requires a fresh process and independent session; never reset at ASR/VAD endpoints or concatenate discontinuous audio.

`guarded_factory(mode_id, campaign_root)` is a PREPARED integration API. It verifies Pi/Linux, CPU2/3, AS<=768MiB, stack<=1MiB and one-thread environment, hashes selected assets, imports the exact adapter, checks actual C-ABI arguments before native model creation, and inspects mapped runtime paths before/after creation. It retains the adapter's push/finish/reset/close interface. The caller must still own a fresh admitted research lease and provide systemd CPU200%/Tasks64/time/output/ownership/closure guards. This API does not acquire authorization, start a process, or capture audio. It has not been exercised with a native model through this new factory yet. No launcher for uncontrolled inference is provided.

check_d1_modes_v1.py checks only the changed pure selection boundaries on CPU14, under a fresh2MiB static-review allowance. It rechecks prior field workers/helper identities and current census/closure before publication. Thirteen checks cover three exact independent geometry expectations with caller-mutation isolation, nine expected rejections and one declared mapped-path list. The path lists and altered inventory dictionaries are fixtures, not actual dynamic loader or corruption tests. The actual guarded factory and Pi asset rehash are not invoked. Existing source/model/geometry/timer/host protocols are not rerun.

Outputs are fresh private d1-mode-selection-v1-evidence/host metadata, failure and closure groups, plus verified-mode-backup. Exact rejected test inputs are declared in the pinned test source. The finite host writer is reused; no new lifetime, whole-host quota or full72MiB backup qualification. Existing Pi app/config/releases and all model assets remain unchanged. At later wakes use fresh census/closure and fresh evidence destinations; never retry an existing failed destination.

## PowerShell

Use the existing interpreter without installs or downloads. Listing a mode is safe and starts no model:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B d1_modes_v1.py --mode delayed
& $py -B d1_modes_v1.py --mode streaming
& $py -B d1_modes_v1.py --mode chunk52
& $py -B check_d1_modes_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V178.json' --closure-version 180 --destination 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\d1-mode-selection-v1-evidence'
```

## Command Prompt / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B d1_modes_v1.py --mode delayed
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_d1_modes_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V178.json" --closure-version 180 --destination "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\d1-mode-selection-v1-evidence"
```

For an admitted future Pi asset-only check, stage only this selector/catalog/README in a fresh bounded directory and invoke the existing Pi Python with `-B d1_modes_v1.py --mode delayed --verify-assets /home/peachyprototype/JustPeachy/research/nemotron-20260928`. That command reads retained assets and prints a manifest; it is not a native model test. Fresh ownership, storage and resource admission still precede dispatch. Native factory passage and selectable GUI integration are the next changed checks.
