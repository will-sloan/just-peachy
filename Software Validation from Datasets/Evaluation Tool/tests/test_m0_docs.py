from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]


REQUIRED_DOCS = [
    "README_inference_pipeline.md",
    "docs/inference_pipeline/FILE_MAP.md",
    "docs/inference_pipeline/DEVELOPMENT_RULES.md",
    "docs/inference_pipeline/MILESTONE_LEDGER.md",
    "reports/milestones/M0_repository_baseline_report.md",
]


def read_text(relative_path: str) -> str:
    return (TOOL_ROOT / relative_path).read_text(encoding="utf-8")


def test_required_m0_docs_exist() -> None:
    missing = [path for path in REQUIRED_DOCS if not (TOOL_ROOT / path).is_file()]

    assert missing == []


def test_file_map_lists_existing_and_proposed_path_groups() -> None:
    text = read_text("docs/inference_pipeline/FILE_MAP.md").lower()

    required_phrases = [
        "existing evaluation tool paths",
        "proposed future inference-pipeline paths",
        "app/model_runner/external_stub.py",
        "app/prediction_io/schema.py",
        "app/dataset_registry/registry.py",
        "app/scoring/scorer.py",
        "app/plotting/plots.py",
        "app/reporting/reporter.py",
        "app/augmentation/processor.py",
        "normalized metadata",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_development_rules_include_explicit_interface_contract() -> None:
    text = read_text("docs/inference_pipeline/DEVELOPMENT_RULES.md").lower()

    required_phrases = [
        "all model work must pass through explicit interfaces",
        'record["inference_audio_path"]',
        "predictions/utterances.jsonl",
        "recording_id",
        "utt_id",
        "start_sec",
        "end_sec",
        "speaker_label",
        "text",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_milestone_ledger_has_required_columns() -> None:
    text = read_text("docs/inference_pipeline/MILESTONE_LEDGER.md").lower()

    required_columns = [
        "milestone",
        "branch",
        "implemented files",
        "tests",
        "report path",
        "open issues",
        "merged yes/no",
    ]

    for column in required_columns:
        assert column in text

