$ErrorActionPreference = "Stop"

$toolRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")

$requiredDocs = @(
    "README_inference_pipeline.md",
    "docs/inference_pipeline/FILE_MAP.md",
    "docs/inference_pipeline/DEVELOPMENT_RULES.md",
    "docs/inference_pipeline/MILESTONE_LEDGER.md",
    "reports/milestones/M0_repository_baseline_report.md"
)

$missing = @(
    $requiredDocs | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $toolRoot $_) -PathType Leaf)
    }
)

if ($missing.Count -gt 0) {
    throw "Missing M0 docs: $($missing -join ', ')"
}

$fileMap = (Get-Content -LiteralPath (Join-Path $toolRoot "docs/inference_pipeline/FILE_MAP.md") -Raw).ToLowerInvariant()
$rules = (Get-Content -LiteralPath (Join-Path $toolRoot "docs/inference_pipeline/DEVELOPMENT_RULES.md") -Raw).ToLowerInvariant()
$ledger = (Get-Content -LiteralPath (Join-Path $toolRoot "docs/inference_pipeline/MILESTONE_LEDGER.md") -Raw).ToLowerInvariant()

$fileMapPhrases = @(
    "existing evaluation tool paths",
    "proposed future inference-pipeline paths",
    "app/model_runner/external_stub.py",
    "app/prediction_io/schema.py",
    "app/dataset_registry/registry.py",
    "app/scoring/scorer.py",
    "app/plotting/plots.py",
    "app/reporting/reporter.py",
    "app/augmentation/processor.py",
    "normalized metadata"
)

$rulesPhrases = @(
    "all model work must pass through explicit interfaces",
    'record["inference_audio_path"]',
    "predictions/utterances.jsonl",
    "recording_id",
    "utt_id",
    "start_sec",
    "end_sec",
    "speaker_label",
    "text"
)

$ledgerColumns = @(
    "milestone",
    "branch",
    "implemented files",
    "tests",
    "report path",
    "open issues",
    "merged yes/no"
)

foreach ($phrase in $fileMapPhrases) {
    if (-not $fileMap.Contains($phrase)) {
        throw "FILE_MAP missing phrase: $phrase"
    }
}

foreach ($phrase in $rulesPhrases) {
    if (-not $rules.Contains($phrase)) {
        throw "DEVELOPMENT_RULES missing phrase: $phrase"
    }
}

foreach ($column in $ledgerColumns) {
    if (-not $ledger.Contains($column)) {
        throw "MILESTONE_LEDGER missing column: $column"
    }
}

$repoRoot = Resolve-Path -LiteralPath (Join-Path $toolRoot "..\..")
$status = git -C $repoRoot status --short
$prohibited = @(
    "Software Validation from Datasets/Evaluation Tool/app/scoring/",
    "Software Validation from Datasets/Evaluation Tool/app/dataset_registry/",
    "Software Validation from Datasets/Evaluation Tool/app/gui/",
    "Software Validation from Datasets/Evaluation Tool/app/cli/",
    "Software Validation from Datasets/Evaluation Tool/app/plotting/",
    "Software Validation from Datasets/Evaluation Tool/app/reporting/",
    "Software Validation from Datasets/Evaluation Tool/app/model_runner/external_stub.py",
    "Software Validation from Datasets/Evaluation Tool/app/prediction_io/schema.py"
)

$violations = @()
foreach ($line in $status) {
    foreach ($path in $prohibited) {
        if ($line -like "*$path*") {
            $violations += $line
        }
    }
}

if ($violations.Count -gt 0) {
    throw "Prohibited paths changed: $($violations -join '; ')"
}

Write-Output "M0 docs smoke check passed."

