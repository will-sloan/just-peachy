[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("materialize", "run", "status", "stop", "resume", "finalize")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [ValidateSet("cpu", "cuda")]
    [string]$Device,

    [string]$Reason = "production rehearsal stop/resume qualification",

    [int]$MaxScenarios = 0
)

. (Join-Path $PSScriptRoot "worker_common.ps1")
trap {
    [Console]::Error.WriteLine("[FAIL] Massive rehearsal: $($_.Exception.Message)")
    exit 2
}
$context = Get-ProductionWorkerContext -MachineId "machine_a" -Device $Device
$campaignId = "campaign_07_massive_rehearsal_$Device"
$campaignRoot = Join-Path $context.EvaluationRoot "automated_runs\$campaignId"

switch ($Action) {
    "materialize" {
        $arguments = @("scripts\production_release.py", "materialize-rehearsal", "--device", $Device)
    }
    "run" {
        $arguments = @("scripts\production_release.py", "run-rehearsal", "--device", $Device)
        if ($MaxScenarios -gt 0) { $arguments += @("--max-scenarios", [string]$MaxScenarios) }
    }
    "resume" {
        $arguments = @("scripts\production_release.py", "run-rehearsal", "--device", $Device, "--resume-stopped")
    }
    "finalize" {
        $arguments = @("scripts\production_release.py", "finalize-rehearsal", "--device", $Device)
    }
    "status" {
        $arguments = @("run_evaluation.py", "campaign", "status", "--campaign-root", $campaignRoot)
    }
    "stop" {
        $arguments = @(
            "run_evaluation.py", "campaign", "stop", "--campaign-root", $campaignRoot,
            "--reason", $Reason
        )
    }
}

Invoke-ProductionChecked -FilePath $context.Python -Arguments $arguments -WorkingDirectory $context.EvaluationRoot
