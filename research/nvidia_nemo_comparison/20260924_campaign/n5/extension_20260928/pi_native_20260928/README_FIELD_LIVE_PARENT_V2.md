# Fresh archive-parent live entry

Purpose: create the single permitted conversation/epochs directory before the
actual EpochArchive constructor. V113 latched pathlib's intermediate missing
parent error. This version preserves the physical guard's failure latch, exact
path/cardinality/byte limits and all installed Field backend/mode/asset checks.
The failed v1 root, admission and sources are immutable.

Selected files: field_live_controller_v5.py, field_live_entry_v2.py,
field_live_gate_v5.py, stage_field_live_entry_v4.py,
dispatch_field_live_entry_v5.py, field_live_export_v3.py and
mirror_field_live_entry_v3.py. The six routing derivatives select the fresh
field-live-entry-v3 root and LIVE_RESOURCE_POLICY_V3.json. The controller alone
adds a first-only empty epochs parent before delegating to the real archive.
The source, D1, native writers and physical guard retain their admitted code.

Inputs: a newly issued private PLAN.json with exact source/config/asset pins,
fresh owner/resource census, explicit quiet authority and measured full
164,406,360-byte reservation. Preserve old WINDOW_V5. Never reuse a closed plan
or root. Review and verify separate backup/restore copies before dispatch.
Native gate and stager run only through the pinned coordinator. Worker limits
remain CPU2,3/shared200%, Tasks64, 768MiB address space, 1MiB stack,
285s runtime/30s Stop. The gate, source child, SSH mirror and host coordinator
retain their own shorter limits and hard-deadline checks.

PowerShell after admission:
    Set-Location 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
    & 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B dispatch_field_live_entry_v5.py --plan '<private-absolute-PLAN.json>' --owner-receipt '<private-fresh-OWNER.json>'

CMD or Anaconda Prompt:
    cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
    "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B dispatch_field_live_entry_v5.py --plan "<private-absolute-PLAN.json>" --owner-receipt "<private-fresh-OWNER.json>"

Outputs: bounded host owner/admission/raw/closure records and private target
source/model/archive/UI receipts, followed by exact closed-tree SSH backup.
A failed run remains failed and retained. Quiet execution proves only observed
function/resources, never new WER/DER or true silence. Python interception is
not a kernel filesystem quota or arbitrary native-library writer interception.
Runtime/offline, physical touch and general operator acceptance need receipts.

The v2 host launch stopped before SSH because its evidence parent was absent.
Retain that failed plan. The fresh issuer creates only the new v3 evidence
parent before dispatch, and this coordinator records its exact identity to the
exclusive caller-reserved receipt before reading the plan. The owner receipt
and existing parent must be included in the measured host metadata allowance.
No existing failed directory or admission is reused.
