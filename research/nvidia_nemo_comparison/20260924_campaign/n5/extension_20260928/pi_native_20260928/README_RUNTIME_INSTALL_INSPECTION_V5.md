# Fresh baseline and private gallery metadata inspection
Purpose: F06/F12/F15 diagnose the observed ReDimNet archive metadata overflow and provide the fresh baseline needed for the corrected install. Reuses inspector4 all owner/lease/capture/boot/config/display/device/resource checks, adding exact already-preserved candidate7 nested owners and a private hash-verified readback of at most64KiB personal gallery metadata. No model constructor, recording, enrollment or writes on the Pi. Metadata stays private.

Inputs: existing private/local roots, complete prior owner binding, last native inspection/preservation, fresh scope. Output: early native owner, bounded raw diagnostics, exact natural process closure and fresh RESULT including private gallery_metadata. CPU14 host; existing native CPU3/128MiB/FSIZE0 guards retained. A successful inspection does not certify a backend.

PowerShell:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\inspect_runtime_install_v5.py --private PRIVATE_ROOT --local LOCAL_ROOT --prior-closure PRIOR.json --previous-inspection LAST_DIR --scope FRESH_SCOPE.json --output FRESH_OUTPUT
~~~
CMD / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B inspect_runtime_install_v5.py --private PRIVATE_ROOT --local LOCAL_ROOT --prior-closure PRIOR.json --previous-inspection LAST_DIR --scope FRESH_SCOPE.json --output FRESH_OUTPUT
~~~
