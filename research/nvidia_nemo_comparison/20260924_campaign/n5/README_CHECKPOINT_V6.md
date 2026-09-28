# September 28 reviewed partial checkpoint V6

Purpose: preserve the latest verified results and remaining work in a compact
analysis handoff. N4/N5 are incomplete. This checkpoint includes the passing
baseline ARM64 C-API parity, the independently reviewed 16-second A2/A3 native
protocol, retained full-source timeout and A3 raw word-time limitation, working
Windows previews, performance reports, 34-method catalogue, tested replay-clock
foundation and the user's mandatory real-world holdout requirement.

Inputs: HANDOFF_SELECTION_V6.json, N5_STATUS_20260928_V20.json and exactly
55 selected reports/tools from the verified remote campaign commit. The
unchanged package_reviewed_handoff_v2.py verifies every selected byte against
Git and its authorized remote branch. Earlier archives and all evidence remain
unchanged. Large detailed historical receipts remain available in the repository
and earlier private archives. Read README_REVIEWED_HANDOFF_V2.md for its rules.

Outputs: a new private ZIP, generated Git backup receipt/member manifest and
separate SHA256/readback receipt. Expected 59 members, all read back exactly,
under the 20-MiB hard cap. No audio, profiles, voiceprints, model weights or raw
transcripts are included. This is an analysis archive, not a Pi installer or
complete standalone source checkout; review tools require the campaign checkout
and private evidence described in their own READMEs. The stdlib replay-clock
tool/tests are included with their own instructions.

Commit and push the selected small files first. Use fresh output names; existing
destinations are refused. PowerShell from the campaign N5 directory:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B package_reviewed_handoff_v2.py --selection HANDOFF_SELECTION_V6.json --status N5_STATUS_20260928_V20.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v6.zip --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260928_V6_RECEIPT.json
```

CMD / Anaconda Prompt (existing pinned interpreter; no installation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B package_reviewed_handoff_v2.py --selection HANDOFF_SELECTION_V6.json --status N5_STATUS_20260928_V20.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v6.zip --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260928_V6_RECEIPT.json
```

Only a verified archive receipt establishes readback, not this preparation
document or an existing filename. No numerical worker, GUI, device operation,
training or Pi contact is performed. Scope and evidence levels remain explicit;
no packaging operation establishes stage acceptance or extends the deadline.
