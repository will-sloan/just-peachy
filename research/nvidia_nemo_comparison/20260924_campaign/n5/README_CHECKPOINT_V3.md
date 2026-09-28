# September 28 partial checkpoint V3

Purpose: package the current reports, actual Windows pair, operating guide and
remaining blockers in a compact readable handoff. N4/N5 remain incomplete.
This reuses the unchanged qualified package_reviewed_handoff_v2.py, whose full
purpose/inputs/outputs and refusal rules are in README_REVIEWED_HANDOFF_V2.md.

Inputs: HANDOFF_SELECTION_V3.json, N5_STATUS_20260928_V17.json and exactly 55
reviewed report files from the verified remote campaign commit. No raw private
data enters the ZIP. Outputs: a fresh private ZIP and SHA256/member-readback
receipt. The 59-member archive includes its own generated Git backup receipt
and manifest. Deployable model bundles remain separate; this is no Pi-ready
alternative or stage acceptance. Earlier checkpoint files stay unchanged.

Commit and push the selected small files first; the tool verifies the remote
branch and byte-for-byte Git contents. Existing destinations are refused.
From the campaign n5 directory, PowerShell:

```powershell
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B package_reviewed_handoff_v2.py --selection HANDOFF_SELECTION_V3.json --status N5_STATUS_20260928_V17.json --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v3.zip' --receipt 'G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260928_V3_RECEIPT.json'
```

CMD / Anaconda Prompt (existing interpreter; no activation/install):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B package_reviewed_handoff_v2.py --selection HANDOFF_SELECTION_V3.json --status N5_STATUS_20260928_V17.json --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v3.zip" --receipt "G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260928_V3_RECEIPT.json"
```

This creates no GUI, inference worker, capture, training, personal profile or
device connection. Repository visibility, original checkout and main remain
unchanged. The campaign packaging reserve and deadline are not extended.
