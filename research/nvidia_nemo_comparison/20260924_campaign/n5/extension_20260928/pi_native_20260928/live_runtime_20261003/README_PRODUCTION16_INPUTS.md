# Production16 review inputs

`prepare_production16_plan.py` prepares an **unaccepted** plan from disabled GUI15. It preserves the exact GUI15 runtime content, derives the thirteen package-path substitutions to production16, retains the246 standard live/saved field-testing permission rows and61 actual asset pins, and binds the verified backup03. It does not build, stage, activate, authorize, or claim246 measured passes.

Inputs are the exact disabled GUI15 package and manifest, the SHA-pinned standard selection matrix and actual61-asset census, the reviewed external builder, verified backup03 reference, and an existing private output directory. Outputs are a fresh UUID preparation containing the unaccepted plan, path-only relocation certificate requiring root review, disabled binding preview, exact matrix/assets/backup references and independently read-back builder copies. The ordinary policy remains300 source seconds with120-second drain/backlog defaults;600-second acceptance ceilings are developer limits, not ordinary defaults.

PowerShell (define `$N` and `$Q` as the canonical runtime-source/private-evidence directories):

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$OldPlan="$Q/audit-preparation/production15-plan-512e145ddc4c4fc0840c0bdee32d9fb5"
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$N/prepare_production16_plan.py" --source "$Q/audit-preparation/gui-policy-derivative-2a7fb109ca0d4501b42a7651755d91b6/package" --source-manifest-sha256 1456ac9ab2e48177d1f4331da416c6e3113fc051a2becbab34726d784321acb0 --matrix "$OldPlan/SUPPORTED_DEFAULT_SELECTIONS_REQUIRES_REVIEW.json" --assets "$OldPlan/SELECTED_ASSETS_ACTUAL_SOURCE.json" --builder "$N/prepare_package.py" --full-backup "$OldPlan/FULL_BACKUP03_REFERENCE.json" --output-root "$Q/audit-preparation"
```

Command Prompt/Anaconda Prompt (same qualified interpreter; no new installation):

```bat
set "OldPlan=%Q%\audit-preparation\production15-plan-512e145ddc4c4fc0840c0bdee32d9fb5"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\prepare_production16_plan.py" --source "%Q%\audit-preparation\gui-policy-derivative-2a7fb109ca0d4501b42a7651755d91b6\package" --source-manifest-sha256 1456ac9ab2e48177d1f4331da416c6e3113fc051a2becbab34726d784321acb0 --matrix "%OldPlan%\SUPPORTED_DEFAULT_SELECTIONS_REQUIRES_REVIEW.json" --assets "%OldPlan%\SELECTED_ASSETS_ACTUAL_SOURCE.json" --builder "%N%\prepare_package.py" --full-backup "%OldPlan%\FULL_BACKUP03_REFERENCE.json" --output-root "%Q%\audit-preparation"
```

The earlier production15 plan is retained historical preparation and was never built. Current source15 is a different GUI-only candidate. Its separately reviewed GUI14-to15 certificate and this new path15-to16 certificate must both be verified before deriving the one optional normal receipt directly from original actual14. Keep all actual14 measurement, policy, ownership and closure fields. Only current candidate/operational pins and explicit reuse provenance change. The optional row is limited to actual live Pyannote/TitaNet/window60 with300/60/30 source/drain/backlog policy and27 unchanged assets. Other optional combinations remain unavailable.

See [the GUI evidence composition contract](README_GUI_POLICY_REUSE.md) and [the generic finalizer](README_PRODUCTION_FINALIZATION.md). Root reviews the concrete certificates and final plan before the finalizer can create accepted production bytes. The new production idle-controller test uses actual Desktop Exec/native_scope and real controls without Start; it does not replace or relabel actual14 capture evidence. Current retained desktop remains unchanged until the guarded activation and consolidation actions complete with full readback.
