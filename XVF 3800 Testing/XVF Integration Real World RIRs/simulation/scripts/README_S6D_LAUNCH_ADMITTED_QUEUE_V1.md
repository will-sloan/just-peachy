# Launch an already admitted literal S6D queue

Purpose: remove repeated manual Windows launch/quoting steps while preserving actual root review and exact queue hashes. This launcher creates no authority and does not advance stages itself. It verifies an existing ROOT_QUEUE_REVIEW.json, performs fresh runner validate-only and (for a single hardware job) owner check-plan, then launches the exact reviewed supervisor hidden through subprocess argument arrays. No shell-generated command is executed. It records actualPID/creation time, exactargv, hashes and an actual-command README beside the queue.

Inputs: `--review-receipt` pointing to a current root-owned queue receipt with queue/approval/runner bindings. Outputs: fresh validation logs, supervisor stdout/stderr, ROOT_LAUNCH_V1.json and README_RUN.md. Existing launch/log files are refused. Use the fixed edge interpreter; the approved job itself selects its original hardware or analysis environment. The runtime supervisor, not this short launcher, owns keep-awake and children.

PowerShell, replacing the example with an actually admitted queue receipt:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_launch_admitted_queue_v1.py" --review-receipt "$sim\reports\S6D\20260913T195357Z\runner\qualification_stage_2_queue_v1\ROOT_QUEUE_REVIEW.json"
```

Anaconda Prompt / CMD, no activation:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_launch_admitted_queue_v1.py" --review-receipt "%SIM%\reports\S6D\20260913T195357Z\runner\qualification_stage_2_queue_v1\ROOT_QUEUE_REVIEW.json"
```

Do not launch concurrent hardware owners. Hardware STOP must use the bound cooperative protocol and actual restoration must close before continuing. This helper cannot repair or retry a partial run. A validation failure is preserved and must be inspected before preparing a new admission. Local progress logging does not itself restart Codex. The root coordinator must complete dependent analysis and the final handoff rather than equating a queue completion with the whole task.
