# Partial checkpoint V5

Purpose: package the current scoped campaign evidence, including the full-bank
workload/availability analysis and passing Cortex-A76 baseline ASR retest,
without treating either as completed N4/N5 acceptance. Uses the unchanged
qualified `package_reviewed_handoff_v2.py`; full refusal rules are in
`README_REVIEWED_HANDOFF_V2.md`.

Inputs: `HANDOFF_SELECTION_V5.json`, `N5_STATUS_20260928_V18.json` and its
55 selected public report files from the exact remotely verified Git commit.
Outputs: fresh private V5 ZIP and separate SHA256/member-readback receipt.
The 59 members include generated Git backup and manifest records. Model
bundles remain separate and private. This report archive is not an installer
and does not assert Pi readiness. Prior archives/receipts are preserved.

Commit and push all selected bytes first. From the campaign N5 directory:

```powershell
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B package_reviewed_handoff_v2.py --selection HANDOFF_SELECTION_V5.json --status N5_STATUS_20260928_V18.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v5.zip --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260928_V5_RECEIPT.json
```

CMD / Anaconda Prompt, using the existing pinned interpreter:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B package_reviewed_handoff_v2.py --selection HANDOFF_SELECTION_V5.json --status N5_STATUS_20260928_V18.json --output G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign_20260928_v5.zip --receipt G:\Just_Peachy_N1\20260924_campaign\local\n5\handoffs\HANDOFF_20260928_V5_RECEIPT.json
```

The builder verifies the authorized remote ref, every selected Git byte and
every archive member. No new tests are necessary for an unchanged builder and
data-only selection; actual archive readback is the relevant check. No GUI,
model inference, training, capture, private profile or device connection is
created. Campaign reserve and deadline remain unchanged.
