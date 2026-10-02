# README_FIELD_RUNTIME_MANAGER_V9

Purpose: Same offline manager8 and all model/storage/capture guards. Handles Close during initial fullscreen settling by checking closed after each Tk update and ending the run loop after Close; journal closes in finally. This fixes the observed completed EXIT followed by destroyed-window failure and automatic rollback. No model algorithm changed.

Inputs: installed canonical root and exact policy hash (manager), or release id/policy/rollback pins (renderer). Outputs: finite idle manager and immutable profile/service bytes. Installer applies these after source backup; never invoke a bare manager outside its required service envelope.

PowerShell:

    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B field_runtime_manager_v9.py --help

CMD / Anaconda Prompt with existing environment:

    python -B field_runtime_manager_v9.py --help

Renderer API: render(release_id, policy_sha256, rollback_sha256). No native action from rendering. Actual startup validation remains required. Use README_RUNTIME_INSTALL_V21.md for full installer argument conventions; later installer version must select these exact backed bytes.
