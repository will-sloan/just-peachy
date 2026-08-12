from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.extended_backends.contracts import (
    QUALIFICATION_STATUSES,
    validate_environment_profiles,
    validate_model_asset_registry,
    validate_qualification_payload,
)
from app.extended_backends.qualification import (
    _configured_fragment,
    _exception_status,
    _preflight_status,
    _qualify_vad,
    qualify_profile,
)
from app.extended_backends.registry import (
    REPOSITORY_ROOT,
    TOOL_ROOT,
    inspect_asset,
    load_backend_catalog,
    load_environment_profiles,
    load_model_asset_registry,
)
from app.extended_backends.reporting import consolidate_qualification_results


def test_environment_profile_schema_and_required_profiles() -> None:
    payload = load_environment_profiles()
    validate_environment_profiles(payload)
    assert {
        "core-cpu",
        "core-cuda",
        "extended-local",
        "onnx",
        "wenet",
        "wespeaker",
        "credential-diarization",
        "nemo-linux-cuda",
        "edge-cpu",
    } <= set(payload["profiles"])


def test_model_asset_registry_schema_and_identity_fields() -> None:
    payload = load_model_asset_registry()
    validate_model_asset_registry(payload)
    asset = payload["assets"]["vosk_small_en_us_0_15"]
    assert asset["expected_sha256"] == (
        "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"
    )
    assert asset["environment_profile"] == "extended-local"


def test_asset_detection_distinguishes_missing_from_corrupt() -> None:
    registry = load_model_asset_registry()
    asset = inspect_asset("vosk_small_en_us_0_15", registry)
    assert asset["verification_status"] in {"missing", "verified"}
    assert isinstance(asset["present"], bool)
    assert "sha256" in asset


