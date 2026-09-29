# Exact-feature graph/state isolation

Purpose: after waveformV2 fails final cache1e-5, feed preserved original PyTorch features into the same candidate graph/state. Compare with preserved original model full/tail probabilities and finalstate to isolate frontend conversion from graph/state numerical differences. No checkpoint load/extraction, new graph, capture or accuracy score. This diagnostic intentionally collects both tail/full/repeat discrepancies; recording them is not passing a numerical gate. The1e-5 probability/state gate stays unchanged.

Inputs: unchanged runtimeV1, existing four-output/smallcompression graphs and frontend coefficientfiles; actual learned silence and original full/tail references fromwaveformV2; original frontend fixturesfull/tail with identical audio bytes. Inputs and exact source hashes are bound before execution. Outputs: fresh private d1-onnx-feature-isolation-v1 arrays, discrepancy flags, timing, source/mapping and lifecycle receipts. The feature-only path uses candidate bounded `_append/_pump` directly; it is a diagnostic, not the public waveform input path or GUI.

WINDOW_V5 fresh measured32MiBoutput/600s/hard6GiBhostjob,CPU4/14one modelthread/coordinator14,GPUoff,originalowner/targetcensus/drivefloors retained. Model-free frontend fixtures are reused unchanged; this numerical graph/state isolation adds new evidence. No assertion is removed from the actual waveform candidate. Even a diagnostic exit0 does not mark violations accepted.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_feature_isolation_launch_v1.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V55.json
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_feature_isolation_launch_v1.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V55.json
```
Fixed fresh root refuses overwrite. Numericalworker --root and launcher --guard are supervision-only. Review all original-array differences, sourcebindings, actualjob/owners and natural closure before drawing the isolation conclusion.
