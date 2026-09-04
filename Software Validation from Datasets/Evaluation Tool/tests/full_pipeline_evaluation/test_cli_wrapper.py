from __future__ import annotations

from pathlib import Path

from app.full_pipeline_evaluation.cli import _parser


TOOL_ROOT = Path(__file__).resolve().parents[2]


def test_cli_exposes_all_twelve_controller_actions() -> None:
    parser = _parser()
    action = next(item for item in parser._actions if item.dest == "action")
    assert set(action.choices) == {
        "audit",
        "prepare",
        "validate",
        "plan",
        "smoke",
        "run-development",
        "freeze",
        "run-evaluation",
        "status",
        "stop",
        "analyze",
        "collect",
    }


def test_plan_defaults_to_both_measurement_modes() -> None:
    args = _parser().parse_args(["plan"])
    assert args.measurement_mode is None


def test_wrappers_are_documented_and_forbid_resource_parallelism() -> None:
    run_wrapper = (
        TOOL_ROOT / "scripts/run_full_pipeline_evaluation.ps1"
    ).read_text(encoding="utf-8")
    monitor = (
        TOOL_ROOT / "scripts/monitor_full_pipeline_evaluation.ps1"
    ).read_text(encoding="utf-8")
    readme = (
        TOOL_ROOT / "app/full_pipeline_evaluation/README.md"
    ).read_text(encoding="utf-8")
    for action in (
        "Audit",
        "Prepare",
        "Validate",
        "Plan",
        "Smoke",
        "RunDevelopment",
        "Freeze",
        "RunEvaluation",
        "Status",
        "Stop",
        "Analyze",
        "Collect",
    ):
        assert action in run_wrapper
    assert "Matched resource measurements must use -ParallelJobs 1" in run_wrapper
    assert "[switch]$Follow" in monitor
    assert "$IntervalSeconds = 30" in monitor
    assert "measured" in readme.casefold()
    assert "anaconda prompt" in readme.casefold()

