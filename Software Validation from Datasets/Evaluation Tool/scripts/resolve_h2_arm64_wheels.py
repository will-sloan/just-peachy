"""Resolve and inventory the exact binary-only H2 Linux ARM64 wheel set.

The resolver downloads wheels into a temporary directory below the selected H2
workspace on C:, hashes the complete direct/transitive set, removes every wheel,
and only then publishes a signed, payload-free receipt.  It never installs a
package, downloads a model, or edits scientific runtime/configuration state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = (
    TOOL_ROOT / "automated_runs/h2_complete_product_pipeline_v17"
).resolve()
DEFAULT_REQUIREMENTS = (
    TOOL_ROOT / "deployment/h2_arm64/requirements-linux-arm64.txt"
).resolve()
DEFAULT_OUTPUT_RELATIVE = Path(
    "storage_maintenance/arm64_wheel_resolution_receipt.json"
)
REQUIREMENTS_MEMBER = "deployment/h2_arm64/requirements-linux-arm64.txt"
INDEX_URL = "https://pypi.org/simple"
PLATFORM_TAGS = (
    "manylinux_2_28_aarch64",
    "manylinux2014_aarch64",
    "manylinux_2_17_aarch64",
    "any",
)
ABIS = ("cp312", "abi3", "none")
SCHEMA_VERSION = "h2-arm64-wheel-resolution-receipt.v1"
SIGNATURE_KEY = "receipt_sha256"


class Arm64WheelResolutionError(RuntimeError):
    """Raised when an exact, binary-only target resolution cannot be proven."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sign(document: Mapping[str, object]) -> dict[str, object]:
    value = dict(document)
    value[SIGNATURE_KEY] = _sha256_bytes(_canonical_bytes(value))
    return value


def _validate_signature(document: Mapping[str, object]) -> None:
    unsigned = dict(document)
    observed = unsigned.pop(SIGNATURE_KEY, None)
    expected = _sha256_bytes(_canonical_bytes(unsigned))
    if observed != expected:
        raise Arm64WheelResolutionError("ARM64 wheel receipt signature differs")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _require_c_drive(path: Path, *, label: str) -> Path:
    resolved = path.resolve(strict=False)
    if os.name == "nt" and resolved.drive.casefold() != "c:":
        raise Arm64WheelResolutionError(f"{label} must remain on C: ({resolved})")
    return resolved


