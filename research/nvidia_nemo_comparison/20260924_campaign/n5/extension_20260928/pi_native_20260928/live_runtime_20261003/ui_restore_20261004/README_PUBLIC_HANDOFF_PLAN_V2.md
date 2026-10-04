# Final repair handoff plan and narrow Git publication

`prepare_public_handoff_plan_v2.py` is the current plan preparer. The executed first preparer and its pending proposal stay unchanged as history. V2 preserves the prior 385-file public-source whitelist, refreshes current bytes, and adds this repair directory's top-level Python/Markdown source, tests and READMEs. It builds no ZIP and always emits `reviewed_publication:false` until the final reviewer approves the exact plan.

The original completion `START_HERE.md` is locked by an unrelated Windows process. V2 does not read or change it. The one permitted member alias places the reviewed `completion_20261001/START_HERE_CURRENT.md` bytes at `completion_20261001/START_HERE.md` in the handoff. It also includes `START_HERE_CURRENT.md` under its own name. Every other member must match its exact repository-relative source path. The builder's manifest records the true current source for the alias.

Inputs are the hash-pinned build16 `REVIEWED_PLAN.json`, current public sources and current Start Here replacement. Outputs in a new private directory are an early CPU14 owner, `PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json`, `PLAN_REVIEW.json`, and a deliberately narrow `GIT_WHITELIST.txt`. The latter contains only the eight repaired tracked guides, the new current Start Here, and repair directory Python/Markdown files. It excludes unrelated historical untracked utilities even when the earlier handoff contains their reviewed readable source.

## PowerShell

```powershell
$repair='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/ui_restore_20261004'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$repair/prepare_public_handoff_plan_v2.py" --label 'public-repair-final-docs-ready'
```

## Command Prompt and Anaconda Prompt

```bat
set "REPAIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\ui_restore_20261004"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%REPAIR%\prepare_public_handoff_plan_v2.py" --label "public-repair-final-docs-ready"
```

Run after the root's final documentation signal. The process is limited to 600 seconds and 16MiB written preparation bytes, with C:50GiB/G:75GiB+128MiB free floors. Public source limits remain 4096 members, 2MiB/member and 20MiB total. It runs no model, native test, Pi operation or Git mutation.

## Review, build and publish

The root reviews the actual native check, normal desktop launch/Exit, final status text, local links, source READMEs and all proposed hashes. Save a new approved plan; do not edit an old proposal. Only after approval, build once using `runtime_handoff_tools/build_handoff_v2.py` with a fresh `final-handoff-v29-build17-20261004` output directory. Require its complete independent ZIP and expanded member readback. See [final publication](../README_FINAL_PUBLICATION.md).

From the existing worktree and branch, stage only `GIT_WHITELIST.txt` with `git add --pathspec-from-file=ABSOLUTE_GIT_WHITELIST.txt`. Compare staged filename membership and bytes to the approved selection; run `git diff --cached --check`; commit and use a normal push to the existing origin branch; verify remote HEAD. Preserve unrelated untracked files, the locked old guide, private `BASE.json`/`SOURCE_REVIEW.json`, caches, old packages and recordings. Do not stage the entire historical handoff list, use `git add .`, force a push or merge main. The root owns commit/push and final receipts.
