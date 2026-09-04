"""Frozen-protocol native-vs-ONNX H2 full-pipeline parity.

This module compares product-visible semantics rather than UUIDs, paths, wall
clocks, or worker telemetry.  The normalization allowlist and tolerances live
in :mod:`app.h2_portability.contracts`; a fresh measurement is rejected unless
its pre-run freeze receipt matches that code constant exactly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from .contracts import (
    H2_E2E_ONNX_PARITY_CONTRACT_VERSION,
    H2_E2E_ONNX_PARITY_TOLERANCES,
)
from .onnx_tooling import atomic_write_json, canonical_sha256, sha256_file
from .runtime_profile import H2_PORTABLE_ONNX_FP32, H2_REFERENCE


E2E_PARITY_REPORT_SCHEMA = "h2-full-pipeline-onnx-parity-report.v1"
E2E_PARITY_FREEZE_SCHEMA = "h2-full-pipeline-onnx-parity-freeze.v1"
E2E_PARITY_CASE_SCHEMA = "h2-full-pipeline-onnx-parity-case.v1"

_UNKNOWN = re.compile(r"^Unknown_(\d+)$")
_VOLATILE_KEYS = {
    "event_id",
    "session_id",
    "stream_id",
    "recording_id",
    "correlation_id",
    "causation_event_id",
    "caused_by_event_ids",
    "source_event_ids",
    "target_span_ids",
    "evidence_event_ids",
    "corrected_event_ids",
    "causal_event_ids",
    "frame_id",
    "hypothesis_id",
    "line_id",
    "transcript_id",
    "span_id",
    "revision_id",
    "supersedes_revision_id",
    "boundary_id",
    "speech_region_id",
    "source_turn_ids",
    "utterance_id",
    "in_memory_handle_id",
    "before_snapshot_sha256",
    "after_snapshot_sha256",
    "updated_at_utc",
    "created_at_utc",
    "completed_at_utc",
    "started_at_utc",
    "pid",
    "process_id",
}
_PROVENANCE_KEYS = {
    "component_identity",
    "processing_timestamps",
    "source_clock",
    "implementation_id",
    "implementation_sha256",
    "environment_fingerprint_sha256",
}
_SOURCE_TIME_KEYS = {
    "audio_start_sec",
    "audio_end_sec",
    "start_sec",
    "end_sec",
    "boundary_sec",
    "audio_consumed_through_sec",
    "source_time_sec",
    "evidence_duration_sec",
}
_IDENTITY_SCORE_KEYS = {
    "top1_raw_score",
    "top2_raw_score",
    "top1_top2_margin",
    "embedding_consistency",
}


class H2E2EParityError(RuntimeError):
    """The parity protocol, run artifact, or comparison is invalid."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tolerance_contract_sha256() -> str:
    return canonical_sha256(H2_E2E_ONNX_PARITY_TOLERANCES)


def _result_affecting_code_inventory() -> dict[str, str]:
    tool_root = Path(__file__).resolve().parents[2]
    paths = {
        "app/h2_portability/contracts.py": tool_root
        / "app/h2_portability/contracts.py",
        "app/h2_portability/e2e_parity.py": Path(__file__).resolve(),
        "app/h2_portability/runtime.py": tool_root / "app/h2_portability/runtime.py",
        "app/h2_portability/runtime_profile.py": tool_root
        / "app/h2_portability/runtime_profile.py",
        "app/full_pipeline/factory.py": tool_root / "app/full_pipeline/factory.py",
        "app/full_pipeline/worker_main.py": tool_root
        / "app/full_pipeline/worker_main.py",
    }
    return {key: sha256_file(path) for key, path in sorted(paths.items())}


