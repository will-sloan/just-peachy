# Bounded raw and processed capture qualification
Purpose: close F14's physical route uncertainty on the actual I2C/I2S Pi.
Inputs: private/local roots, exact prior closure, completed raw-route inspection, candidate installation, fresh 600-second scope and absent output directory.
Outputs: full raw process/failure evidence, independently verified route backup/restore copies, measured resource policy, capture/helper identities and closure, and two identical private packed PCM copies. Twelve seconds of input-only capture runs; about0.2seconds after verified routing is retained. Strict marker decoding is still required before claiming raw support.
No model, playback, reset, enrollment, downloads or Pi payload file writes. Existing vendor packed_recorder is not run, because its I2C path resets firmware and opens playback.
The six firmware16kHz channels are auto-ASR, auto-select processed, MIC0, MIC1, MIC2, MIC3. The physical microphones use pre-gain category1. Packing carries them over48kHz stereo S32LE with one marker bit; this is not a claim of48kHz raw ADC audio.
Safety: early helper and arecord identities;128MiB AS/1MiB stacks/FSIZE0; current manager shared200%CPU/2-3/64tasks;180second unit/150second alarm/165second host/finite12second arecord. Exact route GET comparison and independent PC restoration readback precede route writes. Routes restore while input clock remains active, then capture and leases close. New2MiB independent host reservation uses fresh full host census and native target check. Failed/deleted/unused allocations never provide credits.
This is a single-attempt qualification utility, not a user launcher. Completed output and unit are consumed. Back up source and independently restore/read it before running.

PowerShell (from this source directory):
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./qualify_runtime_raw_pair_v1.py --private '<private-root>' --local '<local-root>' --prior-closure '<prior.json>' --previous-inspection '<readonly-raw-output>' --candidate-install '<candidate-install>' --scope '<fresh-scope.json>' --output '<absent-private-output>'
```
CMD and Anaconda Prompt (existing environment; no installation):
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B qualify_runtime_raw_pair_v1.py --private "<private-root>" --local "<local-root>" --prior-closure "<prior.json>" --previous-inspection "<readonly-raw-output>" --candidate-install "<candidate-install>" --scope "<fresh-scope.json>" --output "<absent-private-output>"
```
Reference: [XMOS I2S packed signal capture](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/programming_guide/04_testing_the_software.html).
