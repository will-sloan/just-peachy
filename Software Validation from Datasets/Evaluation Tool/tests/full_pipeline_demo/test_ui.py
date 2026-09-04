from __future__ import annotations

from pathlib import Path
import threading
import time

import pytest

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_demo.presets import PresetCatalog
from app.full_pipeline_demo.enrollment import LabelledWav
from app.full_pipeline_demo.state import DemoViewState, RosterParticipant
from app.full_pipeline_demo.ui import (
    BackgroundTaskRunner,
    embedding_inspector_display,
    enrollment_display,
    h2_preset_table_rows,
    merge_selective_replacements,
    parse_optional_duration,
    parse_pace,
    preset_table_rows,
    required_enrollment_take_count,
    roster_display_rows,
    selective_repeat_plan,
)


EVALUATION_ROOT = Path(__file__).resolve().parents[2]


def test_ui_table_exposes_all_presets_and_exactly_six_highlights() -> None:
    matrix = FullPipelineMatrix(
        EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml",
        EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml",
    )
    rows = preset_table_rows(PresetCatalog(matrix))
    assert len(rows) == 18
    assert len([row for row in rows if row.highlighted]) == 6
    assert all("Frozen anchor" in row.status for row in rows if row.highlighted)
    assert all(
        "known-name release off" in row.status
        for row in rows
        if not row.highlighted
    )
    catalog = PresetCatalog(matrix)
    assert required_enrollment_take_count(catalog, rows[0].preset_id) == 3


def test_h2_product_rows_are_primary_giga_then_original_fallback() -> None:
    matrix = FullPipelineMatrix(
        EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml",
        EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml",
    )
    rows = h2_preset_table_rows(PresetCatalog(matrix))
    assert [row.preset_id for row in rows] == [
        "fullpipe_v1_ag_dr_ir",
        "fullpipe_v1_ao_dr_ir",
    ]
    assert rows[0].highlighted and "Primary" in rows[0].status
    assert not rows[1].highlighted and "Fallback" in rows[1].status


def test_embedding_inspector_is_explicitly_raw_and_roster_honors_known_only() -> None:
    state = DemoViewState(
        product_mode="H2_KNOWN_ONLY",
        current_cluster_id="anon_1",
        top1_candidate_display_label="Ada",
        top1_raw_score=0.71,
        top2_raw_score=0.61,
        top1_top2_margin=0.10,
        evidence_duration_sec=2.0,
        identity_quality_status="accepted",
        embedding_backend_id="redimnet2_b2_speaker_embedding",
        embedding_model_id="ReDimNet2-B2",
        embedding_checkpoint_sha256="a" * 64,
        active_roster={
            "anon_1": RosterParticipant(
                "anon_1", "Speaker_1", "anonymous", "cluster_1"
            ),
            "known_1": RosterParticipant(
                "known_1", "Ada", "confirmed", "cluster_2"
            ),
        },
    )
    inspector = embedding_inspector_display(state)
    assert inspector.closest_identity == "Ada"
    assert inspector.top1_raw_score == "0.710"
    assert inspector.margin == "0.100"
    assert "redimnet" in inspector.backend_identity
    assert not hasattr(inspector, "probability")
    assert [row.display_label for row in roster_display_rows(state)] == ["Ada"]


def test_background_runner_is_nonblocking_coalesces_and_callbacks_on_drain() -> None:
    runner = BackgroundTaskRunner()
    release = threading.Event()
    worker_threads: list[int] = []
    callback_threads: list[int] = []
    values: list[object] = []
    caller = threading.get_ident()

    def action() -> object:
        worker_threads.append(threading.get_ident())
        assert release.wait(timeout=1.0)
        return {"ok": True}

    assert runner.submit(
        "session-poll",
        action,
        lambda value: (
            callback_threads.append(threading.get_ident()),
            values.append(value),
        ),
        lambda exc: pytest.fail(str(exc)),
    )
    assert runner.pending("session-poll")
    assert not runner.submit(
        "session-poll", lambda: None, lambda _value: None, lambda _exc: None
    )
    release.set()
    deadline = time.monotonic() + 1.0
    while runner.drain() == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert values == [{"ok": True}]
    assert worker_threads[0] != caller
    assert callback_threads == [caller]
    assert not runner.pending("session-poll")
    runner.close()