def freeze_e2e_parity_protocol(
    output_path: Path,
    *,
    planned_cases: Sequence[Mapping[str, object]],
    engineering_smokes_excluded: Sequence[str] = (),
) -> dict[str, object]:
    """Write the immutable pre-measurement receipt required by fresh cases."""

    output = Path(output_path).resolve()
    if output.exists():
        existing = _read_json(output, "E2E parity freeze receipt")
        _validate_freeze(existing)
        return existing
    code_inventory = _result_affecting_code_inventory()
    payload = {
        "schema_version": E2E_PARITY_FREEZE_SCHEMA,
        "contract_version": H2_E2E_ONNX_PARITY_CONTRACT_VERSION,
        "frozen_at_utc": _utc_now(),
        "tolerances": H2_E2E_ONNX_PARITY_TOLERANCES,
        "tolerance_contract_sha256": tolerance_contract_sha256(),
        "result_affecting_code_sha256": code_inventory,
        "result_affecting_code_set_sha256": canonical_sha256(code_inventory),
        "normalization_policy": {
            "cluster_labels": "permutation-aware canonical first appearance",
            "exact_fields": (
                "event order/types, semantic nonnumeric payloads, transcript words/text, "
                "cluster coassignment, identity states/labels"
            ),
            "tolerance_fields": (
                "source-media times, speech/transcript boundaries, FP32 identity scores, "
                "segmentation/boundary scores"
            ),
            "forbidden_post_hoc_changes": True,
        },
        "planned_cases": [dict(row) for row in planned_cases],
        "engineering_smokes_excluded_from_final_decision": list(
            engineering_smokes_excluded
        ),
        "sequence": [
            "freeze contract and normalization",
            "create bounded checksum-bound enrollment after freeze",
            "run fresh native H2_REFERENCE case",
            "run fresh H2_PORTABLE_ONNX_FP32 case on identical input/profile",
            "compare exact and tolerance-based surfaces without retuning",
        ],
    }
    atomic_write_json(output, payload)
    return payload


def _validate_freeze(value: Mapping[str, object]) -> None:
    checks = {
        "schema": value.get("schema_version") == E2E_PARITY_FREEZE_SCHEMA,
        "version": value.get("contract_version")
        == H2_E2E_ONNX_PARITY_CONTRACT_VERSION,
        "tolerances": value.get("tolerances") == H2_E2E_ONNX_PARITY_TOLERANCES,
        "hash": value.get("tolerance_contract_sha256")
        == tolerance_contract_sha256(),
    }
    if value.get("result_affecting_code_sha256") is not None:
        inventory = _result_affecting_code_inventory()
        checks["result_affecting_code"] = (
            value.get("result_affecting_code_sha256") == inventory
            and value.get("result_affecting_code_set_sha256")
            == canonical_sha256(inventory)
        )
    failed = sorted(key for key, passed in checks.items() if not passed)
    if failed:
        raise H2E2EParityError(
            f"E2E parity freeze receipt does not match code contract: {failed}"
        )


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not Path(path).is_file():
        raise H2E2EParityError(f"{label} is missing: {path}")
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise H2E2EParityError(f"{label} must contain a JSON object: {path}")
    return value


def _read_jsonl(path: Path, label: str) -> list[dict[str, object]]:
    if not Path(path).is_file():
        raise H2E2EParityError(f"{label} is missing: {path}")
    rows = []
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise H2E2EParityError(
                f"{label} row {line_number} must contain a JSON object"
            )
        rows.append(value)
    return rows


def _cluster_maps(rows: Sequence[Mapping[str, object]]) -> tuple[dict[str, str], dict[str, str]]:
    clusters: dict[str, str] = {}
    unknowns: dict[str, str] = {}
    cluster_fields = (
        "anonymous_speaker_id",
        "previous_anonymous_speaker_id",
        "next_anonymous_speaker_id",
    )
    for row in rows:
        for field in cluster_fields:
            value = row.get(field)
            if isinstance(value, str) and value and value not in clusters:
                clusters[value] = f"cluster_{len(clusters) + 1:04d}"
        label = row.get("unknown_label")
        if isinstance(label, str) and _UNKNOWN.fullmatch(label) and label not in unknowns:
            cluster = row.get("anonymous_speaker_id")
            unknowns[label] = clusters.get(str(cluster), f"unknown_{len(unknowns) + 1:04d}")
    return clusters, unknowns


def _canonical_label(
    value: object,
    clusters: Mapping[str, str],
    unknowns: Mapping[str, str],
) -> object:
    if not isinstance(value, str):
        return value
    if value in clusters:
        return clusters[value]
    if _UNKNOWN.fullmatch(value):
        return unknowns.get(value, value)
    return value


