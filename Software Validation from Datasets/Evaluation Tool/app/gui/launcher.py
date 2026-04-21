"""Sequential GUI batch launcher that reuses the existing CLI pipeline."""

from __future__ import annotations

import queue
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.gui.state import GuiRunConfig, build_cli_commands


LineCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int, str], None]
DoneCallback = Callable[[bool, str], None]


@dataclass(frozen=True)
class BatchLaunchResult:
    """Summary of a completed GUI batch."""

    success: bool
    message: str
    commands_run: int


class BatchLauncher:
    """Launch one or more dataset runs sequentially through the existing CLI."""

    def __init__(
        self,
        tool_root: Path,
        python_executable: str | None = None,
    ) -> None:
        self.tool_root = tool_root
        self.python_executable = python_executable

    def build_commands(self, config: GuiRunConfig) -> list[list[str]]:
        """Return commands this launcher would execute."""

        return build_cli_commands(config, self.tool_root, self.python_executable)

    def run_batch(
        self,
        config: GuiRunConfig,
        on_line: LineCallback | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> BatchLaunchResult:
        """Run all configured dataset commands sequentially."""

        commands = self.build_commands(config)
        total = len(commands)
        warning_datasets: list[str] = []
        for index, command in enumerate(commands, start=1):
            dataset_key = _dataset_from_command(command)
            missing_predictions = 0
            if on_progress:
                on_progress(index - 1, total, f"Starting {dataset_key}")
            if on_line:
                on_line("$ " + subprocess.list2cmdline(command))
            process = subprocess.Popen(
                command,
                cwd=self.tool_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert process.stdout is not None
            for line in process.stdout:
                missing_predictions = max(missing_predictions, _missing_count_from_line(line))
                if on_line:
                    on_line(line.rstrip())
            return_code = process.wait()
            if return_code != 0:
                message = f"{dataset_key} failed with exit code {return_code}"
                if on_progress:
                    on_progress(index, total, message)
                return BatchLaunchResult(False, message, index)
            if missing_predictions:
                warning_datasets.append(f"{dataset_key} ({missing_predictions} missing prediction(s))")
            if on_progress:
                if missing_predictions:
                    on_progress(index, total, f"Finished {dataset_key} with warnings")
                else:
                    on_progress(index, total, f"Finished {dataset_key}")
        if warning_datasets:
            return BatchLaunchResult(
                True,
                f"Completed {total} run(s); warnings: " + ", ".join(warning_datasets),
                total,
            )
        return BatchLaunchResult(True, f"Completed {total} run(s)", total)

    def run_batch_async(
        self,
        config: GuiRunConfig,
        event_queue: "queue.Queue[tuple[str, object]]",
    ) -> threading.Thread:
        """Run a batch in a background thread and post events to a queue."""

        def worker() -> None:
            try:
                result = self.run_batch(
                    config,
                    on_line=lambda line: event_queue.put(("line", line)),
                    on_progress=lambda done, total, msg: event_queue.put(
                        ("progress", (done, total, msg))
                    ),
                )
            except Exception as exc:  # pragma: no cover - GUI boundary
                event_queue.put(("done", BatchLaunchResult(False, str(exc), 0)))
            else:
                event_queue.put(("done", result))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return thread


def _dataset_from_command(command: list[str]) -> str:
    if "--dataset" in command:
        index = command.index("--dataset")
        if index + 1 < len(command):
            return command[index + 1]
    return "dataset"


def _missing_count_from_line(line: str) -> int:
    """Extract final missing-prediction counts from CLI progress lines."""

    matches = re.findall(r"\bmissing=(\d+)\b", line)
    if matches:
        return int(matches[-1])
    matches = re.findall(r"Missing predictions:\s*`?(\d+)`?", line, flags=re.IGNORECASE)
    if matches:
        return int(matches[-1])
    return 0
