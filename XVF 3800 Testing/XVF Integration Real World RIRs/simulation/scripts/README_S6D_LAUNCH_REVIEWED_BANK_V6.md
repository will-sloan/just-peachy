# Launch the already admitted remaining S6D hardware bank

Purpose: start the exact bank V6 after root has accepted all twelve N6h calibration cases and closed both collection supervisors. This launcher does not modify or regenerate any capture plan. Existing root admission54f991 and independent literal reviewab0d54 cover54 stages/312 future attempts; historical121 charges remain. Forecast433 attempts/19818.0819375 charged seconds is within480/21600 limits. The physical40GiB cap, C50/G75 free floors, original deadline and45-minute closeout reserve remain unchanged.

Inputs: root C12 acceptance path/SHA, existing immutable bank V6 queue/approval/reviews, source guards, reviewed allocation checker and frozen V4 supervisor. The C12 record must be `ROOT_ACCEPTED_C12_ALL12_COLLECTION`, accepted/planned12, old_failure_credit0, all_owners_closed true; include both `phase_closures` with supervisor-closure bindings/state directories and `closed_instances` with PID/creation-time pairs. Actual complete process inventory checks no other neural/device owner, retaining unrelated H2 maintenance. Later hardware/host overlap requires a separate explicit allocation. User analog-output disconnection confirmation is already present; do not ask again.

Outputs: fresh `ROOT_LAUNCH_PREFLIGHT.json`, `ROOT_LAUNCH.json` and stdout/stderr logs under `simulation/reports/S6D/20260913T195357Z/runner/bank_queue_v6`; live supervisor state under `G:/Just_Peachy_S6D/20260913T195357Z/runner/bank_queue_v6/supervisor_state`. All capture output paths come from the unchanged admitted plans. The supervisor launches hidden with keep-awake, its existing source/transport/process/resource guards and 15-second local health checks. No device process is forcibly killed. Existing launch/state files are refused.

PowerShell (root only after reviewing actual C12 closure):

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_launch_reviewed_bank_v6.py" --c12-acceptance '<actual root C12 acceptance path>' --c12-acceptance-sha256 '<exact SHA256>'
```

Anaconda Prompt or Command Prompt:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_launch_reviewed_bank_v6.py" --c12-acceptance "<actual root C12 acceptance path>" --c12-acceptance-sha256 "<exact SHA256>"
```

Use the compact state checkpoint for progress and immutable closures for acceptance. A launch, successful transport, or completed queue alone is not scientific qualification or completion of S6D. Preserve failed attempts and report genuine limitations. Source review and unchanged V4 queue validation precede playback; the first stage performs the already admitted fresh pre-QA.
