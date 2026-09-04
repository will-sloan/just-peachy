"""Deterministic campaign planning across the locked 18-pipeline matrix."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix

from .io import canonical_json_bytes, sha256_bytes, sha256_file
from .schema import normalize_reuse_identity
from .store import EvaluationJobSpec


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
RUNTIME_CONFIG_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"
)
DEFAULT_WORKSPACE_ROOT = (
    EVALUATION_ROOT / "automated_runs/full_speech_pipeline_v1"
)
DEFAULT_RESULTS_ROOT = (
    EVALUATION_ROOT / "JustPeachyResults/full_pipeline/full_speech_pipeline_v1"
)
DEFAULT_SUMMARY_ROOT = (
    EVALUATION_ROOT / "JustPeachyResearchSummaries/full_pipeline/full_speech_pipeline_v1"
)
SCORER_VERSION = "full-pipeline-evaluation-scorers.v2"
RESULT_CONTRACT_VERSION = "full-pipeline-evaluation-result.v1"
DEFAULT_SEED = 5107


def matrix() -> FullPipelineMatrix:
    return FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)


def build_campaign_manifest(
    cases: Iterable[Mapping[str, object]],
    *,
    protocol_id: str,
    development_identity: str,
    evaluation_identity: str,
    seed: int = DEFAULT_SEED,
    pipeline_ids: Sequence[str] = (),
    measurement_modes: Sequence[str] = ("accuracy", "resources"),
    campaign_stage: str = "full_protocol",
    decision_policy_registry_sha256: str | None = None,
) -> tuple[dict[str, object], tuple[EvaluationJobSpec, ...]]:
    """Build a stable manifest; no paths or current timestamps affect identity."""

    case_rows = tuple(sorted((dict(row) for row in cases), key=_case_sort_key))
    if not case_rows:
        raise ValueError("the full-pipeline protocol contains no cases")
    if not campaign_stage.strip():
        raise ValueError("campaign_stage must be nonempty")
    modes = tuple(dict.fromkeys(str(value) for value in measurement_modes))
    if not modes or set(modes) - {"accuracy", "resources"}:
        raise ValueError("measurement_modes must contain accuracy and/or resources")
    if decision_policy_registry_sha256 is not None:
        registry_sha = str(decision_policy_registry_sha256).lower()
        if len(registry_sha) != 64 or any(
            char not in "0123456789abcdef" for char in registry_sha
        ):
            raise ValueError("decision_policy_registry_sha256 must be SHA-256")
    else:
        registry_sha = None
    implementation_identity = _implementation_identity()
    grouped: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    seen_case_ids: set[str] = set()
    for row in case_rows:
        split = str(row.get("split") or row.get("partition") or "")
        if split not in {"development", "evaluation"}:
            raise ValueError(f"invalid full-pipeline case split: {split}")
        case_id = _case_id(row)
        if case_id in seen_case_ids:
            raise ValueError(f"duplicate full-pipeline case ID: {case_id}")
        seen_case_ids.add(case_id)
        source_key = str(row.get("source_key") or "")
        source_protocol_id = str(
            row.get("source_protocol_id") or row.get("protocol_id") or ""
        )
        if not source_key or not source_protocol_id:
            raise ValueError(
                f"case {case_id} lacks source_key/source_protocol_id"
            )
        scoring_stratum = str(row.get("scoring_stratum") or "default")
        grouped[(split, source_key, source_protocol_id, scoring_stratum)].append(row)

    resolved_matrix = matrix()
    unknown_pipelines = set(pipeline_ids) - set(resolved_matrix.pipeline_ids)
    if unknown_pipelines:
        raise ValueError(
            "unknown exact pipeline selection(s): "
            + ", ".join(sorted(unknown_pipelines))
        )
    selected_pipeline_ids = tuple(
        pipeline_id
        for pipeline_id in resolved_matrix.pipeline_ids
        if not pipeline_ids or pipeline_id in pipeline_ids
    )
    jobs: list[EvaluationJobSpec] = []
    case_index = {_case_id(row): row for row in case_rows}
    case_selection_sha256 = sha256_bytes(canonical_json_bytes(case_rows))
    for pipeline_id in selected_pipeline_ids:
        selection = resolved_matrix.resolve(pipeline_id)
        for (split, source_key, source_protocol_id, scoring_stratum), rows in sorted(
            grouped.items()
        ):
            job_source_key = (
                source_key
                if scoring_stratum == "default"
                else f"{source_key}__{_portable_stratum(scoring_stratum)}"
            )
            protocol_identity = (
                development_identity if split == "development" else evaluation_identity
            )
            case_ids = tuple(_case_id(row) for row in rows)
            audio_duration_sec = sum(_duration(row) for row in rows)
            case_identity = sha256_bytes(
                canonical_json_bytes([case_index[case_id] for case_id in case_ids])
            )
            for measurement_mode in modes:
                case_manifest_sha256 = sha256_bytes(
                    canonical_json_bytes(
                        {
                            "source_protocol_id": source_protocol_id,
                            "source_key": source_key,
                            "scoring_stratum": scoring_stratum,
                            "split": split,
                            "measurement_mode": measurement_mode,
                            "case_identity": case_identity,
                            "scorer_version": SCORER_VERSION,
                            "result_contract_version": RESULT_CONTRACT_VERSION,
                            "implementation_identity": implementation_identity,
                            "campaign_stage": campaign_stage,
                            "decision_policy_registry_sha256": registry_sha,
                            "case_selection_sha256": case_selection_sha256,
                        }
                    )
                )
                reuse_identity = normalize_reuse_identity(
                    {
                        "program_id": "just_peachy_full_pipeline_program_v1",
                        "evaluation_protocol_id": protocol_id,
                        "evaluation_protocol_sha256": protocol_identity,
                        "pipeline_id": pipeline_id,
                        "pipeline_config_sha256": selection.pipeline_config_sha256,
                        "case_manifest_id": (
                            f"{source_protocol_id}:{split}:{source_key}:"
                            f"{scoring_stratum}:{measurement_mode}:{campaign_stage}"
                        ),
                        "case_manifest_sha256": case_manifest_sha256,
                        "runtime_config_sha256": selection.runtime_config_sha256,
                        "partition": split,
                        "seed": seed,
                    }
                )
                identity_payload = {
                    "schema_version": "full-pipeline-evaluation-job-identity.v1",
                    "reuse_identity": reuse_identity,
                    "source_protocol_id": source_protocol_id,
                    "scoring_stratum": scoring_stratum,
                    "pipeline_id": pipeline_id,
                    "measurement_mode": measurement_mode,
                    "scorer_version": SCORER_VERSION,
                    "result_contract_version": RESULT_CONTRACT_VERSION,
                }
                reuse_identity_sha = str(reuse_identity["identity_sha256"])
                job_id = (
                    f"fpjob_{split[:4]}_{measurement_mode[:3]}_"
                    f"{pipeline_id.removeprefix('fullpipe_v1_')}_"
                    f"{job_source_key}_{reuse_identity_sha[:12]}"
                )
                relative = (
                    f"{split}/{measurement_mode}/{job_source_key}/"
                    f"{pipeline_id}/{job_id}"
                )
                jobs.append(
                    EvaluationJobSpec(
                        job_id=job_id,
                        pipeline_id=pipeline_id,
                        protocol_id=source_protocol_id,
                        split=split,
                        source_key=job_source_key,
                        measurement_mode=measurement_mode,
                        seed=seed,
                        case_count=len(case_ids),
                        audio_duration_sec=audio_duration_sec,
                        protocol_identity=protocol_identity,
                        pipeline_identity=selection.pipeline_config_sha256,
                        reuse_identity=reuse_identity,
                        case_ids=case_ids,
                        result_relative_path=relative,
                    )
                )
    jobs.sort(key=lambda item: item.job_id)
    identity_payload = {
        "schema_version": "full-pipeline-evaluation-campaign-identity.v1",
        "full_protocol_id": protocol_id,
        "development_identity": development_identity,
        "evaluation_identity": evaluation_identity,
        "matrix_sha256": sha256_file(MATRIX_PATH),
        "runtime_config_sha256": sha256_file(RUNTIME_CONFIG_PATH),
        "scorer_version": SCORER_VERSION,
        "result_contract_version": RESULT_CONTRACT_VERSION,
        "implementation_identity": implementation_identity,
        "seed": seed,
        "campaign_stage": campaign_stage,
        "selected_pipeline_ids": list(selected_pipeline_ids),
        "measurement_modes": list(modes),
        "decision_policy_registry_sha256": registry_sha,
        "decision_policy_registry": (
            {
                "logical_path": "decision_policy_registry.json",
                "sha256": registry_sha,
            }
            if registry_sha is not None
            else None
        ),
        "case_selection_sha256": case_selection_sha256,
        "selected_case_ids": [_case_id(row) for row in case_rows],
        "jobs": [item.to_jsonable() for item in jobs],
    }
    identity = sha256_bytes(canonical_json_bytes(identity_payload))
    campaign_id = f"full_speech_pipeline_v1_{identity[:12]}"
    manifest: dict[str, object] = {
        "schema_version": "full-pipeline-evaluation-campaign.v1",
        "campaign_id": campaign_id,
        "campaign_identity_sha256": identity,
        **identity_payload,
        "pipeline_count": len(selected_pipeline_ids),
        "job_count": len(jobs),
        "case_count": len(case_rows),
        "case_index": case_index,
        "parallelism_policy": {
            "accuracy_maximum_jobs": 2,
            "resource_measurement_jobs": 1,
            "resource_results_comparable_only_with_serial_resource_results": True,
            "memory_gate_required": True,
        },
        "downloads_allowed": False,
        "isolated_environments_required": True,
        "shared_stage_cache_required": True,
        "previous_frozen_protocols_modified": False,
    }
    return manifest, tuple(jobs)


def _implementation_identity() -> dict[str, str]:
    """Bind exact result-affecting source trees into result reuse."""

    evaluation_files = tuple(sorted(Path(__file__).resolve().parent.glob("*.py")))
    runtime_root = EVALUATION_ROOT / "app/full_pipeline"
    runtime_files = tuple(sorted(runtime_root.glob("*.py"))) + (
        EVALUATION_ROOT / "app/inference_pipeline/asr/sherpa_onnx_adapter.py",
    )
    development_root = EVALUATION_ROOT / "app/full_pipeline_development"
    development_files = tuple(sorted(development_root.glob("*.py")))
    return {
        "evaluation_package_sha256": _source_tree_sha256(evaluation_files),
        "streaming_runtime_package_sha256": _source_tree_sha256(runtime_files),
        "development_policy_package_sha256": _source_tree_sha256(
            development_files
        ),
    }


def _source_tree_sha256(paths: Sequence[Path]) -> str:
    rows = {
        path.resolve().relative_to(EVALUATION_ROOT).as_posix(): sha256_file(path)
        for path in paths
    }
    return sha256_bytes(canonical_json_bytes(rows))


def filter_jobs(
    jobs: Sequence[EvaluationJobSpec],
    *,
    split: str | None = None,
    measurement_mode: str | None = None,
    pipeline_ids: Sequence[str] = (),
    protocol_ids: Sequence[str] = (),
) -> tuple[EvaluationJobSpec, ...]:
    available_pipelines = {job.pipeline_id for job in jobs}
    available_protocols = {job.protocol_id for job in jobs}
    unknown_pipelines = set(pipeline_ids) - available_pipelines
    unknown_protocols = set(protocol_ids) - available_protocols
    if unknown_pipelines:
        raise ValueError(
            "unknown exact pipeline filter(s): " + ", ".join(sorted(unknown_pipelines))
        )
    if unknown_protocols:
        raise ValueError(
            "unknown exact protocol filter(s): " + ", ".join(sorted(unknown_protocols))
        )
    return tuple(
        job
        for job in jobs
        if (split is None or job.split == split)
        and (measurement_mode is None or job.measurement_mode == measurement_mode)
        and (not pipeline_ids or job.pipeline_id in pipeline_ids)
        and (not protocol_ids or job.protocol_id in protocol_ids)
    )


def manifest_jobs(manifest: Mapping[str, object]) -> tuple[EvaluationJobSpec, ...]:
    values = manifest.get("jobs")
    if not isinstance(values, list):
        raise ValueError("campaign manifest jobs must be an array")
    return tuple(
        EvaluationJobSpec.from_jsonable(row)
        for row in values
        if isinstance(row, Mapping)
    )


def _case_id(row: Mapping[str, object]) -> str:
    value = (
        row.get("case_id")
        or row.get("protocol_case_id")
        or row.get("recording_id")
        or row.get("utt_id")
    )
    if value is None or not str(value).strip():
        raise ValueError("full-pipeline case lacks case_id")
    return str(value)


def _duration(row: Mapping[str, object]) -> float:
    value = row.get("duration_sec") or row.get("audio_duration_sec") or 0.0
    duration = float(value)
    if duration < 0:
        raise ValueError(f"negative case duration: {_case_id(row)}")
    return duration


def _case_sort_key(row: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(row.get("split") or row.get("partition") or ""),
        (
            f"{row.get('source_key') or ''}:"
            f"{row.get('scoring_stratum') or 'default'}"
        ),
        _case_id(row),
    )


def _portable_stratum(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() or character in "_-" else "_"
        for character in value.casefold()
    ).strip("_")
    if not normalized:
        raise ValueError("scoring_stratum must contain a portable character")
    return normalized[:80]
