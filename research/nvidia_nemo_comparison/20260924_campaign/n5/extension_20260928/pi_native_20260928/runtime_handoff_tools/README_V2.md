# Final handoff builder V2

Use build_handoff_v2.py for future final publication. The original builder is
preserved historical source; do not execute it during the current campaign.
V2 changes only early Windows owner registration plus an identity-only check.
It pins CPU14 before project reads, records actual kernel creation FILETIME,
PID, derived creation time and affinity in REGISTERED_OWNER.json, fsyncs and
reads it back before opening the publication plan. The ZIP whitelist, finite
allocation, exact source hashes, independent ZIP and expanded restore are
unchanged.

Input: a finally reviewed just-peachy.reviewed-public-handoff.v1 JSON plan
with reviewed_publication true, scope and exact source/member/bytes/SHA rows.
Use reviewed text/code only, no private transcripts, audio, model/gallery data,
credentials, runtime profile/config/admission/owner payloads or private
receipts. The current proposed plan is intentionally false and must not be
used as a final publication approval.

Output: a fresh private audit-preparation directory with owner, plan,
JustPeachy-v29-ChatGPT-handoff.zip, independent ZIP copy, expanded full-member
readback and HANDOFF_RECEIPT.json. Failure keeps all partial files.
Bounds:4096 members,2MiB/file,20MiB source and20MiB ZIP,96MiB total outputs;
C:50GiB and G:75GiB+128MiB free floors. This is explanatory source, not a
standalone model/OS installation. No network/native/model action occurs.

## PowerShell

Choose a new private directory below the actual audit-preparation root so the
strict host-owner census can recognize this exact Windows owner form.
Do not run the final command until the final source and outcome review closes.

    $py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
    $t='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/runtime_handoff_tools'
    $q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
    & $py -B "$t/build_handoff_v2.py" --plan "$q/audit-preparation/FINAL_REVIEWED_PLAN.json" --output "$q/audit-preparation/FINAL_HANDOFF_FRESH"

FINAL_REVIEWED_PLAN.json and FINAL_HANDOFF_FRESH are explicit placeholders for
the operator's reviewed actual plan and a never-used output directory.
No environment installation or activation is required.

## Command Prompt and Anaconda Prompt

    set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
    set "T=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\runtime_handoff_tools"
    set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
    "%PY%" -B "%T%\build_handoff_v2.py" --plan "%Q%\audit-preparation\FINAL_REVIEWED_PLAN.json" --output "%Q%\audit-preparation\FINAL_HANDOFF_FRESH"

## Focused owner check, no ZIP

Only the changed registration path needs this check; it does not rebuild a
healthy archive or read a project plan. In PowerShell after setting the paths:

    & $py -B "$t/build_handoff_v2.py" --verify-owner-only --output "$q/audit-preparation/FRESH_HANDOFF_OWNER_CHECK"

CMD/Anaconda:

    "%PY%" -B "%T%\build_handoff_v2.py" --verify-owner-only --output "%Q%\audit-preparation\FRESH_HANDOFF_OWNER_CHECK"

Require OWNER_VERIFICATION.json passed=true, actual_affinity=[14],
exact_filetime=true, project_plan_read=false and zip_created=false.
Both modes preserve exact owner receipts; no malformed registration is deleted.