from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.h2_portability.platform_support import (
    PORT_REQUIRES_WORK,
    arm64_diagnostic,
    two_gib_budget,
)
from app.h2_portability.contracts import (
    SPATIAL_EVIDENCE_INTERFACE_VERSION,
    XVF_NO_EFFECT_PLACEHOLDER_ID,
)
from app.h2_portability.spatial import NoEffectXVFPlaceholder, SpatialEvidence
from app.h2_product_program.io import canonical_sha256
from app.h2_product_program.reporting import ARM64_PACKAGE_FILES
from scripts.augment_h2_final_package import (
    ARM64_V2_PREFIX,
    build_arm64_deployment_v2,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = TOOL_ROOT / "deployment/h2_arm64"


def test_xvf_placeholder_is_deep_no_effect() -> None:
    source = {"type": "identity", "payload": {"label": "Unknown_1"}}
    result = NoEffectXVFPlaceholder().pass_through_event(
        source, SpatialEvidence(timestamp_sec=1.25, energy=0.4)
    )
    assert result == source
    assert result is not source
    result["payload"]["label"] = "changed"  # type: ignore[index]
    assert source["payload"]["label"] == "Unknown_1"  # type: ignore[index]


def test_xvf_v2_contract_is_complete_canonical_and_no_effect() -> None:
    evidence = SpatialEvidence(
        timestamp_sec=1.25,
        source_clock="xvf_device_monotonic",
        aoa_deg=-23.0,
        aoa_confidence=0.8,
        speech_energy=-18.5,
        speech_activity=True,
        direction_change_deg=11.0,
        beamformer_state={"beam": 2, "locked": True},
        channel_state={"active_channels": [0, 1, 2, 3]},
        available=True,
        quality_flags=("CLOCK_SYNCHRONIZED", "AOA_VALID"),
    )
    payload = evidence.to_jsonable()
    receipt = NoEffectXVFPlaceholder().observe(evidence).to_jsonable()

    assert set(payload) == {
        "timestamp_sec",
        "source_clock",
        "aoa_deg",
        "aoa_confidence",
        "speech_energy",
        "speech_activity",
        "direction_change_deg",
        "beamformer_state",
        "channel_state",
        "available",
        "quality_flags",
    }
    assert payload["available"] is True
    assert receipt["interface_version"] == SPATIAL_EVIDENCE_INTERFACE_VERSION
    assert receipt["implementation_id"] == XVF_NO_EFFECT_PLACEHOLDER_ID
    assert receipt["evidence_available"] is True
    assert receipt["evidence_values_affect_results"] is False
    assert receipt["missing_or_default_evidence_affects_results"] is False
    assert all(
        receipt[key] is False
        for key in (
            "applied_to_audio",
            "applied_to_segmentation",
            "applied_to_clustering",
            "applied_to_identity",
            "applied_to_transcript",
        )
    )


def test_xvf_v1_aliases_remain_compatible_but_serialize_as_v2() -> None:
    evidence = SpatialEvidence(
        timestamp_sec=0.5,
        energy=0.4,
        angle_of_arrival_deg=17.0,
        angle_confidence=0.6,
        direction_change=True,
    )

    assert evidence.speech_energy == 0.4
    assert evidence.aoa_deg == 17.0
    assert evidence.aoa_confidence == 0.6
    assert "energy" not in evidence.to_jsonable()
    assert evidence.to_jsonable()["available"] is False


def test_xvf_v2_rejects_conflicting_legacy_aliases() -> None:
    with pytest.raises(ValueError, match="disagree"):
        SpatialEvidence(timestamp_sec=0.5, aoa_deg=5.0, angle_of_arrival_deg=6.0)


def test_two_gib_budget_is_bounded_but_not_qualification() -> None:
    value = two_gib_budget()
    assert value["allocation_total_mib"] == 2048
    assert value["within_nominal_2gib"] is True
    assert value["qualification_status"] == "DESIGN_BUDGET_ONLY_NOT_HARDWARE_MEASURED"


def test_local_diagnostic_never_claims_arm64_ready() -> None:
    value = arm64_diagnostic(require_linux_arm64=False)
    assert value["status"] == "DIAGNOSTIC_PASS"
    assert value["candidate_classification"] == PORT_REQUIRES_WORK
    assert value["linux_arm64_ready_claimed"] is False


def test_arm64_package_has_pinned_assets_and_no_model_binaries() -> None:
    manifest = json.loads((PACKAGE_ROOT / "asset_manifest.json").read_text("utf-8"))
    assert len(manifest["assets"]) == 6
    assert all(len(row["sha256"]) == 64 for row in manifest["assets"])
    assert not list(PACKAGE_ROOT.glob("*.onnx"))
    assert not list(PACKAGE_ROOT.glob("*.pt"))


def test_arm64_package_scripts_are_fail_closed_and_documented() -> None:
    installer = (PACKAGE_ROOT / "install_linux_arm64.sh").read_text("utf-8")
    service = (PACKAGE_ROOT / "run_h2_service.sh").read_text("utf-8")
    docker = (PACKAGE_ROOT / "Dockerfile.arm64").read_text("utf-8")
    assert "set -euo pipefail" in installer
    assert "--only-binary=:all:" in installer
    assert "DownloadModels" not in installer + service
    assert "validate_arm64_package.py" in service
    assert "JP_H2_REDIM_ONNX" in service
    assert "JP_H2_SEGMENTATION_ONNX" in service
    source_payloads = {}
    component_rows = {}
    for name in ARM64_PACKAGE_FILES:
        member = f"deployment/h2_arm64/{name}"
        payload = (PACKAGE_ROOT / name).read_bytes()
        source_payloads[member] = payload
        component_rows[
            f"Software Validation from Datasets/Evaluation Tool/{member}"
        ] = hashlib.sha256(payload).hexdigest()
    source_payloads["protocol/runtime_implementation_identity.json"] = (
        json.dumps(
            {
                "schema_version": "h2-runtime-implementation-identity.v2",
                "identity_sha256": "fixture",
                "components": {
                    "h2_arm64_deployment_bundle": canonical_sha256(
                        component_rows
                    )
                },
            }
        ).encode("utf-8")
    )
    v2, provenance = build_arm64_deployment_v2(source_payloads)
    systemd_v2 = v2[f"{ARM64_V2_PREFIX}h2-pipeline.service"].decode("utf-8")
    installer_v2 = v2[f"{ARM64_V2_PREFIX}install_linux_arm64.sh"].decode(
        "utf-8"
    )
    assert (
        'WorkingDirectory="/opt/just-peachy/Software Validation from '
        'Datasets/Evaluation Tool"' in systemd_v2
    )
    assert (
        'ExecStart="/opt/just-peachy/Software Validation from Datasets/'
        'Evaluation Tool/deployment/h2_arm64_v2/run_h2_service.sh"' in systemd_v2
    )
    assert installer_v2.count("${PIP_SOURCE[@]}") == 2
    assert provenance["scientific_runtime_or_policy_changed"] is False
    assert provenance["arm64_hardware_validated"] is False
    assert "--platform=linux/arm64" in docker
    assert (PACKAGE_ROOT / "README.md").is_file()
    assert (TOOL_ROOT / "app/h2_portability/README.md").is_file()


def test_h2_operator_runbook_uses_component_native_onnx_environments() -> None:
    readme = (TOOL_ROOT / "app/h2_product_program/README.md").read_text(
        encoding="utf-8"
    )

    assert ".stage8-envs\\redimnet2\\Scripts\\python.exe" in readme
    assert (
        ".stage8-envs\\credential-diarization\\Scripts\\python.exe" in readme
    )
    assert (
        "& $RedimPython -m app.h2_portability export --component "
        "redimnet2_b2_speaker_embedding"
    ) in readme
    assert (
        "& $SegmentationPython -m app.h2_portability export --component "
        "pyannote_segmentation_3_0"
    ) in readme
    assert "$Python -m app.h2_portability export" not in readme
