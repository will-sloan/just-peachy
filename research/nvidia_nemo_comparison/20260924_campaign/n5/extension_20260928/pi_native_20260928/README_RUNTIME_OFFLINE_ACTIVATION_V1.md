# Offline socket enforcement for the local runtime
Purpose: F19 runs the installed manager, broker and model child while the kernel rejects IPv4/IPv6 socket creation. The launcher and broker service set RestrictAddressFamilies=AF_UNIX AF_NETLINK, NoNewPrivileges=yes and native syscall architecture. Local GUI/D-Bus/kernel device communication remains available. SSH is unaffected. This is software socket denial, not a physically unplugged test or a general security sandbox.
Inputs: exact candidate14 common capsule, unchanged local assets and explicit fresh release admission. Outputs: pinned derived64-member capsule, manager8 and renderer5; runtime proof requires actual Seccomp2/NoNewPrivs1, no inherited nonlocal sockets, successful Unix socket creation, and denied IPv4TCP/IPv6UDP socket creation. No connection or packet is sent. A missing restriction blocks startup.
Model, audio, storage, ownership, consent, deadlines and independent backup allocations are unchanged. No downloads. Guard proof is stored in existing broker/worker receipts and manager stdout, without adding a file slot. Native execution remains unqualified until a new admitted release runs.
Python API:
~~~python
from field_runtime_offline_v1 import derive
new_capsule, review = derive(exact_common_capsule_bytes)
from prepare_runtime_activation_v5 import render
launch_files = render(fresh_release_id, actual_policy_sha256, actual_rollback_sha256)
~~~
PowerShell:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\install_field_runtime_v18.py --local LOCAL_ROOT --private PRIVATE_ROOT --assets VERIFIED_ASSET_RESTORE --prior-closure PRIOR_BINDING --inspection FRESH_INSPECTION --inputs PREPARED_INPUTS --scope CURRENT_SCOPE --output NEW_INSTALL --version 15
~~~
CMD / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B install_field_runtime_v18.py --local LOCAL_ROOT --private PRIVATE_ROOT --assets VERIFIED_ASSET_RESTORE --prior-closure PRIOR_BINDING --inspection FRESH_INSPECTION --inputs PREPARED_INPUTS --scope CURRENT_SCOPE --output NEW_INSTALL --version 15
~~~
The version18 installer is pending preparation; do not dispatch until its source and all changed files are backed and independently restored. The Pi command is the installed version's bin/launch-profile --profile PROFILE, opening idle. Source backup and a fresh full allocation are mandatory.
Reference: systemd primary documentation https://raw.githubusercontent.com/systemd/systemd/v257/man/systemd.exec.xml (RestrictAddressFamilies). Its socket-call restriction does not itself block arbitrary delegated services or io_uring; this evidence describes the actual application process tree and normal socket API, not adversarial isolation.
