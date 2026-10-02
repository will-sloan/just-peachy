# Private raw-pair verification
Purpose: F14 verifies the completed actual native route/capture, strict packing markers and independent PC WAV readbacks. No SSH, device, capture, model or playback is performed.
Inputs: completed probe directory, SOURCE_CLOSED receipt binding field_runtime_raw_decoder_v1.py, fresh host scope and absent PRIVATE output directory.
Outputs: three synthetic alignment checks plus one corruption reject; six-channel PCM32 WAV, physical MIC0..3 PCM32 WAV, auto-ASR PCM32 WAV and processed auto-select PCM32 WAV, each with independent restore copy, complete readback and SHA256 receipt. A decoder failure preserves the original packed bytes and writes DECODE_FAILURE.
Native/host capture closures, exact mux values and restored route are mandatory. All outputs plus probe stay within the existing2MiB probe admission. It establishes firmware16kHz pre-gain raw taps, not48kHz ADC bit-perfectness, acoustic delay calibration, recognition quality or final model integration.
PowerShell:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./verify_runtime_raw_pair_v1.py --probe '<closed-private-probe>' --source-closed '<SOURCE_CLOSED_V139.json>' --scope '<fresh-scope.json>' --output '<absent-private-output>'
```
CMD / Anaconda Prompt:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B verify_runtime_raw_pair_v1.py --probe "<closed-private-probe>" --source-closed "<SOURCE_CLOSED_V139.json>" --scope "<fresh-scope.json>" --output "<absent-private-output>"
```
Use only the existing Python environment. Keep private PCM/WAV out of Git and handoff documentation ZIP. Never rerun the healthy check into a completed directory.
