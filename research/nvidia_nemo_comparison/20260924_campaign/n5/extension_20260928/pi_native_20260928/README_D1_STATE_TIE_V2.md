# Cache-compression export: boolean-union repair

V1 reconstructed the observed finite tie and verified failure atomicity, but ORT rejected the exported graph's boolean Add. Original NeMo uses an in-place addition on two boolean masks, which has union semantics in PyTorch. Fresh V2 changes exactly one exported Add whose inputs are both comparison-produced booleans to Or; requires that exact structural pattern and full ONNX checker. Original installed sources, V1 graph/failure/admission and all fixtures remain unchanged. The repair does not decide top-k ties or change any scores/indices. Original versus explicit silence-embedding PyTorch results must remain exact; original-versus-ORT1e-5 gate stays unchanged.

Purpose/inputs/outputs follow [V1 diagnostic](README_D1_STATE_TIE_V1.md). V2 additionally saves original PyTorch arrays before ORT loading, preserving them on failure, and writes BOOLEAN_UNION_REPAIR.json. Private write-once root d1-onnx-state-tie-v2. Same target-inclusive16MiB reservation, CPU4/14total2/coordinator14,one thread,GPUoff,hard6GiB host jobcommit,600s and existing guards. No model inference, capture, playback or native Pi acceptance.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_state_tie_launch_v2.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V48.json'
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_state_tie_launch_v2.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V48.json
```
Independent review still determines whether this observed tie matches. Export success alone cannot qualify cache-history equivalence or a complete backend.
