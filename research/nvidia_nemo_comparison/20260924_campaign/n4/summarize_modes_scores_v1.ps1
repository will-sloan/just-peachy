# Purpose and run commands: README_MODES_SCORE_SUMMARY_V1.md.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Acceptance,
    [Parameter(Mandatory)][string]$Output
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$jpSelf = [System.Diagnostics.Process]::GetCurrentProcess()
$jpSelf.ProcessorAffinity = [IntPtr]16384
$jpSelf.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal

function Assert-Jp([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Read-Jp([string]$Path) {
    Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json -Depth 100 -AsHashtable
}
function Verify-Jp($Binding) {
    $jpItem = Get-Item -LiteralPath $Binding.path
    Assert-Jp ($jpItem.Length -eq $Binding.bytes) 'Bound file length changed'
    Assert-Jp ((Get-FileHash -LiteralPath $Binding.path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $Binding.sha256) 'Bound file hash changed'
}
function Metric-Jp($Metric) {
    Assert-Jp ($Metric.words -ge 0 -and $Metric.errors -ge 0) 'Negative metric counts'
    if ($Metric.words -eq 0) {
        Assert-Jp ($null -eq $Metric.rate) 'Zero denominator has a rate'
        return "unavailable ($($Metric.errors)/0)"
    }
    $jpRate = [double]$Metric.errors / [double]$Metric.words
    Assert-Jp ([Math]::Abs($jpRate - [double]$Metric.rate) -lt 1e-12) 'Rate differs from edit/word counts'
    return ('{0:F2}% ({1}/{2})' -f (100*$jpRate),$Metric.errors,$Metric.words)
}

Assert-Jp (-not (Test-Path -LiteralPath $Output)) 'Preserve existing report; choose a fresh output'
$jpAcceptanceHash = (Get-FileHash -LiteralPath $Acceptance -Algorithm SHA256).Hash
$jpA = Read-Jp $Acceptance
Assert-Jp ($jpA.status -eq 'ACCEPTED_REVIEWED_MODES_MODELED_SCORING_ONLY' -and $jpA.modes_modeled_scoring_accepted -eq $true -and $jpA.N4_accepted -eq $false) 'Accepted modeled modes scope required'
foreach ($jpB in @($jpA.review,$jpA.scoring_result,$jpA.scoring_report)) { Verify-Jp $jpB }
$jpReview = Read-Jp $jpA.review.path
$jpScored = Read-Jp $jpA.scoring_result.path
Assert-Jp ($jpReview.status -eq 'PASS_REVIEWED_MODELED_SCORING_ONLY' -and $jpReview.reviewed -eq 1536 -and $jpReview.required -eq 1536 -and $jpReview.all_metric_inputs_and_report_totals_verified -eq $true) 'Complete independent score review required'
foreach ($jpKey in @('path','sha256','bytes')) {
    Assert-Jp ($jpReview.report[$jpKey] -eq $jpA.scoring_report[$jpKey] -and $jpScored.report[$jpKey] -eq $jpA.scoring_report[$jpKey]) 'Report joins differ'
    Assert-Jp ($jpReview.scoring_result[$jpKey] -eq $jpA.scoring_result[$jpKey]) 'Scorer join differs'
}
Assert-Jp ($jpScored.prediction_completed -eq 1536 -and $jpScored.prediction_failed -eq 0 -and $jpScored.prediction_not_tested -eq 0 -and $jpScored.metrics_unavailable_for_complete_predictions -eq 0) 'Incomplete scoring population'
$jpReport = Read-Jp $jpA.scoring_report.path
Assert-Jp ($jpReport.scope -eq 'modes-panel' -and $jpReport.required_cells -eq 1536 -and $jpReport.cohorts.Count -eq 128 -and $jpReport.paired.Count -eq 180) 'Wrong report census'
$jpModes = @('anonymous_conversation','enrolled_names','selected_closed','selected_focus')
$jpExpected = [System.Collections.Generic.HashSet[string]]::new()
foreach ($jpMode in $jpModes) {
    foreach ($jpAsr in 0..3) { foreach ($jpDiar in 0..1) { foreach ($jpEmbed in 0..1) {
        foreach ($jpTap in @('O0','O1')) { [void]$jpExpected.Add("$jpMode|A${jpAsr}_D${jpDiar}_E${jpEmbed}|$jpTap") }
    } } }
}
$jpRows = [System.Collections.Generic.List[string]]::new()
$jpRows.Add('# Modes modeled scoring results')
$jpRows.Add('')
$jpRows.Add('All 1,536/1,536 saved-scene mode cases completed and passed independent score review, with no failed predictions or unavailable metrics. This is the predeclared 24-output panel (12 scenes per tap), evaluated across 16 compositions and four modes. It is separate from the 7,680-case main bank and is not full-bank coverage for every mode.')
$jpRows.Add('')
$jpRows.Add('These tables report modeled word/assignment metrics. Naming recognition, first-visible labels, widget timing, resource feasibility and CM5 performance remain unvalidated. A closed roster is an assumption; its labels do not certify identity recognition. Selected-focus modes intentionally have a different target. Compare methods within the same mode and supported-reference population; do not rank modes by a single error rate.')
$jpRows.Add('')
$jpRows.Add('WER sums errors and reference words on complete nonoverlap references. cpWER and MIMO have their own supported populations. Missing reference support stays unavailable, and an error rate can exceed 100%. Both taps share scene dependencies; this seen engineering panel is not independent unseen-room validation. The private report retains all 180 matched comparisons and condition strata. This summary does not recompute alignments or imply statistical significance.')
$jpRows.Add('')
foreach ($jpMode in $jpModes) {
    $jpRows.Add("## $jpMode")
    $jpRows.Add('')
    $jpRows.Add('| Composition | Tap | Complete | Primary WER (errors/words) | cpWER (errors/words) | MIMO (errors/words) |')
    $jpRows.Add('|---|---|---:|---:|---:|---:|')
    foreach ($jpC in @($jpReport.cohorts | Where-Object { $_.mode -eq $jpMode } | Sort-Object { $_.composition }, { $_.tap })) {
        Assert-Jp ($jpExpected.Remove("$($jpC.mode)|$($jpC.composition)|$($jpC.tap)")) 'Duplicate or foreign cohort'
        $jpN = $jpC.counts
        Assert-Jp ($jpN.required_cells -eq 12 -and $jpN.execution_statuses.Count -eq 1 -and $jpN.execution_statuses.COMPLETE -eq 12 -and $jpN.metric_statuses.Count -eq 1 -and $jpN.metric_statuses.SCORED -eq 12) 'Incomplete cohort'
        Assert-Jp ($jpN.naming_widget_resources -eq 'UNAVAILABLE_MODELED_METHOD_BANK_ONLY') 'Unexpected acceptance scope'
        $jpMetrics = @('primary_wer','cpwer','mimo') | ForEach-Object { Metric-Jp $jpN.word_metrics[$_] }
        $jpRows.Add("| $($jpC.composition) | $($jpC.tap) | 12/12 | $($jpMetrics -join ' | ') |")
    }
    $jpRows.Add('')
}
Assert-Jp ($jpExpected.Count -eq 0) 'Missing composition/mode/tap cohort'
$jpRows.Add('## Provenance and remaining work')
$jpRows.Add('')
$jpRows.Add('No release or default backend is selected by this report. Paced native application checks, naming semantics, GUI/resource measurements, stop/restart and 20-minute continuity tests remain prerequisites for release qualification. N4/N5 remain incomplete. Live CM5 checks are deferred until reconnection.')
$jpRows.Add('')
$jpRows.Add("Acceptance SHA-256: $($jpAcceptanceHash.ToLowerInvariant()).")
$jpRows.Add("Private aggregate report SHA-256: $($jpA.scoring_report.sha256).")
$jpRows.Add("Independent review SHA-256: $($jpA.review.sha256).")
$jpRows.Add('See README_MODES_SCORE_SUMMARY_V1.md for reproduction. Private per-scene evidence stays outside Git.')
$jpRows.Add('')
foreach ($jpB in @($jpA.review,$jpA.scoring_result,$jpA.scoring_report)) { Verify-Jp $jpB }
Assert-Jp ((Get-FileHash -LiteralPath $Acceptance -Algorithm SHA256).Hash -eq $jpAcceptanceHash) 'Acceptance changed during read'
$jpBytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($jpRows -join "`n"))
Assert-Jp ($jpBytes.Length -le 64*1024) 'Summary exceeds declared output cap'
$jpStream = [System.IO.File]::Open($Output,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write)
try { $jpStream.Write($jpBytes,0,$jpBytes.Length) } finally { $jpStream.Dispose() }
[pscustomobject]@{status='WROTE_AGGREGATE_MODELED_SUMMARY_ONLY';cohorts=128;cases=1536;output=$Output;sha256=(Get-FileHash -LiteralPath $Output -Algorithm SHA256).Hash.ToLowerInvariant();N4_accepted=$false} | ConvertTo-Json
