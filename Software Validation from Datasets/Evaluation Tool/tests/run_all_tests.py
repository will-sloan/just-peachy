"""Run every test command independently and summarize the results.

This runner intentionally does not stop at the first failure. It runs each
pytest file separately and exits non-zero only after every discovered test
command has had a chance to run.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent
TOOL_ROOT = TESTS_ROOT.parent
TEST_MILESTONES = {
    "tests/test_m0_docs.py": ("M0",),
    "tests/inference_pipeline/test_contracts.py": ("M1",),
    "tests/inference_pipeline/test_config_registry.py": ("M2",),
}


@dataclass(frozen=True)
class TestResult:
    """Result for one test command."""

    name: str
    milestones: tuple[str, ...]
    exit_code: int
    duration_sec: float

    @property
    def status(self) -> str:
        return "PASS" if self.exit_code == 0 else "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run all Evaluation Tool tests without stopping on first failure.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for pytest files. Defaults to this interpreter.",
    )
    args = parser.parse_args()

    results: list[TestResult] = []

    python_tests = sorted(TESTS_ROOT.rglob("test_*.py"))
    for test_path in python_tests:
        results.append(
            run_command(
                name=relative_name(test_path),
                milestones=milestones_for(test_path),
                command=[args.python, "-m", "pytest", str(test_path)],
            )
        )

    print_summary(results)
    return 1 if any(result.exit_code != 0 for result in results) else 0


def run_command(name: str, milestones: tuple[str, ...], command: list[str]) -> TestResult:
    """Run one test command and return its result without raising."""

    milestone_label = ", ".join(milestones)
    print(f"\n== Running {name} [{milestone_label}] ==", flush=True)
    started_at = time.perf_counter()
    try:
        completed = subprocess.run(command, cwd=TOOL_ROOT, check=False)
        exit_code = completed.returncode
    except Exception as exc:  # pragma: no cover - defensive command boundary
        print(exc)
        exit_code = 1
    duration_sec = round(time.perf_counter() - started_at, 2)
    return TestResult(
        name=name,
        milestones=milestones,
        exit_code=exit_code,
        duration_sec=duration_sec,
    )


def relative_name(path: Path) -> str:
    """Return a display path relative to the Evaluation Tool root."""

    return str(path.relative_to(TOOL_ROOT))


def milestones_for(path: Path) -> tuple[str, ...]:
    """Return milestone labels for a test file."""

    normalized = path.relative_to(TOOL_ROOT).as_posix()
    return TEST_MILESTONES.get(normalized, ("unmapped",))


def print_summary(results: list[TestResult]) -> None:
    """Print a compact pass/fail table."""

    print("\n== Test Summary ==", flush=True)
    if not results:
        print("No tests discovered.", flush=True)
        return

    name_width = max(len("Test"), *(len(result.name) for result in results))
    milestone_width = max(
        len("Milestones"),
        *(len(", ".join(result.milestones)) for result in results),
    )
    print(
        f"{'Test':<{name_width}}  "
        f"{'Milestones':<{milestone_width}}  "
        "Status  Exit  Seconds",
        flush=True,
    )
    print(
        f"{'-' * name_width}  "
        f"{'-' * milestone_width}  "
        "------  ----  -------",
        flush=True,
    )
    for result in results:
        milestone_label = ", ".join(result.milestones)
        print(
            f"{result.name:<{name_width}}  "
            f"{milestone_label:<{milestone_width}}  "
            f"{result.status:<6}  "
            f"{result.exit_code:<4}  "
            f"{result.duration_sec:>7.2f}",
            flush=True,
        )

    failures = [result for result in results if result.exit_code != 0]
    if failures:
        print(f"\n{len(failures)} test command(s) failed.", flush=True)
    else:
        print("\nAll test commands passed.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
