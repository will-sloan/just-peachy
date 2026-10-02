# Final idle startup and early Close check
Purpose: F03/F07/F09/F19. On the fresh candidate with four unused recording slots, execute all ten pinned shortcuts against the active manager and require duplicate exclusion. Normal Close, TitaNet shortcut launch followed promptly by normal Close, then actual autostart command restart. Require exact death/successful EXIT, idle480x800 selected profiles, unchanged old pins and four still-unused recording slots.
Uses launch02/03, leaves manager active/capture off. No recording/model/coldboot/physical-unplug claim. Manager9 fixes the observed early-Close window-settling error; only the changed startup lifecycle is exercised.
Inputs: installed candidate, prior closed-owner binding, previous inspection, fresh600s scope and absent output. Outputs: bounded raw phase evidence, exact utility closure and restart facts.
PowerShell from native report directory:
    & 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B control_runtime_restart_v4.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection INSPECTION --candidate-install INSTALL --scope SCOPE.json --output NEW_OUTPUT
CMD / Anaconda Prompt:
    python -B control_runtime_restart_v4.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection INSPECTION --candidate-install INSTALL --scope SCOPE.json --output NEW_OUTPUT
Back up source and verify independent restore before use. Do not reuse an output or repeat a failed mutation.
