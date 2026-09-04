"""Independent validator for bounded universal stage-completion envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from . import SCOPE_CLASS, SCOPE_ID
from .io import HardeningError, ensure_c, read_json, sha256_file


STAGE_SCHEMA = "full-pipeline-eight-day-stage-completion.v1"
MANIFEST_SCHEMA = "full-pipeline-eight-day-artifact-manifest.v1"
GATE_SCHEMA = "full-pipeline-eight-day-gate.v1"
GATES = ("hash_validation", "firewall_validation", "prerequisite_validation")


@dataclass(frozen=True)
class CompletionEvidence:
    prompt_index: int
    marker: str
    path: Path
    sha256: str
    record: Mapping[str, object]
    artifacts: tuple[Path, ...]
    artifacts_by_name: Mapping[str, tuple[Path, ...]]


def validate_completion(
    path: Path | str,
    *,
    prompt_index: int,
    marker: str,
    required_basenames: Sequence[str] = (),
) -> CompletionEvidence:
    completion_path = ensure_c(
        path, label=f"Prompt-{prompt_index} completion", must_exist=True
    )
    record = read_json(completion_path)
    expected = {
        "schema_version": STAGE_SCHEMA,
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": False,
        "prompt_index": prompt_index,
        "status": "COMPLETE",
        "completion_marker": marker,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise HardeningError(
                f"Prompt-{prompt_index} completion {key} differs: {record.get(key)!r}"
            )
    if not str(record.get("adapter_id") or "").strip():
        raise HardeningError(f"Prompt-{prompt_index} completion adapter_id is absent")
    _require_sha(record.get("adapter_contract_sha256"), "adapter contract")

    manifest_ref = record.get("artifact_manifest")
    if not isinstance(manifest_ref, Mapping):
        raise HardeningError(
            f"Prompt-{prompt_index} artifact manifest reference is absent"
        )
    manifest_path = _verified_ref(manifest_ref, "artifact manifest")
    manifest = read_json(manifest_path)
    for key, value in {
        "schema_version": MANIFEST_SCHEMA,
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": False,
        "prompt_index": prompt_index,
    }.items():
        if manifest.get(key) != value:
            raise HardeningError(
                f"Prompt-{prompt_index} artifact manifest {key} differs"
            )
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise HardeningError(f"Prompt-{prompt_index} artifact manifest is empty")
    artifacts: list[Path] = []
    by_name: dict[str, list[Path]] = {}
    for index, raw in enumerate(raw_artifacts):
        if not isinstance(raw, Mapping) or raw.get("required") is not True:
            raise HardeningError(
                f"Prompt-{prompt_index} artifact {index} is not required"
            )
        artifact = _verified_ref(raw, f"artifact {index}")
        artifacts.append(artifact)
        by_name.setdefault(artifact.name, []).append(artifact)

    gate_refs = record.get("gate_records")
    if not isinstance(gate_refs, Mapping) or set(gate_refs) != set(GATES):
        raise HardeningError(f"Prompt-{prompt_index} exact gate record set differs")
    artifact_set = set(artifacts)
    for gate_name in GATES:
        raw = gate_refs[gate_name]
        if not isinstance(raw, Mapping):
            raise HardeningError(
                f"Prompt-{prompt_index} {gate_name} reference is invalid"
            )
        gate_path = _verified_ref(raw, f"{gate_name} gate")
        if gate_path not in artifact_set:
            raise HardeningError(
                f"Prompt-{prompt_index} {gate_name} is absent from manifest"
            )
        gate = read_json(gate_path)
        for key, value in {
            "schema_version": GATE_SCHEMA,
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "prompt_index": prompt_index,
            "gate": gate_name,
            "status": "PASS",
        }.items():
            if gate.get(key) != value:
                raise HardeningError(
                    f"Prompt-{prompt_index} {gate_name} gate {key} differs"
                )

    for basename in required_basenames:
        matches = by_name.get(basename, [])
        if len(matches) != 1:
            raise HardeningError(
                f"Prompt-{prompt_index} requires exactly one {basename}; found {len(matches)}"
            )
    return CompletionEvidence(
        prompt_index=prompt_index,
        marker=marker,
        path=completion_path,
        sha256=sha256_file(completion_path),
        record=record,
        artifacts=tuple(artifacts),
        artifacts_by_name={key: tuple(value) for key, value in by_name.items()},
    )


def single_artifact(evidence: CompletionEvidence, basename: str) -> Path:
    matches = evidence.artifacts_by_name.get(basename, ())
    if len(matches) != 1:
        raise HardeningError(
            f"Prompt-{evidence.prompt_index} artifact {basename} is not unique"
        )
    return matches[0]


def _verified_ref(raw: Mapping[str, object], label: str) -> Path:
    path = ensure_c(str(raw.get("path") or ""), label=label, must_exist=True)
    if not path.is_file():
        raise HardeningError(f"{label} is not a file: {path}")
    expected = str(raw.get("sha256") or "").casefold()
    if expected != sha256_file(path):
        raise HardeningError(f"{label} checksum differs: {path}")
    return path


def _require_sha(value: object, label: str) -> None:
    text = str(value or "").casefold()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise HardeningError(f"{label} is not a SHA-256 digest")


__all__ = ["CompletionEvidence", "single_artifact", "validate_completion"]
