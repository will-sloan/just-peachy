"""Machine-readable H2 program contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from .io import canonical_sha256


H2_PROGRAM_SCHEMA_VERSION = "h2-product-program-state.v1"
H2_JOB_SCHEMA_VERSION = "h2-product-program-job.v1"
H2_PROTOCOL_SCHEMA_VERSION = "h2-product-protocol.v1"
H2_MODES = (
    "H2_KNOWN_ONLY",
    "H2_SESSION_ANONYMOUS",
    "H2_SESSION_MEMORY_ENHANCED",
)
TERMINAL_JOB_STATES = {"COMPLETE", "FAILED", "STOPPED", "SUPERSEDED"}


class H2ProgramError(RuntimeError):
    """A fail-closed H2 program invariant was violated."""


@dataclass(frozen=True)
class H2Job:
    job_id: str
    phase_index: int
    phase_name: str
    job_kind: str
    split: str
    pipeline_id: str
    configuration_id: str
    mode: str
    case_ids: tuple[str, ...]
    audio_duration_sec: float
    runtime_tuning: Mapping[str, object]
    dependencies: tuple[str, ...] = ()
    serial: bool = False
    development_only: bool = True
    optional: bool = False
    estimated_wall_hours: float = 0.0

    def __post_init__(self) -> None:
        if self.phase_index not in range(8):
            raise H2ProgramError(f"invalid phase index for {self.job_id}")
        if self.split not in {"development", "evaluation", "none"}:
            raise H2ProgramError(f"invalid split for {self.job_id}: {self.split}")
        if self.mode not in {*H2_MODES, "NOT_APPLICABLE"}:
            raise H2ProgramError(f"invalid mode for {self.job_id}: {self.mode}")
        if self.pipeline_id not in {
            "fullpipe_v1_ag_dr_ir",
            "fullpipe_v1_ao_dr_ir",
            "NOT_APPLICABLE",
        }:
            raise H2ProgramError(f"non-H2 pipeline in H2 job: {self.pipeline_id}")
        if self.split == "evaluation" and self.development_only:
            raise H2ProgramError(f"evaluation job marked development-only: {self.job_id}")
        if self.audio_duration_sec < 0 or self.estimated_wall_hours < 0:
            raise H2ProgramError(f"negative duration for {self.job_id}")
        if len(set(self.case_ids)) != len(self.case_ids):
            raise H2ProgramError(f"duplicate cases in {self.job_id}")

    @property
    def identity_sha256(self) -> str:
        return canonical_sha256(self.identity_payload())

    def identity_payload(self) -> dict[str, object]:
        value = asdict(self)
        value["schema_version"] = H2_JOB_SCHEMA_VERSION
        value["case_ids"] = list(self.case_ids)
        value["dependencies"] = list(self.dependencies)
        value["runtime_tuning"] = dict(self.runtime_tuning)
        return value

    def to_jsonable(self) -> dict[str, object]:
        return {**self.identity_payload(), "identity_sha256": self.identity_sha256}

    @classmethod
    def from_jsonable(cls, value: Mapping[str, object]) -> "H2Job":
        job = cls(
            job_id=str(value["job_id"]),
            phase_index=int(value["phase_index"]),
            phase_name=str(value["phase_name"]),
            job_kind=str(value["job_kind"]),
            split=str(value["split"]),
            pipeline_id=str(value["pipeline_id"]),
            configuration_id=str(value["configuration_id"]),
            mode=str(value["mode"]),
            case_ids=tuple(str(item) for item in value.get("case_ids", ())),
            audio_duration_sec=float(value.get("audio_duration_sec") or 0.0),
            runtime_tuning=dict(value.get("runtime_tuning") or {}),
            dependencies=tuple(str(item) for item in value.get("dependencies", ())),
            serial=bool(value.get("serial")),
            development_only=bool(value.get("development_only", True)),
            optional=bool(value.get("optional")),
            estimated_wall_hours=float(value.get("estimated_wall_hours") or 0.0),
        )
        expected = str(value.get("identity_sha256") or job.identity_sha256)
        if expected != job.identity_sha256:
            raise H2ProgramError(f"job identity mismatch: {job.job_id}")
        return job


@dataclass(frozen=True)
class ProgramPaths:
    evaluation_root: Path
    workspace: Path
    results_root: Path
    summary_root: Path
    config_path: Path

    @property
    def state_path(self) -> Path:
        return self.workspace / "program_state.json"

    @property
    def stop_path(self) -> Path:
        return self.workspace / "stop_request.json"

    @property
    def protocol_path(self) -> Path:
        return self.workspace / "protocol_manifest.json"

    @property
    def jobs_path(self) -> Path:
        return self.workspace / "job_manifest.json"

    @property
    def freeze_path(self) -> Path:
        return self.workspace / "frozen_policy.json"


__all__ = [
    "H2Job",
    "H2ProgramError",
    "H2_MODES",
    "H2_JOB_SCHEMA_VERSION",
    "H2_PROGRAM_SCHEMA_VERSION",
    "H2_PROTOCOL_SCHEMA_VERSION",
    "ProgramPaths",
    "TERMINAL_JOB_STATES",
]
