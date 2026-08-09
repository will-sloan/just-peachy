"""Coordinate sampling, spans, summaries, and atomic Stage 5 artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Mapping
import uuid

import yaml

from app.artifact_contracts.atomic import ScenarioArtifactStore
from app.artifact_contracts.registry import (
    LATEST_ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
)
from app.artifact_contracts.schemas import validate_artifact
from app.resource_telemetry.contracts import (
    COMPONENT_SPANS_SCHEMA_VERSION,
    RESOURCE_AVAILABILITY_SCHEMA_VERSION,
    RESOURCE_METRIC_FIELDS,
    RESOURCE_SUMMARY_SCHEMA_VERSION,
    metric_summary,
    resource_table,
)
from app.resource_telemetry.providers import GpuTelemetryProvider, SystemTelemetryProvider
from app.resource_telemetry.sampler import ResourceSampler
from app.resource_telemetry.validation import validate_spans


class ScenarioTelemetrySession:
    """Collect and atomically publish one scenario attempt's telemetry."""

    def __init__(
        self,
        *,
        campaign_id: str,
        scenario_id: str,
        scenario_hash: str,
        attempt: int,
        worker_id: str,
        host: str,
        root_pid: int,
        disk_path: Path,
        staging_root: Path,
        gpu_index: str | None = None,
        interval_sec: float = 1.0,
        system_provider: SystemTelemetryProvider | None = None,
        gpu_provider: GpuTelemetryProvider | None = None,
        clock: object | None = None,
    ) -> None:
        self.campaign_id = campaign_id
        self.scenario_id = scenario_id
        self.scenario_hash = scenario_hash
        self.attempt = int(attempt)
        self.worker_id = worker_id
        self.host = host
        self.root_pid = int(root_pid)
        self.staging_root = staging_root.resolve()
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self.span_path = self.staging_root / "component_spans.raw.jsonl"
        self.active_state_path = self.staging_root / "active_component.json"
        self.sampler = ResourceSampler(
            campaign_id=campaign_id,
            scenario_id=scenario_id,
            attempt=attempt,
            worker_id=worker_id,
            host=host,
            root_pid=root_pid,
            disk_path=disk_path,
            active_state_path=self.active_state_path,
            gpu_index=gpu_index,
            interval_sec=interval_sec,
            system_provider=system_provider,
            gpu_provider=gpu_provider,
            clock=clock,
        )
        self.interval_sec = float(interval_sec)
        self._stopped = False

    def start(self) -> None:
        self.sampler.start()

    def stop(self) -> None:
        if not self._stopped:
            self.sampler.stop()
            self._stopped = True

    def publish(self, scenario_root: Path) -> dict[str, object]:
        """Stop collection and publish typed, checksummed scenario artifacts."""

        self.stop()
        samples = list(self.sampler.samples)
        spans, read_warnings = _read_spans(self.span_path)
        if not any(row.get("name") == "scenario_total" for row in spans):
            spans.append(self._scenario_total_span(samples))
        relationship_warnings = validate_spans(spans, scenario_id=self.scenario_id)
        warnings = [
            *self.sampler.warnings,
            *read_warnings,
            *relationship_warnings,
        ]
        availability = _reconciled_availability(
            self.sampler.availability(), samples
        )
        summary = self._summary(samples, spans, availability, warnings)
        registry = ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION)
        migrate_scenario_registry(scenario_root, self.scenario_id, registry)
        store = ScenarioArtifactStore(
            scenario_root,
            self.scenario_id,
            registry=registry,
        )
        store.publish_parquet(
            "resource_logs/resource_usage.parquet",
            resource_table(samples),
        )
        store.publish_jsonl("resource_logs/component_spans.jsonl", spans)
        store.publish_json("resource_logs/resource_summary.json", summary)
        store.publish_json(
            "resource_logs/availability.json",
            {
                "schema_version": RESOURCE_AVAILABILITY_SCHEMA_VERSION,
                "scenario_id": self.scenario_id,
                "scenario_hash": self.scenario_hash,
                "fields": availability,
                "warnings": warnings,
            },
        )
        store.reconcile_checksum_manifest()
        return summary

    def _scenario_total_span(self, samples: list[dict[str, object]]) -> dict[str, object]:
        if samples:
            start_ns = int(samples[0]["monotonic_ns"])
            end_ns = int(samples[-1]["monotonic_ns"])
            timestamp = str(samples[0]["timestamp_utc"])
        else:
            start_ns = end_ns = 0
            timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
                "+00:00", "Z"
            )
        return {
            "schema_version": COMPONENT_SPANS_SCHEMA_VERSION,
            "campaign_id": self.campaign_id,
            "scenario_id": self.scenario_id,
            "attempt": self.attempt,
            "worker_id": self.worker_id,
            "host": self.host,
            "pid": self.root_pid,
            "thread_id": 0,
            "span_id": f"supervisor{uuid.uuid4().hex[:6]}",
            "parent_span_id": None,
            "name": "scenario_total",
            "phase": "total_scenario",
            "start_timestamp_utc": timestamp,
            "start_monotonic_ns": start_ns,
            "end_monotonic_ns": end_ns,
            "duration_ns": max(0, end_ns - start_ns),
            "status": "ok",
            "error_type": None,
            "cuda_timing_requested": False,
            "cuda_timing_available": False,
            "cuda_elapsed_ms": None,
            "cuda_availability_reason": "supervisor wall span",
            "recording_id": None,
            "utt_id": None,
            "segment_index": None,
        }

    def _summary(
        self,
        samples: list[dict[str, object]],
        spans: list[dict[str, object]],
        availability: Mapping[str, Mapping[str, object]],
        warnings: list[str],
    ) -> dict[str, object]:
        resources = {
            field: metric_summary(row.get(field) for row in samples)
            for field in RESOURCE_METRIC_FIELDS
        }
        by_component: dict[str, dict[str, object]] = {}
        for name in sorted({str(row.get("name")) for row in spans}):
            selected = [row for row in spans if str(row.get("name")) == name]
            by_component[name] = {
                **metric_summary(float(row["duration_ns"]) / 1_000_000_000 for row in selected),
                "error_count": sum(row.get("status") != "ok" for row in selected),
                "cuda_elapsed_ms": metric_summary(row.get("cuda_elapsed_ms") for row in selected),
            }
        by_phase = {
            phase: metric_summary(
                float(row["duration_ns"]) / 1_000_000_000
                for row in spans
                if row.get("phase") == phase
            )
            for phase in sorted({str(row.get("phase")) for row in spans})
        }
        return {
            "schema_version": RESOURCE_SUMMARY_SCHEMA_VERSION,
            "scenario_id": self.scenario_id,
            "scenario_hash": self.scenario_hash,
            "campaign_id": self.campaign_id,
            "attempt": self.attempt,
            "worker_id": self.worker_id,
            "host": self.host,
            "sampling_interval_sec": self.interval_sec,
            "sample_count": len(samples),
            "span_count": len(spans),
            "sampling_gap_count": sum(bool(row.get("sampling_gap")) for row in samples),
            "resources": resources,
            "components": by_component,
            "phases": by_phase,
            "availability": availability,
            "warnings": warnings,
        }


