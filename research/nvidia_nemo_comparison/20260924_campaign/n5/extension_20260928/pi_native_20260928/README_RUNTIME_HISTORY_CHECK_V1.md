# Changed history consumer check

Purpose: one focused check of the new read-only history reader against existing closed private Audio Off and Processed recordings. It reuses actual installed decoder/SessionStore methods, asserts a nonempty caption result, and rejects changed pins and a writer. No capture, model, GUI or new audio test.

Inputs: --private private native evidence root, --local campaign local root, --scope fresh bounded host scope, --output fresh directory under that scope. Outputs: early CPU14 owner, compact owner preread and RESULT.json. Never reuse output directories or rerun a healthy check for a version number.

PowerShell, from this source directory:

    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B check_runtime_history_v1.py --private PRIVATE_ROOT --local LOCAL_ROOT --scope HOST_SCOPE.json --output NEW_OUTPUT

CMD / Anaconda Prompt in the existing environment:

    python -B check_runtime_history_v1.py --private PRIVATE_ROOT --local LOCAL_ROOT --scope HOST_SCOPE.json --output NEW_OUTPUT

Replace uppercase placeholders with the established absolute paths. Source backup/independent restore must be closed before this check runs.
