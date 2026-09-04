from __future__ import annotations

from collections import Counter, defaultdict

import pytest

from app.full_pipeline_bounded_development import orchestration
from app.full_pipeline_bounded_development.selection import (
    BoundedSelectionError,
    build_selection_manifest,
)


EXPECTED_SELECTION_SHA256 = "b7ce90b70b2c3f4a3cbec76ff42d286757b77de42fd503f9f7b11f39d2a2b1d4"


def _rows() -> tuple[dict[str, object], ...]:
    return orchestration._development_rows()  # noqa: SLF001


def test_fixed_panel_is_balanced_and_pinned() -> None:
    value = build_selection_manifest(_rows())

    assert value["selected_case_count"] == 180
    assert value["excluded_case_count"] == 627
    assert value["selection_seed"] == 5107
    assert value["selection_identity_sha256"] == EXPECTED_SELECTION_SHA256
    assert value["scope_class"] == "BOUNDED_REDUCED"
    assert value["original_full_scope_complete"] is False
    coverage = value["achieved_coverage"]
    assert coverage["source_case_counts"] == {
        "controlled_v1": 72,
        "product_v2": 108,
    }
    assert coverage["source_unique_audio_counts"] == {
        "controlled_v1": 24,
        "product_v2": 36,
    }
    assert coverage["overlay_counts"] == {
        "ALL_KNOWN": 60,
        "ALL_UNKNOWN": 60,
        "MIXED_KNOWN_UNKNOWN": 60,
    }
    assert coverage["gallery_requested_counts"] == {
        "1": 12,
        "10": 12,
        "2": 12,
        "20": 12,
        "5": 12,
        "50": 12,
        "full": 36,
        "source_full": 72,
    }


def test_product_keeps_every_audio_with_three_truth_overlays_and_full_gallery() -> None:
    value = build_selection_manifest(_rows())
    product = [
        row
        for row in value["selected_case_inventory"]
        if row["source_key"] == "product_v2"
    ]
    by_audio: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in product:
        by_audio[str(row["pcm_sha256"])].append(row)

    assert len(by_audio) == 36
    for rows in by_audio.values():
        assert len(rows) == 3
        assert {row["overlay_id"] for row in rows} == {
            "ALL_KNOWN",
            "ALL_UNKNOWN",
            "MIXED_KNOWN_UNKNOWN",
        }
        assert Counter(row["gallery_requested_size"] for row in rows)["full"] == 1


def test_selection_is_independent_of_input_order() -> None:
    rows = _rows()
    forward = build_selection_manifest(rows)
    reverse = build_selection_manifest(tuple(reversed(rows)))

    assert reverse == forward


def test_selector_rejects_held_out_row_before_sampling() -> None:
    rows = list(_rows())
    rows[0] = {**rows[0], "partition": "evaluation"}

    with pytest.raises(BoundedSelectionError, match="held-out/evaluation"):
        build_selection_manifest(rows)
