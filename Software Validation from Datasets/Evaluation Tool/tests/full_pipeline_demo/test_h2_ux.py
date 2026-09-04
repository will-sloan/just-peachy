from __future__ import annotations

import pytest

from app.full_pipeline_demo.h2_ux import (
    H2_DEFAULT_PRODUCT_MODE,
    H2_PIPELINE_IDS,
    H2_PRODUCT_MODE_IDS,
    h2_mode_display_values,
    h2_mode_id_from_display,
    h2_pipeline_role,
    h2_product_mode,
    require_h2_pipeline_id,
)


def test_h2_modes_are_exact_complete_and_round_trip_ui_labels() -> None:
    assert H2_PRODUCT_MODE_IDS == (
        "H2_KNOWN_ONLY",
        "H2_SESSION_ANONYMOUS",
        "H2_SESSION_MEMORY_ENHANCED",
    )
    assert H2_DEFAULT_PRODUCT_MODE == "H2_SESSION_MEMORY_ENHANCED"
    displays = h2_mode_display_values()
    assert len(displays) == 3 and len(set(displays)) == 3
    assert tuple(h2_mode_id_from_display(value) for value in displays) == (
        H2_PRODUCT_MODE_IDS
    )
    assert h2_product_mode(H2_DEFAULT_PRODUCT_MODE).session_memory
    with pytest.raises(ValueError, match="unsupported H2 product mode"):
        h2_product_mode("best-effort")


def test_h2_pipeline_roles_reject_non_h2_matrix_rows() -> None:
    assert H2_PIPELINE_IDS == (
        "fullpipe_v1_ag_dr_ir",
        "fullpipe_v1_ao_dr_ir",
    )
    assert h2_pipeline_role(H2_PIPELINE_IDS[0]) == "PRIMARY"
    assert h2_pipeline_role(H2_PIPELINE_IDS[1]) == "FALLBACK_REFERENCE"
    with pytest.raises(ValueError, match="accepts only AG-H2 primary"):
        require_h2_pipeline_id("fullpipe_v1_ag_dr_ie")
