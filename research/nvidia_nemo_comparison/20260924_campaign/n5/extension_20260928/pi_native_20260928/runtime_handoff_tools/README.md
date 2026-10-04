Current operator entrypoint is [build_handoff_v2.py](build_handoff_v2.py);
see [README_V2](README_V2.md) for exact Windows FILETIME registration and
current PowerShell/CMD/Anaconda commands. The original builder below is
preserved history and must not be executed during the current campaign.
No final handoff is created until the separate publication review closes.

# Build the final public-source handoff

`build_handoff.py` packages an explicitly reviewed list of repository documents
and readable source. It never contacts the Pi, changes a runtime, edits source,
downloads models or deletes recordings. It pins this PC's Python coordinator to
CPU14 and registers its identity before project reads.

Input is a UTF-8 JSON plan with schema
`just-peachy.reviewed-public-handoff.v1`, `reviewed_publication:true`, a `scope`
description, and `files`. Each file has an absolute `source`, archive `member`,
integer `bytes`, and exact `sha256`. Sources must be ordinary UTF-8 text files
inside the worktree. Review the contents before setting the publication flag:
the extension check cannot determine whether text contains personal data.
Use only reviewed code, guides and non-personal aggregate evidence. Never include
recordings, transcripts, vectors, credentials, galleries or model weights.

Output is a fresh private directory containing the ZIP, an independent ZIP copy,
every independently expanded/read-back member, the plan, manifest and
`HANDOFF_RECEIPT.json`. Failure preserves the partial output and writes a failure
receipt. Each run needs a new directory; existing archives are never overwritten.
The ZIP and source total are each bounded to20MiB; target ZIP size is under10MiB.
Each source is at most2MiB and the total output/restore allocation is96MiB.
Free-space floors remain C:50GiB and G:75GiB plus128MiB.

PowerShell (replace the two input/output placeholders with actual fresh paths):

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$T='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/runtime_handoff_tools'
& $PY -B "$T/build_handoff.py" --plan 'REVIEWED_PLAN.json' --output 'NEW_PRIVATE_DIRECTORY'
```

Command Prompt and Anaconda Prompt use the same installed interpreter:

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "T=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\runtime_handoff_tools"
"%PY%" -B "%T%\build_handoff.py" --plan "REVIEWED_PLAN.json" --output "NEW_PRIVATE_DIRECTORY"
```

No package installation or environment activation is needed. Check the returned
receipt against the archive before sharing it. The handoff is explanatory source
and documentation, not a standalone deployable OS image or model bundle.
