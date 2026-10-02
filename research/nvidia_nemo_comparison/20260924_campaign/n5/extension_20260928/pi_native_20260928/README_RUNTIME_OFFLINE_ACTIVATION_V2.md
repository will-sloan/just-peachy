# README_RUNTIME_OFFLINE_ACTIVATION_V2

Purpose: Render exact manager9 offline launch assets. Anonymous shortcuts explicitly say no embedding instead of including ReDimNet in the label. Same ten profiles, original transient-service and rollback/resource/socket guards.

Inputs: installed canonical root and exact policy hash (manager), or release id/policy/rollback pins (renderer). Outputs: finite idle manager and immutable profile/service bytes. Installer applies these after source backup; never invoke a bare manager outside its required service envelope.

PowerShell:

    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B prepare_runtime_activation_v6.py --help

CMD / Anaconda Prompt with existing environment:

    python -B prepare_runtime_activation_v6.py --help

Renderer API: render(release_id, policy_sha256, rollback_sha256). No native action from rendering. Actual startup validation remains required. Use README_RUNTIME_INSTALL_V21.md for full installer argument conventions; later installer version must select these exact backed bytes.
