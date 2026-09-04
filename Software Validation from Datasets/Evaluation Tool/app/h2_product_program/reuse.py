"""Measured development-only R2/R3/R4 ReDim embedding-reuse qualification.

The public science receipt contains aggregate booleans, scalar error bounds,
checksums, and engineering counters only.  Exact per-window hashes and raw
gallery score diagnostics remain in the H2 workspace's private case shards;
embedding vectors are never serialized by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import shutil
from typing import Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.product_modes import H2RuntimeTuning
from app.full_pipeline_evaluation.results import result_tree_reusable
from app.full_pipeline_evaluation.schema import normalize_reuse_identity
from app.full_pipeline_evaluation.store import EvaluationJobSpec
from app.full_pipeline_evaluation.worker import (
    PreparedGallery,
    _FrozenGalleryPreparer,
    _load_valid_case_shard,
    execute_evaluation_job,
)
from app.h2_portability.e2e_parity import _VOLATILE_KEYS, _event_views

from .contracts import H2Job, H2ProgramError, ProgramPaths
from .execution import load_cases_for_job
from .io import (
    canonical_sha256,
    read_json,
    sha256_file,
    write_json_atomic,
    write_once_or_verify,
)
from .planning import MATRIX_PATH, RUNTIME_PATH


R2 = "R2_ONE_SHARED_MODEL"
R3 = "R3_EXACT_WINDOW_EMBEDDING_REUSE"
R4 = "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION"
REUSE_PARITY_SCHEMA_VERSION = "h2-embedding-reuse-parity.v3"
PRIVATE_ROOT_SCHEMA_VERSION = "h2-private-embedding-reuse-measurement.v1"

# Frozen before either variant starts.  Same-backend/same-FP32 execution is
# expected to be exact; the tiny score/margin allowance only accommodates a
# deterministic reduction-order difference in downstream aggregation.
REUSE_PARITY_TOLERANCES: Mapping[str, object] = {
    "contract_id": "h2-redim-r2-r3-r4-paired-parity-tolerances.v1",
    "embedding_cosine_minimum": 0.999999,
    "embedding_maximum_absolute_error": 1.0e-6,
    "raw_score_maximum_absolute_error": 1.0e-6,
    "margin_maximum_absolute_error": 1.0e-6,
    "event_numeric_maximum_absolute_error": 1.0e-6,
    "source_time_maximum_absolute_error_sec": 1.0e-6,
    "transcript_boundary_maximum_absolute_error_sec": 1.0e-6,
    "engineering_benefit": (
        "candidate total embedding calls must be lower than matched R2 and "
        "the candidate must record at least one exact reuse hit"
    ),
    "event_sequence_scope": (
        "ordered product events only; periodic resource telemetry and raw "
        "adapter diagnostic rows are compared through their dedicated "
        "engineering surfaces, not semantic event parity"
    ),
    "post_hoc_tolerance_changes_allowed": False,
}
REUSE_PARITY_TOLERANCE_SHA256 = canonical_sha256(REUSE_PARITY_TOLERANCES)

_PRIVATE_DIRECTORY = "private_embedding_reuse_parity_v1"
_UNKNOWN = re.compile(r"^(?:Unknown|Speaker)_(\d+)$")
_VOLATILE_SEMANTIC_KEYS = frozenset(
    {
        "backend_latency_ms",
        "compute_latency_ms",
        "processing_latency_ms",
        "queue_latency_ms",
        "runtime_tuning_identity_sha256",
        "runtime_tuning_sha256",
        "redim_execution_strategy",
        "embedding_reuse_qualification_sha256",
        "reuse_implementation_version",
        "policy_id",
        "decision_policy_sha256",
        "threshold_policy_id",
        "threshold_policy_sha256",
    }
) | frozenset(_VOLATILE_KEYS) | frozenset({"event_sequence"})
_NON_SEMANTIC_EVENT_TYPES = frozenset({"resource_telemetry"})


@dataclass(frozen=True)
class VariantExecution:
    """One checksum-valid private result plus its compact observations."""

    strategy: str
    spec: EvaluationJobSpec
    result_root: Path
    measurement_path: Path
    measurement_sha256: str
    measurement: Mapping[str, object]
    bundle: Mapping[str, object]


class ReuseParityStopped(H2ProgramError):
    """A user stop was honored at an atomic case boundary."""


class _PairedGalleryPreparer:
    """Persist one exact protected gallery across every paired variant.

    The underlying evaluation preparer validates and reopens immutable profile
    documents on restart.  Closing its adapter immediately after each prepare
    keeps enrollment-model lifetime outside the measured probe runtime span.
    """

    def __init__(self, *, selection: object, root: Path) -> None:
        self._inner = _FrozenGalleryPreparer(
            selection=selection,
            attempt_root=Path(root).resolve(),
            lazy_worker_start=True,
        )

    def prepare(self, case: Mapping[str, object], context: object) -> PreparedGallery:
        try:
            return self._inner.prepare(case, context)  # type: ignore[arg-type]
        finally:
            self._inner.close()

    def close(self) -> None:
        self._inner.close()


def execute_embedding_reuse_parity(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> tuple[dict[str, object], dict[str, Sequence[Mapping[str, object]]]]:
    """Run or reuse one real, bounded, paired development qualification."""

    strategy = job.configuration_id
    if strategy not in {R3, R4}:
        raise H2ProgramError(f"unexpected embedding-reuse candidate: {strategy}")
    if job.split != "development" or not job.development_only:
        raise H2ProgramError("embedding-reuse parity must remain development-only")
    if not paths.protocol_path.is_file():
        raise H2ProgramError("H2 protocol manifest is missing")
    protocol = read_json(paths.protocol_path)
    if protocol.get("protocol_sha256") is None:
        raise H2ProgramError("H2 protocol manifest lacks its frozen identity")

    all_cases = load_cases_for_job(job, open_evaluation=False)
    cases, case_roles = _bounded_parity_cases(all_cases)
    baseline_tuning = _strategy_tuning(job.runtime_tuning, R2)
    candidate_tuning = _strategy_tuning(job.runtime_tuning, strategy)
    common_contract = _common_contract(
        paths=paths,
        protocol=protocol,
        job=job,
        cases=cases,
        case_roles=case_roles,
        baseline_tuning=baseline_tuning,
    )
    private_root = (
        paths.workspace
        / _PRIVATE_DIRECTORY
        / str(common_contract["common_contract_sha256"])
    )
    write_once_or_verify(private_root / "common_contract.json", common_contract)
    selection = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH).resolve(
        "fullpipe_v1_ag_dr_ir"
    )
    gallery_preparer = _PairedGalleryPreparer(
        selection=selection,
        root=private_root / "shared_enrollment_profiles",
    )

    try:
        baseline = _run_or_reuse_variant(
            paths=paths,
            protocol=protocol,
            cases=cases,
            tuning=baseline_tuning,
            strategy=R2,
            common_contract=common_contract,
            private_root=private_root,
            enrollment_preparer=gallery_preparer,
        )
        candidate = _run_or_reuse_variant(
            paths=paths,
            protocol=protocol,
            cases=cases,
            tuning=candidate_tuning,
            strategy=strategy,
            common_contract=common_contract,
            private_root=private_root,
            enrollment_preparer=gallery_preparer,
        )
    except ReuseParityStopped as exc:
        row = {
            "strategy": strategy,
            "status": "STOPPED",
            "bounded_exact_parity_executed": False,
            "parity_passed": False,
            "candidate_qualified": False,
            "promotion_eligible": False,
            "reason": str(exc),
        }
        return (
            {
                "schema_version": REUSE_PARITY_SCHEMA_VERSION,
                "status": "STOPPED",
                "job_id": job.job_id,
                "job_kind": job.job_kind,
                "candidate_strategy": strategy,
                "promotion_eligible": False,
                "selected_runtime_tuning": {},
                "selected_runtime_axes": [],
                "bounded_exact_parity_executed": False,
                "scientific_outcome": row,
                "development_only_selection": True,
                "evaluation_material_inspected": False,
                "neural_inference_performed": False,
                "fabricated_equivalence_claim": False,
            },
            {"embedding_reuse_parity.csv": (row,)},
        )
    finally:
        gallery_preparer.close()

    comparison = compare_paired_bundles(
        baseline.bundle,
        candidate.bundle,
        strategy=strategy,
        tolerances=REUSE_PARITY_TOLERANCES,
    )
    parity_passed = bool(comparison["parity_passed"])
    engineering_benefit = bool(comparison["engineering_benefit_measured"])
    candidate_qualified = parity_passed and engineering_benefit
    prior_r3: Mapping[str, object] | None = None
    selected_tuning: dict[str, object] = {}
    selected_axes: list[str] = []
    promotion_eligible = False
    combined_decision: Mapping[str, object] | None = None
    if strategy == R4:
        prior_r3 = _validated_r3_result(state, jobs, common_contract)
        combined_decision = _combined_strategy_decision(
            baseline=baseline,
            r3_result=prior_r3,
            r4_candidate=candidate,
            r4_comparison=comparison,
        )
        selected_strategy = str(combined_decision["selected_strategy"])
        # R4 is the only job authorized to publish the combined selection, but
        # it may not promote R3 as a side effect of an incomplete/failed R4
        # qualification.  Reporting can still inspect the deterministic
        # decision while the runtime remains on frozen R2.
        promotion_eligible = candidate_qualified and selected_strategy in {
            R3,
            R4,
        }
        if promotion_eligible:
            qualification = str(combined_decision["combined_decision_sha256"])
            selected_tuning = {
                "redim_execution_strategy": selected_strategy,
                "embedding_reuse_qualification_sha256": qualification,
            }
            selected_axes = [
                "redim_execution_strategy",
                "embedding_reuse_qualification_sha256",
            ]

    outcome_status = "COMPLETE" if candidate_qualified else "GATED_NOT_PROMOTED"
    row = {
        "strategy": strategy,
        "status": outcome_status,
        "bounded_exact_parity_executed": True,
        "parity_measured": True,
        "required_parity_outputs_measured": bool(
            comparison["required_parity_outputs_measured"]
        ),
        "required_parity_outputs_complete": parity_passed,
        "required_parity_outputs_passed": parity_passed,
        "parity_passed": parity_passed,
        "candidate_qualified": candidate_qualified,
        "promotion_eligible": promotion_eligible,
        "embedding_cosine_agreement": comparison[
            "embedding_cosine_agreement"
        ],
        "maximum_absolute_error": comparison["maximum_absolute_error"],
        "score_agreement": comparison["score_agreement"],
        "top1_agreement": comparison["top1_agreement"],
        "top2_agreement": comparison["top2_agreement"],
        "margin_agreement": comparison["margin_agreement"],
        "known_unknown_decision_agreement": comparison[
            "known_unknown_decision_agreement"
        ],
        "cluster_assignment_agreement": comparison[
            "cluster_assignment_agreement"
        ],
        "transcript_label_agreement": comparison[
            "transcript_label_agreement"
        ],
        "event_sequence_semantic_agreement": comparison[
            "event_sequence_semantic_agreement"
        ],
        "engineering_benefit_measured": engineering_benefit,
        "baseline_total_embedding_calls": _measurement_number(
            baseline.measurement, "total_embedding_model_calls"
        ),
        "candidate_total_embedding_calls": _measurement_number(
            candidate.measurement, "total_embedding_model_calls"
        ),
        "candidate_reuse_hits": _measurement_number(
            candidate.measurement, "reuse_hits"
        ),
        "reason": comparison.get("reason"),
        "common_contract_sha256": common_contract["common_contract_sha256"],
        "baseline_measurement_sha256": baseline.measurement_sha256,
        "candidate_measurement_sha256": candidate.measurement_sha256,
    }
    payload: dict[str, object] = {
        "schema_version": REUSE_PARITY_SCHEMA_VERSION,
        "status": outcome_status,
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "candidate_strategy": strategy,
        "parity_passed": parity_passed,
        "candidate_qualified": candidate_qualified,
        "promotion_eligible": promotion_eligible,
        "selected_runtime_tuning": selected_tuning,
        "selected_runtime_axes": selected_axes,
        "bounded_exact_parity_executed": True,
        "required_parity_outputs_measured": bool(
            comparison["required_parity_outputs_measured"]
        ),
        "required_parity_outputs_complete": parity_passed,
        "required_parity_outputs_passed": parity_passed,
        "scientific_outcome": row,
        "parity": comparison,
        "engineering": {
            "baseline": dict(baseline.measurement),
            "candidate": dict(candidate.measurement),
        },
        "common_contract_path": str(private_root / "common_contract.json"),
        "common_contract_sha256": common_contract["common_contract_sha256"],
        "baseline_private_measurement_path": str(baseline.measurement_path),
        "baseline_measurement_sha256": baseline.measurement_sha256,
        "candidate_private_measurement_path": str(candidate.measurement_path),
        "candidate_measurement_sha256": candidate.measurement_sha256,
        "paired_case_ids": [str(row["protocol_case_id"]) for row in cases],
        "paired_case_roles": dict(case_roles),
        "paired_audio_duration_sec_per_variant": sum(
            float(row["duration_sec"]) for row in cases
        ),
        "development_only_selection": True,
        "evaluation_material_inspected": False,
        "neural_inference_performed": bool(
            _measurement_number(baseline.measurement, "neural_embedding_calls")
            and _measurement_number(candidate.measurement, "neural_embedding_calls")
        ),
        "same_exact_development_inputs": True,
        "same_exact_enrollment_profile_identities": comparison[
            "enrollment_profile_identity_agreement"
        ],
        "scientific_thresholds_retuned": False,
        "tolerances_predeclared_before_inference": True,
        "tolerance_contract": dict(REUSE_PARITY_TOLERANCES),
        "tolerance_contract_sha256": REUSE_PARITY_TOLERANCE_SHA256,
        "private_diagnostics_hashes_and_scalars_only": True,
        "raw_embedding_vectors_serialized": False,
        "public_derived_probe_vectors_retained_after_success": False,
        "biometric_sensitive_private_artifacts_excluded_from_final_zip": True,
        "fabricated_equivalence_claim": False,
    }
    if prior_r3 is not None:
        payload["validated_r3_prerequisite"] = {
            "job_id": prior_r3["job_id"],
            "published_result_sha256": prior_r3["published_result_sha256"],
            "candidate_measurement_sha256": prior_r3[
                "candidate_measurement_sha256"
            ],
            "candidate_qualified": prior_r3["candidate_qualified"],
        }
    if combined_decision is not None:
        payload["combined_strategy_decision"] = dict(combined_decision)
    return payload, {"embedding_reuse_parity.csv": (row,)}


def compare_paired_bundles(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    *,
    strategy: str,
    tolerances: Mapping[str, object] = REUSE_PARITY_TOLERANCES,
) -> dict[str, object]:
    """Compare every required scientific surface without exposing vectors."""

    if strategy not in {R3, R4}:
        raise ValueError(f"unsupported reuse parity strategy: {strategy}")
    embedding = _embedding_agreement(baseline, candidate, tolerances)
    scores = _score_agreement(baseline, candidate, tolerances)
    decisions = _decision_agreement(baseline, candidate, tolerances)
    clusters = _cluster_agreement(baseline, candidate, tolerances)
    transcripts = _transcript_agreement(baseline, candidate, tolerances)
    events = _event_agreement(baseline, candidate, tolerances)
    profiles_match = baseline.get("selected_profile_identity_sha256") == candidate.get(
        "selected_profile_identity_sha256"
    ) and bool(baseline.get("selected_profile_identity_sha256"))
    baseline_calls = _bundle_number(baseline, "total_embedding_model_calls")
    candidate_calls = _bundle_number(candidate, "total_embedding_model_calls")
    reuse_hits = _bundle_number(candidate, "reuse_hits")
    engineering = (
        baseline_calls is not None
        and candidate_calls is not None
        and candidate_calls < baseline_calls
        and reuse_hits is not None
        and reuse_hits > 0
    )
    required = {
        "embedding": bool(embedding["passed"]),
        "score": bool(scores["score_agreement"]),
        "top1": bool(scores["top1_agreement"]),
        "top2": bool(scores["top2_agreement"]),
        "margin": bool(scores["margin_agreement"]),
        "known_unknown_decision": bool(decisions["passed"]),
        "anonymous_cluster_assignment": bool(clusters["passed"]),
        "transcript_label": bool(transcripts["passed"]),
        "event_sequence_semantic": bool(events["passed"]),
        "enrollment_profile_identity": bool(profiles_match),
    }
    parity_passed = all(required.values())
    failures = [name for name, passed in required.items() if not passed]
    if not engineering:
        failures.append("measured_engineering_benefit")
    return {
        "schema_version": "h2-embedding-reuse-paired-comparison.v1",
        "strategy": strategy,
        "tolerance_contract_sha256": canonical_sha256(tolerances),
        "required_parity_outputs_measured": all(
            bool(value.get("measured"))
            for value in (embedding, scores, decisions, clusters, transcripts, events)
        ),
        "parity_passed": parity_passed,
        "candidate_qualified": parity_passed and engineering,
        "embedding_cosine_agreement": embedding.get("minimum_cosine"),
        "maximum_absolute_error": embedding.get("maximum_absolute_error"),
        "score_agreement": scores["score_agreement"],
        "score_maximum_absolute_error": scores["maximum_score_error"],
        "top1_agreement": scores["top1_agreement"],
        "top2_agreement": scores["top2_agreement"],
        "margin_agreement": scores["margin_agreement"],
        "margin_maximum_absolute_error": scores["maximum_margin_error"],
        "known_unknown_decision_agreement": decisions["passed"],
        "cluster_assignment_agreement": clusters["passed"],
        "transcript_label_agreement": transcripts["passed"],
        "event_sequence_semantic_agreement": events["passed"],
        "enrollment_profile_identity_agreement": bool(profiles_match),
        "engineering_benefit_measured": engineering,
        "baseline_total_embedding_calls": baseline_calls,
        "candidate_total_embedding_calls": candidate_calls,
        "embedding_call_reduction": (
            baseline_calls - candidate_calls
            if baseline_calls is not None and candidate_calls is not None
            else None
        ),
        "candidate_reuse_hits": reuse_hits,
        "checks": required,
        "details": {
            "embedding": embedding,
            "scores": scores,
            "decisions": decisions,
            "clusters": clusters,
            "transcripts": transcripts,
            "events": events,
        },
        "reason": (
            "all paired scientific surfaces passed and an embedding-call "
            "reduction was measured"
            if parity_passed and engineering
            else "paired qualification failed: " + ", ".join(failures)
        ),
        "raw_embedding_vectors_present": False,
    }


def _bounded_parity_cases(
    cases: Sequence[Mapping[str, object]],
) -> tuple[tuple[dict[str, object], ...], dict[str, str]]:
    if not cases:
        raise H2ProgramError("embedding-reuse parity has no declared development cases")
    known = sorted(
        (
            dict(row)
            for row in cases
            if int(row.get("known_speaker_count") or 0) > 0
        ),
        key=_bounded_case_key,
    )
    all_unknown = sorted(
        (
            dict(row)
            for row in cases
            if int(row.get("known_speaker_count") or 0) == 0
            and int(row.get("unknown_speaker_count") or 0) > 0
        ),
        key=_bounded_case_key,
    )
    if not known or not all_unknown:
        raise H2ProgramError(
            "paired reuse panel requires an enrolled-known case and an "
            "all-unknown/no-matching-profile case"
        )
    selected = (known[0], all_unknown[0])
    if any(str(row.get("partition")) != "development" for row in selected):
        raise H2ProgramError("reuse parity selected a non-development case")
    roles = {
        _case_id(known[0]): "enrolled_known_or_mixed",
        _case_id(all_unknown[0]): "all_unknown_no_matching_profile",
    }
    return selected, roles


def _bounded_case_key(row: Mapping[str, object]) -> tuple[float, str]:
    return float(row.get("duration_sec") or math.inf), _case_id(row)


def _common_contract(
    *,
    paths: ProgramPaths,
    protocol: Mapping[str, object],
    job: H2Job,
    cases: Sequence[Mapping[str, object]],
    case_roles: Mapping[str, str],
    baseline_tuning: H2RuntimeTuning,
) -> dict[str, object]:
    files = (
        Path(__file__),
        paths.evaluation_root / "app/full_pipeline/embedding_reuse.py",
        paths.evaluation_root / "app/full_pipeline/coordinator.py",
        paths.evaluation_root / "app/full_pipeline/factory.py",
        paths.evaluation_root / "app/full_pipeline/runtime_components.py",
        paths.evaluation_root / "app/full_pipeline/product_modes.py",
        paths.evaluation_root / "app/full_pipeline_evaluation/worker.py",
    )
    code = {
        str(path.relative_to(paths.evaluation_root)).replace("\\", "/"): sha256_file(
            path
        )
        for path in files
    }
    core = {
        "schema_version": "h2-embedding-reuse-common-contract.v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": protocol["protocol_sha256"],
        "pipeline_id": job.pipeline_id,
        "split": "development",
        "declared_parent_case_ids": list(job.case_ids),
        "paired_cases": [
            {
                "case_id": _case_id(row),
                "case_identity_sha256": canonical_sha256(row),
                "audio_sha256": row.get("audio_sha256"),
                "pcm_sha256": row.get("pcm_sha256"),
                "duration_sec": float(row["duration_sec"]),
                "role": case_roles[_case_id(row)],
                "known_speaker_count": int(row.get("known_speaker_count") or 0),
                "unknown_speaker_count": int(
                    row.get("unknown_speaker_count") or 0
                ),
                "gallery_enrolled_ids": list(row.get("gallery_enrolled_ids") or ()),
            }
            for row in cases
        ],
        "baseline_runtime_tuning": baseline_tuning.to_jsonable(),
        "baseline_runtime_tuning_sha256": baseline_tuning.identity_sha256,
        "measurement_mode": "resources",
        "same_exact_case_and_profile_inputs_required": True,
        "emit_identity_score_diagnostics": True,
        "shared_exact_enrollment_profiles_across_variants": True,
        "tolerance_contract": dict(REUSE_PARITY_TOLERANCES),
        "tolerance_contract_sha256": REUSE_PARITY_TOLERANCE_SHA256,
        "result_affecting_code_sha256": code,
        "result_affecting_code_set_sha256": canonical_sha256(code),
        "evaluation_material_inspected": False,
        "post_hoc_tolerance_changes_allowed": False,
    }
    return {**core, "common_contract_sha256": canonical_sha256(core)}


def _strategy_tuning(
    raw: Mapping[str, object], strategy: str
) -> H2RuntimeTuning:
    value = dict(raw)
    value.pop("schema_version", None)
    value.pop("scientific_capabilities", None)
    value.pop("identity_sha256", None)
    value.pop("embedding_reuse_qualification_sha256", None)
    value["redim_execution_strategy"] = strategy
    return H2RuntimeTuning.from_mapping(value)


def _run_or_reuse_variant(
    *,
    paths: ProgramPaths,
    protocol: Mapping[str, object],
    cases: Sequence[Mapping[str, object]],
    tuning: H2RuntimeTuning,
    strategy: str,
    common_contract: Mapping[str, object],
    private_root: Path,
    enrollment_preparer: _PairedGalleryPreparer,
) -> VariantExecution:
    variant_root = private_root / _portable_id(strategy.casefold())
    spec = _variant_spec(
        protocol=protocol,
        cases=cases,
        tuning=tuning,
        strategy=strategy,
        common_contract=common_contract,
    )
    reused = _find_reusable_variant(variant_root, spec, cases)
    if reused is not None:
        return reused
    if _stop_requested(paths):
        raise ReuseParityStopped("stop requested before the next paired variant")
    attempts_root = variant_root / "attempts"
    attempts_root.mkdir(parents=True, exist_ok=True)
    attempt_number = 1 + max(
        (
            int(path.name.rsplit("_", 1)[-1])
            for path in attempts_root.glob("attempt_[0-9][0-9][0-9]")
            if path.is_dir()
        ),
        default=0,
    )
    attempt_root = attempts_root / f"attempt_{attempt_number:03d}"
    result_root = attempt_root / "result"

    def progress(**values: object) -> None:
        write_json_atomic(
            variant_root / "progress.json",
            {
                "schema_version": "h2-embedding-reuse-private-progress.v1",
                "strategy": strategy,
                "attempt": attempt_number,
                **dict(values),
            },
        )

    outcome = execute_evaluation_job(
        spec,
        cases,
        result_root,
        progress,
        lambda: _stop_requested(paths),
        execution_contract={
            "schema_version": "h2-embedding-reuse-private-execution.v1",
            "development_only": True,
            "emit_identity_score_diagnostics": True,
            "common_contract_sha256": common_contract["common_contract_sha256"],
            "candidate_strategy": strategy,
            "biometric_sensitive_private_artifacts": True,
            "exclude_from_final_zip": True,
        },
        enrollment_preparer=enrollment_preparer,
        runtime_tuning=tuning.to_jsonable(),
        stop_at_case_boundary=True,
        storage_reserve_callback=lambda: _require_storage_reserve(paths),
    )
    if outcome.get("state") == "stopped":
        raise ReuseParityStopped(
            f"stop requested after an atomic {strategy} case boundary"
        )
    if outcome.get("state") != "complete" or not result_tree_reusable(
        result_root, spec.reuse_identity
    ):
        raise H2ProgramError(
            f"paired {strategy} runtime did not produce a reusable complete result: "
            f"{outcome.get('error')}"
        )
    execution = _seal_variant(variant_root, spec, cases, result_root)
    _cleanup_empty_attempt_runtime(attempt_root)
    return execution


def _variant_spec(
    *,
    protocol: Mapping[str, object],
    cases: Sequence[Mapping[str, object]],
    tuning: H2RuntimeTuning,
    strategy: str,
    common_contract: Mapping[str, object],
) -> EvaluationJobSpec:
    selection = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH).resolve(
        "fullpipe_v1_ag_dr_ir"
    )
    case_contract = {
        "common_contract_sha256": common_contract["common_contract_sha256"],
        "strategy": strategy,
        "runtime_tuning_identity_sha256": tuning.identity_sha256,
        "runtime_tuning": tuning.to_jsonable(),
        "case_identities": [
            {"case_id": _case_id(row), "sha256": canonical_sha256(row)}
            for row in cases
        ],
        "execution_contract": {
            "measurement_mode": "resources",
            "emit_identity_score_diagnostics": True,
            "isolated_probe_embedding_cache": True,
            "development_only": True,
        },
    }
    reuse_identity = normalize_reuse_identity(
        {
            "program_id": "just_peachy_full_pipeline_program_v1",
            "evaluation_protocol_id": str(protocol["protocol_id"]),
            "evaluation_protocol_sha256": str(protocol["protocol_sha256"]),
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "pipeline_config_sha256": selection.pipeline_config_sha256,
            "case_manifest_id": f"h2-private-reuse-parity:{strategy}",
            "case_manifest_sha256": canonical_sha256(case_contract),
            "runtime_config_sha256": selection.runtime_config_sha256,
            "partition": "development",
            "seed": int(protocol.get("seed") or 3800),
        }
    )
    return EvaluationJobSpec(
        job_id=f"h2_reuse_{_portable_id(strategy.casefold())}_{reuse_identity['identity_sha256'][:12]}",
        pipeline_id="fullpipe_v1_ag_dr_ir",
        protocol_id=str(protocol["protocol_id"]),
        split="development",
        source_key="h2_private_embedding_reuse_parity",
        measurement_mode="resources",
        seed=int(protocol.get("seed") or 3800),
        case_count=len(cases),
        audio_duration_sec=sum(float(row["duration_sec"]) for row in cases),
        protocol_identity=str(protocol["protocol_sha256"]),
        pipeline_identity=selection.pipeline_config_sha256,
        reuse_identity=reuse_identity,
        case_ids=tuple(_case_id(row) for row in cases),
        result_relative_path="private_embedding_reuse_parity/result",
    )


def _find_reusable_variant(
    variant_root: Path,
    spec: EvaluationJobSpec,
    cases: Sequence[Mapping[str, object]],
) -> VariantExecution | None:
    candidates: list[Path] = []
    receipt_path = variant_root / "selected_measurement.json"
    if receipt_path.is_file():
        try:
            receipt = read_json(receipt_path)
            result_value = receipt.get("result_root")
            if isinstance(result_value, str):
                candidates.append(Path(result_value))
        except (OSError, ValueError):
            pass
    attempts_root = variant_root / "attempts"
    if attempts_root.is_dir():
        candidates.extend(
            path / "result"
            for path in sorted(attempts_root.glob("attempt_[0-9][0-9][0-9]"))
            if path.is_dir()
        )
    seen: set[Path] = set()
    for raw in candidates:
        result_root = raw.resolve(strict=False)
        if result_root in seen:
            continue
        seen.add(result_root)
        if result_tree_reusable(result_root, spec.reuse_identity):
            try:
                return _seal_variant(variant_root, spec, cases, result_root)
            except (H2ProgramError, OSError, ValueError):
                continue
    return None


def _seal_variant(
    variant_root: Path,
    spec: EvaluationJobSpec,
    cases: Sequence[Mapping[str, object]],
    result_root: Path,
) -> VariantExecution:
    bundle = _load_private_bundle(result_root, spec, cases)
    measurement = _compact_measurement(spec, result_root, bundle)
    measurement_path = variant_root / "measurement.json"
    write_json_atomic(measurement_path, measurement)
    measurement_sha = sha256_file(measurement_path)
    if sha256_file(measurement_path) != measurement_sha:
        raise H2ProgramError("private reuse measurement changed while sealing")
    probe_cache_cleanup = _cleanup_private_probe_vector_cache(
        result_root.resolve().parent
    )
    if probe_cache_cleanup["status"] == "FAILED":
        raise H2ProgramError(
            "private probe-embedding cache cleanup failed after measurement "
            f"seal: {probe_cache_cleanup['reason']}"
        )
    receipt = {
        "schema_version": PRIVATE_ROOT_SCHEMA_VERSION,
        "strategy": measurement["strategy"],
        "result_root": str(result_root.resolve()),
        "reuse_identity_sha256": spec.reuse_identity["identity_sha256"],
        "result_checksums_sha256": sha256_file(result_root / "checksums.json"),
        "measurement_path": str(measurement_path.resolve()),
        "measurement_sha256": measurement_sha,
        "case_shard_sha256s": measurement["case_shard_sha256s"],
        "probe_embedding_cache_cleanup": probe_cache_cleanup,
        "public_derived_probe_vectors_retained": False,
        "raw_embedding_vectors_present": False,
    }
    write_json_atomic(variant_root / "selected_measurement.json", receipt)
    if sha256_file(measurement_path) != measurement_sha:
        raise H2ProgramError("private reuse measurement checksum changed after sealing")
    return VariantExecution(
        strategy=str(measurement["strategy"]),
        spec=spec,
        result_root=result_root.resolve(),
        measurement_path=measurement_path.resolve(),
        measurement_sha256=measurement_sha,
        measurement=measurement,
        bundle=bundle,
    )


def _load_private_bundle(
    result_root: Path,
    spec: EvaluationJobSpec,
    cases: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    attempts_root = result_root.resolve().parent.parent
    shard_root = attempts_root / "case_shards_v1"
    aggregate: dict[str, object] = {
        "embedding_reuse_observations": [],
        "challenger_score_observations": [],
        "events": [],
        "labelled_rows": [],
        "hypothesis_segments": [],
        "selected_profile_rows": [],
        "telemetry_rows": [],
        "case_shard_sha256s": {},
        "runtime_wall_sec": 0.0,
        "rss_mb_values": [],
    }
    for ordinal, case in enumerate(cases, start=1):
        case_id = _case_id(case)
        shard_path = shard_root / _portable_id(case_id) / "case_shard.json"
        document = _load_valid_case_shard(
            shard_path, job=spec, case=case, ordinal=ordinal
        )
        if document is None:
            raise H2ProgramError(f"private reuse case shard is missing/corrupt: {case_id}")
        payload = document["payload"]
        if not isinstance(payload, Mapping):
            raise H2ProgramError("validated private reuse shard lacks payload")
        aggregate["case_shard_sha256s"][case_id] = document["shard_sha256"]  # type: ignore[index]
        for target, source in (
            ("embedding_reuse_observations", "embedding_reuse_observations"),
            ("challenger_score_observations", "challenger_score_observations"),
            ("events", "events"),
            ("labelled_rows", "labelled_rows"),
            ("hypothesis_segments", "hypothesis_segments"),
            ("selected_profile_rows", "selected_profile_rows"),
            ("telemetry_rows", "embedding_reuse_telemetry"),
        ):
            raw_rows = payload.get(source)
            if not isinstance(raw_rows, list) or any(
                not isinstance(row, Mapping) for row in raw_rows
            ):
                raise H2ProgramError(f"private shard {source} contract differs")
            aggregate[target].extend(dict(row) for row in raw_rows)  # type: ignore[union-attr]
        aggregate["runtime_wall_sec"] = float(aggregate["runtime_wall_sec"]) + float(
            payload.get("measured_runtime_wall_sec") or 0.0
        )
        rss = payload.get("rss_mb")
        if isinstance(rss, (int, float)) and math.isfinite(float(rss)):
            aggregate["rss_mb_values"].append(float(rss))  # type: ignore[union-attr]
    observations = aggregate["embedding_reuse_observations"]
    if not observations:
        raise H2ProgramError("paired runtime emitted no embedding-reuse observations")
    _assert_no_raw_embedding_vectors(aggregate)
    telemetry = _telemetry_summary(aggregate["telemetry_rows"])
    aggregate.update(telemetry)
    aggregate["selected_profile_identity_sha256"] = canonical_sha256(
        aggregate["selected_profile_rows"]
    )
    return aggregate


def _compact_measurement(
    spec: EvaluationJobSpec,
    result_root: Path,
    bundle: Mapping[str, object],
) -> dict[str, object]:
    strategy = str(
        next(iter(bundle["telemetry_rows"]), {}).get("strategy")  # type: ignore[union-attr]
        or "UNKNOWN"
    )
    audio = float(spec.audio_duration_sec)
    wall = float(bundle.get("runtime_wall_sec") or 0.0)
    rss_values = [float(value) for value in bundle.get("rss_mb_values", [])]  # type: ignore[arg-type]
    core = {
        "schema_version": PRIVATE_ROOT_SCHEMA_VERSION,
        "strategy": strategy,
        "reuse_identity_sha256": spec.reuse_identity["identity_sha256"],
        "result_checksums_sha256": sha256_file(result_root / "checksums.json"),
        "case_ids": list(spec.case_ids),
        "case_count": spec.case_count,
        "audio_duration_sec": audio,
        "runtime_wall_sec": wall,
        "total_runtime_rtf": wall / audio if audio > 0 else None,
        "peak_rss_mb": max(rss_values) if rss_values else None,
        "peak_rss_status": "MEASURED" if rss_values else "UNSUPPORTED_NO_SAMPLE",
        "embedding_observation_count": len(
            bundle["embedding_reuse_observations"]  # type: ignore[arg-type]
        ),
        "score_observation_count": len(
            bundle["challenger_score_observations"]  # type: ignore[arg-type]
        ),
        "event_count": len(bundle["events"]),  # type: ignore[arg-type]
        "case_shard_sha256s": dict(bundle["case_shard_sha256s"]),  # type: ignore[arg-type]
        "selected_profile_identity_sha256": bundle[
            "selected_profile_identity_sha256"
        ],
        **{
            key: bundle.get(key)
            for key in (
                "diarization_requests",
                "identity_requests",
                "diarization_model_calls",
                "identity_model_calls",
                "total_embedding_model_calls",
                "neural_embedding_calls",
                "reuse_hits",
                "fresh_fallbacks",
                "fingerprint_mismatches",
                "quality_fallbacks",
                "audio_seconds_embedded",
                "audio_seconds_reused",
                "embedding_rtf",
                "model_instances_loaded",
                "initialization_sec",
                "startup_sec",
                "model_bytes",
                "model_bytes_status",
                "queue_delay_ms",
                "queue_delay_status",
            )
        },
        "private_hash_scalar_observations_only": True,
        "raw_embedding_vectors_present": False,
        "raw_score_vectors_in_compact_measurement": False,
    }
    return {**core, "measurement_identity_sha256": canonical_sha256(core)}


def _telemetry_summary(rows: object) -> dict[str, object]:
    if not isinstance(rows, list) or not rows:
        raise H2ProgramError("paired runtime emitted no embedding telemetry")
    summed = {
        key: 0.0
        for key in (
            "diarization_requests",
            "identity_requests",
            "diarization_model_calls",
            "identity_model_calls",
            "total_embedding_model_calls",
            "reuse_hits",
            "fresh_fallbacks",
            "fingerprint_mismatches",
            "quality_fallbacks",
            "audio_seconds_embedded",
            "audio_seconds_reused",
            "routing_wall_sec",
        )
    }
    neural_calls = 0.0
    initialization = 0.0
    model_instances = 0.0
    model_bytes_values: list[float] = []
    queue_delays: list[float] = []
    queue_statuses: set[str] = set()
    model_statuses: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise H2ProgramError("embedding telemetry row is not an object")
        for key in summed:
            value = raw.get(key)
            if isinstance(value, (int, float)):
                summed[key] += float(value)
        # Every row is one case-level snapshot of the same shared job-local
        # adapter/worker topology.  Summing snapshots would falsely report one
        # additional loaded model per case, so retain the measured maximum.
        model_instances = max(
            model_instances,
            float(raw.get("model_instances_loaded") or 0.0),
        )
        initialization += float(raw.get("initialization_sec") or 0.0)
        if isinstance(raw.get("model_bytes"), (int, float)):
            model_bytes_values.append(float(raw["model_bytes"]))
        if isinstance(raw.get("queue_delay_ms"), (int, float)):
            queue_delays.append(float(raw["queue_delay_ms"]))
        queue_statuses.add(str(raw.get("queue_delay_status") or "UNSUPPORTED"))
        model_statuses.add(str(raw.get("model_bytes_status") or "UNSUPPORTED"))
        statuses = raw.get("adapter_statuses")
        if isinstance(statuses, list):
            for status in statuses:
                if not isinstance(status, Mapping):
                    continue
                adapter = status.get("embedding_telemetry")
                if isinstance(adapter, Mapping):
                    neural_calls += float(adapter.get("neural_embedding_calls") or 0.0)
    audio = summed["audio_seconds_embedded"]
    return {
        **{
            key: int(value) if key not in {
                "audio_seconds_embedded",
                "audio_seconds_reused",
                "routing_wall_sec",
            } else value
            for key, value in summed.items()
        },
        "neural_embedding_calls": int(neural_calls),
        "embedding_rtf": summed["routing_wall_sec"] / audio if audio > 0 else None,
        "model_instances_loaded": int(model_instances),
        "initialization_sec": initialization,
        "startup_sec": initialization,
        "model_bytes": max(model_bytes_values) if model_bytes_values else None,
        "model_bytes_status": " | ".join(sorted(model_statuses)),
        "queue_delay_ms": max(queue_delays) if queue_delays else None,
        "queue_delay_status": " | ".join(sorted(queue_statuses)),
        "telemetry_row_count": len(rows),
    }


def _embedding_agreement(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    tolerances: Mapping[str, object],
) -> dict[str, object]:
    left = _rows(baseline, "embedding_reuse_observations")
    right = _rows(candidate, "embedding_reuse_observations")
    aligned = len(left) == len(right) and bool(left)
    failures: list[str] = []
    cosines: list[float] = []
    errors: list[float] = []
    if aligned:
        for index, (base, cand) in enumerate(zip(left, right)):
            fields = ("case_id", "window_id")
            if any(base.get(field) != cand.get(field) for field in fields):
                failures.append(f"window alignment differs at index {index}")
                continue
            same_identity = base.get("identity_vector_sha256") == cand.get(
                "identity_vector_sha256"
            )
            same_diar = base.get("diarization_vector_sha256") == cand.get(
                "diarization_vector_sha256"
            )
            if same_identity and same_diar:
                cosines.append(1.0)
                errors.append(0.0)
                continue
            # For a reused candidate, the common diarization vector gives a
            # direct scalar comparison already measured in the R2 observation.
            baseline_identity_is_common_diarization = (
                same_diar
                and base.get("identity_vector_sha256")
                == base.get("diarization_vector_sha256")
            )
            inferable = (
                cand.get("reused") is True
                and baseline_identity_is_common_diarization
                and isinstance(
                    cand.get("embedding_cosine_agreement"), (int, float)
                )
                and isinstance(cand.get("maximum_absolute_error"), (int, float))
            )
            if inferable:
                # EmbeddingResult normalizes an already normalized reused
                # vector once more.  That can change a few FP32 low bits even
                # though both vectors are measured against the exact same
                # checksum-bound diarization vector.  The predeclared scalar
                # tolerances therefore govern this directly measured delta;
                # no tolerance is relaxed after observing the result.
                cosines.append(float(cand["embedding_cosine_agreement"]))
                errors.append(float(cand["maximum_absolute_error"]))
            else:
                failures.append(
                    f"vector hash/scalar chain differs or is not inferable at index {index}"
                )
    else:
        failures.append(
            f"embedding observation counts differ: {len(left)} != {len(right)}"
        )
    minimum = min(cosines) if cosines else None
    maximum = max(errors) if errors else None
    measured = aligned and len(cosines) == len(left)
    passed = (
        measured
        and not failures
        and minimum is not None
        and minimum + 1e-12 >= float(tolerances["embedding_cosine_minimum"])
        and maximum is not None
        and maximum
        <= float(tolerances["embedding_maximum_absolute_error"]) + 1e-12
    )
    return {
        "measured": measured,
        "passed": passed,
        "observation_count": len(left),
        "minimum_cosine": minimum,
        "maximum_absolute_error": maximum,
        "exact_identity_vector_hash_count": sum(
            a.get("identity_vector_sha256") == b.get("identity_vector_sha256")
            for a, b in zip(left, right)
        ),
        "failures": failures[:50],
    }


def _score_agreement(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    tolerances: Mapping[str, object],
) -> dict[str, object]:
    left = _rows(baseline, "challenger_score_observations")
    right = _rows(candidate, "challenger_score_observations")
    measured = len(left) == len(right) and bool(left)
    failures: list[str] = []
    max_score = 0.0
    max_margin = 0.0
    top1 = True
    top2 = True
    if measured:
        for index, (base, cand) in enumerate(zip(left, right)):
            for field in ("case_id", "source_time_sec", "predicted_overlap"):
                if base.get(field) != cand.get(field):
                    failures.append(f"score observation {field} differs at {index}")
            base_scores = base.get("candidate_raw_cosine_scores")
            cand_scores = cand.get("candidate_raw_cosine_scores")
            if not isinstance(base_scores, Mapping) or not isinstance(
                cand_scores, Mapping
            ) or set(base_scores) != set(cand_scores):
                failures.append(f"score candidate set differs at {index}")
                continue
            for key in base_scores:
                max_score = max(
                    max_score,
                    abs(float(base_scores[key]) - float(cand_scores[key])),
                )
            top1 = top1 and base.get("top1_candidate_id") == cand.get(
                "top1_candidate_id"
            )
            top2 = top2 and base.get("top2_candidate_id") == cand.get(
                "top2_candidate_id"
            )
            base_margin = _margin(base)
            cand_margin = _margin(cand)
            if base_margin is None or cand_margin is None:
                if base_margin != cand_margin:
                    failures.append(f"score margin presence differs at {index}")
            else:
                max_margin = max(max_margin, abs(base_margin - cand_margin))
    else:
        failures.append(f"score observation counts differ: {len(left)} != {len(right)}")
    score_pass = measured and not failures and max_score <= float(
        tolerances["raw_score_maximum_absolute_error"]
    )
    margin_pass = measured and not failures and max_margin <= float(
        tolerances["margin_maximum_absolute_error"]
    )
    return {
        "measured": measured,
        "score_agreement": score_pass,
        "top1_agreement": measured and top1,
        "top2_agreement": measured and top2,
        "margin_agreement": margin_pass,
        "maximum_score_error": max_score if measured else None,
        "maximum_margin_error": max_margin if measured else None,
        "observation_count": len(left),
        "failures": failures[:50],
    }


def _decision_agreement(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    tolerances: Mapping[str, object],
) -> dict[str, object]:
    left = _identity_event_views(_rows(baseline, "events"))
    right = _identity_event_views(_rows(candidate, "events"))
    measured = len(left) == len(right) and bool(left)
    failures: list[str] = []
    max_numeric = 0.0
    if measured:
        for index, (base, cand) in enumerate(zip(left, right)):
            if base["exact"] != cand["exact"]:
                failures.append(f"identity decision semantic differs at {index}")
            delta = _numeric_pairs_max(base["numeric"], cand["numeric"])
            if delta is None:
                failures.append(f"identity decision numeric shape differs at {index}")
            else:
                max_numeric = max(max_numeric, delta)
    else:
        failures.append(f"identity event counts differ: {len(left)} != {len(right)}")
    passed = measured and not failures and max_numeric <= float(
        tolerances["event_numeric_maximum_absolute_error"]
    )
    return {
        "measured": measured,
        "passed": passed,
        "identity_event_count": len(left),
        "maximum_numeric_error": max_numeric if measured else None,
        "failures": failures[:50],
    }


def _cluster_agreement(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    tolerances: Mapping[str, object],
) -> dict[str, object]:
    left = _rows(baseline, "hypothesis_segments")
    right = _rows(candidate, "hypothesis_segments")
    measured = len(left) == len(right) and bool(left)
    failures: list[str] = []
    maximum_boundary = 0.0
    if measured:
        left_speakers = [
            str(row.get("anonymous_speaker_id") or row.get("speaker_id"))
            for row in left
        ]
        right_speakers = [
            str(row.get("anonymous_speaker_id") or row.get("speaker_id"))
            for row in right
        ]
        left_co = [[a == b for b in left_speakers] for a in left_speakers]
        right_co = [[a == b for b in right_speakers] for a in right_speakers]
        if left_co != right_co:
            failures.append("anonymous cluster coassignment differs")
        for index, (base, cand) in enumerate(zip(left, right)):
            for field in ("start_sec", "end_sec"):
                maximum_boundary = max(
                    maximum_boundary,
                    abs(float(base.get(field) or 0.0) - float(cand.get(field) or 0.0)),
                )
            if bool(base.get("overlap")) != bool(cand.get("overlap")):
                failures.append(f"overlap assignment differs at segment {index}")
    else:
        failures.append(f"hypothesis segment counts differ: {len(left)} != {len(right)}")
    passed = measured and not failures and maximum_boundary <= float(
        tolerances["source_time_maximum_absolute_error_sec"]
    )
    return {
        "measured": measured,
        "passed": passed,
        "segment_count": len(left),
        "maximum_boundary_error_sec": maximum_boundary if measured else None,
        "failures": failures[:50],
    }


def _transcript_agreement(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    tolerances: Mapping[str, object],
) -> dict[str, object]:
    left = _canonical_transcript_rows(_rows(baseline, "labelled_rows"))
    right = _canonical_transcript_rows(_rows(candidate, "labelled_rows"))
    measured = len(left) == len(right) and bool(left)
    failures: list[str] = []
    maximum_boundary = 0.0
    if measured:
        for index, (base, cand) in enumerate(zip(left, right)):
            base_exact = {key: value for key, value in base.items() if key not in {"start_sec", "end_sec"}}
            cand_exact = {key: value for key, value in cand.items() if key not in {"start_sec", "end_sec"}}
            if base_exact != cand_exact:
                failures.append(f"labelled transcript semantic differs at row {index}")
            for field in ("start_sec", "end_sec"):
                if field in base or field in cand:
                    if field not in base or field not in cand:
                        failures.append(f"transcript {field} presence differs at row {index}")
                    else:
                        maximum_boundary = max(
                            maximum_boundary,
                            abs(float(base[field]) - float(cand[field])),
                        )
    else:
        failures.append(f"labelled transcript row counts differ: {len(left)} != {len(right)}")
    passed = measured and not failures and maximum_boundary <= float(
        tolerances["transcript_boundary_maximum_absolute_error_sec"]
    )
    return {
        "measured": measured,
        "passed": passed,
        "row_count": len(left),
        "maximum_boundary_error_sec": maximum_boundary if measured else None,
        "failures": failures[:50],
    }


def _event_agreement(
    baseline: Mapping[str, object],
    candidate: Mapping[str, object],
    tolerances: Mapping[str, object],
) -> dict[str, object]:
    left_events = [
        _strip_semantic_noise(row)
        for row in _rows(baseline, "events")
        if _is_product_semantic_event(row)
    ]
    right_events = [
        _strip_semantic_noise(row)
        for row in _rows(candidate, "events")
        if _is_product_semantic_event(row)
    ]
    left = _event_views(left_events)
    right = _event_views(right_events)
    measured = bool(left_events) and bool(right_events)
    exact = (
        left["event_types"] == right["event_types"]
        and left["exact_semantic_events"] == right["exact_semantic_events"]
    )
    numeric = _numeric_pairs_max(left["numeric_fields"], right["numeric_fields"])
    numeric_pass = numeric is not None and numeric <= float(
        tolerances["event_numeric_maximum_absolute_error"]
    )
    failures = []
    if left["event_types"] != right["event_types"]:
        failures.append("event type/order sequence differs")
    if left["exact_semantic_events"] != right["exact_semantic_events"]:
        failures.append("event semantic payload sequence differs")
    if numeric is None:
        failures.append("event numeric field shape differs")
    elif not numeric_pass:
        failures.append("event numeric tolerance exceeded")
    return {
        "measured": measured,
        "passed": measured and exact and numeric_pass,
        "event_count_baseline": len(left_events),
        "event_count_candidate": len(right_events),
        "event_type_sequence_agreement": left["event_types"] == right["event_types"],
        "semantic_payload_agreement": left["exact_semantic_events"]
        == right["exact_semantic_events"],
        "maximum_numeric_error": numeric,
        "failures": failures,
    }


def _is_product_semantic_event(row: Mapping[str, object]) -> bool:
    event_type = str(row.get("event_type") or "")
    return bool(event_type) and event_type not in _NON_SEMANTIC_EVENT_TYPES


def _validated_r3_result(
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    common_contract: Mapping[str, object],
) -> dict[str, object]:
    candidates = [
        candidate
        for candidate in jobs
        if candidate.job_kind == "embedding_reuse_parity"
        and candidate.configuration_id == R3
    ]
    if len(candidates) != 1:
        raise H2ProgramError("R4 requires exactly one declared R3 parity job")
    r3_job = candidates[0]
    raw_jobs = state.get("jobs")
    row = raw_jobs.get(r3_job.job_id) if isinstance(raw_jobs, Mapping) else None
    if not isinstance(row, Mapping) or row.get("state") != "COMPLETE":
        raise H2ProgramError("R4 requires a complete R3 parity result")
    path_value = row.get("result_path")
    expected = str(row.get("result_sha256") or "")
    path = Path(str(path_value)) if path_value else Path()
    if not path.is_file() or not expected or sha256_file(path) != expected:
        raise H2ProgramError("R3 parity result path/checksum differs")
    result = read_json(path)
    status = str(result.get("status") or "")
    if status not in {"COMPLETE", "GATED_NOT_PROMOTED"}:
        raise H2ProgramError("R3 parity prerequisite has no terminal science outcome")
    exact = {
        "candidate_strategy": R3,
        "promotion_eligible": False,
        "common_contract_sha256": common_contract["common_contract_sha256"],
    }
    if any(result.get(key) != value for key, value in exact.items()):
        raise H2ProgramError("R3 parity prerequisite is incomplete or stale")
    qualified = (
        result.get("parity_passed") is True
        and result.get("candidate_qualified") is True
    )
    if (status == "COMPLETE") != qualified:
        raise H2ProgramError("R3 parity status and qualification disagree")
    if result.get("bounded_exact_parity_executed") is not True:
        raise H2ProgramError("R3 parity did not execute its bounded paired panel")
    if result.get("evaluation_material_inspected") is not False:
        raise H2ProgramError("R3 parity crossed the development/evaluation firewall")
    if result.get("selected_runtime_axes") not in ([], ()): 
        raise H2ProgramError("R3 must qualify without selecting runtime axes")
    measurement_path = Path(str(result.get("candidate_private_measurement_path") or ""))
    measurement_sha = str(result.get("candidate_measurement_sha256") or "")
    if (
        not measurement_path.is_file()
        or not measurement_sha
        or sha256_file(measurement_path) != measurement_sha
    ):
        raise H2ProgramError("R3 private candidate measurement checksum differs")
    return {
        **result,
        "job_id": r3_job.job_id,
        "published_result_path": str(path),
        "published_result_sha256": expected,
        "candidate_measurement": read_json(measurement_path),
    }


def _combined_strategy_decision(
    *,
    baseline: VariantExecution,
    r3_result: Mapping[str, object],
    r4_candidate: VariantExecution,
    r4_comparison: Mapping[str, object],
) -> dict[str, object]:
    r3_measurement = r3_result.get("candidate_measurement")
    if not isinstance(r3_measurement, Mapping):
        raise H2ProgramError("R3 candidate measurement is missing")
    rows = [
        _selection_row(R2, baseline.measurement, qualified=True),
        _selection_row(
            R3,
            r3_measurement,
            qualified=(
                r3_result.get("candidate_qualified") is True
                and r3_result.get("parity_passed") is True
            ),
        ),
        _selection_row(
            R4,
            r4_candidate.measurement,
            qualified=(
                r4_comparison.get("candidate_qualified") is True
                and r4_comparison.get("parity_passed") is True
            ),
        ),
    ]
    eligible = [row for row in rows if row["qualified"] is True]
    frontier = [
        row
        for row in eligible
        if not any(
            _dominates(other, row)
            for other in eligible
            if other["strategy"] != row["strategy"]
        )
    ]
    priority = {R3: 0, R4: 1, R2: 2}
    selected = min(
        frontier,
        key=lambda row: (
            int(row["identity_model_calls"]),
            int(row["total_embedding_model_calls"]),
            float(row["audio_seconds_embedded"]),
            priority[str(row["strategy"])],
        ),
    )
    core = {
        "schema_version": "h2-redim-combined-strategy-decision.v1",
        "baseline_measurement_sha256": baseline.measurement_sha256,
        "r3_candidate_measurement_sha256": r3_result[
            "candidate_measurement_sha256"
        ],
        "r3_published_result_sha256": r3_result["published_result_sha256"],
        "r4_candidate_measurement_sha256": r4_candidate.measurement_sha256,
        "tolerance_contract_sha256": REUSE_PARITY_TOLERANCE_SHA256,
        "strategies": rows,
        "pareto_frontier": [str(row["strategy"]) for row in frontier],
        "selected_strategy": selected["strategy"],
        "selection_method": (
            "development-only Pareto screen on embedding calls/audio, then "
            "lexicographic identity calls, total calls, embedded audio, and "
            "predeclared simplicity order R3/R4/R2"
        ),
        "last_job_wins_used": False,
        "heldout_results_used": False,
        "scientific_thresholds_retuned": False,
    }
    return {**core, "combined_decision_sha256": canonical_sha256(core)}


def _selection_row(
    strategy: str, measurement: Mapping[str, object], *, qualified: bool
) -> dict[str, object]:
    required = (
        "identity_model_calls",
        "total_embedding_model_calls",
        "audio_seconds_embedded",
    )
    values = {key: _measurement_number(measurement, key) for key in required}
    if any(value is None for value in values.values()):
        raise H2ProgramError(f"strategy selection lacks telemetry: {strategy}")
    return {
        "strategy": strategy,
        "qualified": bool(qualified),
        **values,
        "runtime_rtf": measurement.get("total_runtime_rtf"),
        "peak_rss_mb": measurement.get("peak_rss_mb"),
        "model_instances_loaded": measurement.get("model_instances_loaded"),
    }


def _dominates(left: Mapping[str, object], right: Mapping[str, object]) -> bool:
    axes = (
        "identity_model_calls",
        "total_embedding_model_calls",
        "audio_seconds_embedded",
    )
    return all(float(left[key]) <= float(right[key]) for key in axes) and any(
        float(left[key]) < float(right[key]) for key in axes
    )


def _identity_event_views(
    events: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in events:
        if row.get("event_type") != "identity_evidence":
            continue
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            payload = row
        exact = {
            "top1_candidate_speaker_id": payload.get("top1_candidate_speaker_id"),
            "top2_candidate_speaker_id": payload.get("top2_candidate_speaker_id"),
            "decision": _strip_numeric(
                _strip_semantic_noise(payload.get("decision"))
            ),
            "decision_reason": _strip_numeric(
                _strip_semantic_noise(payload.get("decision_reason"))
            ),
            "threshold_identity": _strip_numeric(
                _strip_semantic_noise(payload.get("threshold_identity"))
            ),
        }
        numeric = _numeric_leaves(
            {
                "top1_raw_score": payload.get("top1_raw_score"),
                "top2_raw_score": payload.get("top2_raw_score"),
                "top1_top2_margin": payload.get("top1_top2_margin"),
                "decision": payload.get("decision"),
                "threshold_identity": payload.get("threshold_identity"),
            }
        )
        output.append({"exact": exact, "numeric": numeric})
    return output


def _canonical_transcript_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    clusters: dict[str, str] = {}
    unknowns: dict[str, str] = {}

    def label(value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("anon_") or value.startswith("cluster_"):
            return clusters.setdefault(value, f"cluster_{len(clusters) + 1:04d}")
        if _UNKNOWN.fullmatch(value):
            return unknowns.setdefault(value, f"unknown_{len(unknowns) + 1:04d}")
        return value

    output = []
    for raw in rows:
        row = {}
        for key, value in sorted(raw.items()):
            if key in {
                "case_id",
                "event_id",
                "span_id",
                "revision_id",
                "source_event_ids",
                "caused_by_event_ids",
                "transcript_id",
            }:
                continue
            if key in {
                "anonymous_speaker_id",
                "speaker_label",
                "unknown_label",
                "speaker_id",
            }:
                row[key] = label(value)
            else:
                row[key] = value
        output.append(row)
    return output


def _strip_semantic_noise(value: object) -> object:
    if isinstance(value, list):
        return [_strip_semantic_noise(item) for item in value]
    if not isinstance(value, Mapping):
        return value
    return {
        str(key): _strip_semantic_noise(item)
        for key, item in value.items()
        if str(key) not in _VOLATILE_SEMANTIC_KEYS
    }


def _strip_numeric(value: object) -> object:
    if isinstance(value, list):
        return [_strip_numeric(item) for item in value]
    if not isinstance(value, Mapping):
        return "__NUMERIC__" if isinstance(value, (int, float)) and not isinstance(value, bool) else value
    return {str(key): _strip_numeric(item) for key, item in sorted(value.items())}


def _numeric_leaves(value: object, path: str = "root") -> list[tuple[str, float | None]]:
    if isinstance(value, Mapping):
        output = []
        for key, item in sorted(value.items()):
            output.extend(_numeric_leaves(item, f"{path}.{key}"))
        return output
    if isinstance(value, list):
        output = []
        for index, item in enumerate(value):
            output.extend(_numeric_leaves(item, f"{path}[{index}]"))
        return output
    if value is None:
        return [(path, None)]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [(path, float(value))]
    return []


def _numeric_pairs_max(left: object, right: object) -> float | None:
    if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
        return None
    maximum = 0.0
    for base, cand in zip(left, right):
        if not isinstance(base, (tuple, list, Mapping)) or not isinstance(
            cand, (tuple, list, Mapping)
        ):
            return None
        if isinstance(base, Mapping):
            base_path, base_value = base.get("path"), base.get("value")
            cand_path, cand_value = cand.get("path"), cand.get("value")  # type: ignore[union-attr]
            base_kind = base.get("kind")
            cand_kind = cand.get("kind")  # type: ignore[union-attr]
            if base_kind != cand_kind:
                return None
        else:
            base_path, base_value = base[0], base[1]
            cand_path, cand_value = cand[0], cand[1]  # type: ignore[index]
        if base_path != cand_path:
            return None
        if base_value is None or cand_value is None:
            if base_value != cand_value:
                return None
            continue
        maximum = max(maximum, abs(float(base_value) - float(cand_value)))
    return maximum


def _margin(row: Mapping[str, object]) -> float | None:
    top1 = row.get("top1_score")
    top2 = row.get("top2_score")
    if top1 is None or top2 is None:
        return None
    return float(top1) - float(top2)


def _rows(value: Mapping[str, object], key: str) -> list[dict[str, object]]:
    rows = value.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError(f"paired bundle {key} must be a list of objects")
    return [dict(row) for row in rows]


def _bundle_number(value: Mapping[str, object], key: str) -> float | None:
    raw = value.get(key)
    return float(raw) if isinstance(raw, (int, float)) else None


def _measurement_number(value: Mapping[str, object], key: str) -> float | None:
    raw = value.get(key)
    return float(raw) if isinstance(raw, (int, float)) else None


def _assert_no_raw_embedding_vectors(value: object, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in {"vector", "embedding_vector", "raw_embedding"}:
                raise H2ProgramError(f"raw embedding vector entered private bundle: {path}.{key}")
            _assert_no_raw_embedding_vectors(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_raw_embedding_vectors(item, f"{path}[{index}]")


def _cleanup_empty_attempt_runtime(attempt_root: Path) -> None:
    runtime = attempt_root / "runtime_cases"
    if runtime.is_dir() and not any(runtime.iterdir()):
        runtime.rmdir()


def _cleanup_private_probe_vector_cache(
    attempt_root: Path,
) -> dict[str, object]:
    """Remove the isolated paired-run cache that can contain probe vectors.

    The worker intentionally keeps shared model/enrollment caches elsewhere.
    Only the exact, non-symlink ``resource_runtime_cache`` child of this one
    private attempt is eligible for deletion after compact case shards and the
    measurement document have both been checksum sealed.
    """

    intended = Path(attempt_root).resolve(strict=False)
    target_path = Path(attempt_root) / "resource_runtime_cache"
    target = target_path.resolve(strict=False)
    if target.parent != intended or target == intended:
        raise H2ProgramError("private probe-cache cleanup target escaped attempt")
    if Path(attempt_root).is_symlink() or target_path.is_symlink():
        raise H2ProgramError("private probe-cache cleanup refuses symlinks")
    if not target_path.exists():
        return {
            "status": "ALREADY_ABSENT",
            "reason": "isolated probe cache did not remain",
        }
    try:
        shutil.rmtree(target_path)
    except OSError as exc:
        return {
            "status": "FAILED",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    return {
        "status": "DELETED_AFTER_CHECKSUM_SEALED_MEASUREMENT",
        "reason": "isolated probe-derived embedding cache removed",
    }


def _require_storage_reserve(paths: ProgramPaths) -> None:
    usage = shutil.disk_usage(paths.workspace.anchor or "C:\\")
    minimum = 35 * 1024**3
    if usage.free < minimum:
        raise H2ProgramError(
            "C: free-space reserve is below 35 GiB; no new paired case was started"
        )


def _stop_requested(paths: ProgramPaths) -> bool:
    return paths.stop_path.is_file()


def _case_id(row: Mapping[str, object]) -> str:
    value = row.get("case_id") or row.get("protocol_case_id")
    if value is None or not str(value).strip():
        raise H2ProgramError("paired development case lacks an ID")
    return str(value)


def _portable_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    if not normalized:
        raise ValueError("portable identifier is empty")
    return normalized[:120]


__all__ = [
    "REUSE_PARITY_SCHEMA_VERSION",
    "REUSE_PARITY_TOLERANCES",
    "REUSE_PARITY_TOLERANCE_SHA256",
    "compare_paired_bundles",
    "execute_embedding_reuse_parity",
]
