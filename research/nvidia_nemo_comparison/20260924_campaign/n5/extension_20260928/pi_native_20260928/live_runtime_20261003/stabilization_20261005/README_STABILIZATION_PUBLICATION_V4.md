# Prepare the build28 publication and handoff source plan

Purpose: refresh the exact approved build26 handoff source plan with the
current reviewed shared microphone Start repair, manual listening controls,
diagnostics and versioned build28 tools. It creates a proposed plan only; it
does not commit, push, build a ZIP, contact the Pi, start capture or certify a
native result. The final findings and operator guides must describe actual
observed results before Root runs this preparation.

Inputs:

- Exact immutable approved plan
  `audit-preparation/final-build26-approved-plan-a99d594386ea48e28b08ca73efdbda2c/REVIEWED_PLAN.json`,
  SHA `7dcf9975ad82e1ff57480a56beef18a6de9564ef316394ea58e988f9e74c6f9e`.
  It contains 643 sources; the previous ZIP's additional member was its
  manifest. All 643 member paths remain in the proposed plan.
- The explicit task sources listed in `SELECTED`, two modified readiness
  modules under `ui_restore_20261004`, the existing tracked operator/mode and
  pipeline guides, and the final `FIRST_START_REPAIR_FINDINGS.md`.
- Actual current source bytes in the worktree. The sole permitted archive
  alias remains completion `START_HERE.md` pointing to `START_HERE_CURRENT.md`.
- A new canonical `--label`, used with a fresh UUID private output directory.

V4 preserves the original 16MiB/600-second changed-source preparation scope,
including 64KiB per output directory, C:50GiB/G:75GiB floors, 2MiB ordinary
source limit and 20MiB/4096-member public source limits. It refreshes and hashes
every planned source, but writes independent source/backup/restore copies only
for changed or new real inputs. Unchanged sources retain the previous closed
backups. The two Start Here archive names use the same independently restored
real input. No scope increase or full recopy of unchanged historical sources
occurs.

Outputs: unique private CPU14/exact-FILETIME registration, finite scope,
backed preparer/README, changed-source triples, proposed plan and its separate
backup/restore copies, `GIT_WHITELIST.txt`, compact `PLAN_REVIEW.json` and
`SOURCE_CLOSED.json`. The proposed plan has `reviewed_publication=false` and
requires final source/results/link review before it can be used for the final
handoff. Existing plans, releases, failures and ZIPs remain immutable.

The Git whitelist explicitly includes current task sources and their linked
historical source READMEs, rather than all untracked files. Media, transcripts,
people galleries/vectors, model weights and credentials are excluded. Root
still reviews the actual whitelist and staged bytes before publication.
The selected build28 manifest identity is
`e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b`;
this identifies prepared package content and is not itself a native pass.

## PowerShell

Run after final findings/guides are updated, with no concurrent source edits.

```powershell
$S='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$S/prepare_stabilization_publication_v4.py" --label first-start-build28-publication
```

## CMD and Anaconda Prompt

Use the existing interpreter; no dependency installation or activation is needed.

```bat
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/prepare_stabilization_publication_v4.py" --label first-start-build28-publication
```

Root verifies the actual registered host process is absent afterward, reviews
all changed sources and actual result scopes, checks unresolved links and
whitespace, then creates a separately backed reviewed plan. Only that reviewed
plan may drive the new immutable handoff ZIP. Do not rerun this preparation or
rebuild an interim ZIP merely to advance a version number.


V4 narrowly canonicalizes each same-directory dependency to its actual resolved
filename before constructing an archive member. Case-insensitive Windows filename
lookups no longer create a differently cased member for README.md. Case-fold alias
rejection, exact source/member paths, the sole StartHere alias and all caps remain.
The failed V3 output is preserved. V4 explicitly selects the six activation files
and the final-plan reviewer/README; it still publishes an unapproved proposal.
