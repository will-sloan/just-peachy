# Focused saved-source composition check

Purpose: verify the changed capsule and the prepared wrapper around the actual installed FileSource, without importing models or contacting the Pi. Inputs are the candidate8 COMMON_BUNDLE.json, preserved installed-v12 tree, current cumulative HOST_SCOPE, and a fresh output directory beneath that scope. Outputs are an early CPU14 host owner, a small synthetic PCM16 WAV, and a bounded RESULT.json. Test pacing is synthetic; this does not prove native GUI, model execution or accuracy.

The check verifies original endpoint bytes,64-member capsule bounds, actual320-sample read/Stop/closed-file receipt, idempotent Stop, and nine new rejection boundaries: capsule/source/contract pins, mode, offset, sample rate, Streaming duration, input drift before Start and input drift during processing. No old healthy native test is rerun.

Run once after exact source backup and independent restore, inside a fresh600s host scope. Do not reuse a consumed output.

PowerShell:

~~~powershell
$python='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $python -B .\check_runtime_saved_modes_v1.py --common '<candidate8 COMMON_BUNDLE.json>' --installed '<preserved installed-v12 directory>' --scope '<current HOST_SCOPE.json>' --output '<new private check directory>'
~~~

CMD or Anaconda Prompt:

~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_runtime_saved_modes_v1.py --common "<candidate8 COMMON_BUNDLE.json>" --installed "<preserved installed-v12 directory>" --scope "<current HOST_SCOPE.json>" --output "<new private check directory>"
~~~

Use the named environment because it already contains psutil and soundfile. Nothing is downloaded. All fixture files remain private, including failures. The selected composition API is documented in README_RUNTIME_SAVED_MODES_V2.md.

