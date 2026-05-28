"""Run the M12 enrollment prompt comparison experiment."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.experiments.enrollment_prompt_eval import (
    DEFAULT_PROMPT_SETS_PATH,
    DEFAULT_SWEEP_CONFIG_PATH,
    DEFAULT_SYNTHETIC_SAMPLES_PATH,
    prompt_comparison_report_path,
    run_enrollment_prompt_eval,
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = args.run_id or time.strftime("m12_enrollment_prompts_%Y%m%d_%H%M%S")
    report_path = args.report or prompt_comparison_report_path(TOOL_ROOT / "reports", run_id)
    result, written_report_path = run_enrollment_prompt_eval(
        run_id=run_id,
        prompt_sets_path=_tool_relative(args.prompt_sets),
        samples_jsonl=_tool_relative(args.samples_jsonl),
        sweep_config_path=_tool_relative(args.sweep_config),
        report_path=report_path,
        smoke_commands=[command_summary(args, report_path)],
    )
    print(f"Prompt comparison report: {written_report_path}")
    print(f"Recommended prompt set: {result.recommended_prompt_set_id or 'n/a'}")
    print(
        "Recommended minimum enrollment duration sec: "
        f"{result.recommended_min_duration_sec if result.recommended_min_duration_sec is not None else 'n/a'}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run enrollment prompt comparison from JSONL embeddings.",
    )
    parser.add_argument(
        "--prompt-sets",
        type=Path,
        default=DEFAULT_PROMPT_SETS_PATH.relative_to(TOOL_ROOT),
        help="Prompt sets YAML path, absolute or Evaluation Tool relative.",
    )
    parser.add_argument(
        "--samples-jsonl",
        type=Path,
        default=DEFAULT_SYNTHETIC_SAMPLES_PATH.relative_to(TOOL_ROOT),
        help="Enrollment prompt sample JSONL, absolute or Evaluation Tool relative.",
    )
    parser.add_argument(
        "--sweep-config",
        type=Path,
        default=DEFAULT_SWEEP_CONFIG_PATH.relative_to(TOOL_ROOT),
        help="Sweep config YAML path, absolute or Evaluation Tool relative.",
    )
    parser.add_argument("--run-id", default=None, help="Run id for the report artifact.")
    parser.add_argument("--report", type=Path, default=None, help="Optional markdown report path.")
    return parser


def _tool_relative(path: Path) -> Path:
    return path if path.is_absolute() else TOOL_ROOT / path


def command_summary(args: argparse.Namespace, report_path: Path) -> str:
    parts = [
        "python",
        "scripts/run_enrollment_prompt_eval.py",
        "--prompt-sets",
        str(args.prompt_sets),
        "--samples-jsonl",
        str(args.samples_jsonl),
        "--sweep-config",
        str(args.sweep_config),
        "--report",
        str(report_path),
    ]
    if args.run_id is not None:
        parts.extend(["--run-id", args.run_id])
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
