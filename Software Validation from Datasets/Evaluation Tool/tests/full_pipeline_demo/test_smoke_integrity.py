from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.full_pipeline_demo.smoke import (
    _useful_labelled_attribution,
    _validate_immutable_transition,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_useful_labelled_attribution_requires_timing_speaker_and_alignment(
    tmp_path: Path,
) -> None:
    path = tmp_path / "labelled.jsonl"
    _write_jsonl(
        path,
        [
            {
                "span_index": 1,
                "start_sec": None,
                "end_sec": None,
                "anonymous_speaker_id": None,
                "speaker_label": "Unassigned",
                "alignment_status": "timestamp_resolution_insufficient",
            },
            {
                "span_index": 2,
                "start_sec": 0.25,
                "end_sec": 1.5,
                "anonymous_speaker_id": "anon_0001",
                "speaker_label": "Local Smoke Speaker",
                "alignment_status": "aligned",
            },
        ],
    )

    assert _useful_labelled_attribution(path) == {
        "span_index": 2,
        "start_sec": 0.25,
        "end_sec": 1.5,
        "anonymous_speaker_id": "anon_0001",
        "speaker_label": "Local Smoke Speaker",
        "alignment_status": "aligned",
    }


@pytest.mark.parametrize(
    "mutation",
    (
        {"start_sec": None},
        {"end_sec": None},
        {"end_sec": 0.0},
        {"anonymous_speaker_id": None},
        {"speaker_label": "Unassigned"},
        {"alignment_status": "evidence_insufficient"},
    ),
)
def test_useful_labelled_attribution_rejects_weak_rows(
    tmp_path: Path,
    mutation: dict[str, object],
) -> None:
    path = tmp_path / "labelled.jsonl"
    row: dict[str, object] = {
        "span_index": 1,
        "start_sec": 0.0,
        "end_sec": 1.0,
        "anonymous_speaker_id": "anon_0001",
        "speaker_label": "Unknown_1",
        "alignment_status": "aligned",
    }
    row.update(mutation)
    _write_jsonl(path, [row])

    with pytest.raises(RuntimeError, match="timed, attributed"):
        _useful_labelled_attribution(path)


def test_immutable_transition_requires_predecessor_and_component_change() -> None:
    transition = _validate_immutable_transition(
        started={
            "session_id": "session-2",
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "output_root": "C:/runs/session-2",
            "predecessor_session_id": "session-1",
        },
        previous_pipeline="fullpipe_v1_ag_dr_ie",
        previous_session_id="session-1",
        previous_output_root="C:/runs/session-1",
        previous_component_ids={
            "asr": "sherpa_giga",
            "speaker_embedding": "speechbrain_ecapa",
        },
        current_component_ids={
            "asr": "sherpa_giga",
            "speaker_embedding": "redimnet2",
        },
        previous_state="completed",
        previous_joined=True,
    )

    assert transition is not None
    assert transition["predecessor_session_id"] == "session-1"
    assert transition["changed_component_families"] == ["speaker_embedding"]

    with pytest.raises(RuntimeError, match="predecessor"):
        _validate_immutable_transition(
            started={
                "session_id": "session-2",
                "pipeline_id": "fullpipe_v1_ag_dr_ir",
                "output_root": "C:/runs/session-2",
                "predecessor_session_id": None,
            },
            previous_pipeline="fullpipe_v1_ag_dr_ie",
            previous_session_id="session-1",
            previous_output_root="C:/runs/session-1",
            previous_component_ids={"speaker_embedding": "speechbrain_ecapa"},
            current_component_ids={"speaker_embedding": "redimnet2"},
            previous_state="completed",
            previous_joined=True,
        )
