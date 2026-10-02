# Actual raw-route capability queries
Purpose: F14. Read the actual I2C XMOS output-packing and six packed-tap selectors while the runtime is idle and hardware/research leases are held. No route write, firmware reset, USB assumption, capture, playback or model action. Stop on the first host-tool failure or inactive-audio-loop/servicer error; no query retries.
Inputs: existing --local, --private, --prior-closure, --previous-inspection, --candidate-install, --scope and fresh --output. Output: actual tool hash/protocol/endpoint, bounded raw replies and exact helper closure. Successful GETs alone do not qualify physical raw or paired recording.
PowerShell from native report directory:
    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B inspect_runtime_raw_route_v1.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection INSPECTION --candidate-install INSTALL --scope SCOPE.json --output NEW_OUTPUT
CMD / Anaconda Prompt in existing environment:
    python -B inspect_runtime_raw_route_v1.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection INSPECTION --candidate-install INSTALL --scope SCOPE.json --output NEW_OUTPUT
Back up source and independently restore before use. Do not run the vendor packed_recorder unchanged: its I2C path resets firmware and its no-file mode opens playback. Those actions are not authorized by this capability read.
