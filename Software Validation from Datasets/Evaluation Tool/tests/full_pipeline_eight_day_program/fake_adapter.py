"""Model-free subprocess used only by eight-day controller tests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


def _bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_bytes(value))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def start() -> int:
    prompt = int(os.environ["JP8_PROMPT_INDEX"])
    workspace = Path(os.environ["JP8_STAGE_WORKSPACE"])
    completion_path = Path(os.environ["JP8_COMPLETION_RECORD"])
    progress_path = Path(os.environ["JP8_PROGRESS_RECORD"])
    workspace.mkdir(parents=True, exist_ok=True)
    native = workspace / "native_stage_evidence.txt"
    native.write_text(f"synthetic prompt {prompt}; no model inference\n", encoding="utf-8")
    gate_refs: dict[str, dict[str, str]] = {}
    gate_paths: list[Path] = []
    for gate_name in (
        "hash_validation",
        "firewall_validation",
        "prerequisite_validation",
    ):
        gate_path = workspace / f"{gate_name}.json"
        _write(
            gate_path,
            {
                "schema_version": "full-pipeline-eight-day-gate.v1",
                "gate": gate_name,
                "status": "PASS",
                "prompt_index": prompt,
                "scope_id": os.environ["JP8_SCOPE_ID"],
                "synthetic_test_only": True,
            },
        )
        gate_paths.append(gate_path)
        gate_refs[gate_name] = {"path": str(gate_path), "sha256": _sha(gate_path)}
    manifest_path = workspace / "artifact_manifest.json"
    artifacts = [native, *gate_paths]
    _write(
        manifest_path,
        {
            "schema_version": "full-pipeline-eight-day-artifact-manifest.v1",
            "scope_id": os.environ["JP8_SCOPE_ID"],
            "scope_class": os.environ["JP8_SCOPE_CLASS"],
            "original_full_scope_complete": False,
            "prompt_index": prompt,
            "artifacts": [
                {
                    "path": str(path),
                    "sha256": _sha(path),
                    "required": True,
                    "kind": "synthetic_test_evidence",
                }
                for path in artifacts
            ],
        },
    )
    predecessor = None
    if os.environ.get("JP8_PREDECESSOR_PROMPT_INDEX"):
        predecessor = {
            "prompt_index": int(os.environ["JP8_PREDECESSOR_PROMPT_INDEX"]),
            "completion_marker": os.environ["JP8_PREDECESSOR_COMPLETION_MARKER"],
            "completion_record_path": os.environ["JP8_PREDECESSOR_COMPLETION_PATH"],
            "completion_record_sha256": os.environ[
                "JP8_PREDECESSOR_COMPLETION_SHA256"
            ],
        }
    _write(
        completion_path,
        {
            "schema_version": "full-pipeline-eight-day-stage-completion.v1",
            "scope_id": os.environ["JP8_SCOPE_ID"],
            "scope_class": os.environ["JP8_SCOPE_CLASS"],
            "original_full_scope_complete": False,
            "prompt_index": prompt,
            "status": "COMPLETE",
            "completion_marker": os.environ["JP8_COMPLETION_MARKER"],
            "adapter_id": os.environ["JP8_ADAPTER_ID"],
            "adapter_contract_sha256": os.environ["JP8_ADAPTER_CONTRACT_SHA256"],
            "predecessor": predecessor,
            "artifact_manifest": {
                "path": str(manifest_path),
                "sha256": _sha(manifest_path),
            },
            "gate_records": gate_refs,
            "synthetic_test_only": True,
        },
    )
    _write(
        progress_path,
        {
            "overall_percentage": 100,
            "eta_seconds": 0,
            "detail": "synthetic adapter complete",
        },
    )
    return 0


def validate() -> int:
    return 0 if Path(os.environ["JP8_COMPLETION_RECORD"]).is_file() else 2


def stop() -> int:
    workspace = Path(os.environ["JP8_STAGE_WORKSPACE"])
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "stop_requested.txt").write_text("graceful\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    action = sys.argv[1]
    raise SystemExit({"start": start, "validate": validate, "stop": stop}[action]())

