# Candidate14 unused-broker preservation
Purpose: close the faulted manager through its normal Close control, verify exact death and its recovery-required EXIT, run the existing pinned rollback, and preserve all five trees. This does not certify the unused fourth slot as a recording. All four gates must be closed; slots1–3 need their existing paired PC copies; slot4 must have no child OWNER and only RESERVED/STARTED records. No ledger is repaired or reused.
Inputs: prior closure, actual inspection and candidate14 install, fresh cumulative host scope, absent private output. Outputs: raw diagnostics, ownership/closure, complete PC trees and BACKUP with recording_success=false. Old receipts remain immutable.

Run from this README directory in PowerShell:

    & 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B preserve_runtime_unstarted_v1.py --help

Command Prompt / Anaconda Prompt (activate the existing environment):

    python -B preserve_runtime_unstarted_v1.py --help
    python -B preserve_runtime_unstarted_v1.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection INSPECTION --candidate-install CANDIDATE14 --scope FRESH_SCOPE.json --output NEW_OUTPUT

This is an exact candidate14 recovery tool, not a general launcher. Requires fresh all-owner precheck and original disk/resource bounds. No capture, model, firmware, personal-data edit or failed-root retry.
