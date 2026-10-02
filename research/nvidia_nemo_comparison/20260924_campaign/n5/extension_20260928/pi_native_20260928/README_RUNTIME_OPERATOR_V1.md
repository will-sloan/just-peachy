# One-command batch refresh on the prepared PC

Purpose: preserve a completed or unused healthy Just Peachy batch, restore the idle baseline, inspect actual ownership/resources, and install a fresh batch with the same ten backend profiles. This is for this prepared Windows PC and CM5 with their existing pinned local assets and receipts. It is not an arbitrary-PC installer or SD image.

Before running: finish Stop, Save, Return and broker Close; wait until the manager returns idle after its local backup. Leave the manager open and the Pi reachable. Do not use this command on a failed/incomplete batch. It preserves every original and independent Pi-local copy; no automatic deletion, slot reset or recording occurs.

Inputs: previous installed version, a never-used higher version, existing model/restore directories, current source backups, private receipts and strict SSH configuration. Outputs: private complete batch copy, rollback receipt, read-only inspection, fresh measured installation policy/code/backups and new idle shortcuts. Every phase shares a fresh600second scope and reserves all independent copies plus4MiB of new PC metadata. Old allocations/evidence remain counted. C50GiB/G75GiB and Pi5GiB free floors, CPU/RAM/cardinality/pending-fault guards remain.

PowerShell, from the native source directory:
    .\Refresh-JustPeachy.ps1 -Version 24 -PreviousVersion 23 -Plan
    .\Refresh-JustPeachy.ps1 -Version 24 -PreviousVersion 23

Command Prompt or Anaconda Prompt, from the same directory:
    powershell -NoProfile -File Refresh-JustPeachy.ps1 -Version 24 -PreviousVersion 23 -Plan
    powershell -NoProfile -File Refresh-JustPeachy.ps1 -Version 24 -PreviousVersion 23

Plan performs PC-only path/source/space checks and writes a uniquely named plan; it does not contact the Pi, create a scope or run preservation/installation. Run it once per proposed version. Actual renewal uses a separate output. Adjust both version numbers on later successful renewals. Never reuse an attempted installation root or a failed output. No execution-policy setting is changed. If local policy blocks a script, use the documented Python commands in README_RUNTIME_REPROVISION_V1.md and the scope helper below.

The helper may be invoked directly in Anaconda/CMD:
    python -B prepare_runtime_operator_v1.py --private PRIVATE --work PRIVATE/deployable-runtime-resume-v1 --sources SOURCE_DIRECTORY --previous-install OLD_INSTALL --output NEW_PREPARATION --scope NEW_SCOPE.json --version 24
PowerShell uses:
    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B prepare_runtime_operator_v1.py --private PRIVATE --work PRIVATE/deployable-runtime-resume-v1 --sources SOURCE_DIRECTORY --previous-install OLD_INSTALL --output NEW_PREPARATION --scope NEW_SCOPE.json --version 24

Replace uppercase paths with the prepared absolute paths. The wrapper already supplies them. It runs Python stages sequentially; each sets CPU14 and registers itself before project reads. A rejection stops the sequence and leaves evidence intact; it does not automatically retry or bypass the guard. The full next-install reservation is3307886087B plus1489965408B for a new complete old-batch PC copy plus4194304B new metadata. This is a prospective reservation, not a claim that every recording will use it.

Per batch: four recordings,16manager launches,24h maximum per idle launch,120s microphone/Chunk52 or30s saved Streaming. A pending/faulted batch requires the documented recovery review, not renewal. The finite1024prior-owner bound remains; reaching it is an explicit guard failure requiring a reviewed ownership continuation, not permission to discard identities. Individual recordings can be copied sooner using README_RUNTIME_RECORDING_EXPORT_V4.md.

