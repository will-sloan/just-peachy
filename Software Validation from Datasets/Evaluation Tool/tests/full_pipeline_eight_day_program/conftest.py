from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import pytest


TOOL_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def canonical_program_tmp_path() -> Path:
    """Create a disposable test root beneath the canonical Evaluation Tool root."""

    base = TOOL_ROOT / "automated_runs/_full_pipeline_eight_day_program_tests"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="synthetic_", dir=base))
    try:
        yield path
    finally:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(base.resolve(strict=True)):
            raise AssertionError(f"Refusing unsafe synthetic test cleanup: {resolved}")
        shutil.rmtree(resolved)