def migrate_scenario_registry(
    scenario_root: Path,
    scenario_id: str,
    registry: ArtifactRegistry | None = None,
) -> None:
    """Atomically migrate mutable artifact metadata from v1 to additive v2."""

    active = registry or ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION)
    root = scenario_root.resolve()
    for relative, loader, dumper, artifact_id in (
        ("run_config.yaml", _yaml_mapping, _yaml_bytes, "run_config"),
        ("status.json", _json_mapping, _json_bytes, "scenario_status"),
    ):
        path = root / relative
        if not path.is_file():
            continue
        value = loader(path)
        if value.get("artifact_registry_version") == active.schema_version:
            continue
        value["artifact_registry_version"] = active.schema_version
        _atomic_mapping_replace(
            path,
            dumper(value),
            lambda temporary, definition=active.get(artifact_id): validate_artifact(
                temporary,
                definition,
                scenario_id=scenario_id,
            ),
        )
    ScenarioArtifactStore(root, scenario_id, registry=active).reconcile_checksum_manifest()


def _read_spans(path: Path) -> tuple[list[dict[str, object]], list[str]]:
    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    if not path.is_file():
        return rows, ["component span source was not produced by the child process"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                warnings.append(f"malformed component span skipped at raw line {line_number}")
                continue
            if not isinstance(value, dict):
                warnings.append(f"non-object component span skipped at raw line {line_number}")
                continue
            rows.append(value)
    return rows, warnings


def _reconciled_availability(
    declared: Mapping[str, Mapping[str, object]],
    samples: list[dict[str, object]],
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for field, raw in sorted(declared.items()):
        value = dict(raw)
        observed = any(row.get(field) is not None for row in samples)
        if value.get("available") is True and not observed:
            value["available"] = False
            value["reason"] = value.get("reason") or "provider returned no values during scenario"
        result[field] = value
    return result


def _atomic_mapping_replace(path: Path, payload: bytes, validator: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        validator(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _json_mapping(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping in {path.name}")
    return value


def _yaml_mapping(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping in {path.name}")
    return value


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _yaml_bytes(value: Mapping[str, object]) -> bytes:
    return yaml.safe_dump(dict(value), sort_keys=False, allow_unicode=True).encode("utf-8")
