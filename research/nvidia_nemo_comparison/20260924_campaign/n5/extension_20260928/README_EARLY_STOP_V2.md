# Explicit Stop → New transcript → full-file Start

Purpose: correct the V1 test's conversation-scope assumption without changing application behavior or relaxing exact parity. SessionWorkflow intentionally appends epochs to the current unpinned draft until the user selects New transcript, opens a saved conversation, or pins it. V1 stopped and restarted without one of those boundaries: its full-file audio/native activity matched, but its saved conversation correctly also contained the stopped prefix. The V1 run remains FAILED_PRESERVED; this is not a cleared pass or an application fix.

V2 uses the application's existing `session_action('new', audio=False, consent=False)` after the stopped prefix drains. It requires a different conversation ID, an empty new view, preservation of the earlier draft before and after restart, two resident-model streams, and exact full-file PCM/activity/caption/time parity with the reviewed reference. Reopen/delete verifies both isolated test records without touching the profile sentinel. No save/reopen requirement is removed.

Inputs: the three immutable V1 generated files and derivation hashes, original E0 application/asset/source bindings and extended time/resource admission. Outputs: fresh V2 harness, launcher, reviewer and derivation receipt, then private result/ownership/review evidence. All numerical, private-desktop and no-hardware constraints in README_EARLY_STOP.md remain, including original drain gate, 240-second phase/600-second run bounds and two CPUs total. The generator performs no inference and refuses existing outputs. The application is unchanged.

PowerShell / Anaconda PowerShell, from this directory:

```powershell
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_early_stop_v2.py
& $researchPython -B prepare_early_stop_v2.py --name a0-early-stop-v2 --backend nemotron_hybrid
# Only after the worker is terminal and exact owners are closed:
& $researchPython -B review_early_stop_v2.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-early-stop-v2' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-early-stop-v2-REVIEW.json'
# After closed review, use a2-early-stop-v2 and --backend nemotron_600m separately.
```

Command Prompt / Anaconda Prompt:

```bat
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_early_stop_v2.py
"%RESEARCH_PY%" -B prepare_early_stop_v2.py --name a0-early-stop-v2 --backend nemotron_hybrid
"%RESEARCH_PY%" -B review_early_stop_v2.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-early-stop-v2" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-early-stop-v2-REVIEW.json"
```

Use fresh names on retries. A V2 pass covers this explicit new-conversation workflow only. Same-draft multiple epochs need their own expected archive mapping and are not tested by comparing a combined draft to a single-file reference. N4/N5 and native Pi acceptance remain separate.
