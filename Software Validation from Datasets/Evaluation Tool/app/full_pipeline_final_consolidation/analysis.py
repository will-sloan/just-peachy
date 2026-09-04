"""Failure retention, component attribution, and conservative adaptation decisions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from . import scope_fields
from .evidence import EvidenceBundle
from .io import read_csv, sha256_bytes, sha256_file
from .ranking import RankingResult


FAILURE_FILES = {
    4: "failure_inventory.csv",
    5: "all18_failures.csv",
    6: "failure_inventory.csv",
    7: "failure_inventory.csv",
}

COMPONENT_RULES = (
    (
        "resource_saturation",
        (
            "resource",
            "rtf",
            "ram",
            "memory",
            "deadline",
            "thermal",
            "dropped frame",
            "queue pressure",
            "oom",
        ),
    ),
    (
        "ui_event_delay",
        ("ui", "event delay", "event latency", "slow consumer", "queue latency"),
    ),
    (
        "transcript_alignment",
        ("alignment", "timestamp fusion", "word attribution", "cpwer"),
    ),
    (
        "session_memory",
        (
            "session memory",
            "reacquisition",
            "expiry",
            "unknown_n persistence",
            "re-entry",
        ),
    ),
    (
        "open_set_policy",
        (
            "open-set",
            "open set",
            "false-known",
            "wrong-known",
            "threshold",
            "top1",
            "margin",
            "fpir",
            "fnir",
        ),
    ),
    ("enrollment", ("enrollment", "profile", "sample consistency", "template")),
    (
        "identity_embedding",
        ("identity", "speaker embedding", "known speaker", "backend"),
    ),
    ("anonymous_clustering", ("cluster", "speaker confusion", "merge", "split")),
    ("segmentation", ("segmentation", "boundary", "overlap", "diarization")),
    ("endpointing", ("endpoint", "silence", "speech start", "speech end")),
    ("asr", ("asr", "transcript", "decoder", "wer", "cer", "partial")),
)

PROPAGATION = {
    "asr": ("WER/CER", "speaker-attributed WER", "transcript revisions"),
    "endpointing": ("WER", "delayed text", "delayed names", "transcript revisions"),
    "segmentation": ("DER/JER", "wrong speaker labels", "delayed names"),
    "anonymous_clustering": (
        "DER/JER",
        "wrong speaker labels",
        "false-known attribution",
        "identity revisions",
    ),
    "identity_embedding": (
        "wrong speaker labels",
        "false-known names",
        "delayed names",
    ),
    "enrollment": ("wrong speaker labels", "false-known names", "known-to-Unknown"),
    "open_set_policy": (
        "false-known names",
        "wrong-known time",
        "delayed/withheld names",
    ),
    "session_memory": ("wrong speaker labels", "delayed names", "identity revisions"),
    "transcript_alignment": (
        "speaker-attributed WER",
        "wrong speaker labels",
        "transcript revisions",
    ),
    "ui_event_delay": ("delayed text", "delayed names", "visible revisions"),
    "resource_saturation": (
        "WER/DER via dropped work",
        "delayed text",
        "delayed names",
        "failures",
    ),
    "unclassified": ("undetermined; requires source-log review",),
}

ALLOWED_ADAPTATION_DECISIONS = {
    "ASR_TARGET_ADAPTATION_CANDIDATE",
    "SPEAKER_EMBEDDING_SHORT_DURATION_CANDIDATE",
    "SEGMENTATION_REAL_DEVICE_DATA_REQUIRED",
    "POLICY_CHANGE_ONLY",
}
SOURCE_DECLARED_ADAPTATION_DECISIONS = ALLOWED_ADAPTATION_DECISIONS - {
    "POLICY_CHANGE_ONLY"
}


@dataclass(frozen=True)
class FailureAnalysis:
    source_row_count: int
    failed_records: tuple[Mapping[str, object], ...]
    component_counts: Mapping[str, int]
    pipeline_counts: Mapping[str, int]
    terminal_status_counts: Mapping[str, int]
    major_failure: str
    major_failure_detail: str
    fine_tuning_decision: str
    adaptation_candidates: tuple[Mapping[str, object], ...]
    measured_error_exposure: tuple[Mapping[str, object], ...]


def result_inventory(
    bundle: EvidenceBundle,
    *,
    authority_paths: Sequence[tuple[Path, str]] = (),
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for prompt, completion in sorted(bundle.completions.items()):
        fixed = [
            (completion.path, completion.sha256, "stage_completion", completion.path),
            (
                completion.manifest_path,
                completion.manifest_sha256,
                "universal_artifact_manifest",
                completion.path,
            ),
        ]
        for path, digest, binding, bound_by in fixed:
            rows.append(
                _inventory_row(
                    prompt=prompt,
                    path=path,
                    sha256=digest,
                    binding=binding,
                    binding_path=bound_by,
                )
            )
        for artifact in completion.artifacts:
            rows.append(
                _inventory_row(
                    prompt=prompt,
                    path=artifact.path,
                    sha256=artifact.sha256,
                    binding=artifact.binding,
                    binding_path=artifact.binding_path,
                )
            )
    for path, binding in authority_paths:
        rows.append(
            _inventory_row(
                prompt=8,
                path=path,
                sha256=sha256_file(path),
                binding=binding,
                binding_path=path,
            )
        )
    deduped: list[dict[str, object]] = []
    seen: set[tuple[int, str, str]] = set()
    for row in rows:
        key = (int(row["source_prompt"]), str(row["path"]), str(row["sha256"]))
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def analyze_failures(
    bundle: EvidenceBundle, rankings: RankingResult
) -> FailureAnalysis:
    source_rows = 0
    failed: list[dict[str, object]] = []
    statuses: Counter[str] = Counter()
    components: Counter[str] = Counter()
    pipelines: Counter[str] = Counter()
    adaptation: list[dict[str, object]] = []
    for prompt, basename in FAILURE_FILES.items():
        path = bundle.completions[prompt].one(basename)
        for row_index, row in enumerate(read_csv(path), start=1):
            source_rows += 1
            status = _status(row)
            statuses[status] += 1
            if not _is_failure(row, status):
                continue
            component = _component(row)
            candidates = _component_candidates(row)
            pipeline = str(
                row.get("pipeline_id") or row.get("preset_id") or "UNSPECIFIED"
            )
            reason = _first(
                row,
                (
                    "error_type",
                    "failure_type",
                    "reason",
                    "detail",
                    "last_error",
                ),
            )
            record = {
                **scope_fields(),
                "source_prompt": prompt,
                "source_file": str(path),
                "source_row_index": row_index,
                "pipeline_id": pipeline,
                "case_or_job_id": _first(
                    row,
                    (
                        "case_id",
                        "job_id",
                        "attempt_id",
                        "scenario_id",
                        "panel_id",
                        "dataset_id",
                        "input_id",
                    ),
                ),
                "terminal_status": status,
                "component": component,
                "component_candidates": candidates,
                "component_attribution": (
                    "SOURCE_DECLARED"
                    if _declared_component(row)
                    else "KEYWORD_ASSOCIATION_NOT_CAUSATION"
                ),
                "failure_reason_sha256": (
                    sha256_bytes(reason.encode("utf-8")) if reason else None
                ),
                "explicit_failure": _truth(row.get("explicit_failure")),
                "missing_result": _truth(row.get("missing_result")),
                "propagates_to": PROPAGATION[component],
                "raw_failure_retained_at_source": True,
            }
            failed.append(record)
            components[component] += 1
            pipelines[pipeline] += 1
            candidate = _adaptation_candidate(row, record)
            if candidate is not None:
                adaptation.append(candidate)

    measured = _measured_error_exposure(rankings.rows)
    wrong_known_total = sum(
        float(row.get("wrong_known_time_sec") or 0.0) for row in rankings.rows
    )
    stranger_false_known_total = sum(
        float(row.get("stranger_false_known_time_sec") or 0.0) for row in rankings.rows
    )
    safety_total = wrong_known_total + stranger_false_known_total
    if safety_total > 0:
        adaptation.append(
            _aggregate_policy_candidate(
                bundle,
                wrong_known_total=wrong_known_total,
                stranger_false_known_total=stranger_false_known_total,
                pipeline_count=len(rankings.rows),
            )
        )
    if safety_total > 0:
        major_failure = "open_set_identity_safety"
        major_detail = (
            "Held-out wrong-known/stranger-false-known exposure is the principal "
            "measured product risk; terminal failure counts remain reported separately."
        )
    elif failed:
        component, count = components.most_common(1)[0]
        major_failure = component
        major_detail = (
            f"{count} retained failed/missing records were attributed to {component}; "
            "this is an evidence association, not an unproven causal claim."
        )
    else:
        major_failure = "bounded_coverage_limit"
        major_detail = (
            "No terminal failure or identity exposure was recorded; the major limitation "
            "is that reduced eight-day evidence does not establish full-scope or real-XVF performance."
        )
    decision = _fine_tuning_decision(adaptation)
    return FailureAnalysis(
        source_row_count=source_rows,
        failed_records=tuple(failed),
        component_counts=dict(sorted(components.items())),
        pipeline_counts=dict(sorted(pipelines.items())),
        terminal_status_counts=dict(sorted(statuses.items())),
        major_failure=major_failure,
        major_failure_detail=major_detail,
        fine_tuning_decision=decision,
        adaptation_candidates=tuple(adaptation),
        measured_error_exposure=tuple(measured),
    )


def _inventory_row(
    *, prompt: int, path: Path, sha256: str, binding: str, binding_path: Path
) -> dict[str, object]:
    name = path.name.casefold()
    category = (
        "failure_inventory"
        if "failure" in name
        else "licensing_provenance"
        if "licens" in name or "provenance" in name
        else "frozen_policy"
        if any(token in name for token in ("frozen", "policy", "extended_set"))
        else "result_or_report"
    )
    return {
        "schema_version": "full-pipeline-final-result-file-inventory.v1",
        **scope_fields(),
        "source_prompt": prompt,
        "category": category,
        "path": str(path),
        "sha256": sha256,
        "binding": binding,
        "binding_path": str(binding_path),
        "required": True,
        "exists": path.is_file(),
        "hash_validated": True,
        "raw_payload_packaged": False,
    }


def _adaptation_candidate(
    row: Mapping[str, str], evidence: Mapping[str, object]
) -> dict[str, object] | None:
    decision = str(
        row.get("fine_tuning_candidate")
        or row.get("adaptation_candidate")
        or row.get("recommended_action")
        or ""
    ).upper()
    reproducible = _truth(
        row.get("reproducible_evidence") or row.get("reproducible_failure")
    )
    frozen_tests = str(
        row.get("frozen_tests_to_rerun") or row.get("regression_test_ids") or ""
    ).strip()
    if (
        decision not in SOURCE_DECLARED_ADAPTATION_DECISIONS
        or not reproducible
        or not frozen_tests
        or not str(evidence.get("case_or_job_id") or "").strip()
        or not evidence.get("failure_reason_sha256")
    ):
        return None
    expected_target = row.get("expected_training_target") or "SOURCE_DECLARED"
    regression_risk = row.get("regression_risk") or "SOURCE_DECLARED_REVIEW_REQUIRED"
    return {
        "decision": decision,
        "observed_failure": evidence["component"],
        "affected_scenario": evidence["case_or_job_id"],
        "pipeline_id": evidence["pipeline_id"],
        "expected_training_target": expected_target,
        "frozen_tests_to_rerun": frozen_tests,
        "regression_risk": regression_risk,
        "real_beaker_xvf_audio_required_first": (
            decision == "SEGMENTATION_REAL_DEVICE_DATA_REQUIRED"
            or _truth(row.get("real_beaker_xvf_audio_required_first"))
        ),
        "admission_basis": "SOURCE_DECLARED_REPRODUCIBLE_ADAPTATION_DECISION",
        "source_file": evidence["source_file"],
        "source_row_index": evidence["source_row_index"],
        "source_failure_reason_sha256": evidence["failure_reason_sha256"],
    }


def _aggregate_policy_candidate(
    bundle: EvidenceBundle,
    *,
    wrong_known_total: float,
    stranger_false_known_total: float,
    pipeline_count: int,
) -> dict[str, object]:
    """Record aggregate safety exposure as policy triage, never neural evidence."""

    source = bundle.completions[5].one("all18_finalist_summary.csv")
    evidence_digest = sha256_bytes(
        (
            f"{pipeline_count}|{wrong_known_total:.17g}|"
            f"{stranger_false_known_total:.17g}"
        ).encode("utf-8")
    )
    return {
        "decision": "POLICY_CHANGE_ONLY",
        "observed_failure": "open_set_policy_aggregate_exposure",
        "affected_scenario": "P5_EXACT_ALL18_HELDOUT_AGGREGATE",
        "pipeline_id": "ALL18_AGGREGATE",
        "expected_training_target": (
            "No neural training; investigate frozen threshold/margin/session policy"
        ),
        "frozen_tests_to_rerun": (
            "PROMPT5_FROZEN_HELDOUT_CORE;PROMPT6_PREDECLARED_EXTENDED_SET;"
            "PROMPT7_FROZEN_CANDIDATE_ACCEPTANCE"
        ),
        "regression_risk": (
            "Policy changes can trade false-known safety against known-speaker recall"
        ),
        "real_beaker_xvf_audio_required_first": False,
        "admission_basis": (
            "CHECKSUM_BOUND_AGGREGATE_HELDOUT_EXPOSURE_POLICY_ONLY_"
            "NOT_NEURAL_ADAPTATION_EVIDENCE"
        ),
        "source_file": str(source),
        "source_row_index": "AGGREGATE_ALL18",
        "source_failure_reason_sha256": evidence_digest,
        "wrong_known_time_sec_total": wrong_known_total,
        "stranger_false_known_time_sec_total": stranger_false_known_total,
        "source_file_sha256": sha256_file(source),
    }


def _component(row: Mapping[str, str]) -> str:
    candidates = _component_candidates(row)
    return candidates[0] if candidates else "unclassified"


def _declared_component(row: Mapping[str, str]) -> str:
    declared = (
        _first(
            row,
            ("component", "subsystem", "stage", "failure_component", "error_component"),
        )
        .strip()
        .casefold()
    )
    return next(
        (
            component
            for component in PROPAGATION
            if component != "unclassified"
            and declared.replace("-", "_").replace(" ", "_") == component
        ),
        "",
    )


def _component_candidates(row: Mapping[str, str]) -> tuple[str, ...]:
    declared = _declared_component(row)
    if declared:
        return (declared,)
    text = " ".join(str(value).casefold() for value in row.values())
    matches = tuple(
        component
        for component, tokens in COMPONENT_RULES
        if any(token in text for token in tokens)
    )
    return matches or ("unclassified",)


def _status(row: Mapping[str, str]) -> str:
    value = _first(row, ("status", "state", "terminal_status", "job_state"))
    return str(value or "UNSPECIFIED").upper()


def _is_failure(row: Mapping[str, str], status: str) -> bool:
    if _truth(row.get("explicit_failure")) or _truth(row.get("missing_result")):
        return True
    if any(
        token in status for token in ("FAIL", "ERROR", "BLOCK", "MISSING", "INVALID")
    ):
        return True
    for key in (
        "failure_count",
        "output_failure_count",
        "failed_case_count",
        "explicit_failed_job_count",
        "failed_job_count",
        "failed_or_missing_task_count",
        "end_to_end_job_failure_numerator",
    ):
        try:
            if float(row.get(key) or 0) > 0:
                return True
        except ValueError:
            return True
    return False


def _fine_tuning_decision(
    candidates: Sequence[Mapping[str, object]],
) -> str:
    if not candidates:
        return "NO_FINE_TUNING_CURRENTLY_JUSTIFIED"
    priority = (
        "ASR_TARGET_ADAPTATION_CANDIDATE",
        "SPEAKER_EMBEDDING_SHORT_DURATION_CANDIDATE",
        "SEGMENTATION_REAL_DEVICE_DATA_REQUIRED",
        "POLICY_CHANGE_ONLY",
    )
    observed = {str(row["decision"]) for row in candidates}
    return next(item for item in priority if item in observed)


def _measured_error_exposure(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    mapping = {
        "asr": ("speaker_attributed_wer", False),
        "endpointing": ("stable_prefix_latency_sec", False),
        "segmentation": ("anonymous_speaker_confusion_rate", False),
        "anonymous_clustering": ("anonymous_speaker_confusion_rate", False),
        "identity_embedding": ("stranger_false_known_time_sec", False),
        "enrollment": ("correctly_named_known_rate", True),
        "open_set_policy": ("wrong_known_time_sec", False),
        "session_memory": ("transcript_identity_revision_count", False),
        "transcript_alignment": ("speaker_attributed_wer", False),
        "ui_event_delay": ("stable_correct_name_latency_sec", False),
        "resource_saturation": ("reliability_failure_count", False),
    }
    output: list[dict[str, object]] = []
    for component, (source_metric, invert_rate) in mapping.items():
        values = [
            (
                1.0 - float(row[source_metric])
                if invert_rate
                else float(row[source_metric])
            )
            for row in rows
            if row.get(source_metric) not in (None, "")
        ]
        metric = "known_naming_error_rate" if invert_rate else source_metric
        output.append(
            {
                "component": component,
                "metric": metric,
                "source_metric": source_metric,
                "computed_pipeline_count": len(values),
                "missing_pipeline_count": len(rows) - len(values),
                "mean": sum(values) / len(values) if values else None,
                "maximum": max(values) if values else None,
                "association_not_causation": True,
                "propagates_to": PROPAGATION[component],
            }
        )
    return output


def _first(row: Mapping[str, str], keys: Sequence[str]) -> str:
    return next((str(row[key]) for key in keys if str(row.get(key) or "").strip()), "")


def _truth(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {
        "true",
        "1",
        "yes",
        "failed",
        "error",
    }


__all__ = ["FailureAnalysis", "analyze_failures", "result_inventory"]