def _read_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Arm64WheelResolutionError(f"cannot read {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Arm64WheelResolutionError(f"{label} is not a JSON object: {path}")
    return value


def _direct_requirements(payload: bytes) -> tuple[str, ...]:
    rows = tuple(
        line.strip()
        for line in payload.decode("utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not rows or any("==" not in row for row in rows):
        raise Arm64WheelResolutionError(
            "ARM64 requirements must contain exact non-empty pins"
        )
    return rows


def _workspace_bindings(workspace: Path) -> tuple[str, str]:
    protocol = _read_object(workspace / "protocol_manifest.json", label="protocol")
    runtime = _read_object(
        workspace / "runtime_implementation_identity.json", label="runtime identity"
    )
    protocol_id = str(protocol.get("protocol_id") or "")
    runtime_sha = str(runtime.get("identity_sha256") or "")
    if not protocol_id or not re.fullmatch(r"[0-9a-f]{64}", runtime_sha):
        raise Arm64WheelResolutionError("workspace protocol/runtime binding is invalid")
    return protocol_id, runtime_sha


def _pip_version(python: Path) -> str:
    completed = subprocess.run(
        [str(python), "-m", "pip", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _download_command(
    *, python: Path, requirements: Path, destination: Path
) -> list[str]:
    command = [
        str(python),
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--dest",
        str(destination),
        "--requirement",
        str(requirements),
        "--only-binary=:all:",
        "--implementation",
        "cp",
        "--python-version",
        "3.12",
        "--index-url",
        INDEX_URL,
    ]
    for abi in ABIS:
        command.extend(("--abi", abi))
    for platform in PLATFORM_TAGS:
        command.extend(("--platform", platform))
    return command


def _wheel_inventory(directory: Path) -> tuple[dict[str, object], ...]:
    children = tuple(sorted(directory.iterdir(), key=lambda path: path.name.casefold()))
    unexpected = tuple(path.name for path in children if path.suffix.casefold() != ".whl")
    if unexpected:
        raise Arm64WheelResolutionError(
            f"binary-only resolution produced non-wheel payloads: {unexpected}"
        )
    wheels = tuple(path for path in children if path.is_file())
    if not wheels:
        raise Arm64WheelResolutionError("binary-only ARM64 resolution returned no wheels")
    names: set[str] = set()
    rows: list[dict[str, object]] = []
    for wheel in wheels:
        name = wheel.name
        if PurePosixPath(name).name != name or name in names:
            raise Arm64WheelResolutionError("ARM64 wheel filenames are invalid/duplicate")
        names.add(name)
        size = wheel.stat().st_size
        if size <= 0:
            raise Arm64WheelResolutionError(f"ARM64 wheel is empty: {name}")
        rows.append({"filename": name, "sha256": _sha256_file(wheel), "bytes": size})
    return tuple(rows)


def build_receipt(
    *,
    workspace: Path,
    requirements: Path,
    wheels: Sequence[Mapping[str, object]],
    pip_version: str,
) -> dict[str, object]:
    """Build and sign a payload-free receipt from a verified wheel directory."""

    workspace = _require_c_drive(workspace, label="workspace")
    requirements = requirements.resolve(strict=True)
    if requirements != DEFAULT_REQUIREMENTS:
        raise Arm64WheelResolutionError(
            f"requirements path differs from frozen ARM64 input: {requirements}"
        )
    requirements_payload = requirements.read_bytes()
    direct = _direct_requirements(requirements_payload)
    protocol_id, runtime_sha = _workspace_bindings(workspace)
    normalized = tuple(dict(row) for row in wheels)
    if len(normalized) < len(direct):
        raise Arm64WheelResolutionError(
            "resolved wheel set is smaller than the direct dependency set"
        )
    total = sum(int(row.get("bytes") or 0) for row in normalized)
    if total <= 0:
        raise Arm64WheelResolutionError("resolved wheel inventory has no bytes")
    return _sign(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "PASS_RESOLVED_EXACT_ARM64_BINARY_SET",
            "protocol_id": protocol_id,
            "runtime_implementation_sha256": runtime_sha,
            "scientific_runtime_or_configuration_edited": False,
            "source": {
                "requirements_path": REQUIREMENTS_MEMBER,
                "requirements_sha256": _sha256_bytes(requirements_payload),
                "index_url": INDEX_URL,
            },
            "target": {
                "operating_system": "Linux",
                "architecture": "aarch64",
                "python_version": "3.12",
                "implementation": "cp",
                "abis": list(ABIS),
                "platform_tags": list(PLATFORM_TAGS),
                "binary_only": True,
            },
            "resolution": {
                "direct_pin_count": len(direct),
                "resolved_wheel_count": len(normalized),
                "resolved_logical_bytes": total,
                "all_direct_and_transitive_dependencies_resolved": True,
                "source_distributions_used": False,
                "model_assets_downloaded": False,
                "wheels_retained_after_audit": False,
            },
            "wheels": list(normalized),
            "qualification_boundary": {
                "wheel_availability_and_target_tag_resolution": "PASS",
                "arm64_import_and_dynamic_link_validation": (
                    "NOT_RUN_REQUIRES_ARM64_LINUX"
                ),
                "arm64_numerical_parity": "NOT_RUN_REQUIRES_ARM64_LINUX",
                "raspberry_pi_hardware_ready_claimed": False,
                "candidate_classification": "PORT_REQUIRES_WORK",
            },
            "resolver": {
                "pip_version": pip_version,
                "resolver_source_sha256": _sha256_file(Path(__file__).resolve()),
                "temporary_wheelhouse_parent": (
                    "<workspace>/storage_maintenance/arm64_wheel_resolution_tmp"
                ),
                "temporary_payload_removed_before_receipt_publication": True,
            },
        }
    )


def validate_receipt(
    path: Path, *, workspace: Path, requirements: Path = DEFAULT_REQUIREMENTS
) -> dict[str, object]:
    """Validate signature, immutable bindings, target, and inventory structure."""

    workspace = _require_c_drive(workspace, label="workspace")
    path = _require_c_drive(path, label="receipt").resolve(strict=True)
    if not _is_relative_to(path, workspace):
        raise Arm64WheelResolutionError("receipt escaped the selected workspace")
    receipt = _read_object(path, label="ARM64 wheel receipt")
    _validate_signature(receipt)
    protocol_id, runtime_sha = _workspace_bindings(workspace)
    requirements = requirements.resolve(strict=True)
    requirements_payload = requirements.read_bytes()
    direct = _direct_requirements(requirements_payload)
    source = receipt.get("source")
    target = receipt.get("target")
    resolution = receipt.get("resolution")
    boundary = receipt.get("qualification_boundary")
    wheels = receipt.get("wheels")
    if not all(
        isinstance(value, Mapping) for value in (source, target, resolution, boundary)
    ) or not isinstance(wheels, list):
        raise Arm64WheelResolutionError("ARM64 wheel receipt structure differs")
    if (
        receipt.get("schema_version") != SCHEMA_VERSION
        or receipt.get("status") != "PASS_RESOLVED_EXACT_ARM64_BINARY_SET"
        or receipt.get("protocol_id") != protocol_id
        or receipt.get("runtime_implementation_sha256") != runtime_sha
        or receipt.get("scientific_runtime_or_configuration_edited") is not False
        or source.get("requirements_path") != REQUIREMENTS_MEMBER
        or source.get("requirements_sha256") != _sha256_bytes(requirements_payload)
        or source.get("index_url") != INDEX_URL
        or target.get("operating_system") != "Linux"
        or target.get("architecture") != "aarch64"
        or target.get("python_version") != "3.12"
        or target.get("implementation") != "cp"
        or target.get("abis") != list(ABIS)
        or target.get("platform_tags") != list(PLATFORM_TAGS)
        or target.get("binary_only") is not True
        or resolution.get("all_direct_and_transitive_dependencies_resolved")
        is not True
        or resolution.get("source_distributions_used") is not False
        or resolution.get("model_assets_downloaded") is not False
        or resolution.get("wheels_retained_after_audit") is not False
        or boundary.get("wheel_availability_and_target_tag_resolution") != "PASS"
        or boundary.get("arm64_import_and_dynamic_link_validation")
        != "NOT_RUN_REQUIRES_ARM64_LINUX"
        or boundary.get("arm64_numerical_parity")
        != "NOT_RUN_REQUIRES_ARM64_LINUX"
        or boundary.get("raspberry_pi_hardware_ready_claimed") is not False
        or boundary.get("candidate_classification") != "PORT_REQUIRES_WORK"
    ):
        raise Arm64WheelResolutionError("ARM64 wheel receipt binding differs")
    if (
        int(resolution.get("direct_pin_count") or 0) != len(direct)
        or int(resolution.get("resolved_wheel_count") or 0) != len(wheels)
        or len(wheels) < len(direct)
    ):
        raise Arm64WheelResolutionError("ARM64 wheel dependency counts differ")
    names: set[str] = set()
    total = 0
    for row in wheels:
        if not isinstance(row, Mapping):
            raise Arm64WheelResolutionError("ARM64 wheel inventory row is invalid")
        name = str(row.get("filename") or "")
        digest = str(row.get("sha256") or "")
        size = int(row.get("bytes") or 0)
        if (
            not name
            or PurePosixPath(name).name != name
            or not name.casefold().endswith(".whl")
            or name in names
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or size <= 0
        ):
            raise Arm64WheelResolutionError("ARM64 wheel inventory differs")
        names.add(name)
        total += size
    if total != int(resolution.get("resolved_logical_bytes") or 0):
        raise Arm64WheelResolutionError("ARM64 wheel byte total differs")
    return receipt


def _write_atomic(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(document) + b"\n"
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def resolve(
    *, workspace: Path, output: Path, requirements: Path, python: Path
) -> dict[str, object]:
    """Resolve, hash, delete payloads, publish the receipt, and validate it."""

    workspace = _require_c_drive(workspace, label="workspace").resolve(strict=True)
    output = _require_c_drive(output, label="output")
    if not _is_relative_to(output, workspace):
        raise Arm64WheelResolutionError("output escaped the selected workspace")
    if output.exists():
        return validate_receipt(output, workspace=workspace, requirements=requirements)
    maintenance = _require_c_drive(
        workspace / "storage_maintenance", label="temporary wheelhouse parent"
    )
    maintenance.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="arm64_wheel_resolution_tmp_", dir=maintenance))
    wheelhouse = temp_root / "wheelhouse"
    wheelhouse.mkdir()
    command = _download_command(
        python=python.resolve(strict=True),
        requirements=requirements.resolve(strict=True),
        destination=wheelhouse,
    )
    try:
        subprocess.run(command, check=True)
        inventory = _wheel_inventory(wheelhouse)
        pip_version = _pip_version(python.resolve(strict=True))
        receipt = build_receipt(
            workspace=workspace,
            requirements=requirements,
            wheels=inventory,
            pip_version=pip_version,
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    if temp_root.exists():
        raise Arm64WheelResolutionError("temporary ARM64 wheelhouse was not removed")
    _write_atomic(output, receipt)
    return validate_receipt(output, workspace=workspace, requirements=requirements)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--validate", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    workspace = args.workspace.resolve(strict=False)
    try:
        if args.validate is not None:
            path = args.validate.resolve(strict=False)
            receipt = validate_receipt(
                path, workspace=workspace, requirements=args.requirements
            )
        else:
            output = (
                args.output.resolve(strict=False)
                if args.output is not None
                else (workspace / DEFAULT_OUTPUT_RELATIVE).resolve(strict=False)
            )
            receipt = resolve(
                workspace=workspace,
                output=output,
                requirements=args.requirements,
                python=args.python,
            )
            path = output
    except (Arm64WheelResolutionError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": "VALID",
                "path": str(path),
                "receipt_sha256": receipt[SIGNATURE_KEY],
                "resolved_wheel_count": receipt["resolution"]["resolved_wheel_count"],
                "resolved_logical_bytes": receipt["resolution"]["resolved_logical_bytes"],
                "wheels_retained": False,
                "hardware_validated": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
