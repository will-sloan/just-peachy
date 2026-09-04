from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.resolve_h2_arm64_wheels import (
    Arm64WheelResolutionError,
    _sign,
    _wheel_inventory,
    build_receipt,
    validate_receipt,
)


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "protocol_manifest.json").write_text(
        json.dumps({"protocol_id": "h2_protocol"}), encoding="utf-8"
    )
    (workspace / "runtime_implementation_identity.json").write_text(
        json.dumps(
            {
                "schema_version": "h2-runtime-implementation-identity.v2",
                "identity_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )
    return workspace


def test_wheel_inventory_rejects_source_distributions(tmp_path: Path) -> None:
    (tmp_path / "example-1.0.tar.gz").write_bytes(b"source")
    with pytest.raises(Arm64WheelResolutionError, match="non-wheel"):
        _wheel_inventory(tmp_path)


def test_receipt_build_and_validation_bind_workspace_and_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    requirements = tmp_path / "requirements-linux-arm64.txt"
    requirements.write_text("one==1.0\ntwo==2.0\n", encoding="utf-8")
    resolver = Path(__file__).resolve().parents[1] / "scripts/resolve_h2_arm64_wheels.py"
    monkeypatch.setattr(
        "scripts.resolve_h2_arm64_wheels.DEFAULT_REQUIREMENTS", requirements.resolve()
    )
    monkeypatch.setattr("scripts.resolve_h2_arm64_wheels.__file__", str(resolver))
    wheels = (
        {"filename": "one-1.0-py3-none-any.whl", "sha256": "1" * 64, "bytes": 11},
        {"filename": "two-2.0-py3-none-any.whl", "sha256": "2" * 64, "bytes": 13},
    )
    receipt = build_receipt(
        workspace=workspace,
        requirements=requirements,
        wheels=wheels,
        pip_version="pip fixture",
    )
    output = workspace / "storage_maintenance/arm64_wheel_resolution_receipt.json"
    output.parent.mkdir()
    output.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    observed = validate_receipt(
        output, workspace=workspace, requirements=requirements
    )
    assert observed["receipt_sha256"] == receipt["receipt_sha256"]
    assert observed["resolution"]["resolved_logical_bytes"] == 24
    assert observed["qualification_boundary"]["raspberry_pi_hardware_ready_claimed"] is False


def test_receipt_validation_rejects_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    requirements = tmp_path / "requirements-linux-arm64.txt"
    requirements.write_text("one==1.0\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.resolve_h2_arm64_wheels.DEFAULT_REQUIREMENTS", requirements.resolve()
    )
    receipt = build_receipt(
        workspace=workspace,
        requirements=requirements,
        wheels=(
            {
                "filename": "one-1.0-py3-none-any.whl",
                "sha256": "1" * 64,
                "bytes": 11,
            },
        ),
        pip_version="pip fixture",
    )
    receipt["resolution"]["resolved_logical_bytes"] = 999
    output = workspace / "storage_maintenance/arm64_wheel_resolution_receipt.json"
    output.parent.mkdir()
    output.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(Arm64WheelResolutionError, match="signature"):
        validate_receipt(output, workspace=workspace, requirements=requirements)


def test_signature_is_deterministic() -> None:
    left = _sign({"schema_version": "fixture", "value": [2, 1]})
    right = _sign({"value": [2, 1], "schema_version": "fixture"})
    assert left["receipt_sha256"] == right["receipt_sha256"]
