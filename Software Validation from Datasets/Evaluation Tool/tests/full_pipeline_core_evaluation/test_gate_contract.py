from __future__ import annotations

from app.full_pipeline_core_evaluation import (
    PROMPT4_COMPLETION_MARKER,
    SCOPE_CLASS,
    SCOPE_ID,
)
from app.full_pipeline_core_evaluation.gate import _validate_amendment


def test_synthetic_amendment_enforces_c_only_and_reduced_marker() -> None:
    value = {
        "amendment_id": SCOPE_ID,
        "scope": {"scope_class": SCOPE_CLASS, "total_wall_target_hours": 192},
        "storage_policy": {
            "allowed_drive": "C:\\",
            "other_drives_allowed": False,
            "minimum_free_space_reserve_gib": 35,
        },
        "required_artifact_labels": {
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
        },
        "completion_markers": {"prompt_4": PROMPT4_COMPLETION_MARKER},
    }

    _validate_amendment(value)