def _numeric_kind(event_type: str, key: str, path: str) -> tuple[str, float] | None:
    tolerance = H2_E2E_ONNX_PARITY_TOLERANCES
    if key in _SOURCE_TIME_KEYS:
        if "transcript" in path and key in {"start_sec", "end_sec"}:
            return "transcript_span_boundary", float(
                tolerance["transcript_span_boundary_max_abs_sec"]
            )
        if event_type in {"speech_activity", "anonymous_speaker", "speaker_boundary"}:
            return "speech_boundary", float(tolerance["speech_boundary_max_abs_sec"])
        return "source_timestamp", float(tolerance["source_timestamp_max_abs_sec"])
    if key in _IDENTITY_SCORE_KEYS or (
        key == "raw_score" and event_type == "identity_evidence"
    ):
        if key == "top1_top2_margin":
            return "identity_margin", float(tolerance["identity_margin_max_abs"])
        if key == "embedding_consistency":
            return "identity_consistency", float(
                tolerance["identity_consistency_max_abs"]
            )
        return "identity_score", float(tolerance["identity_score_max_abs"])
    if key == "raw_score" and event_type == "speech_activity":
        return "segmentation_raw_score", float(
            tolerance["segmentation_raw_score_max_abs"]
        )
    if key == "raw_score" and event_type == "speaker_boundary":
        return "speaker_boundary_raw_score", float(
            tolerance["speaker_boundary_raw_score_max_abs"]
        )
    return None


def _semantic_projection(
    value: object,
    *,
    event_type: str,
    clusters: Mapping[str, str],
    unknowns: Mapping[str, str],
    path: str,
    numerics: list[dict[str, object]],
) -> object:
    if isinstance(value, list):
        return [
            _semantic_projection(
                item,
                event_type=event_type,
                clusters=clusters,
                unknowns=unknowns,
                path=f"{path}[{index}]",
                numerics=numerics,
            )
            for index, item in enumerate(value)
        ]
    if not isinstance(value, Mapping):
        return _canonical_label(value, clusters, unknowns)
    projected: dict[str, object] = {}
    for key in sorted(value):
        item = value[key]
        child_path = f"{path}.{key}" if path else key
        if key in _VOLATILE_KEYS or key in _PROVENANCE_KEYS:
            continue
        if key in {"capture_start_monotonic_ns", "capture_end_monotonic_ns", "capture_start_utc", "capture_end_utc"}:
            continue
        if key == "artifact":
            # Artifact locations are machine-local; representation is retained
            # by the surrounding payload and content is bound by input hashes.
            continue
        if key == "inline_base64":
            continue
        if key == "detail" and path.endswith(("event_reason", "reason")):
            # Details carry paths, PIDs, component provenance, and measured
            # latency.  The result-affecting reason code is retained.
            continue
        if key == "component_statuses" and isinstance(item, list):
            projected[key] = [
                {
                    "state": row.get("state"),
                    "errors": row.get("errors", []),
                    "reason_code": (
                        row.get("reason", {}).get("code")
                        if isinstance(row, Mapping)
                        and isinstance(row.get("reason"), Mapping)
                        else None
                    ),
                }
                for row in item
                if isinstance(row, Mapping)
            ]
            continue
        numeric = _numeric_kind(event_type, key, child_path)
        if numeric is not None and (item is None or isinstance(item, (int, float))):
            kind, allowed = numeric
            numerics.append(
                {
                    "path": child_path,
                    "kind": kind,
                    "allowed_max_abs": allowed,
                    "value": None if item is None else float(item),
                }
            )
            continue
        if key in {
            "anonymous_speaker_id",
            "previous_anonymous_speaker_id",
            "next_anonymous_speaker_id",
            "unknown_label",
        }:
            projected[key] = _canonical_label(item, clusters, unknowns)
            continue
        projected[key] = _semantic_projection(
            item,
            event_type=event_type,
            clusters=clusters,
            unknowns=unknowns,
            path=child_path,
            numerics=numerics,
        )
    return projected


