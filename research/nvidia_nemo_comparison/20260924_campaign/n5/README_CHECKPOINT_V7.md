# September 28 consolidated partial handoff V7

Purpose: put the corrected current backend/workbook guides, Pi reconnection
companion receipt, existing performance results and held-out real-world methods
in one compact analysis handoff. N4/N5 remain incomplete. This adds packaging
and documentation evidence, not new model performance or application acceptance.

Inputs: HANDOFF_SELECTION_V7.json, N5_STATUS_20260928_V21.json and 55 selected
reports/tools from the exact remotely verified campaign commit. V21 is a compact
current status with links to the detailed V20 numerical checkpoint and original
receipts. The unchanged package_reviewed_handoff_v2.py checks all selected bytes
against Git and the authorized remote. README_REVIEWED_HANDOFF_V2.md describes
its refusal rules. Commit and push reviewed files before building.

Outputs: one new private analysis ZIP with 59 members, plus a separate digest
and readback receipt. The ZIP includes its selection, current status and generated
member-hash/Git-backup records. Every member is read back exactly. Target <=10 MiB,
hard cap 20 MiB. Earlier ZIPs, receipts, failures and immutable releases remain.
Only a successful verified receipt establishes the build; a filename is not proof.

The selection replaces five older or detailed files with the current quickstart,
companion verification, workbook proposal, guide verification and artifact index.
The omitted implementation/review tools and optional asset estimates remain in
the Git repository and previous private archives. This ZIP is neither an installer
nor a complete source checkout. The actual baseline and companion archives stay
separate; PI_RECONNECT_QUICKSTART_V1.md identifies both. No weights, audio,
personal profiles, voiceprints, raw transcripts or run logs enter the analysis ZIP.

PowerShell, using the existing interpreter and read-only pinning helper:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B -c "from pi_storage_preflight_v1 import pin_windows; pin_windows(); import runpy; runpy.run_path('package_reviewed_handoff_v2.py', run_name='__main__')" --selection HANDOFF_SELECTION_V7.json --status N5_STATUS_20260928_V21.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v7.zip --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260928_V7_RECEIPT.json
```

CMD / Anaconda Prompt, no environment activation or installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -c "from pi_storage_preflight_v1 import pin_windows; pin_windows(); import runpy; runpy.run_path('package_reviewed_handoff_v2.py', run_name='__main__')" --selection HANDOFF_SELECTION_V7.json --status N5_STATUS_20260928_V21.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v7.zip --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260928_V7_RECEIPT.json
```

The wrapper pins only its own process to CPU14/BelowNormal, one numerical thread
and GPU off. Verify C:50/G:75-GiB free-space floors before writing; the expected
archive is small. Use fresh output names on any repeat. Existing qualified builder
code is reused unchanged, with actual selected-byte and archive readback checks.
No numerical worker, GUI launch, target connection or hardware access occurs.

The important limits remain explicit: baseline emulated C-API parity and short
A2/A3 native protocols pass, the long A2 repeat failure is preserved, full ARM64
software remains unverified, and no new N4 release profile is accepted. The 34
method proposals and six tested model-free clock modes are retained without
claiming an integrated optimized runtime. Sparse synthetic silence savings are
not real-world or Pi performance. Reserve/deadline remain unchanged; unfinished
gates stay in the final outcome rather than being inferred complete from this ZIP.
