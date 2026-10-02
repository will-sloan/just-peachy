# Cancel a broker before recording
Purpose: close F05/F09's observed unused-broker lifecycle defect through actual manager New and broker Close controls. Verifies distinct CANCELLED_BEFORE_RECORDING receipt, no child/source/model creation, capture off, all three broker owners dead and complete independent local backup. Consumes one full original slot; no released-credit or recording-success claim. Earlier recordings and copies are fully rehashed before/after.
Inputs: current candidate install, fresh scope/prior-owner inspection, one installed microphone profile and next unused slot. Outputs: actual UI events, early identity/closure, cancellation/CLOSED/BACKUP facts. Requires separate PC offload. No microphone, playback, enrollment or network change.

PowerShell from this source directory:

    & 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B control_runtime_cancellation_v1.py --help

CMD / Anaconda Prompt with existing environment:

    python -B control_runtime_cancellation_v1.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection INSPECTION --candidate-install INSTALL --scope SCOPE.json --output NEW_OUTPUT --profile baseline-anonymous --slot recording-04

Native115s bound and original admission/backup/resource guards retained. Do not use on a consumed slot. Back up this source and independently restore before use.