def test_credential_status_never_requires_reading_value(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = {
        "id": "gated",
        "platforms": ["Windows", "Linux", "Darwin"],
        "licence_ack_env": "PYANNOTE_LICENSE_ACCEPTED",
        "credential_env": "PYANNOTE_AUTH_TOKEN",
    }
    monkeypatch.delenv("PYANNOTE_LICENSE_ACCEPTED", raising=False)
    monkeypatch.setenv("PYANNOTE_AUTH_TOKEN", "do-not-serialize-this-value")
    status = _preflight_status(definition, {}, [], "cpu")
    assert status is not None
    assert status[0] == "licence_action_required"
    assert "do-not-serialize" not in status[1]


def test_unavailable_package_and_asset_are_distinct() -> None:
    definition = {"id": "backend", "platforms": ["Windows", "Linux", "Darwin"]}
    missing_package = _preflight_status(definition, {"not-installed": None}, [], "cpu")
    assert missing_package and missing_package[0] == "unavailable_package"
    missing_asset = _preflight_status(
        definition,
        {"installed": "1.0"},
        [{"asset_id": "model", "present": False}],
        "cpu",
    )
    assert missing_asset and missing_asset[0] == "unavailable_asset"


def test_runtime_and_contract_failure_classification() -> None:
    assert _exception_status(RuntimeError("backend crashed")) == "runtime_failure"
    assert _exception_status(ValueError("invalid output")) == "contract_failure"


def test_qualification_consolidation_detects_complete_coverage(tmp_path: Path) -> None:
    result_root = tmp_path / "results"
    result_root.mkdir()
    profiles = ("profile-a", "profile-b")
    for profile, backend in zip(profiles, ("backend-a", "backend-b"), strict=True):
        payload = {
            "schema_version": "extended-backend-qualification.v1",
            "generated_at": "2026-08-07T00:00:00+00:00",
            "profile": profile,
            "environment": {"python": "3.12"},
            "secret_audit": {
                "values_serialized": False,
                "credential_presence_only": True,
            },
            "summary": {"total": 1},
            "results": [
                {
                    "backend_id": backend,
                    "family": "asr",
                    "profile": profile,
                    "status": "qualified" if backend == "backend-a" else "deferred",
                    "explanation": "fixture",
                    "package_versions": {},
                    "asset_identities": [],
                    "device": "cpu",
                    "schema_validation": backend == "backend-a",
                    "timing": {},
                    "warnings": [],
                    "failure_category": None,
                    "command": "python qualifier.py",
                }
            ],
        }
        (result_root / f"{profile}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    output = result_root / "summary.json"
    payload = consolidate_qualification_results(
        result_root=result_root,
        output_path=output,
        profile_names=profiles,
        expected_backend_ids={"backend-a", "backend-b"},
    )

    assert payload["summary"] == {
        "total": 2,
        "qualified_real_output": 1,
        "not_qualified": 1,
        "status_counts": {"deferred": 1, "qualified": 1},
        "coverage_complete": True,
    }
    assert output.is_file()
    assert output.with_suffix(".json.sha256").is_file()


def test_component_identity_and_no_implicit_download() -> None:
    definition = next(
        item
        for item in load_backend_catalog()["backends"]
        if item["id"] == "faster_whisper"
    )
    fragment = _configured_fragment(definition, "cpu")
    assert fragment["params"]["allow_model_downloads"] is False
    config_path = TOOL_ROOT / definition["config"]
    assert config_path.is_file()
    assert definition["config"].endswith("faster_whisper.yaml")


def test_device_selection_is_explicit() -> None:
    definition = next(
        item
        for item in load_backend_catalog()["backends"]
        if item["id"] == "faster_whisper"
    )
    assert _configured_fragment(definition, "cpu")["params"]["device"] == "cpu"
    assert _configured_fragment(definition, "cuda")["params"]["device"] == "cuda"


def test_credential_gated_output_schema_and_secret_redaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "stage8-secret-sentinel-never-write"
    monkeypatch.delenv("PYANNOTE_LICENSE_ACCEPTED", raising=False)
    monkeypatch.delenv("PICOVOICE_LICENSE_ACCEPTED", raising=False)
    monkeypatch.setenv("PYANNOTE_AUTH_TOKEN", secret)
    destination = tmp_path / "qualification.json"
    payload = qualify_profile("credential-diarization", output_path=destination)
    validate_qualification_payload(payload)
    serialized = destination.read_text(encoding="utf-8")
    assert secret not in serialized
    assert payload["secret_audit"]["values_serialized"] is False
    assert all(result["status"] in QUALIFICATION_STATUSES for result in payload["results"])


def test_vad_adapter_contract_and_chunker_composition() -> None:
    definition = {
        "id": "energy_contract_control",
        "family": "vad",
        "profile": "test",
        "config": "configs/inference/components/vad/energy.yaml",
    }
    audio = (
        REPOSITORY_ROOT
        / "Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic/"
        "cmu_us_aew_arctic/wav/arctic_b0476.wav"
    )
    if not audio.is_file():
        pytest.skip("local real qualification audio is unavailable")
    details = _qualify_vad(definition, audio, 2, "cpu")
    assert details["bounded"] is True
    assert details["monotonic_nonoverlapping"] is True
    assert details["vad_chunker_compatible"] is True
    assert details["pipeline_composition"] is True


@pytest.mark.skipif(
    importlib.util.find_spec("webrtcvad") is None,
    reason="authorized WebRTC VAD profile is not installed in this interpreter",
)
def test_real_webrtc_qualification_when_installed() -> None:
    definition = next(
        item
        for item in load_backend_catalog()["backends"]
        if item["id"] == "webrtc_vad"
    )
    audio = (
        REPOSITORY_ROOT
        / "Software Validation from Datasets/Raw Datasets (Not formatted)/CMU Arctic/"
        "cmu_us_aew_arctic/wav/arctic_b0476.wav"
    )
    details = _qualify_vad(definition, audio, 2, "cpu")
    assert details["region_count"] > 0


def test_catalog_has_one_status_path_for_every_required_backend() -> None:
    catalog = load_backend_catalog()
    required = {
        "faster_whisper",
        "sherpa_onnx_asr",
        "vosk",
        "wenet",
        "webrtc_vad",
        "sherpa_onnx_vad",
        "resemblyzer",
        "wespeaker",
        "sherpa_onnx_speaker_embedding",
        "pyannote_community",
        "sherpa_onnx_diarization",
        "picovoice_falcon",
        "nemo_diarization",
    }
    assert required <= {item["id"] for item in catalog["backends"]}
    assert {
        "moonshine_streaming_tiny",
        "moonshine_streaming_small",
        "moonshine_streaming_medium",
        "sherpa_onnx_streaming_zipformer_20m_int8",
        "fsmn_vad",
        "campplus_speaker_embedding",
        "eres2net_base_speaker_embedding",
    } <= {item["id"] for item in catalog["backends"]}


def test_schema_documents_are_valid_json() -> None:
    schema_root = TOOL_ROOT / "configs" / "automated_evaluation" / "schemas"
    for name in (
        "environment_profiles.stage8.v1.schema.json",
        "model_asset_registry.v1.schema.json",
        "extended_backend_qualification.v1.schema.json",
    ):
        assert json.loads((schema_root / name).read_text(encoding="utf-8"))["$schema"]