def test_background_runner_surfaces_worker_error_only_on_drain() -> None:
    runner = BackgroundTaskRunner()
    errors: list[str] = []
    assert runner.submit(
        "devices",
        lambda: (_ for _ in ()).throw(RuntimeError("device unavailable")),
        lambda _value: pytest.fail("success callback should not run"),
        lambda exc: errors.append(str(exc)),
    )
    deadline = time.monotonic() + 1.0
    while runner.drain() == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert errors == ["device unavailable"]
    runner.close()


def test_ui_numeric_controls_reject_unsafe_values() -> None:
    assert parse_pace("0") == 0.0
    assert parse_pace("1.5") == 1.5
    with pytest.raises(ValueError, match="non-negative"):
        parse_pace("-1")
    assert parse_optional_duration("") is None
    assert parse_optional_duration("4.5") == 4.5
    with pytest.raises(ValueError, match="positive"):
        parse_optional_duration("0")


def test_enrollment_display_keeps_all_qc_and_repeat_diagnostics() -> None:
    display = enrollment_display(
        {
            "state": "repeat_required",
            "takes": [
                {
                    "prompt_id": "prompt_2",
                    "duration_sec": 0.5,
                    "rms_dbfs": -61.2,
                    "peak_dbfs": -50.1,
                    "clipped_fraction": 0.002,
                    "status": "repeat_required",
                    "reason_codes": ["duration_below_minimum", "rms_below_minimum"],
                }
            ],
            "within_enrollment_consistency": 0.2,
            "outlier_take_id": "take_2",
            "repeat_prompt_ids": ["prompt_2"],
            "recommendation_codes": ["repeat_embedding_consistency_outlier"],
            "backend": {
                "backend_id": "wespeaker",
                "model_id": "model-a",
                "model_sha256": "a" * 64,
            },
        }
    )
    assert display.state == "repeat_required"
    assert display.takes[0].duration_sec == 0.5
    assert display.takes[0].rms_dbfs == -61.2
    assert display.takes[0].peak_dbfs == -50.1
    assert display.takes[0].clipped_fraction == 0.002
    assert display.takes[0].reason_codes == (
        "duration_below_minimum",
        "rms_below_minimum",
    )
    assert display.consistency == 0.2
    assert display.outlier_take_id == "take_2"
    assert display.repeat_prompt_ids == ("prompt_2",)
    assert "wespeaker" in display.identity_summary


def test_selective_repeat_retains_passed_takes_and_replaces_only_failed(
    tmp_path: Path,
) -> None:
    payload = {
        "pipeline_id": "fullpipe_v1_ao_dr_ir",
        "speaker_id": "speaker_1",
        "takes": [
            {
                "prompt_id": f"prompt_{index}",
                "prompt_text": f"Prompt {index}",
                "local_audio_path": str(tmp_path / f"accepted_{index}.wav"),
            }
            for index in (1, 2, 3)
        ],
    }
    plan = selective_repeat_plan(
        payload,
        display_label="Amina",
        repeat_prompt_ids=("prompt_2",),
        fallback_pipeline_id="unused",
    )
    assert tuple(plan.retained) == ("prompt_1", "prompt_3")
    replacement = LabelledWav("prompt_2", tmp_path / "replacement.wav")
    merged = merge_selective_replacements(plan, (replacement,))
    assert [row.prompt_id for row in merged] == ["prompt_1", "prompt_2", "prompt_3"]
    assert merged[1].path == replacement.path
    with pytest.raises(ValueError, match="do not match"):
        merge_selective_replacements(
            plan,
            (LabelledWav("prompt_1", tmp_path / "wrong.wav"),),
        )
