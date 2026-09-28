# Full-file cumulative cost and parity validation

Purpose: validate the new bounded counters against all accepted saved audio, native frames and embedding calls, with exact full-file parity against previously reviewed A0/D1/E0 and A2/D1/E0 references. This is justified by new instrumentation; it does not repeat earlier empty-store or prefix tests. Actual Tk render/save/reopen/delete and exact worker/job/thread/lock closure remain required. No visible desktop or input control is used.

Inputs: fresh `component-costs-v1` source derivative (build/test instructions in README_COMPONENT_COSTS_V1.md), original 44.6954375-second PCM, model/config/accepted N3 bindings, matching full-file reference, extension window and fresh resource census. The builder derives the preserved E0 full-file lifecycle/reviewer and current extension admission launcher. Their unchanged 1x source, all-audio shadow observer, parity, 60-second inference drain, 240-second child, 285-second job and 600-second admission contracts remain. Eight counter keys have explicit call/sample/error/frame checks; every ASR quantum, D1 input sample and final call must be counted. D1 empty-output calls must occur. E0 call count must equal the original telemetry count. Completed totals must match the independently persisted atomic session summary. All raw outputs stay private.

Outputs: generated fresh launcher/harness/reviewer plus derivation manifest; per-run private admission, infer/reopen receipts, COSTS.json and hash-bound session summary; independent review with complete targeted call-cost totals and parity. These are wall times around application model calls, not all process CPU, all orchestration costs or native Pi measurements. Setup/acquisition is reported separately. Compare no claimed optimized speedup; the acoustic computation is unchanged. Full N4 panel, longer endurance and real-world validity remain separate. The eight fixed counters do not collect raw audio, text or voice vectors.

PowerShell / Anaconda PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928'
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_cost_run_v1.py
& $researchPython -B prepare_cost_run_v1.py --name a0-costs-v1 --backend nemotron_hybrid
# Only after the terminal result and all exact run owners exit:
& $researchPython -B review_cost_run_v1.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-costs-v1' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-costs-v1-REVIEW.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_cost_run_v1.py
"%RESEARCH_PY%" -B prepare_cost_run_v1.py --name a0-costs-v1 --backend nemotron_hybrid
"%RESEARCH_PY%" -B review_cost_run_v1.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-costs-v1" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-costs-v1-REVIEW.json"
```

Builders run once and refuse existing outputs. After independently reviewed A0 closure, A2 uses name `a2-costs-v1` and backend `nemotron_600m` with matching review paths. One supervised job at a time. Existing interpreter only; no install/download. Shared limits: CPUs4/14 total, coordinator14, one native thread/model, GPU off, 128-MiB job output bound, combined 1-GiB extension/prepi allowance and original C50/G75-GiB floors. No Pi contact, capture, playback, training or enrollment. Preserve any failed run and derive a fresh repair instead of changing its bound files.
