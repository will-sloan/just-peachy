"""Logging setup for CLI runs."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_run_logger(log_path: Path) -> logging.Logger:
    """Create a run-specific logger that writes concise logs to disk."""

    logger = logging.getLogger(f"evaluation_tool.{log_path.parent.parent.name}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

