"""Development-only analysis and deterministic compact reporting.

The analyzer consumes checksum-validated controller outputs and a passing
all-18 qualification bundle.  It refuses held-out rows, keeps missing and
failed evidence explicit, publishes the mandatory six Tier-B anchors plus at
most two development-nondominated challengers, and never declares a winner.
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
import shutil
from typing import Mapping, Sequence
import zipfile

import yaml

from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    read_json,
    sha256_bytes,
    sha256_file,
    write_bytes_atomic,
    write_json_atomic,
)
from app.full_pipeline_evaluation.metrics import METRIC_CATALOG
from app.full_pipeline_evaluation.planning import matrix

from .freeze import MANDATORY_EXTENDED_PIPELINES, build_extended_set
from .qualification import require_valid_qualification_bundle


DEVELOPMENT_ANALYSIS_SCHEMA_VERSION = "full-pipeline-development-analysis.v1"
DEVELOPMENT_REPORT_SCHEMA_VERSION = "full-pipeline-development-report.v1"
COMPACT_ZIP_NAME = "full_pipeline_development_compact.zip"
REQUESTED_OUTPUTS = (
    "development_matrix.csv",
    "development_summary.csv",
    "extended_set.yaml",
    "development_report.md",
    "metric_guide.md",
    "failure_inventory.csv",
    "resource_spot_checks.csv",
    "development_analysis.json",
    "checksums.json",
)


class DevelopmentReportingError(RuntimeError):
    """Development artifacts are incomplete, non-comparable, or contaminated."""


def publish_development_report(
    *,
    analysis_index: Mapping[str, object] | Path,
    campaign_manifest: Mapping[str, object] | Path,
    qualification_bundle: Mapping[str, object] | Path,
    frozen_config_root: Path,
    output_root: Path,
    qualification_plan: Mapping[str, object] | Path | None = None,
    qualification_evidence_root: Path | None = None,
    verify_qualification_evidence: bool = True,
) -> dict[str, object]:
    """Validate and publish every exact Prompt-4 development output."""

    analysis = _mapping_or_json(analysis_index, "analysis index")
    manifest = _mapping_or_json(campaign_manifest, "campaign manifest")
    bundle = _mapping_or_json(qualification_bundle, "qualification bundle")
    qualification_validation = require_valid_qualification_bundle(
        qualification_bundle,
        plan=qualification_plan,
        evidence_root=qualification_evidence_root,
        verify_evidence_files=verify_qualification_evidence,
    )
    for bundle_field, manifest_field in (
        ("development_identity_sha256", "development_identity"),
        ("matrix_sha256", "matrix_sha256"),
        ("runtime_config_sha256", "runtime_config_sha256"),
    ):
        if bundle.get(bundle_field) != manifest.get(manifest_field):
            raise DevelopmentReportingError(
                f"qualification {bundle_field} differs from the campaign manifest"
            )
    rows = _validated_development_rows(analysis, manifest)
    metric_rows, failures = _metric_rows(rows)
    summary_rows = _pipeline_summaries(metric_rows, rows)
    extended_set = build_extended_set(summary_rows, maximum_additional_challengers=2)
    if extended_set["mandatory_pipeline_ids"] != list(MANDATORY_EXTENDED_PIPELINES):
        raise DevelopmentReportingError("mandatory six Tier-B anchors changed")
    if len(extended_set["additional_challenger_pipeline_ids"]) > 2:
        raise DevelopmentReportingError("more than two development challengers selected")

    destination = Path(output_root).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    _copy_frozen_configs(Path(frozen_config_root), destination / "frozen_pipeline_configs")
    qualification_records = {
        str(row["pipeline_id"]): row
        for row in bundle["records"]
        if isinstance(row, Mapping)
    }
    matrix_rows = _development_matrix_rows(qualification_records)
    resource_rows = _resource_spot_check_rows(metric_rows)
    _write_csv(destination / "development_matrix.csv", matrix_rows)
    _write_csv(destination / "development_summary.csv", summary_rows)
    _write_csv(destination / "failure_inventory.csv", failures)
    _write_csv(destination / "resource_spot_checks.csv", resource_rows)
    _write_yaml(destination / "extended_set.yaml", extended_set)
    write_bytes_atomic(destination / "metric_guide.md", _metric_guide().encode("utf-8"))

    analysis_core = {
        "schema_version": DEVELOPMENT_ANALYSIS_SCHEMA_VERSION,
        "status": "PASS",
        "campaign_id": manifest["campaign_id"],
        "campaign_identity_sha256": manifest["campaign_identity_sha256"],
        "development_identity_sha256": manifest["development_identity"],
        "matrix_sha256": manifest["matrix_sha256"],
        "runtime_config_sha256": manifest["runtime_config_sha256"],
        "qualification_result_sha256": bundle["qualification_result_sha256"],
        "qualification_validation": qualification_validation,
        "pipeline_count": len(summary_rows),
        "development_job_count": len(rows),
        "failure_inventory_count": len(failures),
        "resource_spot_check_count": len(resource_rows),
        "pipeline_summaries": summary_rows,
        "extended_set": extended_set,
        "weighted_composite_score_created": False,
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
        "final_winner": None,
    }
    analysis_document = {
        **analysis_core,
        "analysis_identity_sha256": sha256_bytes(canonical_json_bytes(analysis_core)),
    }
    write_json_atomic(destination / "development_analysis.json", analysis_document)
    report_text = _development_report(analysis_document)
    write_bytes_atomic(destination / "development_report.md", report_text.encode("utf-8"))

    checksums = checksum_map(
        destination,
        exclude=("checksums.json", COMPACT_ZIP_NAME),
    )
    write_json_atomic(
        destination / "checksums.json",
        {
            "schema_version": "full-pipeline-development-report-checksums.v1",
            "hash_algorithm": "sha256",
            "entries": checksums,
            "raw_audio_included": False,
            "model_assets_included": False,
            "cache_payloads_included": False,
            "biometric_vectors_included": False,
        },
    )
    zip_path = destination / COMPACT_ZIP_NAME
    _write_deterministic_zip(destination, zip_path)
    return {
        "schema_version": DEVELOPMENT_REPORT_SCHEMA_VERSION,
        "status": "PASS",
        "output_root": str(destination),
        "pipeline_count": len(summary_rows),
        "mandatory_anchor_count": len(MANDATORY_EXTENDED_PIPELINES),
        "additional_challenger_count": len(
            extended_set["additional_challenger_pipeline_ids"]
        ),
        "production_winner_selected": False,
        "evaluation_material_inspected": False,
        "requested_outputs": [*REQUESTED_OUTPUTS, "frozen_pipeline_configs/"],
        "compact_zip": str(zip_path),
        "compact_zip_sha256": sha256_file(zip_path),
    }


def collect_development_report(output_root: Path) -> dict[str, object]:
    """Revalidate report checksums and deterministically rebuild the compact ZIP."""

    root = Path(output_root).resolve()
    checksums_path = root / "checksums.json"
    if not checksums_path.is_file():
        raise DevelopmentReportingError("development report checksums are absent")
    value = read_json(checksums_path)
    entries = value.get("entries")
    if not isinstance(entries, Mapping):
        raise DevelopmentReportingError("development report checksum entries are invalid")
    actual = checksum_map(root, exclude=("checksums.json", COMPACT_ZIP_NAME))
    if dict(entries) != actual:
        raise DevelopmentReportingError("development report bytes differ from checksums")
    zip_path = root / COMPACT_ZIP_NAME
    _write_deterministic_zip(root, zip_path)
    return {
        "schema_version": "full-pipeline-development-report-collection.v1",
        "status": "PASS",
        "output_root": str(root),
        "artifact_count": len(actual),
        "compact_zip": str(zip_path),
        "compact_zip_sha256": sha256_file(zip_path),
        "raw_audio_included": False,
        "model_assets_included": False,
        "cache_payloads_included": False,
        "biometric_vectors_included": False,
    }


def _validated_development_rows(
    analysis: Mapping[str, object], manifest: Mapping[str, object]
) -> list[dict[str, object]]:
    if analysis.get("schema_version") != "full-pipeline-evaluation-analysis.v1":
        raise DevelopmentReportingError("controller analysis schema differs")
    if analysis.get("campaign_id") != manifest.get("campaign_id"):
        raise DevelopmentReportingError("analysis and campaign identities differ")
    parallelism = manifest.get("parallelism_policy")
    if not isinstance(parallelism, Mapping) or parallelism.get(
        "resource_measurement_jobs"
    ) != 1:
        raise DevelopmentReportingError(
            "campaign does not attest serial matched resource measurement"
        )
    expected_jobs_value = manifest.get("jobs")
    if not isinstance(expected_jobs_value, list):
        raise DevelopmentReportingError("campaign manifest jobs are absent")
    expected = {
        str(row["job_id"]): row
        for row in expected_jobs_value
        if isinstance(row, Mapping) and row.get("split") == "development"
    }
    raw_rows = analysis.get("rows")
    if not isinstance(raw_rows, list) or not all(
        isinstance(row, Mapping) for row in raw_rows
    ):
        raise DevelopmentReportingError("analysis rows are invalid")
    rows = [dict(row) for row in raw_rows]
    if any(str(row.get("split")) != "development" for row in rows):
        raise DevelopmentReportingError("held-out evaluation row reached development analysis")
    if any(row.get("evaluation_material_inspected") not in {None, False} for row in rows):
        raise DevelopmentReportingError("development result inspected evaluation material")
    actual = {str(row.get("job_id") or ""): row for row in rows}
    if len(actual) != len(rows):
        raise DevelopmentReportingError("analysis contains duplicate development job IDs")
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise DevelopmentReportingError(
            f"development result set is incomplete; missing={len(missing)}, extra={len(extra)}"
        )
    for job_id, row in actual.items():
        spec = expected[job_id]
        for field in ("pipeline_id", "protocol_id", "source_key", "measurement_mode"):
            if row.get(field) != spec.get(field):
                raise DevelopmentReportingError(f"{job_id}: {field} differs from campaign")
        if not _is_sha256(row.get("result_checksums_sha256")):
            raise DevelopmentReportingError(f"{job_id}: validated result checksum is absent")
    pipeline_ids = {str(row["pipeline_id"]) for row in rows}
    if pipeline_ids != set(matrix().pipeline_ids):
        raise DevelopmentReportingError("development results do not cover all 18 pipelines")
    for pipeline_id in pipeline_ids:
        modes = {
            str(row["measurement_mode"])
            for row in rows
            if row["pipeline_id"] == pipeline_id
        }
        if modes != {"accuracy", "resources"}:
            raise DevelopmentReportingError(
                f"{pipeline_id}: matched accuracy/resources development evidence is incomplete"
            )
    return sorted(rows, key=lambda row: str(row["job_id"]))


def _metric_rows(
    rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    metrics: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for row in rows:
        documents = _metric_documents(row)
        seen: set[str] = set()
        for view, document in sorted(documents.items()):
            subviews = document.get("subviews")
            if not isinstance(subviews, Mapping):
                raise DevelopmentReportingError(f"{row['job_id']}: {view} subviews absent")
            for category, report in sorted(subviews.items()):
                if not isinstance(report, Mapping) or not isinstance(
                    report.get("metrics"), Mapping
                ):
                    raise DevelopmentReportingError(
                        f"{row['job_id']}: {category} metric report invalid"
                    )
                for metric_id, raw in sorted(report["metrics"].items()):
                    if metric_id in seen:
                        raise DevelopmentReportingError(
                            f"{row['job_id']}: metric {metric_id} appears more than once"
                        )
                    seen.add(str(metric_id))
                    if not isinstance(raw, Mapping):
                        raise DevelopmentReportingError(
                            f"{row['job_id']}: metric {metric_id} is invalid"
                        )
                    metric = {
                        "job_id": row["job_id"],
                        "pipeline_id": row["pipeline_id"],
                        "source_key": row["source_key"],
                        "measurement_mode": row["measurement_mode"],
                        "view": view,
                        "category": category,
                        "metric_id": metric_id,
                        "status": raw.get("status"),
                        "value": raw.get("value"),
                        "numerator": raw.get("numerator"),
                        "denominator": raw.get("denominator"),
                        "reason": raw.get("reason"),
                    }
                    metrics.append(metric)
                    if raw.get("status") != "computed":
                        failures.append(
                            {
                                "pipeline_id": row["pipeline_id"],
                                "job_id": row["job_id"],
                                "source_key": row["source_key"],
                                "measurement_mode": row["measurement_mode"],
                                "category": category,
                                "metric_id": metric_id,
                                "status": raw.get("status"),
                                "reason": raw.get("reason"),
                            }
                        )
        missing = set(METRIC_CATALOG) - seen
        if missing:
            raise DevelopmentReportingError(
                f"{row['job_id']}: required metrics omitted: {sorted(missing)}"
            )
    return metrics, failures


def _pipeline_summaries(
    metrics: Sequence[Mapping[str, object]],
    result_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for pipeline_id in matrix().pipeline_ids:
        selection = matrix().resolve(pipeline_id)
        accuracy = [
            row
            for row in metrics
            if row["pipeline_id"] == pipeline_id
            and row["measurement_mode"] == "accuracy"
        ]
        resources = [
            row
            for row in metrics
            if row["pipeline_id"] == pipeline_id
            and row["measurement_mode"] == "resources"
        ]
        wrong_seconds = _sum_values(accuracy, "wrong_known_time_sec")
        known_duration = _sum_denominators(accuracy, "correctly_named_known_rate")
        if known_duration <= 0:
            raise DevelopmentReportingError(f"{pipeline_id}: known duration is unavailable")
        wrong_known_rate = wrong_seconds / known_duration
        stranger_false_known_rate = _ratio(accuracy, "fpir")
        speaker_attributed_wer = _ratio(accuracy, "speaker_attributed_wer")
        stable_name_latency_sec = _ratio(accuracy, "stable_name_latency_sec")
        total_rtf = _ratio(resources, "total_rtf")
        peak_rss_bytes = _maximum(resources, "peak_rss_bytes")
        pipeline_jobs = [row for row in result_rows if row["pipeline_id"] == pipeline_id]
        summaries.append(
            {
                "pipeline_id": pipeline_id,
                "asr_alias": selection.asr_alias,
                "diarization_alias": selection.diarization_alias,
                "identity_alias": selection.identity_alias,
                "hybrid_label": selection.hybrid_label,
                "frozen_anchor": selection.frozen_hybrid_anchor,
                "qualification_status": "VALID",
                "split": "development",
                "evaluation_material_inspected": False,
                "wrong_known_rate": wrong_known_rate,
                "stranger_false_known_rate": stranger_false_known_rate,
                "speaker_attributed_wer": speaker_attributed_wer,
                "stable_name_latency_sec": stable_name_latency_sec,
                "total_rtf": total_rtf,
                "peak_rss_bytes": peak_rss_bytes,
                "development_job_count": len(pipeline_jobs),
                "accuracy_job_count": sum(
                    row["measurement_mode"] == "accuracy" for row in pipeline_jobs
                ),
                "resource_job_count": sum(
                    row["measurement_mode"] == "resources" for row in pipeline_jobs
                ),
                "result_set_sha256": sha256_bytes(
                    canonical_json_bytes(
                        sorted(
                            (
                                str(row["job_id"]),
                                str(row["result_checksums_sha256"]),
                            )
                            for row in pipeline_jobs
                        )
                    )
                ),
            }
        )
    return summaries


def _development_matrix_rows(
    qualification_records: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for pipeline_id in matrix().pipeline_ids:
        record = qualification_records[pipeline_id]
        expected = record.get("expected_contract")
        if not isinstance(expected, Mapping):
            # Runtime bundles may omit the verbose plan body; current plan is authority.
            expected = {}
        minimum = expected.get("minimum_duration")
        minimum = minimum if isinstance(minimum, Mapping) else {}
        environments = expected.get("environments")
        environments = environments if isinstance(environments, Mapping) else {}
        equivalence = record["checks"]["cold_vs_shared_equivalence"]
        aliases = record["aliases"]
        rows.append(
            {
                "pipeline_id": pipeline_id,
                "asr_alias": aliases["asr"],
                "diarization_alias": aliases["anonymous_diarization"],
                "identity_alias": aliases["identity"],
                "hybrid_label": aliases["hybrid"],
                "frozen_anchor": record["frozen_anchor"],
                "qualification_status": record["qualification_status"],
                "expected_contract_sha256": record["expected_contract_sha256"],
                "record_identity_sha256": record["record_identity_sha256"],
                "asr_environment": environments.get("asr"),
                "segmentation_environment": environments.get("segmentation"),
                "diarization_embedding_environment": environments.get(
                    "diarization_embedding"
                ),
                "identity_environment": environments.get("identity"),
                "documented_minimum_duration_sec": minimum.get(
                    "documented_minimum_duration_sec"
                ),
                "technical_checkpoint_duration_sec": minimum.get(
                    "technical_checkpoint_duration_sec"
                ),
                "checkpoint_outcome": record["checks"]["minimum_duration"].get(
                    "checkpoint_outcome"
                ),
                "cold_vs_shared_semantically_equivalent": equivalence.get(
                    "semantically_equivalent"
                ),
                "evaluation_material_inspected": False,
            }
        )
    return rows


def _resource_spot_check_rows(
    metrics: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    wanted = {
        "total_rtf",
        "peak_rss_bytes",
        "process_cpu_mean_percent",
        "process_cpu_p95_percent",
        "gpu_peak_memory_bytes",
        "model_startup_sec",
        "model_bytes",
        "cache_bytes",
        "maximum_queue_depth",
        "failure_count",
        "retry_count",
    }
    return [
        {
            "pipeline_id": row["pipeline_id"],
            "job_id": row["job_id"],
            "source_key": row["source_key"],
            "metric_id": row["metric_id"],
            "status": row["status"],
            "value": row["value"],
            "reason": row["reason"],
            "comparison_scope": "serial_matched_resource_jobs_only",
        }
        for row in metrics
        if row["measurement_mode"] == "resources" and row["metric_id"] in wanted
    ]


def _metric_documents(row: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    injected = row.get("metric_documents")
    if isinstance(injected, Mapping):
        return {
            str(key): value
            for key, value in injected.items()
            if isinstance(value, Mapping)
        }
    root = Path(str(row.get("result_root") or "")).resolve()
    documents: dict[str, Mapping[str, object]] = {}
    for path in sorted((root / "metrics").glob("*.json")):
        if path.name == "summary.json":
            continue
        value = read_json(path)
        documents[path.stem] = value
    if not documents:
        raise DevelopmentReportingError(f"{row['job_id']}: metric documents are absent")
    return documents


def _ratio(rows: Sequence[Mapping[str, object]], metric_id: str) -> float:
    selected = _computed(rows, metric_id)
    numerator = sum(float(row["numerator"]) for row in selected if _finite(row["numerator"]))
    denominator = sum(
        float(row["denominator"]) for row in selected if _finite(row["denominator"])
    )
    if denominator <= 0 or len(selected) != sum(
        _finite(row["numerator"]) and _finite(row["denominator"]) for row in selected
    ):
        raise DevelopmentReportingError(
            f"computed {metric_id} lacks complete positive numerator/denominator evidence"
        )
    return numerator / denominator


def _sum_values(rows: Sequence[Mapping[str, object]], metric_id: str) -> float:
    selected = _computed(rows, metric_id)
    if not selected or not all(_finite(row["value"]) for row in selected):
        raise DevelopmentReportingError(f"computed {metric_id} values are incomplete")
    return sum(float(row["value"]) for row in selected)


def _sum_denominators(rows: Sequence[Mapping[str, object]], metric_id: str) -> float:
    selected = _computed(rows, metric_id)
    if not selected or not all(_finite(row["denominator"]) for row in selected):
        raise DevelopmentReportingError(f"computed {metric_id} denominators are incomplete")
    return sum(float(row["denominator"]) for row in selected)


def _maximum(rows: Sequence[Mapping[str, object]], metric_id: str) -> float:
    selected = _computed(rows, metric_id)
    values = [float(row["value"]) for row in selected if _finite(row["value"])]
    if len(values) != len(selected) or not values:
        raise DevelopmentReportingError(f"computed {metric_id} values are incomplete")
    return max(values)


def _computed(
    rows: Sequence[Mapping[str, object]], metric_id: str
) -> list[Mapping[str, object]]:
    selected = [
        row
        for row in rows
        if row["metric_id"] == metric_id and row["status"] == "computed"
    ]
    if not selected:
        raise DevelopmentReportingError(f"required metric {metric_id} is not computed")
    return selected


def _copy_frozen_configs(source: Path, destination: Path) -> None:
    source = source.resolve()
    expected_names = {f"{pipeline_id}.yaml" for pipeline_id in matrix().pipeline_ids}
    names = {path.name for path in source.glob("*.yaml")}
    if names != expected_names or not (source / "checksums.json").is_file():
        raise DevelopmentReportingError(
            "frozen config root must contain exactly 18 pipeline YAMLs and checksums.json"
        )
    source_checksums = read_json(source / "checksums.json").get("entries")
    actual = checksum_map(source, exclude=("checksums.json",))
    if not isinstance(source_checksums, Mapping) or dict(source_checksums) != actual:
        raise DevelopmentReportingError("frozen config checksum coverage differs")
    destination.mkdir(parents=True, exist_ok=True)
    allowed = expected_names | {"checksums.json"}
    extras = {
        path.name for path in destination.iterdir() if path.is_file() and path.name not in allowed
    }
    if extras:
        raise DevelopmentReportingError(f"frozen config destination has extra files: {sorted(extras)}")
    for name in sorted(allowed):
        source_path = source / name
        target = destination / name
        if target.is_file() and target.read_bytes() != source_path.read_bytes():
            raise DevelopmentReportingError(f"existing frozen config conflicts: {name}")
        if not target.is_file():
            shutil.copy2(source_path, target)


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if rows:
        fields = list(rows[0])
        if any(set(row) != set(fields) for row in rows):
            raise DevelopmentReportingError(f"CSV rows have inconsistent fields: {path.name}")
    else:
        fields = [
            "pipeline_id",
            "job_id",
            "source_key",
            "measurement_mode",
            "category",
            "metric_id",
            "status",
            "reason",
        ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_bytes_atomic(path, stream.getvalue().encode("utf-8"))


def _write_yaml(path: Path, value: Mapping[str, object]) -> None:
    payload = yaml.safe_dump(
        dict(value), sort_keys=True, allow_unicode=True, default_flow_style=False
    ).encode("utf-8")
    write_bytes_atomic(path, payload)


def _metric_guide() -> str:
    lines = [
        "# Full-Pipeline Development Metric Guide",
        "",
        "All metrics are development-only. Raw cosine similarity is not a probability. "
        "Unsupported and undefined metrics remain explicit and are never replaced by zero.",
        "",
        "The Tier-B frontier is unweighted. `wrong_known_rate` is wrong-known speaker "
        "time divided by known-reference time; `stranger_false_known_rate` is the "
        "episode-level FPIR aggregate. Resource comparisons use serial matched jobs only.",
        "",
        "| Metric | Category | Unit | Direction | Definition |",
        "|---|---|---|---|---|",
    ]
    for metric_id, definition in METRIC_CATALOG.items():
        direction = (
            "maximize"
            if definition.higher_is_better is True
            else "minimize"
            if definition.higher_is_better is False
            else "descriptive"
        )
        description = definition.definition.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{metric_id}` | {definition.category} | {definition.unit} | "
            f"{direction} | {description} |"
        )
    return "\n".join(lines) + "\n"


def _development_report(analysis: Mapping[str, object]) -> str:
    extended = analysis["extended_set"]
    summaries = analysis["pipeline_summaries"]
    assert isinstance(extended, Mapping) and isinstance(summaries, list)
    lines = [
        "# Full-Pipeline Development Report",
        "",
        "Status: PASS",
        "",
        "This is development qualification and Pareto triage, not held-out evidence. "
        "No production winner has been selected.",
        "",
        f"- Pipelines qualified and analyzed: {analysis['pipeline_count']}",
        f"- Complete development jobs: {analysis['development_job_count']}",
        f"- Explicit unsupported/undefined metric rows: {analysis['failure_inventory_count']}",
        "- Weighted composite score: not created",
        "- Evaluation material inspected: no",
        "- Production winner: none",
        "",
        "## Tier-B development set",
        "",
        "The six AO/AG × H2/H4/H5 anchors always advance. At most two additional "
        "pipelines may advance only when development-nondominated.",
        "",
        "Mandatory anchors:",
        "",
    ]
    lines.extend(f"- `{value}`" for value in extended["mandatory_pipeline_ids"])
    lines.extend(["", "Additional development challengers:", ""])
    challengers = list(extended["additional_challenger_pipeline_ids"])
    lines.extend(f"- `{value}`" for value in challengers)
    if not challengers:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This report does not inspect or tune on the held-out evaluation partition, "
            "does not convert raw similarity to probability, and does not rank technical "
            "performance as license or deployment clearance.",
            "",
            "See `development_summary.csv` for the six unweighted frontier axes, "
            "`failure_inventory.csv` for all unavailable metrics, and `metric_guide.md` "
            "for definitions.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_deterministic_zip(root: Path, destination: Path) -> None:
    allowed_top_level = set(REQUESTED_OUTPUTS) | {"frozen_pipeline_configs"}
    files = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.resolve() != destination.resolve()
        and path.relative_to(root).parts[0] in allowed_top_level
    ]
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in files:
                relative = path.relative_to(root).as_posix()
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                archive.writestr(info, path.read_bytes(), compresslevel=9)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _mapping_or_json(
    value: Mapping[str, object] | Path, label: str
) -> dict[str, object]:
    if isinstance(value, Path):
        if not value.is_file():
            raise DevelopmentReportingError(f"{label} is missing: {value}")
        return read_json(value)
    return dict(value)


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _is_sha256(value: object) -> bool:
    text = str(value or "").casefold()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


__all__ = [
    "COMPACT_ZIP_NAME",
    "DEVELOPMENT_ANALYSIS_SCHEMA_VERSION",
    "DevelopmentReportingError",
    "collect_development_report",
    "publish_development_report",
]