def _event_views(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    clusters, unknowns = _cluster_maps(rows)
    exact = []
    numerics: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        event_type = str(row.get("event_type", ""))
        exact.append(
            _semantic_projection(
                row,
                event_type=event_type,
                clusters=clusters,
                unknowns=unknowns,
                path=f"events[{index}]",
                numerics=numerics,
            )
        )
    return {
        "event_types": [str(row.get("event_type", "")) for row in rows],
        "exact_semantic_events": exact,
        "numeric_fields": numerics,
        "cluster_map": clusters,
        "unknown_label_map": unknowns,
    }


def _transcript_views(
    transcript: Mapping[str, object],
    *,
    clusters: Mapping[str, str],
    unknowns: Mapping[str, str],
) -> dict[str, object]:
    numerics: list[dict[str, object]] = []
    exact = _semantic_projection(
        transcript,
        event_type="final_transcript",
        clusters=clusters,
        unknowns=unknowns,
        path="final_transcript",
        numerics=numerics,
    )
    return {"exact": exact, "numeric_fields": numerics}


def _rttm_view(
    rows: Sequence[Mapping[str, object]], clusters: Mapping[str, str]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    exact = []
    numerics = []
    tolerance = float(
        H2_E2E_ONNX_PARITY_TOLERANCES["speech_boundary_max_abs_sec"]
    )
    for index, row in enumerate(rows):
        speaker = str(row.get("anonymous_speaker_id"))
        exact.append(
            {
                "index": index,
                "speaker": clusters.get(speaker, speaker),
                "cluster_state": row.get("cluster_state"),
                "overlap": row.get("overlap"),
                "revision_number": (
                    row.get("revision", {}).get("revision_number")
                    if isinstance(row.get("revision"), Mapping)
                    else None
                ),
            }
        )
        for field in ("start_sec", "end_sec"):
            numerics.append(
                {
                    "path": f"rttm[{index}].{field}",
                    "kind": "speech_boundary",
                    "allowed_max_abs": tolerance,
                    "value": float(row[field]),
                }
            )
    return exact, numerics


def _coassignment_view(rows: Sequence[Mapping[str, object]]) -> list[list[bool]]:
    speakers = [str(row.get("anonymous_speaker_id")) for row in rows]
    return [[left == right for right in speakers] for left in speakers]


def _numeric_compare(
    native: Sequence[Mapping[str, object]],
    portable: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if len(native) != len(portable):
        return {
            "passed": False,
            "field_count_native": len(native),
            "field_count_portable": len(portable),
            "path_alignment_exact": False,
            "failures": ["numeric field counts differ"],
            "maximum_abs_by_kind": {},
        }
    failures = []
    maxima: dict[str, float] = {}
    path_alignment = True
    for left, right in zip(native, portable):
        if left.get("path") != right.get("path") or left.get("kind") != right.get("kind"):
            path_alignment = False
            failures.append(
                f"numeric path differs: {left.get('path')} vs {right.get('path')}"
            )
            continue
        lv, rv = left.get("value"), right.get("value")
        if lv is None or rv is None:
            if lv != rv:
                failures.append(f"None/value mismatch at {left.get('path')}")
            continue
        delta = abs(float(lv) - float(rv))
        kind = str(left["kind"])
        maxima[kind] = max(maxima.get(kind, 0.0), delta)
        allowed = min(float(left["allowed_max_abs"]), float(right["allowed_max_abs"]))
        if delta > allowed:
            failures.append(
                f"{left.get('path')} delta {delta:.12g} exceeds {allowed:.12g}"
            )
    return {
        "passed": not failures and path_alignment,
        "field_count_native": len(native),
        "field_count_portable": len(portable),
        "path_alignment_exact": path_alignment,
        "maximum_abs_by_kind": dict(sorted(maxima.items())),
        "failures": failures[:100],
        "failure_count": len(failures),
    }


def _first_differences(left: object, right: object, *, limit: int = 50) -> list[str]:
    values: list[str] = []

    def visit(a: object, b: object, path: str) -> None:
        if len(values) >= limit or a == b:
            return
        if isinstance(a, Mapping) and isinstance(b, Mapping):
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    values.append(f"{path}.{key}: key presence differs")
                else:
                    visit(a[key], b[key], f"{path}.{key}")
                if len(values) >= limit:
                    return
            return
        if isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                values.append(f"{path}: list lengths {len(a)} != {len(b)}")
                return
            for index, (av, bv) in enumerate(zip(a, b)):
                visit(av, bv, f"{path}[{index}]")
                if len(values) >= limit:
                    return
            return
        values.append(f"{path}: {a!r} != {b!r}")

    visit(left, right, "root")
    return values


def _inventory(root: Path) -> list[dict[str, object]]:
    required = (
        "result.json",
        "events/events.jsonl",
        "transcript/final_transcript.json",
        "speakers/anonymous.jsonl",
        "speakers/identity_evidence.jsonl",
        "speakers/identity_labels.jsonl",
    )
    rows = []
    for relative in required:
        path = root / relative
        if not path.is_file():
            raise H2E2EParityError(f"required run artifact is missing: {path}")
        rows.append(
            {
                "relative_path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def compare_full_pipeline_runs(
    native_root: Path,
    portable_root: Path,
    *,
    output_path: Path,
    freeze_receipt_path: Path,
    case_identity: Mapping[str, object],
) -> dict[str, object]:
    """Compare two fresh, identical-input full-pipeline runs."""

    native_root = Path(native_root).resolve()
    portable_root = Path(portable_root).resolve()
    freeze_path = Path(freeze_receipt_path).resolve()
    freeze = _read_json(freeze_path, "E2E parity freeze receipt")
    _validate_freeze(freeze)
    native_result = _read_json(native_root / "result.json", "native result")
    portable_result = _read_json(portable_root / "result.json", "portable result")
    for label, result in (("native", native_result), ("portable", portable_result)):
        if result.get("completion_state") != "complete":
            raise H2E2EParityError(f"{label} run is not complete")
        if result.get("errors") not in ([], None):
            raise H2E2EParityError(f"{label} run contains errors")
    native_events = _read_jsonl(native_root / "events/events.jsonl", "native events")
    portable_events = _read_jsonl(
        portable_root / "events/events.jsonl", "portable events"
    )
    native_view = _event_views(native_events)
    portable_view = _event_views(portable_events)
    native_transcript = _read_json(
        native_root / "transcript/final_transcript.json", "native transcript"
    )
    portable_transcript = _read_json(
        portable_root / "transcript/final_transcript.json", "portable transcript"
    )
    native_tv = _transcript_views(
        native_transcript,
        clusters=native_view["cluster_map"],
        unknowns=native_view["unknown_label_map"],
    )
    portable_tv = _transcript_views(
        portable_transcript,
        clusters=portable_view["cluster_map"],
        unknowns=portable_view["unknown_label_map"],
    )
    native_anon = _read_jsonl(
        native_root / "speakers/anonymous.jsonl", "native anonymous speakers"
    )
    portable_anon = _read_jsonl(
        portable_root / "speakers/anonymous.jsonl", "portable anonymous speakers"
    )
    native_rttm, native_rttm_numeric = _rttm_view(
        native_anon, native_view["cluster_map"]
    )
    portable_rttm, portable_rttm_numeric = _rttm_view(
        portable_anon, portable_view["cluster_map"]
    )
    identity_was_exercised = native_view["event_types"].count(
        "identity_evidence"
    ) > 0 and native_view["event_types"].count("identity_label") > 0
    require_identity_exercised = bool(
        case_identity.get("require_identity_exercised", True)
    )
    exact_checks = {
        "event_type_sequence": native_view["event_types"]
        == portable_view["event_types"],
        "event_semantic_payload": native_view["exact_semantic_events"]
        == portable_view["exact_semantic_events"],
        "final_transcript_text_words_states_labels": native_tv["exact"]
        == portable_tv["exact"],
        "rttm_speaker_structure_after_cluster_permutation": native_rttm
        == portable_rttm,
        "cluster_coassignment": _coassignment_view(native_anon)
        == _coassignment_view(portable_anon),
        "identity_event_type_counts": {
            key: native_view["event_types"].count(key)
            for key in ("identity_evidence", "identity_label")
        }
        == {
            key: portable_view["event_types"].count(key)
            for key in ("identity_evidence", "identity_label")
        },
        "identity_requirement_satisfied": identity_was_exercised
        or not require_identity_exercised,
    }
    event_numeric = _numeric_compare(
        native_view["numeric_fields"], portable_view["numeric_fields"]
    )
    transcript_numeric = _numeric_compare(
        native_tv["numeric_fields"], portable_tv["numeric_fields"]
    )
    rttm_numeric = _numeric_compare(native_rttm_numeric, portable_rttm_numeric)
    tolerance_checks = {
        "event_numeric_fields": event_numeric,
        "transcript_boundaries": transcript_numeric,
        "rttm_boundaries": rttm_numeric,
    }
    exact_pass = all(exact_checks.values())
    tolerance_pass = all(bool(row["passed"]) for row in tolerance_checks.values())
    passed = exact_pass and tolerance_pass
    payload = {
        "schema_version": E2E_PARITY_REPORT_SCHEMA,
        "status": "E2E_PARITY_PASS" if passed else "E2E_PARITY_FAIL",
        "measured_at_utc": _utc_now(),
        "runtime_profiles": {
            "native": H2_REFERENCE,
            "portable": H2_PORTABLE_ONNX_FP32,
        },
        "case_identity": dict(case_identity),
        "freeze_receipt_path": str(freeze_path),
        "freeze_receipt_sha256": sha256_file(freeze_path),
        "contract_version": H2_E2E_ONNX_PARITY_CONTRACT_VERSION,
        "tolerance_contract_sha256": tolerance_contract_sha256(),
        "tolerances": H2_E2E_ONNX_PARITY_TOLERANCES,
        "full_live_pipeline_parity_measured": True,
        "identity_path_exercised": identity_was_exercised,
        "identity_path_required_for_case": require_identity_exercised,
        "scientific_thresholds_retuned": False,
        "exact_checks": exact_checks,
        "tolerance_checks": tolerance_checks,
        "exact_check_passed": exact_pass,
        "tolerance_check_passed": tolerance_pass,
        "differences": {
            "event_semantic": _first_differences(
                native_view["exact_semantic_events"],
                portable_view["exact_semantic_events"],
            ),
            "transcript": _first_differences(native_tv["exact"], portable_tv["exact"]),
            "rttm": _first_differences(native_rttm, portable_rttm),
        },
        "normalized_view_sha256": {
            "native_events": canonical_sha256(native_view["exact_semantic_events"]),
            "portable_events": canonical_sha256(
                portable_view["exact_semantic_events"]
            ),
            "native_transcript": canonical_sha256(native_tv["exact"]),
            "portable_transcript": canonical_sha256(portable_tv["exact"]),
            "native_rttm": canonical_sha256(native_rttm),
            "portable_rttm": canonical_sha256(portable_rttm),
        },
        "run_artifacts": {
            "native_root": str(native_root),
            "portable_root": str(portable_root),
            "native_inventory": _inventory(native_root),
            "portable_inventory": _inventory(portable_root),
        },
        "measurement_sequence": [
            {
                "step": 1,
                "action": "contract frozen",
                "at_utc": freeze.get("frozen_at_utc"),
            },
            {
                "step": 2,
                "action": "fresh native run completed",
                "result_sha256": sha256_file(native_root / "result.json"),
            },
            {
                "step": 3,
                "action": "fresh ONNX run completed",
                "result_sha256": sha256_file(portable_root / "result.json"),
            },
            {
                "step": 4,
                "action": "predeclared semantic comparison applied",
                "post_hoc_tolerance_changes": False,
            },
        ],
        "engineering_smokes_used_for_final_decision": False,
        "arm64_hardware_validated": False,
        "linux_arm64_ready_claimed": False,
    }
    atomic_write_json(Path(output_path).resolve(), payload)
    return payload


def run_fresh_factory_pair(
    *,
    input_path: Path,
    enrollment_root: Path,
    output_root: Path,
    freeze_receipt_path: Path,
    graph_paths: Mapping[str, Path],
    graph_sha256: Mapping[str, str],
    pipeline_id: str,
    duration_sec: float,
    product_mode: str,
    runtime_tuning: Mapping[str, object] | None = None,
    selected_runtime_snapshot_sha256: str | None = None,
    require_identity_exercised: bool = True,
) -> dict[str, object]:
    """Run one bounded enrolled native/ONNX pair after protocol freeze."""

    from app.full_pipeline.factory import build_file_runtime

    freeze = _read_json(Path(freeze_receipt_path), "E2E parity freeze receipt")
    _validate_freeze(freeze)
    input_path = Path(input_path).resolve()
    enrollment_root = Path(enrollment_root).resolve()
    output_root = Path(output_root).resolve()
    native_root = output_root / "native_h2_reference"
    portable_root = output_root / "portable_h2_onnx_fp32"
    for root in (native_root, portable_root):
        if root.exists():
            raise H2E2EParityError(
                f"fresh parity output already exists and will not be overwritten: {root}"
            )
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if not enrollment_root.is_dir():
        raise FileNotFoundError(enrollment_root)
    graphs = {str(key): Path(value).resolve() for key, value in graph_paths.items()}
    hashes = {str(key): str(value) for key, value in graph_sha256.items()}
    for component_id, graph in graphs.items():
        if sha256_file(graph) != hashes.get(component_id):
            raise H2E2EParityError(f"graph hash mismatch before E2E run: {component_id}")
    invocation = {
        "schema_version": E2E_PARITY_CASE_SCHEMA,
        "created_at_utc": _utc_now(),
        "contract_frozen_at_utc": freeze.get("frozen_at_utc"),
        "freeze_receipt_sha256": sha256_file(Path(freeze_receipt_path)),
        "input_path": str(input_path),
        "input_sha256": sha256_file(input_path),
        "enrollment_root": str(enrollment_root),
        "pipeline_id": pipeline_id,
        "duration_sec": float(duration_sec),
        "product_mode": product_mode,
        "runtime_tuning": dict(runtime_tuning or {}),
        "selected_runtime_snapshot_sha256": selected_runtime_snapshot_sha256,
        "graph_sha256": dict(sorted(hashes.items())),
        "telemetry_enabled": False,
        "isolated_profile_caches": True,
        "scientific_thresholds_retuned": False,
        "require_identity_exercised": require_identity_exercised,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    invocation_path = output_root / "case_invocation.json"
    atomic_write_json(invocation_path, invocation)
    native = build_file_runtime(
        pipeline_id=pipeline_id,
        input_path=input_path,
        output_root=native_root,
        enrollment_root=enrollment_root,
        session_id="h2_e2e_native_fresh",
        duration_sec=duration_sec,
        telemetry_enabled=False,
        cache_root=output_root / "native_cache",
        product_mode=product_mode,
        runtime_tuning=runtime_tuning,
        runtime_profile=H2_REFERENCE,
    ).run()
    if native.get("completion_state") != "complete":
        raise H2E2EParityError(f"fresh native run failed: {native.get('errors')}")
    portable = build_file_runtime(
        pipeline_id=pipeline_id,
        input_path=input_path,
        output_root=portable_root,
        enrollment_root=enrollment_root,
        session_id="h2_e2e_portable_fresh",
        duration_sec=duration_sec,
        telemetry_enabled=False,
        cache_root=output_root / "portable_cache",
        product_mode=product_mode,
        runtime_tuning=runtime_tuning,
        runtime_profile=H2_PORTABLE_ONNX_FP32,
        h2_onnx_graphs=graphs,
        h2_onnx_expected_sha256=hashes,
    ).run()
    if portable.get("completion_state") != "complete":
        raise H2E2EParityError(f"fresh portable run failed: {portable.get('errors')}")
    report = compare_full_pipeline_runs(
        native_root,
        portable_root,
        output_path=output_root / "e2e_parity_report.json",
        freeze_receipt_path=freeze_receipt_path,
        case_identity={
            **invocation,
            "invocation_path": str(invocation_path),
            "invocation_sha256": sha256_file(invocation_path),
        },
    )
    return report


__all__ = [
    "E2E_PARITY_CASE_SCHEMA",
    "E2E_PARITY_FREEZE_SCHEMA",
    "E2E_PARITY_REPORT_SCHEMA",
    "H2E2EParityError",
    "compare_full_pipeline_runs",
    "freeze_e2e_parity_protocol",
    "run_fresh_factory_pair",
    "tolerance_contract_sha256",
]
