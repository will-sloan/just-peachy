# Closing before a recording starts
Purpose: derive three hash-pinned manager modules so a normally closed, completely unused broker is independently copied and consumes its reserved slot without inventing a child recording. A distinct CLOSED_UNUSED_BROKER health status requires all child slots UNUSED, an empty recordings directory, exactly three dead broker owners, successful gate and broker closure, capture off and free leases. Real recordings retain all existing checks. The manager CLOSED fact explicitly records recording_created=false and CANCELLED_BEFORE_RECORDING. No failed, deleted or unused storage credit; full local/PC reservations remain.

Inputs: dict of the 16 actual manager module byte strings after optional-health derivation. Output: same keys, three changed hash-pinned sources; no native action or file writes in derive(). Installer20 applies it. Native cancellation check remains required.
PowerShell, from this directory:

    & 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "from field_runtime_unused_broker_v1 import PINS; print(PINS)"

Command Prompt / Anaconda Prompt after activating the existing environment:

    python -B -c "from field_runtime_unused_broker_v1 import derive; print(derive.__doc__)"

API: updated = derive(original_module_bytes). Use the installer with fresh measured admission; never patch an existing capsule or journal.
