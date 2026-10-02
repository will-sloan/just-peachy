# Runtime archive metadata encoding
Purpose: F08/F15 fix archive control overflow caused by pretty-printed JSON in the complete runtime capsule. The derivation preserves every JSON field/value and changes only insignificant whitespace. Initial32768B, runtime24576B, complete65536B, pending slots, finite-number checks and all physical storage bounds are unchanged. The old source and failed runtime remain immutable.

Inputs: exact barrier-corrected COMMON_BUNDLE.json from candidate4; output: a new bytes capsule and derivation receipt. It is an API called by the versioned installer before source backup/native dispatch, not a standalone Pi launch command. The same member filename is retained to preserve the verified dependency graph; the new capsule pins its changed digest.

PowerShell:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\check_runtime_archive_encoding_v1.py --private PRIVATE_ROOT --output FRESH_OUTPUT
~~~
Command Prompt / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B check_runtime_archive_encoding_v1.py --private PRIVATE_ROOT --output FRESH_OUTPUT
~~~
The focused host check reads existing actual archived metadata and validates exact JSON round trips and unchanged size/finite rejection. It creates no model, microphone, installed app or native archive. Native runtime acceptance still requires a fresh complete recording.
