"""Analyze validated Stage 7 campaign artifacts and declare shortlists."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from app.benchmark_contracts.canonical import canonical_sha256
from app.benchmark_contracts.manifest_io import file_sha256, read_manifest
from app.core_screening.metrics import (
    STAGE10_ONLY_METRICS,
    analyze_asr_items,
    analyze_reliability,
    analyze_vad_segments,
)
from app.core_screening.selection import AdvancementRules, Objective, select_candidates
from app.utils.json_utils import read_json, write_json


ANALYSIS_SCHEMA_VERSION = "core-screening-analysis.v1"


def analyze_screening_campaign(
    plan_path: Path,
    analysis_index_path: Path,
    *,
    qualification_path: Path | None = None,
    output_dir: Path | None = None,
    expected_plan_schema: str = "core-screening-plan.v1",
    analysis_schema_version: str = ANALYSIS_SCHEMA_VERSION,
    analysis_id_prefix: str = "core_screening",
    write_outputs: bool = True,
) -> dict[str, object]:
    """Consume a Stage 6 analysis index without changing scenario artifacts."""

    plan_file = plan_path.resolve()
    index_file = analysis_index_path.resolve()
    plan = _mapping(read_json(plan_file), "plan")
    if plan.get("schema_version") != expected_plan_schema:
        raise ValueError(f"unsupported screening plan: {plan.get('schema_version')!r}")
    index = _mapping(read_json(index_file), "analysis input index")
    if index.get("schema_version") != "analysis-input-index.v1":
        raise ValueError("Stage 7 analysis requires a validated Stage 6 analysis index")
    campaign_root = index_file.parent.parent
    scenario_catalog_path = plan_file.parent / str(plan["scenario_catalog"]["path"])
    if file_sha256(scenario_catalog_path) != plan["scenario_catalog"]["sha256"]:
        raise ValueError("Stage 7 screening scenario catalog checksum mismatch")
    scenarios = {
        str(row["scenario_id"]): row
        for row in _read_jsonl_tolerant(scenario_catalog_path)
        if isinstance(row, Mapping) and row.get("scenario_id")
    }
    manifest_name = Path(str(plan["benchmark"]["manifest"]["path"])).name
    manifest_path = campaign_root / "benchmark_manifests" / manifest_name
    if not manifest_path.is_file():
        fallback = plan_file.parent.parent / "benchmarks" / "v1" / manifest_name
        manifest_path = fallback if fallback.is_file() else manifest_path
    if file_sha256(manifest_path) != plan["benchmark"]["manifest"]["sha256"]:
        raise ValueError("analysis benchmark manifest checksum mismatch")
    manifest_rows = read_manifest(manifest_path)
    indexed_results = {
        str(row["scenario_id"]): row
        for row in index.get("scenario_results", [])
        if isinstance(row, Mapping)
    }

    stage_results = []
    for stage in plan["stages"]:
        if not isinstance(stage, Mapping) or stage.get("mode") != "campaign_scenarios":
            continue
        stage_id = str(stage["stage_id"])
        if stage_id == "FINAL" and not stage.get("candidates"):
            continue
        candidates = []
        membership = _mapping(
            stage.get("scenario_ids_by_candidate"), "stage membership"
        )
        for candidate_id in stage.get("candidates", []):
            scenario_ids = [str(value) for value in membership.get(candidate_id, [])]
            candidates.append(
                _analyze_candidate(
                    str(candidate_id),
                    scenario_ids,
                    scenarios,
                    indexed_results,
                    campaign_root,
                    manifest_rows,
                )
            )
        if stage_id == "C":
            fixed = _mapping(stage.get("fixed"), "Stage C fixed settings")
            _attach_reference_deltas(
                candidates,
                f"full_record__{fixed['asr']}",
            )
        item_hashes = {str(row["comparison_item_set_sha256"]) for row in candidates}
        identical_items = len(item_hashes) <= 1
        if not identical_items:
            raise ValueError(
                f"Stage {stage_id} candidates do not use identical benchmark items"
            )
        selection = None
        rule_name = stage.get("advancement_rule")
        if rule_name and candidates:
            rules = _advancement_rules(plan, str(rule_name))
            selection = select_candidates(candidates, rules)
        stage_results.append(
            {
                "stage_id": stage_id,
                "name": stage["name"],
                "identical_benchmark_items": identical_items,
                "comparison_item_set_sha256": next(iter(item_hashes), None),
                "candidates": candidates,
                "selection": selection,
            }
        )

    qualification = None
    if qualification_path is not None:
        qualification = _mapping(
            read_json(qualification_path.resolve()), "qualification"
        )
        if qualification.get("schema_version") != "core-component-qualification.v1":
            raise ValueError("unsupported Stage 7 qualification artifact")

    result: dict[str, object] = {
        "schema_version": analysis_schema_version,
        "plan_id": plan["plan_id"],
        "plan_hash": plan["plan_hash"],
        "campaign_id": index["campaign_id"],
        "analysis_input_id": index.get("analysis_input_id"),
        "benchmark_manifest_id": plan["benchmark"]["manifest"]["manifest_id"],
        "qualification": qualification,
        "stages": stage_results,
        "stage10_metric_fields_emitted": False,
        "unsupported_metrics_policy": (
            "metrics are emitted only when their required reference/output contract is present"
        ),
    }
    _assert_no_stage10_metric_fields(result)
    digest = canonical_sha256(result)
    result["analysis_hash"] = digest
    result["analysis_id"] = f"{analysis_id_prefix}_{digest[:12].lower()}"
    destination = (
        output_dir or campaign_root / "analysis" / "core_screening"
    ).resolve()
    if write_outputs:
        destination.mkdir(parents=True, exist_ok=True)
        write_json(destination / "screening_analysis.json", result)
        _write_analysis_markdown(destination / "screening_analysis.md", result)
    return result


def _analyze_candidate(
    candidate_id: str,
    scenario_ids: Sequence[str],
    scenarios: Mapping[str, Mapping[str, object]],
    indexed_results: Mapping[str, Mapping[str, object]],
    campaign_root: Path,
    manifest_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    expected_all: list[dict[str, object]] = []
    prediction_all: list[object] = []
    failure_all: list[dict[str, object]] = []
    diagnostic_all: list[dict[str, object]] = []
    component_spans: list[dict[str, object]] = []
    vad_items: list[dict[str, object]] = []
    reliability_rows = []
    repetitions: set[int] = set()
    planned_item_identities: list[str] = []
    resource_summaries = []

    for scenario_id in scenario_ids:
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            raise ValueError(
                f"screening plan references unknown scenario {scenario_id}"
            )
        repetition = int(scenario["repetition"])
        repetitions.add(repetition)
        expected = _expected_scenario_items(manifest_rows, scenario)
        prefix = f"rep{repetition}:"
        expected_prefixed = [_prefix_item(row, prefix) for row in expected]
        expected_all.extend(expected_prefixed)
        planned_item_identities.extend(
            f"{repetition}:{row['recording_id']}:{row['utt_id']}" for row in expected
        )

        indexed = indexed_results.get(scenario_id)
        if indexed is None:
            reliability_rows.append({"status": "failed_terminal", "attempt": 1})
            vad_items.extend(
                {
                    "duration_sec": row.get("duration_sec"),
                    "predicted_regions": [],
                    "segments": [],
                }
                for row in expected_prefixed
            )
            continue
        result_root = campaign_root / str(indexed["result_root"])
        status = _scenario_status(result_root)
        reliability_rows.append(status)
        predictions = _read_jsonl_tolerant(
            result_root / "predictions" / "utterances.jsonl"
        )
        diagnostics = _read_jsonl_tolerant(
            result_root / "predictions" / "diagnostics.jsonl"
        )
        failures = _read_failures(result_root / "metrics" / "failures.parquet")
        spans = _read_jsonl_tolerant(
            result_root / "resource_logs" / "component_spans.jsonl"
        )
        resource_path = result_root / "resource_logs" / "resource_summary.json"
        if resource_path.is_file():
            resource_summaries.append(
                _mapping(read_json(resource_path), "resource summary")
            )
        prediction_all.extend(_prefix_output(row, prefix) for row in predictions)
        failure_all.extend(
            _prefix_output(row, prefix) for row in failures if isinstance(row, Mapping)
        )
        diagnostic_rows = [
            _prefix_output(_flatten_diagnostic(row), prefix)
            for row in diagnostics
            if isinstance(row, Mapping)
        ]
        diagnostic_all.extend(diagnostic_rows)
        component_spans.extend(row for row in spans if isinstance(row, Mapping))
        diagnostics_by_key = {
            (str(row.get("recording_id")), str(row.get("utt_id"))): row
            for row in diagnostic_rows
        }
        for item in expected_prefixed:
            diagnostic = diagnostics_by_key.get(
                (str(item["recording_id"]), str(item["utt_id"]))
            )
            vad_item = {
                "duration_sec": item.get("duration_sec"),
                "predicted_regions": (
                    diagnostic.get("vad_regions", []) if diagnostic else []
                ),
                "segments": diagnostic.get("segments", []) if diagnostic else [],
            }
            if item.get("reference_regions") is not None:
                vad_item["reference_regions"] = item["reference_regions"]
            vad_items.append(vad_item)

    resources = _merge_resource_summaries(resource_summaries)
    asr = analyze_asr_items(
        expected_all,
        prediction_all,
        failure_rows=failure_all,
        diagnostic_rows=diagnostic_all,
        component_spans=component_spans,
        resource_summary=resources or None,
    )
    grouped_metrics = _group_asr_metrics(
        expected_all,
        prediction_all,
        failure_all,
        diagnostic_all,
    )
    condition_rows = grouped_metrics.get("condition_id", [])
    condition_wers = [
        float(row["micro_wer"])
        for row in condition_rows
        if row.get("micro_wer") is not None
    ]
    clean_wer = next(
        (
            float(row["micro_wer"])
            for row in condition_rows
            if row.get("group_value") == "clean" and row.get("micro_wer") is not None
        ),
        None,
    )
    vad = analyze_vad_segments(vad_items)
    vad["downstream_asr"] = {
        "micro_wer": asr["micro_wer"],
        "macro_wer": asr["macro_wer"],
        "micro_cer": asr["micro_cer"],
        "macro_cer": asr["macro_cer"],
        "valid_output_rate": asr["valid_output_rate"],
    }
    reliability = analyze_reliability(reliability_rows)
    result: dict[str, object] = {
        "candidate_id": candidate_id,
        "scenario_count": len(scenario_ids),
        "repetitions": len(repetitions),
        "comparison_item_set_sha256": canonical_sha256(sorted(planned_item_identities)),
        "reliability": reliability,
        "vad": vad,
        "grouped_metrics": grouped_metrics,
        "worst_condition_micro_wer": max(condition_wers) if condition_wers else None,
        "max_condition_wer_degradation_vs_clean": (
            max(value - clean_wer for value in condition_wers)
            if condition_wers and clean_wer is not None
            else None
        ),
        **{
            key: deepcopy(value)
            for key, value in asr.items()
            if key not in {"schema_version", "supported_metrics", "unsupported_metrics"}
        },
        "asr_schema_version": asr["schema_version"],
        "supported_metrics": asr["supported_metrics"],
        "unsupported_metrics": asr["unsupported_metrics"],
        "timeout_rate": reliability["timeout_rate"],
        "oom_rate": reliability["oom_rate"],
        "scenario_completion_rate": reliability["scenario_completion_rate"],
    }
    return result


def _group_asr_metrics(
    expected: Sequence[Mapping[str, object]],
    predictions: Sequence[object],
    failures: Sequence[Mapping[str, object]],
    diagnostics: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for dimension in (
        "dataset",
        "condition_id",
        "noise_type",
        "snr_db",
        "rir_environment",
        "speaker_id",
        "gender",
        "accent",
    ):
        values = sorted(
            {
                str(row[dimension])
                for row in expected
                if row.get(dimension) not in {None, ""}
            }
        )
        groups = []
        for value in values:
            selected = [row for row in expected if str(row.get(dimension)) == value]
            keys = {(str(row["recording_id"]), str(row["utt_id"])) for row in selected}
            selected_predictions = [
                row
                for row in predictions
                if isinstance(row, Mapping)
                and (str(row.get("recording_id")), str(row.get("utt_id"))) in keys
            ]
            selected_failures = [
                row
                for row in failures
                if (str(row.get("recording_id")), str(row.get("utt_id"))) in keys
            ]
            selected_diagnostics = [
                row
                for row in diagnostics
                if (str(row.get("recording_id")), str(row.get("utt_id"))) in keys
            ]
            metrics = analyze_asr_items(
                selected,
                selected_predictions,
                failure_rows=selected_failures,
                diagnostic_rows=selected_diagnostics,
            )
            groups.append(
                {
                    "group_value": value,
                    "expected_items": metrics["expected_items"],
                    "valid_output_rate": metrics["valid_output_rate"],
                    "missing_prediction_rate": metrics["missing_prediction_rate"],
                    "failure_rate": metrics["failure_rate"],
                    "micro_wer": metrics["micro_wer"],
                    "macro_wer": metrics["macro_wer"],
                    "micro_cer": metrics["micro_cer"],
                    "macro_cer": metrics["macro_cer"],
                }
            )
        if groups:
            result[dimension] = groups
    return result


def _attach_reference_deltas(
    candidates: Sequence[dict[str, object]], reference_candidate_id: str
) -> None:
    reference = next(
        (
            candidate
            for candidate in candidates
            if candidate.get("candidate_id") == reference_candidate_id
        ),
        None,
    )
    if reference is None:
        return
    for candidate in candidates:
        candidate["downstream_delta_vs_reference"] = {
            "reference_candidate_id": reference_candidate_id,
            "micro_wer": _numeric_delta(
                candidate.get("micro_wer"), reference.get("micro_wer")
            ),
            "micro_cer": _numeric_delta(
                candidate.get("micro_cer"), reference.get("micro_cer")
            ),
            "valid_output_rate": _numeric_delta(
                candidate.get("valid_output_rate"), reference.get("valid_output_rate")
            ),
        }


def _numeric_delta(value: object, reference: object) -> float | None:
    if value is None or reference is None:
        return None
    try:
        return float(value) - float(reference)
    except (TypeError, ValueError):
        return None


def _expected_scenario_items(
    rows: Sequence[Mapping[str, object]], scenario: Mapping[str, object]
) -> list[dict[str, object]]:
    data_slice = _mapping(scenario["dataset_slice"], "dataset slice")
    filters = _mapping(data_slice["filters"], "dataset filters")
    condition = _mapping(scenario["condition"], "condition")
    selected = []
    for row in rows:
        if row.get("dataset") != data_slice["dataset"]:
            continue
        if (
            row.get("benchmark_tier") != scenario["tier"]
            or row.get("panel") != scenario["panel"]
        ):
            continue
        if any(
            row.get(key) != value for key, value in filters.items() if value is not None
        ):
            continue
        recording_id = str(row["recording_id"])
        if condition["augmentation"] != "none":
            recording_id = f"{recording_id}__aug_{condition['id']}"
        current = {
            "recording_id": recording_id,
            "utt_id": str(row["utt_id"]),
            "reference_text": str(row["reference_text"]),
            "duration_sec": float(row["duration_sec"]),
            "dataset": str(row["dataset"]),
            "condition_id": str(condition["id"]),
            "noise_type": condition.get("noise_type"),
            "snr_db": condition.get("snr_db"),
            "rir_environment": (
                condition["rir"].get("environment")
                if isinstance(condition.get("rir"), Mapping)
                else None
            ),
            "speaker_id": row.get("speaker_id"),
            "gender": row.get("gender"),
            "accent": row.get("accent"),
        }
        if row.get("reference_regions") is not None:
            current["reference_regions"] = row["reference_regions"]
        selected.append(current)
    selected.sort(key=lambda row: (str(row["recording_id"]), str(row["utt_id"])))
    if len(selected) != int(data_slice["row_count"]):
        raise ValueError(
            f"scenario {scenario['scenario_id']} benchmark row count mismatch"
        )
    return selected


def _prefix_item(row: Mapping[str, object], prefix: str) -> dict[str, object]:
    result = dict(row)
    result["recording_id"] = prefix + str(row["recording_id"])
    return result


def _prefix_output(row: object, prefix: str) -> object:
    if not isinstance(row, Mapping):
        return row
    result = dict(row)
    if result.get("recording_id"):
        result["recording_id"] = prefix + str(result["recording_id"])
    return result


def _flatten_diagnostic(row: Mapping[str, object]) -> dict[str, object]:
    result = dict(row)
    nested = row.get("diagnostics")
    if isinstance(nested, Mapping):
        result.update({str(key): value for key, value in nested.items()})
    return result


def _scenario_status(root: Path) -> dict[str, object]:
    path = root / "status.json"
    if not path.is_file():
        return {"status": "invalid", "attempt": 1}
    value = _mapping(read_json(path), "scenario status")
    return {
        "status": str(value.get("state") or value.get("status") or "invalid"),
        "attempt": int(value.get("attempt") or value.get("attempt_count") or 1),
    }


def _read_failures(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    frame = pd.read_parquet(path)
    return [
        {str(key): value for key, value in row.items() if not pd.isna(value)}
        for row in frame.to_dict(orient="records")
    ]


def _read_jsonl_tolerant(path: Path) -> list[object]:
    if not path.is_file():
        return []
    rows: list[object] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"malformed_json": True})
    return rows


def _merge_resource_summaries(
    summaries: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not summaries:
        return {}
    result: dict[str, object] = {
        "scenario_summary_count": len(summaries),
        "sample_count": sum(int(value.get("sample_count") or 0) for value in summaries),
        "span_count": sum(int(value.get("span_count") or 0) for value in summaries),
        "sampling_gap_count": sum(
            int(value.get("sampling_gap_count") or 0) for value in summaries
        ),
        "sampling_interval_sec": sorted(
            {
                float(value["sampling_interval_sec"])
                for value in summaries
                if value.get("sampling_interval_sec") is not None
            }
        ),
        "resources": _merge_named_metric_summaries(summaries, "resources"),
        "components": _merge_named_metric_summaries(summaries, "components"),
        "phases": _merge_named_metric_summaries(summaries, "phases"),
        "warnings": sorted(
            {
                str(warning)
                for summary in summaries
                for warning in summary.get("warnings", [])
            }
        ),
    }
    return result


def _merge_named_metric_summaries(
    summaries: Sequence[Mapping[str, object]], key: str
) -> dict[str, object]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for summary in summaries:
        values = summary.get(key)
        if not isinstance(values, Mapping):
            continue
        for name, value in values.items():
            if isinstance(value, Mapping):
                grouped.setdefault(str(name), []).append(value)
    result = {}
    for name, values in sorted(grouped.items()):
        counts = [int(value.get("count") or 0) for value in values]
        means = [
            (float(value["mean"]), count)
            for value, count in zip(values, counts, strict=True)
            if value.get("mean") is not None and count > 0
        ]
        maxima = [
            float(value["max"]) for value in values if value.get("max") is not None
        ]
        result[name] = {
            "count": sum(counts),
            "weighted_mean": (
                sum(mean * count for mean, count in means)
                / sum(count for _mean, count in means)
                if means
                else None
            ),
            "scenario_max": max(maxima) if maxima else None,
            "scenario_count": len(values),
        }
    return result


def _advancement_rules(plan: Mapping[str, object], name: str) -> AdvancementRules:
    protocol = _mapping(plan["protocol"], "protocol")
    contents = _mapping(protocol["contents"], "protocol contents")
    advancement = _mapping(contents["advancement"], "advancement")
    raw = _mapping(advancement[name], f"advancement.{name}")
    objectives = tuple(
        Objective(
            metric=str(value["metric"]),
            direction=str(value["direction"]),
            category=str(value["category"]),
            required=bool(value.get("required", True)),
            tolerance=float(value.get("tolerance", 0.0)),
        )
        for value in raw["objectives"]
        if isinstance(value, Mapping)
    )
    return AdvancementRules(
        objectives=objectives,
        maximum_candidates=int(raw["maximum_candidates"]),
        minimum_valid_output_rate=float(raw["minimum_valid_output_rate"]),
        maximum_failure_rate=float(raw["maximum_failure_rate"]),
        maximum_timeout_rate=float(raw["maximum_timeout_rate"]),
        maximum_oom_rate=float(raw["maximum_oom_rate"]),
        minimum_repetitions=int(raw["minimum_repetitions"]),
    )


def _assert_no_stage10_metric_fields(value: object) -> None:
    forbidden = {metric.casefold() for metric in STAGE10_ONLY_METRICS}
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in forbidden:
                raise ValueError(f"Stage 10-only metric field was emitted: {key}")
            _assert_no_stage10_metric_fields(item)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            _assert_no_stage10_metric_fields(item)


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return dict(value)


def _write_analysis_markdown(path: Path, result: Mapping[str, object]) -> None:
    lines = [
        "# Stage 7 Core Screening Analysis",
        "",
        f"- Analysis ID: `{result['analysis_id']}`",
        f"- Campaign: `{result['campaign_id']}`",
        f"- Plan: `{result['plan_id']}`",
        "",
    ]
    for stage in result["stages"]:
        lines.extend([f"## Stage {stage['stage_id']} — {stage['name']}", ""])
        selection = stage.get("selection")
        if selection:
            advanced = ", ".join(selection["advanced_candidate_ids"]) or "none"
            lines.append(f"Advanced: {advanced}")
        else:
            lines.append("No advancement decision is defined for this stage.")
        lines.append("")
    lines.extend(
        [
            "Missing and failed outputs remained in every expected-item denominator. Metrics requiring unavailable references were listed as unsupported rather than emitted.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
