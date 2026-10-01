# Read-only reconnect inspection V2

Current entry: inspect_user_reconnect_v2.py. Purpose, inputs, outputs, bounds,
PowerShell, Command Prompt and Anaconda instructions are in
[README_USER_RECONNECT_V1.md](README_USER_RECONNECT_V1.md). Substitute the script
suffix v2 and fresh output user-reconnect-20261001-v4 in all commands.

V1 observed a new boot but stopped at a busy lease before returning the census.
V2 reports each lease as free/busy with inode and reads kernel lock ownership;
it does not release another process's lock or stop an app. It checks the exact
earlier inspector identity and retains all original resource and no-write bounds.
The hard completion guard is now16:14:58Z under DEADLINE_AUTHORITY_V2.json.
The V1 failed output remains immutable. This read-only changed inspection is
not an activation, capture attempt, complete lifecycle admission or offline proof.
