"""Common Prompt-3 result identities and metric-document contracts.

This module is intentionally model-free.  It defines the comparable output
surface shared by every full-pipeline evaluation attempt and keeps unsupported
measurements explicit instead of treating absent keys as zero-valued evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Mapping, Sequence

from .metrics import METRIC_CATALOG as SCIENTIFIC_METRIC_CATALOG
from .metrics import METRICS_SCHEMA_VERSION, MetricReport, MetricValue
from .metrics import build_metric_report, metric_ids


PROGRAM_ID = "just_peachy_full_pipeline_program_v1"
RESULT_TREE_SCHEMA_VERSION = "full-pipeline-evaluation-result-tree.v1"
COMPACT_RESULT_TREE_SCHEMA_VERSION = "full-pipeline-evaluation-result-tree.v2"
RESULT_TREE_SCHEMA_VERSIONS = frozenset(
    {RESULT_TREE_SCHEMA_VERSION, COMPACT_RESULT_TREE_SCHEMA_VERSION}
)
RUN_SCHEMA_VERSION = "full-pipeline-evaluation-run.v1"
PIPELINE_IDENTITY_SCHEMA_VERSION = "full-pipeline-evaluation-pipeline-identity.v1"
MODEL_ASSETS_SCHEMA_VERSION = "full-pipeline-evaluation-model-assets.v1"
METRIC_SCHEMA_VERSION = "full-pipeline-evaluation-metrics.v1"
SUMMARY_SCHEMA_VERSION = "full-pipeline-evaluation-summary.v1"
REFERENCE_MANIFEST_SCHEMA_VERSION = "full-pipeline-evaluation-references.v1"
DIAGNOSTIC_MANIFEST_SCHEMA_VERSION = "full-pipeline-evaluation-diagnostics.v1"
CHECKSUM_SCHEMA_VERSION = "full-pipeline-evaluation-checksums.v1"

METRIC_VIEWS = ("asr", "diarization", "identity", "streaming", "resources")
TERMINAL_RUN_STATES = frozenset({"complete", "failed", "stopped"})
RUN_STATES = frozenset({"prepared", "running", *TERMINAL_RUN_STATES})
PARTITIONS = frozenset({"development", "evaluation", "smoke"})

REUSE_IDENTITY_FIELDS = (
    "program_id",
    "evaluation_protocol_id",
    "evaluation_protocol_sha256",
    "pipeline_id",
    "pipeline_config_sha256",
    "case_manifest_id",
    "case_manifest_sha256",
    "runtime_config_sha256",
    "partition",
    "seed",
)

FIXED_REQUIRED_FILES = (
    "run.json",
    "pipeline_identity.json",
    "model_assets.json",
    "events.jsonl",
    "predictions/transcript.jsonl",
    "predictions/labelled_transcript.jsonl",
    "predictions/diarization.rttm",
    "references/manifest.json",
    "metrics/summary.json",
    "metrics/asr.json",
    "metrics/diarization.json",
    "metrics/identity.json",
    "metrics/streaming.json",
    "metrics/resources.json",
    "diagnostics/manifest.json",
    "checksums.json",
)


def fixed_required_files(result_tree_schema_version: str) -> tuple[str, ...]:
    """Return the immutable file contract for one result-tree version.

    Version 2 is additive and differs only in storing the lossless event stream
    as deterministic gzip NDJSON.  Version 1 remains the default so existing
    Prompt-3 result identities and validators are unchanged.
    """

    if result_tree_schema_version == RESULT_TREE_SCHEMA_VERSION:
        return FIXED_REQUIRED_FILES
    if result_tree_schema_version == COMPACT_RESULT_TREE_SCHEMA_VERSION:
        return tuple(
            "events.jsonl.gz" if value == "events.jsonl" else value
            for value in FIXED_REQUIRED_FILES
        )
    raise ResultSchemaError(
        f"unsupported result-tree schema version: {result_tree_schema_version}"
    )

REQUIRED_DIRECTORIES = (
    "predictions",
    "references",
    "metrics",
    "diagnostics",
)

ARTIFACT_SUPPORT_IDS = (
    "events",
    "transcript_predictions",
    "labelled_transcript_predictions",
    "diarization_predictions",
    "references",
    "diagnostics",
)


RESULT_VIEW_CATEGORIES: dict[str, tuple[str, ...]] = {
    "asr": ("asr", "speaker_transcription"),
    "diarization": ("diarization",),
    "identity": ("identity",),
    "streaming": ("streaming", "ux"),
    "resources": ("resources",),
}

TRACK_B_CATEGORY_TO_RESULT_VIEW = {
    category: view
    for view, categories in RESULT_VIEW_CATEGORIES.items()
    for category in categories
}

# Result views contain named Track-B reports. Speaker-transcription is preserved
# as an ASR subview and UX as a streaming subview, avoiding a lossy flat adapter.
METRIC_CATALOG: dict[str, tuple[str, ...]] = {
    view: tuple(
        metric_id
        for category in categories
        for metric_id in metric_ids(category)
    )
    for view, categories in RESULT_VIEW_CATEGORIES.items()
}


class ResultSchemaError(ValueError):
    """A result document violates the common Prompt-3 contract."""


def metric_value_to_result_entry(value: MetricValue) -> dict[str, object]:
    """Serialize one Track-B value verbatim, preserving status and provenance."""

    return value.to_jsonable()


def build_metric_documents_from_reports(
    reports: Mapping[str, MetricReport],
    *,
    run_id: str,
    pipeline_id: str,
    missing_reason: str = "Track-B scorer category was not evaluated for this attempt.",
) -> dict[str, dict[str, object]]:
    """Fold seven Track-B reports into the five common result-tree views."""

    unknown = set(reports) - set(TRACK_B_CATEGORY_TO_RESULT_VIEW)
    if unknown:
        raise ResultSchemaError(f"unknown Track-B metric categories: {sorted(unknown)}")
    for category, report in reports.items():
        if report.category != category:
            raise ResultSchemaError(
                f"Track-B report key {category!r} differs from {report.category!r}"
            )
    documents: dict[str, dict[str, object]] = {}
    for view, categories in RESULT_VIEW_CATEGORIES.items():
        subviews: dict[str, Mapping[str, object]] = {}
        for category in categories:
            report = reports.get(category) or build_metric_report(
                category,
                {},
                missing_reason=missing_reason,
            )
            subviews[category] = report.to_jsonable()
        documents[view] = build_metric_document(
            view,
            run_id=run_id,
            pipeline_id=pipeline_id,
            subviews=subviews,
        )
    return documents


def unsupported_metric_document(
    view: str,
    *,
    run_id: str,
    pipeline_id: str,
    reason: str,
) -> dict[str, object]:
    """Materialize every Track-B subview metric as explicitly unsupported."""

    try:
        categories = RESULT_VIEW_CATEGORIES[view]
    except KeyError as exc:
        raise ResultSchemaError(f"unknown metric view: {view}") from exc
    return build_metric_document(
        view,
        run_id=run_id,
        pipeline_id=pipeline_id,
        subviews={
            category: build_metric_report(
                category,
                {},
                missing_reason=reason,
            ).to_jsonable()
            for category in categories
        },
    )


def build_metric_document(
    view: str,
    *,
    run_id: str,
    pipeline_id: str,
    subviews: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    document = {
        "schema_version": METRIC_SCHEMA_VERSION,
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "view": view,
        "subviews": {str(key): dict(value) for key, value in subviews.items()},
    }
    validate_metric_document(document, expected_view=view)
    return document


def build_run_document(
    *,
    run_id: str,
    attempt_id: str,
    reuse_identity: Mapping[str, object],
    status: str,
    created_at_utc: str,
    artifact_support: Mapping[str, Mapping[str, object]],
    counts: Mapping[str, object] | None = None,
    started_at_utc: str | None = None,
    ended_at_utc: str | None = None,
    warnings: Sequence[object] = (),
    errors: Sequence[object] = (),
    result_tree_schema_version: str = RESULT_TREE_SCHEMA_VERSION,
) -> dict[str, object]:
    normalized_identity = normalize_reuse_identity(reuse_identity)
    result = {
        "schema_version": RUN_SCHEMA_VERSION,
        "result_tree_schema_version": result_tree_schema_version,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "status": status,
        "created_at_utc": created_at_utc,
        "started_at_utc": started_at_utc,
        "ended_at_utc": ended_at_utc,
        "reuse_identity": normalized_identity,
        "artifact_support": {
            str(key): dict(value) for key, value in artifact_support.items()
        },
        "counts": dict(counts or {}),
        "warnings": list(warnings),
        "errors": list(errors),
        "long_scientific_campaign_started_by_builder": False,
    }
    validate_run_document(result)
    return result


def normalize_reuse_identity(value: Mapping[str, object]) -> dict[str, object]:
    """Return the exact canonical identity used to authorize result reuse."""

    missing = set(REUSE_IDENTITY_FIELDS) - set(value)
    extra = set(value) - {*REUSE_IDENTITY_FIELDS, "identity_sha256"}
    if missing or extra:
        raise ResultSchemaError(
            f"reuse identity fields differ; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    normalized = {field: value[field] for field in REUSE_IDENTITY_FIELDS}
    for field in (
        "evaluation_protocol_sha256",
        "pipeline_config_sha256",
        "case_manifest_sha256",
        "runtime_config_sha256",
    ):
        if not is_sha256(normalized[field]):
            raise ResultSchemaError(f"reuse identity {field} is not SHA-256")
        normalized[field] = str(normalized[field]).lower()
    for field in (
        "program_id",
        "evaluation_protocol_id",
        "pipeline_id",
        "case_manifest_id",
    ):
        if not _nonempty_string(normalized[field]):
            raise ResultSchemaError(f"reuse identity {field} must be nonempty")
    if normalized["program_id"] != PROGRAM_ID:
        raise ResultSchemaError("reuse identity program ID is not the locked program")
    if not re.fullmatch(r"fullpipe_v1_[a-z0-9_]+", str(normalized["pipeline_id"])):
        raise ResultSchemaError("reuse identity pipeline ID is invalid")
    if normalized["partition"] not in PARTITIONS:
        raise ResultSchemaError("reuse identity partition is invalid")
    seed = normalized["seed"]
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ResultSchemaError("reuse identity seed must be a nonnegative integer")
    identity_hash = canonical_sha256(normalized)
    claimed = value.get("identity_sha256")
    if claimed is not None and str(claimed).lower() != identity_hash:
        raise ResultSchemaError("reuse identity hash does not match its fields")
    return {**normalized, "identity_sha256": identity_hash}


def validate_run_document(value: Mapping[str, object]) -> None:
    required = {
        "schema_version",
        "result_tree_schema_version",
        "run_id",
        "attempt_id",
        "status",
        "created_at_utc",
        "started_at_utc",
        "ended_at_utc",
        "reuse_identity",
        "artifact_support",
        "counts",
        "warnings",
        "errors",
        "long_scientific_campaign_started_by_builder",
    }
    missing = required - set(value)
    if missing:
        raise ResultSchemaError(f"run document missing fields: {sorted(missing)}")
    if value.get("schema_version") != RUN_SCHEMA_VERSION:
        raise ResultSchemaError("run document schema version is invalid")
    if value.get("result_tree_schema_version") not in RESULT_TREE_SCHEMA_VERSIONS:
        raise ResultSchemaError("run document result-tree schema is invalid")
    for field in ("run_id", "attempt_id"):
        if not _portable_id(value.get(field)):
            raise ResultSchemaError(f"run document {field} is not portable")
    if value.get("status") not in RUN_STATES:
        raise ResultSchemaError("run status is invalid")
    _require_timestamp(value.get("created_at_utc"), "created_at_utc")
    for field in ("started_at_utc", "ended_at_utc"):
        if value.get(field) is not None:
            _require_timestamp(value.get(field), field)
    identity = value.get("reuse_identity")
    if not isinstance(identity, Mapping):
        raise ResultSchemaError("run reuse_identity must be an object")
    normalize_reuse_identity(identity)
    support = value.get("artifact_support")
    if not isinstance(support, Mapping) or set(support) != set(ARTIFACT_SUPPORT_IDS):
        raise ResultSchemaError("run artifact_support must cover every required artifact class")
    for artifact_id, raw in support.items():
        if not isinstance(raw, Mapping):
            raise ResultSchemaError(f"artifact support {artifact_id} must be an object")
        status = raw.get("status")
        reason = raw.get("reason")
        if status not in {"supported", "unsupported"}:
            raise ResultSchemaError(f"artifact support {artifact_id} has invalid status")
        if status == "unsupported" and not _nonempty_string(reason):
            raise ResultSchemaError(f"unsupported artifact {artifact_id} requires a reason")
        if status == "supported" and reason not in {None, ""}:
            raise ResultSchemaError(f"supported artifact {artifact_id} cannot have a reason")
    if not isinstance(value.get("counts"), Mapping):
        raise ResultSchemaError("run counts must be an object")
    if not isinstance(value.get("warnings"), list) or not isinstance(value.get("errors"), list):
        raise ResultSchemaError("run warnings and errors must be lists")
    if value.get("long_scientific_campaign_started_by_builder") is not False:
        raise ResultSchemaError("result builder cannot claim it started a campaign")


def validate_metric_document(
    value: Mapping[str, object], *, expected_view: str | None = None
) -> None:
    if value.get("schema_version") != METRIC_SCHEMA_VERSION:
        raise ResultSchemaError("metric document schema version is invalid")
    view = value.get("view")
    if not isinstance(view, str) or view not in METRIC_CATALOG:
        raise ResultSchemaError("metric document view is invalid")
    if expected_view is not None and view != expected_view:
        raise ResultSchemaError(f"expected {expected_view} metrics, observed {view}")
    for field in ("run_id", "pipeline_id"):
        if not _nonempty_string(value.get(field)):
            raise ResultSchemaError(f"metric document {field} must be nonempty")
    subviews = value.get("subviews")
    if not isinstance(subviews, Mapping):
        raise ResultSchemaError("metric document subviews must be an object")
    expected_categories = set(RESULT_VIEW_CATEGORIES[view])
    if set(subviews) != expected_categories:
        missing = expected_categories - set(subviews)
        extra = set(subviews) - expected_categories
        raise ResultSchemaError(
            f"{view} subview coverage differs; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    for category in RESULT_VIEW_CATEGORIES[view]:
        raw = subviews[category]
        if not isinstance(raw, Mapping):
            raise ResultSchemaError(f"metric subview {category} must be an object")
        _validate_metric_report_document(raw, expected_category=category)


def validate_summary_document(
    value: Mapping[str, object], metric_documents: Mapping[str, Mapping[str, object]]
) -> None:
    required = {
        "schema_version",
        "run_id",
        "pipeline_id",
        "completion_state",
        "views",
        "computed_metric_count",
        "undefined_metric_count",
        "unsupported_metric_count",
        "missing_metric_count",
        "unsupported_metrics_are_not_zero",
    }
    if required - set(value):
        raise ResultSchemaError("summary document is incomplete")
    if value.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        raise ResultSchemaError("summary schema version is invalid")
    for field in ("run_id", "pipeline_id"):
        if not _nonempty_string(value.get(field)):
            raise ResultSchemaError(f"summary {field} must be nonempty")
    if value.get("completion_state") not in TERMINAL_RUN_STATES:
        raise ResultSchemaError("summary completion state must be terminal")
    if set(metric_documents) != set(METRIC_VIEWS):
        raise ResultSchemaError("summary validation requires every metric view")
    views = value.get("views")
    if not isinstance(views, Mapping) or set(views) != set(METRIC_VIEWS):
        raise ResultSchemaError("summary must index every metric view")
    computed_total = 0
    undefined_total = 0
    unsupported_total = 0
    for view in METRIC_VIEWS:
        document = metric_documents[view]
        validate_metric_document(document, expected_view=view)
        subview_counts, counts = _metric_document_counts(document)
        computed, undefined, unsupported = counts
        expected = {
            "logical_path": f"metrics/{view}.json",
            "subviews": subview_counts,
            "computed_metric_count": computed,
            "undefined_metric_count": undefined,
            "unsupported_metric_count": unsupported,
        }
        if views.get(view) != expected:
            raise ResultSchemaError(f"summary counts do not match {view} metrics")
        computed_total += computed
        undefined_total += undefined
        unsupported_total += unsupported
    if value.get("computed_metric_count") != computed_total:
        raise ResultSchemaError("summary computed metric count is inconsistent")
    if value.get("unsupported_metric_count") != unsupported_total:
        raise ResultSchemaError("summary unsupported metric count is inconsistent")
    if value.get("undefined_metric_count") != undefined_total:
        raise ResultSchemaError("summary undefined metric count is inconsistent")
    if value.get("missing_metric_count") != 0:
        raise ResultSchemaError("summary cannot omit required metrics")
    if value.get("unsupported_metrics_are_not_zero") is not True:
        raise ResultSchemaError("summary must distinguish unsupported metrics from zero")


def build_summary_document(
    *,
    run_id: str,
    pipeline_id: str,
    completion_state: str,
    metric_documents: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    views: dict[str, object] = {}
    computed_total = 0
    undefined_total = 0
    unsupported_total = 0
    for view in METRIC_VIEWS:
        document = metric_documents[view]
        validate_metric_document(document, expected_view=view)
        subview_counts, counts = _metric_document_counts(document)
        computed, undefined, unsupported = counts
        views[view] = {
            "logical_path": f"metrics/{view}.json",
            "subviews": subview_counts,
            "computed_metric_count": computed,
            "undefined_metric_count": undefined,
            "unsupported_metric_count": unsupported,
        }
        computed_total += computed
        undefined_total += undefined
        unsupported_total += unsupported
    result = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "pipeline_id": pipeline_id,
        "completion_state": completion_state,
        "views": views,
        "computed_metric_count": computed_total,
        "undefined_metric_count": undefined_total,
        "unsupported_metric_count": unsupported_total,
        "missing_metric_count": 0,
        "unsupported_metrics_are_not_zero": True,
    }
    validate_summary_document(result, metric_documents)
    return result


def validate_pipeline_identity_document(value: Mapping[str, object]) -> None:
    required = {
        "schema_version",
        "run_id",
        "pipeline_id",
        "protocol_version",
        "pipeline_config_sha256",
        "matrix_sha256",
        "aliases",
        "component_identities",
        "policy_identities",
        "environment_identities",
    }
    if required - set(value):
        raise ResultSchemaError("pipeline identity document is incomplete")
    if value.get("schema_version") != PIPELINE_IDENTITY_SCHEMA_VERSION:
        raise ResultSchemaError("pipeline identity schema version is invalid")
    for field in ("run_id", "pipeline_id", "protocol_version"):
        if not _nonempty_string(value.get(field)):
            raise ResultSchemaError(f"pipeline identity {field} must be nonempty")
    for field in ("pipeline_config_sha256", "matrix_sha256"):
        if not is_sha256(value.get(field)):
            raise ResultSchemaError(f"pipeline identity {field} is invalid")
    if not isinstance(value.get("aliases"), Mapping):
        raise ResultSchemaError("pipeline aliases must be an object")
    for field in ("component_identities", "policy_identities", "environment_identities"):
        if not isinstance(value.get(field), (list, dict)):
            raise ResultSchemaError(f"pipeline identity {field} has invalid type")


def validate_model_assets_document(value: Mapping[str, object]) -> None:
    required = {"schema_version", "run_id", "pipeline_id", "assets", "no_implicit_downloads"}
    if required - set(value):
        raise ResultSchemaError("model-assets document is incomplete")
    if value.get("schema_version") != MODEL_ASSETS_SCHEMA_VERSION:
        raise ResultSchemaError("model-assets schema version is invalid")
    for field in ("run_id", "pipeline_id"):
        if not _nonempty_string(value.get(field)):
            raise ResultSchemaError(f"model-assets {field} must be nonempty")
    if value.get("no_implicit_downloads") is not True:
        raise ResultSchemaError("model-assets document must prohibit implicit downloads")
    assets = value.get("assets")
    if not isinstance(assets, list):
        raise ResultSchemaError("model assets must be a list")
    for index, raw in enumerate(assets):
        if not isinstance(raw, Mapping):
            raise ResultSchemaError(f"model asset {index} must be an object")
        for field in ("role", "asset_id", "sha256"):
            if field not in raw:
                raise ResultSchemaError(f"model asset {index} lacks {field}")
        for field in ("role", "asset_id"):
            if not _nonempty_string(raw.get(field)):
                raise ResultSchemaError(f"model asset {index} has empty {field}")
        if not is_sha256(raw.get("sha256")):
            raise ResultSchemaError(f"model asset {index} has invalid SHA-256")


def validate_directory_manifest(
    value: Mapping[str, object], *, directory: str
) -> None:
    expected_schema = {
        "references": REFERENCE_MANIFEST_SCHEMA_VERSION,
        "diagnostics": DIAGNOSTIC_MANIFEST_SCHEMA_VERSION,
    }.get(directory)
    if expected_schema is None:
        raise ResultSchemaError(f"unsupported directory manifest: {directory}")
    if value.get("schema_version") != expected_schema:
        raise ResultSchemaError(f"{directory} manifest schema version is invalid")
    if not _nonempty_string(value.get("run_id")):
        raise ResultSchemaError(f"{directory} manifest run ID is missing")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list):
        raise ResultSchemaError(f"{directory} manifest artifacts must be a list")
    ids: set[str] = set()
    paths: set[str] = set()
    for raw in artifacts:
        if not isinstance(raw, Mapping):
            raise ResultSchemaError(f"{directory} manifest entry must be an object")
        artifact_id = raw.get("artifact_id")
        if not _nonempty_string(artifact_id) or artifact_id in ids:
            raise ResultSchemaError(f"{directory} artifact IDs must be unique and nonempty")
        ids.add(str(artifact_id))
        status = raw.get("status")
        if status not in {"available", "unsupported"}:
            raise ResultSchemaError(f"{directory} artifact status is invalid")
        logical_path = raw.get("logical_path")
        if not _portable_relative_path(logical_path, required_prefix=f"{directory}/"):
            raise ResultSchemaError(f"{directory} artifact path is invalid")
        if logical_path == f"{directory}/manifest.json" or logical_path in paths:
            raise ResultSchemaError(f"{directory} artifact paths must be unique")
        paths.add(str(logical_path))
        if status == "available":
            if not is_sha256(raw.get("sha256")):
                raise ResultSchemaError(f"available {directory} artifact lacks SHA-256")
            byte_count = raw.get("bytes")
            if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
                raise ResultSchemaError(f"available {directory} artifact has invalid bytes")
            if raw.get("reason") not in {None, ""}:
                raise ResultSchemaError(f"available {directory} artifact cannot have a reason")
        elif not _nonempty_string(raw.get("reason")):
            raise ResultSchemaError(f"unsupported {directory} artifact requires a reason")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def _validate_metric_report_document(
    raw: Mapping[str, object], *, expected_category: str
) -> None:
    required = {
        "schema_version",
        "category",
        "metrics",
        "computed_metric_count",
        "unsupported_metric_count",
        "undefined_metric_count",
        "warnings",
    }
    if required - set(raw):
        raise ResultSchemaError(f"metric subview {expected_category} is incomplete")
    if raw.get("schema_version") != METRICS_SCHEMA_VERSION:
        raise ResultSchemaError(f"metric subview {expected_category} schema is invalid")
    if raw.get("category") != expected_category:
        raise ResultSchemaError(f"metric subview {expected_category} category differs")
    metrics = raw.get("metrics")
    expected_ids = set(metric_ids(expected_category))
    if not isinstance(metrics, Mapping) or set(metrics) != expected_ids:
        observed = set(metrics) if isinstance(metrics, Mapping) else set()
        raise ResultSchemaError(
            f"{expected_category} metric coverage differs; "
            f"missing={sorted(expected_ids - observed)}, "
            f"extra={sorted(observed - expected_ids)}"
        )
    counts = {"computed": 0, "unsupported": 0, "undefined": 0}
    for metric_id in metric_ids(expected_category):
        value = metrics[metric_id]
        if not isinstance(value, Mapping):
            raise ResultSchemaError(f"metric {metric_id} must be an object")
        _validate_track_b_metric_entry(metric_id, value)
        counts[str(value["status"])] += 1
    for status, count in counts.items():
        if raw.get(f"{status}_metric_count") != count:
            raise ResultSchemaError(
                f"metric subview {expected_category} {status} count differs"
            )
    warnings = raw.get("warnings")
    if not isinstance(warnings, list) or not all(isinstance(value, str) for value in warnings):
        raise ResultSchemaError(f"metric subview {expected_category} warnings are invalid")


def _validate_track_b_metric_entry(
    metric_id: str, raw: Mapping[str, object]
) -> None:
    definition = SCIENTIFIC_METRIC_CATALOG[metric_id]
    expected_definition = definition.to_jsonable()
    for field, expected in expected_definition.items():
        if raw.get(field) != expected:
            raise ResultSchemaError(f"metric {metric_id} definition field {field} differs")
    required = {
        *expected_definition,
        "status",
        "value",
        "numerator",
        "denominator",
        "reason",
        "details",
    }
    if required - set(raw):
        raise ResultSchemaError(f"metric {metric_id} entry is incomplete")
    status = raw.get("status")
    if status not in {"computed", "unsupported", "undefined"}:
        raise ResultSchemaError(f"metric {metric_id} has invalid status")
    if status == "computed":
        metric_value = raw.get("value")
        if (
            not isinstance(metric_value, (int, float))
            or isinstance(metric_value, bool)
            or (isinstance(metric_value, float) and not math.isfinite(metric_value))
        ):
            raise ResultSchemaError(f"computed metric {metric_id} has invalid value")
        if raw.get("reason") not in {None, ""}:
            raise ResultSchemaError(f"computed metric {metric_id} has a failure reason")
    else:
        if raw.get("value") is not None:
            raise ResultSchemaError(f"{status} metric {metric_id} fabricated a value")
        if not _nonempty_string(raw.get("reason")):
            raise ResultSchemaError(f"{status} metric {metric_id} requires a reason")
    for field in ("numerator", "denominator"):
        number = raw.get(field)
        if number is not None and (
            not isinstance(number, (int, float))
            or isinstance(number, bool)
            or (isinstance(number, float) and not math.isfinite(number))
        ):
            raise ResultSchemaError(f"metric {metric_id} {field} is invalid")
    details = raw.get("details")
    if not isinstance(details, Mapping):
        raise ResultSchemaError(f"metric {metric_id} details must be an object")
    _validate_json_metric_value(metric_id, details)


def _metric_document_counts(
    document: Mapping[str, object],
) -> tuple[dict[str, dict[str, int]], tuple[int, int, int]]:
    subviews = document["subviews"]
    per_subview: dict[str, dict[str, int]] = {}
    totals = [0, 0, 0]
    for category in RESULT_VIEW_CATEGORIES[str(document["view"])]:
        report = subviews[category]
        counts = {
            "computed_metric_count": int(report["computed_metric_count"]),
            "undefined_metric_count": int(report["undefined_metric_count"]),
            "unsupported_metric_count": int(report["unsupported_metric_count"]),
        }
        per_subview[category] = counts
        totals[0] += counts["computed_metric_count"]
        totals[1] += counts["undefined_metric_count"]
        totals[2] += counts["unsupported_metric_count"]
    return per_subview, (totals[0], totals[1], totals[2])


def _validate_json_metric_value(metric_id: str, value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ResultSchemaError(f"metric {metric_id} cannot contain NaN or infinity")
    if isinstance(value, Mapping):
        for child in value.values():
            _validate_json_metric_value(metric_id, child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            _validate_json_metric_value(metric_id, child)
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ResultSchemaError(f"metric {metric_id} contains a non-JSON value")


def _portable_id(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value) is not None


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _portable_relative_path(value: object, *, required_prefix: str) -> bool:
    if not isinstance(value, str) or not value.startswith(required_prefix):
        return False
    normalized = value.replace("\\", "/")
    return (
        normalized == value
        and not normalized.startswith("/")
        and ":" not in normalized
        and all(part not in {"", ".", ".."} for part in normalized.split("/"))
    )


def _require_timestamp(value: object, field: str) -> None:
    if not isinstance(value, str) or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value
    ) is None:
        raise ResultSchemaError(f"{field} must be RFC3339 UTC")
