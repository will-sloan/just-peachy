# Prepare final S6C narratives

Purpose: create thirteen updated Markdown copies of reviewed handoff drafts using
completed596 paced cells, five continuous sessions and the fresh5,891-attempt
census. Original drafts and Word master remain unchanged. No inference, scoring,
hardware or campaign acceptance is performed.

Inputs: the fixed20260910T123540Z handoff_drafts, final census
EXECUTION_INVENTORY.json and COMPACT_LONG_OBSERVATIONS_V1.json. The helper rejects
unexpected counts, unclosed long rows, missing/nonunique anchors and an existing
output directory. The receipt binds every actual input and output.

Outputs: handoff_final_v1 Markdown files and NARRATIVE_PREPARATION_RECEIPT.json.
This is prepared content awaiting independent acceptance. Exact operating
commands, disposition, coverage, artifact index and paced synthesis must be
included before packaging. Do not rerun into an occupied output directory.

PowerShell:

~~~powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$s6cRepo\.edge-speech-env\python.exe" -B "$s6cSim\scripts\s6c_final_narratives_v1.py"
~~~

Anaconda Prompt / CMD:

~~~bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%S6C_REPO%\.edge-speech-env\python.exe" -B "%S6C_SIM%\scripts\s6c_final_narratives_v1.py"
~~~

Validation: actual source-bound run and independent reading against the existing
numerical authorities. Do not rerun experiments for this document-only change.
An anchor failure occurs before output creation; preserve any failed diagnostics.

