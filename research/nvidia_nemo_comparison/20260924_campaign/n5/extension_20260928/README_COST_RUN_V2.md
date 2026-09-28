# Corrected cumulative-cost admission launcher

V1 preflight failed before dispatch: a global README rename made one preserved LEGACY dependency point to a new README that exists only in this extension directory. No numerical worker or application ran. The failed precheck/census/launch log and V1 code remain preserved. V2 restores that single legacy README binding, uses a new launcher filename and binds its own builder/README/derivation. Its builder checks every literal HERE/LEGACY code path before dispatch. The application derivative, V1 lifecycle/reviewer, counter protocol and every parity/resource/drain gate remain unchanged.

Purpose, inputs, outputs and measurement limits are those in README_COST_RUN_V1.md and README_COMPONENT_COSTS_V1.md. Additional input is the hash-bound generated V1 launcher. Output is fresh prepare_cost_run_v2.py and COST_RUN_DERIVATION_V2.json; a run emits fresh private receipts under prepi-20260928. No cleanup/rewrite of failed evidence. No hardware, microphone, playback, download, training or enrollment. One supervised worker; unchanged CPUs4/14, thread/model1, GPU off and storage/output limits.

PowerShell / Anaconda PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928'
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_cost_run_v2.py
& $researchPython -B prepare_cost_run_v2.py --name a0-costs-v2 --backend nemotron_hybrid
# After terminal completion and exact owner exit:
& $researchPython -B review_cost_run_v1.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-costs-v2' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-costs-v2-REVIEW.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_cost_run_v2.py
"%RESEARCH_PY%" -B prepare_cost_run_v2.py --name a0-costs-v2 --backend nemotron_hybrid
"%RESEARCH_PY%" -B review_cost_run_v1.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-costs-v2" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-costs-v2-REVIEW.json"
```

Run the builder once. Only after independently reviewed A0 closure, use backend nemotron_600m and fresh a2-costs-v2 run/review paths. No existing passing test is scheduled for repetition without a new concern. This is counter validation and full-file parity, not full N4/N5 or CM5 acceptance.
