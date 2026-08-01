from __future__ import annotations

from pathlib import Path

import pytest

from scripts.qualify_speech_components import (
    COMPONENT_ROOT,
    QualificationResult,
    _assert_permitted_asr,
    _atomic_write_json,
    _component_fragments,
    _config_with_components,
    _read_component_fragment,
    _summary,
)


def test_every_runnable_asr_fragment_obeys_whisper_safety_policy() -> None:
    fragments = _component_fragments("asr")

    for path in fragments:
        _assert_permitted_asr(_read_component_fragment(path), path)

    assert {path.name for path in fragments} == {
        "faster_whisper.yaml",
        "sherpa_onnx.yaml",
        "vosk.yaml",
        "wenet.yaml",
        "whisper_base.yaml",
        "whisper_small.yaml",
        "whisper_tiny.yaml",
    }


@pytest.mark.parametrize("model_size", ["medium", "large-v3", "large-v3-turbo"])
def test_qualification_hard_rejects_prohibited_whisper_sizes(model_size: str) -> None:
    component = {
        "name": "whisper_candidate",
        "params": {"model_size": model_size},
    }

    with pytest.raises(RuntimeError, match="prohibited Whisper model"):
        _assert_permitted_asr(component, Path(f"whisper_{model_size}.yaml"))


def test_asr_qualification_config_uses_full_record_and_disables_unrelated_slots() -> None:
    asr = _read_component_fragment(COMPONENT_ROOT / "asr" / "vosk.yaml")

    config = _config_with_components(asr=asr)

    assert config.components["asr"].enabled is True
    assert config.components["asr"].name == "vosk"
    assert config.components["segmentation"].enabled is False
    assert config.components["vad"].enabled is False
    assert config.components["diarization"].enabled is False
    assert config.components["speaker_embedding"].enabled is False
    assert config.components["speaker_matching"].enabled is False
    assert config.runtime.dry_run is False
    assert config.runtime.allow_model_downloads is False


def test_qualification_summary_distinguishes_unavailable_from_failed() -> None:
    results = [
        QualificationResult("a", "asr", "a", "qualified", 0.1, {}),
        QualificationResult("b", "asr", "b", "unavailable", 0.1, {}, "token"),
        QualificationResult("c", "asr", "c", "failed", 0.1, {}, "bug"),
    ]

    assert _summary(results) == {
        "total": 3,
        "qualified": 1,
        "unavailable": 1,
        "failed": 1,
        "all_qualified": False,
    }


def test_qualification_json_write_is_atomic_and_replaces_existing_file(
    tmp_path: Path,
) -> None:
    output = tmp_path / "qualification.json"
    output.write_text("stale", encoding="utf-8")

    _atomic_write_json(output, {"status": "qualified"})

    assert output.read_text(encoding="utf-8") == '{\n  "status": "qualified"\n}\n'
    assert not (tmp_path / ".qualification.json.tmp").exists()
