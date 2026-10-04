# Prepare the current repair handoff whitelist

`prepare_public_handoff_plan.py` creates a proposed public-source plan for the build17 classic frontend and microphone-readiness repair. It preserves the exact 385-member whitelist from the closed build16 handoff, refreshes those public files from the current worktree, and adds only top-level Python/Markdown source, tests and READMEs in this repair directory. It reads no private audio, transcript, gallery, model, admission or owner payload into the public plan.

The input is the hash-pinned prior `REVIEWED_PLAN.json` and current regular repository files. The output is a fresh private directory containing an early CPU14 owner, `PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json`, `GIT_WHITELIST.txt` and compact `PLAN_REVIEW.json`. The proposal always has `reviewed_publication:false`. This tool performs no Pi action, test, Git mutation or ZIP build. The final reviewer must inspect the text and refresh the proposal after the final native outcome and documentation edits are complete.

## PowerShell

```powershell
$repair='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/ui_restore_20261004'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$repair/prepare_public_handoff_plan.py" --label 'public-repair-plan-pending'
```

## Command Prompt and Anaconda Prompt

```bat
set "REPAIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\ui_restore_20261004"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%REPAIR%\prepare_public_handoff_plan.py" --label "public-repair-plan-pending"
```

Use a fresh label for final documentation refresh. Registration precedes project reads; the run is limited to 600 seconds and 16MiB of written preparation bytes. Existing C:50GiB/G:75GiB+128MiB floors and the handoff's 4096-member, 2MiB/member, 20MiB/source limits remain intact.

## Final publication workflow

After the final documentation signal, inspect the actual native outcome and current guides; generate a fresh proposal; review its exact text, local links, new code READMEs, byte counts and hashes; then save a fresh approved plan with `reviewed_publication:true`. Keep all earlier proposals intact. Use the existing `runtime_handoff_tools/build_handoff_v2.py` once with that reviewed plan and a new `final-handoff-v29-build17-20261004` output directory. Its independent ZIP and expanded member readback remain required; see [final publication](../README_FINAL_PUBLICATION.md).

For Git, review `git status --short`, stage only the exact `GIT_WHITELIST.txt` paths with `git add --pathspec-from-file=ABSOLUTE_GIT_WHITELIST.txt`, and compare staged bytes with the approved plan before committing. Preserve unrelated untracked Office lock files, private `BASE.json`/`SOURCE_REVIEW.json`, caches and historical unselected utilities. Check `git diff --cached --check` and the staged filename list; commit on the existing branch; use a normal push to its existing origin branch; verify the remote commit. Do not use `git add .`, destructive cleanup, a forced push or a main-branch merge. The parent operator owns the final commit/push and receipt.
