"""Raspberry Pi candidate handoff derived without changing desktop science."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix, PipelineSelection
from app.full_pipeline_deployment_evidence import (
    DeploymentEvidenceError,
    validate_deployment_evidence_document,
    validate_evidence,
)

from . import (
    PI_CANDIDATE_FIELDS,
    PI_DEPLOYMENT_ATTRIBUTES,
    PI_FEASIBILITY_CLASSES,
    PI_FUTURE_LINUX_ARM64_TESTS,
    PI_FUTURE_TESTS,
    PI_HANDOFF_FILENAME,
    PI_LINUX_ARM64_PORTABILITY_CLASSES,
    scope_fields,
)
from .evidence import EvidenceBundle, load_yaml
from .io import (
    IncompleteEvidenceError,
    ProductionCandidateError,
    artifact_ref,
    canonical_json_bytes,
    ensure_c,
    read_csv,
    read_json,
    sha256_bytes,
    sha256_file,
)
from .ranking import RankingResult


HANDOFF_SCHEMA = "full-pipeline-raspberry-pi-deployment-handoff.v1"
STATISTICAL_METRICS = {
    "wer",
    "der",
    "wrong_known_time_sec",
    "stranger_false_known_time_sec",
}


def build_pi_handoff(
    bundle: EvidenceBundle, rankings: RankingResult
) -> dict[str, object]:
    """Create an unordered 2-4 architecture shortlist for future ARM work."""

    matrix = FullPipelineMatrix(bundle.matrix_path, bundle.runtime_path)
    rows = {str(row["pipeline_id"]): row for row in rankings.rows}
    credible = {
        pipeline_id: row
        for pipeline_id, row in rows.items()
        if _scientifically_credible(row)
    }
    if rankings.primary not in credible:
        raise ProductionCandidateError(
            "desktop primary lacks complete safety/reliability evidence for Pi handoff"
        )
    if len(credible) < 2:
        raise IncompleteEvidenceError(
            "fewer than two scientifically credible Pi deployment candidates"
        )

    upstream = _validate_upstream_deployment_evidence(
        bundle=bundle,
        rankings=rankings,
        matrix=matrix,
        credible=credible,
    )
    prompt7_candidates = upstream["prompt7_candidates"]
    assert isinstance(prompt7_candidates, Mapping)
    selected_ids = tuple(str(item) for item in prompt7_candidates)
    if not 2 <= len(selected_ids) <= 4:
        raise ProductionCandidateError(
            "Pi deployment shortlist is outside the required 2-4 candidate range"
        )

    p5 = bundle.completions[5]
    bootstrap_path = p5.one("bootstrap_intervals.csv")
    paired_path = p5.one("paired_comparisons.csv")
    bootstrap = read_csv(bootstrap_path)
    paired = read_csv(paired_path)
    candidates: list[dict[str, object]] = []
    attributes: dict[str, Mapping[str, object]] = {}
    feasibility: dict[str, Mapping[str, object]] = {}
    for pipeline_id in sorted(selected_ids):
        row = credible[pipeline_id]
        selection = matrix.resolve(pipeline_id)
        prompt7_candidate = prompt7_candidates[pipeline_id]
        assert isinstance(prompt7_candidate, Mapping)
        statistical = _statistical_context(
            pipeline_id=pipeline_id,
            primary=rankings.primary,
            bootstrap_rows=bootstrap,
            paired_rows=paired,
            bootstrap_path=bootstrap_path,
            paired_path=paired_path,
        )
        prompt7_attributes = upstream["prompt7_attributes"]
        prompt7_feasibility = upstream["prompt7_feasibility"]
        assert isinstance(prompt7_attributes, Mapping)
        assert isinstance(prompt7_feasibility, Mapping)
        deployment = prompt7_attributes[pipeline_id]
        if not isinstance(deployment, Mapping):
            raise ProductionCandidateError(
                f"Prompt-7 deployment attributes are invalid: {pipeline_id}"
            )
        attributes[pipeline_id] = deployment
        feasibility_evidence = prompt7_feasibility[pipeline_id]
        if not isinstance(feasibility_evidence, Mapping):
            raise ProductionCandidateError(
                f"Prompt-7 feasibility evidence is invalid: {pipeline_id}"
            )
        feasibility[pipeline_id] = feasibility_evidence
        candidate = dict(prompt7_candidate)
        candidate.update(
            {
                "current_desktop_accuracy": {
                    "prompt7_frozen_value": prompt7_candidate.get(
                        "current_desktop_accuracy"
                    ),
                    "evidence_scope": "P5_EXACT_ALL18_UNTOUCHED_HELDOUT_DESKTOP",
                    "technical_performance_rank": row["technical_performance_rank"],
                    "user_experience_safety_rank": row["user_experience_safety_rank"],
                    "resource_efficiency_rank": row["resource_efficiency_rank"],
                    "pareto_frontier": row["pareto_frontier"],
                    "statistical_context": statistical,
                    "universal_within_one_percent_equivalence_rule_used": False,
                    "safety_errors_discounted_as_ordinary_small_differences": False,
                },
                "two_gib_feasibility_class": feasibility_evidence["class"],
            }
        )
        _validate_prompt7_candidate_binding(
            candidate,
            prompt7_candidate=prompt7_candidate,
            selection=selection,
            row=row,
            deployment=deployment,
            feasibility=feasibility_evidence,
        )
        if set(candidate) != set(PI_CANDIDATE_FIELDS):
            raise ProductionCandidateError(
                f"internal Pi candidate field set differs: {pipeline_id}"
            )
        candidates.append(candidate)

    steering_ref = artifact_ref(bundle.pi_deployment_steering_path)
    core = {
        "schema_version": HANDOFF_SCHEMA,
        **scope_fields(),
        "status": "CANDIDATES_FOR_FUTURE_ARM_BENCHMARK_NOT_A_FINAL_WINNER",
        "steering_authority": {
            **steering_ref,
            "embedded_document": dict(bundle.pi_deployment_steering),
            "embedded_canonical_sha256": sha256_bytes(
                canonical_json_bytes(bundle.pi_deployment_steering)
            ),
        },
        "desktop_software_scientific_ranking_source": ("FINAL_PIPELINE_RANKING.csv"),
        "raspberry_pi_candidate_shortlist_is_separate": True,
        "candidate_count": len(candidates),
        "candidates_are_unordered": True,
        "candidates": candidates,
        "deployment_attributes_by_pipeline": attributes,
        "two_gib_feasibility_evidence_by_pipeline": feasibility,
        "upstream_deployment_evidence": {
            "prompt5": artifact_ref(
                bundle.completions[5].one("all18_deployment_evidence.json")
            ),
            "prompt6": artifact_ref(
                bundle.completions[6].one("extended_deployment_evidence.json")
            ),
            "prompt7_shortlist_membership_authority": artifact_ref(
                bundle.completions[7].one("raspberry_pi_candidate_shortlist.json")
            ),
            "membership_reselected_in_prompt8": False,
        },
        "architecture_tradeoff_audit": upstream["architecture_tradeoff_audit"],
        "selection_policy": {
            "policy_id": "categorical_arm_candidate_preservation_no_composite.v1",
            "scientific_rankings_changed": False,
            "prompt7_desktop_roles_changed": False,
            "weighted_composite_used": False,
            "universal_within_one_percent_equivalence_rule_used": False,
            "bootstrap_intervals_consumed": True,
            "paired_effect_sizes_consumed": True,
            "ordinary_accuracy_and_high_cost_safety_distinguished": True,
            "two_gib_used_as_premature_hard_filter": False,
            "desktop_rtf_used_as_pi_rtf": False,
            "desktop_winner_used_as_pi_winner": False,
            "candidate_membership_consumed_from_prompt7_without_reselection": True,
        },
        "future_target_hardware_tests": [
            {"order": index, "test_id": test_id, "required": True}
            for index, test_id in enumerate(PI_FUTURE_TESTS, start=1)
        ],
        "future_linux_arm64_validation": [
            {"order": index, "test_id": test_id, "required": True}
            for index, test_id in enumerate(PI_FUTURE_LINUX_ARM64_TESTS, start=1)
        ],
        "target_hardware_decision_boundary": {
            "approximate_ram_gib": 2,
            "final_raspberry_pi_winner": None,
            "final_raspberry_pi_winner_claimed": False,
            "requires_export_optimization_and_real_arm_measurement": True,
            "desktop_measurements_are_arm_measurements": False,
        },
        "output_filename": PI_HANDOFF_FILENAME,
    }
    document = {
        **core,
        "handoff_identity_sha256": sha256_bytes(canonical_json_bytes(core)),
    }
    validate_pi_handoff(document, bundle.pi_deployment_steering)
    return document


def validate_pi_handoff(
    value: Mapping[str, object], steering: Mapping[str, object]
) -> None:
    if (
        steering.get("schema_version") != "full-pipeline-deployment-steering.v1"
        or steering.get("steering_id") != "raspberry_pi_compute_module_2gb.v1"
        or tuple(steering.get("two_gib_feasibility_classes") or ())
        != PI_FEASIBILITY_CLASSES
        or tuple(steering.get("deployment_attributes") or ())
        != PI_DEPLOYMENT_ATTRIBUTES
        or tuple(steering.get("raspberry_pi_candidate_fields") or ())
        != PI_CANDIDATE_FIELDS
        or tuple(steering.get("future_target_hardware_tests") or ()) != PI_FUTURE_TESTS
        or tuple(steering.get("future_linux_arm64_validation") or ())
        != PI_FUTURE_LINUX_ARM64_TESTS
        or tuple(steering.get("linux_arm64_portability_classes") or ())
        != PI_LINUX_ARM64_PORTABILITY_CLASSES
    ):
        raise ProductionCandidateError("Pi steering authority contract differs")
    if (
        value.get("schema_version") != HANDOFF_SCHEMA
        or value.get("status")
        != "CANDIDATES_FOR_FUTURE_ARM_BENCHMARK_NOT_A_FINAL_WINNER"
        or value.get("raspberry_pi_candidate_shortlist_is_separate") is not True
        or value.get("candidates_are_unordered") is not True
        or value.get("output_filename") != PI_HANDOFF_FILENAME
    ):
        raise ProductionCandidateError("Pi handoff core contract differs")
    unsigned = dict(value)
    identity = str(unsigned.pop("handoff_identity_sha256", "")).casefold()
    if identity != sha256_bytes(canonical_json_bytes(unsigned)):
        raise ProductionCandidateError("Pi handoff identity differs")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not 2 <= len(candidates) <= 4:
        raise ProductionCandidateError("Pi handoff candidate count differs")
    if int(value.get("candidate_count") or 0) != len(candidates):
        raise ProductionCandidateError("Pi handoff candidate count binding differs")
    candidate_ids: list[str] = []
    for raw in candidates:
        if not isinstance(raw, Mapping) or set(raw) != set(PI_CANDIDATE_FIELDS):
            raise ProductionCandidateError("Pi handoff exact candidate fields differ")
        pipeline_id = str(raw.get("pipeline_id") or "")
        candidate_ids.append(pipeline_id)
        if (
            not pipeline_id
            or raw.get("two_gib_feasibility_class") not in PI_FEASIBILITY_CLASSES
            or raw.get("linux_arm64_portability_class")
            not in PI_LINUX_ARM64_PORTABILITY_CLASSES
            or not isinstance(raw.get("reason_retained"), list)
            or not raw.get("reason_retained")
            or not isinstance(raw.get("linux_arm64_dependency_status"), Mapping)
            or not isinstance(raw.get("export_path"), Mapping)
            or not raw.get("export_path")
            or not isinstance(raw.get("quantization_opportunities"), list)
            or not raw.get("quantization_opportunities")
            or not isinstance(raw.get("model_sharing_opportunities"), list)
            or not raw.get("model_sharing_opportunities")
            or not isinstance(raw.get("arm_runtime_risks"), list)
            or not raw.get("arm_runtime_risks")
        ):
            raise ProductionCandidateError(f"Pi candidate is incomplete: {pipeline_id}")
        desktop = raw.get("current_desktop_accuracy")
        if not isinstance(desktop, Mapping):
            raise ProductionCandidateError("Pi candidate desktop evidence is absent")
        statistical = desktop.get("statistical_context")
        if (
            desktop.get("universal_within_one_percent_equivalence_rule_used")
            is not False
            or desktop.get("safety_errors_discounted_as_ordinary_small_differences")
            is not False
            or not isinstance(statistical, Mapping)
            or statistical.get("bootstrap_interval_source_consumed") is not True
            or statistical.get("paired_effect_size_source_consumed") is not True
        ):
            raise ProductionCandidateError(
                f"Pi statistical/safety evidence differs: {pipeline_id}"
            )
        bootstrap_path = _validate_live_artifact_ref(
            statistical.get("bootstrap_interval_source"),
            label=f"{pipeline_id} bootstrap interval source",
        )
        paired_path = _validate_live_artifact_ref(
            statistical.get("paired_effect_size_source"),
            label=f"{pipeline_id} paired effect-size source",
        )
        if (
            bootstrap_path.name != "bootstrap_intervals.csv"
            or paired_path.name != "paired_comparisons.csv"
        ):
            raise ProductionCandidateError(
                f"Pi statistical source artifact names differ: {pipeline_id}"
            )
        for field in (
            "wer",
            "der",
            "wrong_known",
            "stranger_false_known",
            "rtf",
            "peak_ram",
            "model_footprint",
            "resident_model_count",
            "windows_specific_assumptions",
            "linux_arm64_dependency_status",
            "required_platform_replacements",
        ):
            _validate_explicit_evidence(raw.get(field), label=f"{pipeline_id} {field}")
        latency = raw.get("latency")
        if not isinstance(latency, Mapping):
            raise ProductionCandidateError(
                f"Pi candidate latency evidence is absent: {pipeline_id}"
            )
        for field in (
            "first_readable_partial",
            "stable_transcript",
            "stable_correct_name",
        ):
            _validate_explicit_evidence(
                latency.get(field), label=f"{pipeline_id} latency {field}"
            )
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ProductionCandidateError("Pi candidate IDs are absent or duplicated")

    upstream = value.get("upstream_deployment_evidence")
    if not isinstance(upstream, Mapping) or set(upstream) != {
        "prompt5",
        "prompt6",
        "prompt7_shortlist_membership_authority",
        "membership_reselected_in_prompt8",
    }:
        raise ProductionCandidateError("Pi upstream evidence binding differs")
    if upstream.get("membership_reselected_in_prompt8") is not False:
        raise ProductionCandidateError("Pi membership was reselected in Prompt 8")
    p5_path = _validate_live_artifact_ref(
        upstream.get("prompt5"), label="Prompt-5 deployment evidence"
    )
    p6_path = _validate_live_artifact_ref(
        upstream.get("prompt6"), label="Prompt-6 deployment evidence"
    )
    p7_path = _validate_live_artifact_ref(
        upstream.get("prompt7_shortlist_membership_authority"),
        label="Prompt-7 Pi shortlist",
    )
    if (
        p5_path.name != "all18_deployment_evidence.json"
        or p6_path.name != ("extended_deployment_evidence.json")
        or p7_path.name != "raspberry_pi_candidate_shortlist.json"
    ):
        raise ProductionCandidateError("Pi upstream evidence artifact names differ")
    prompt7 = read_json(p7_path)
    prompt7_candidates = prompt7.get("candidates")
    if not isinstance(prompt7_candidates, list):
        raise ProductionCandidateError("Prompt-7 shortlist candidates are absent")
    prompt7_ids = [
        str(row.get("pipeline_id") or "")
        for row in prompt7_candidates
        if isinstance(row, Mapping)
    ]
    if set(prompt7_ids) != set(candidate_ids) or len(prompt7_ids) != len(candidate_ids):
        raise ProductionCandidateError(
            "Pi final candidate membership differs from Prompt-7 authority"
        )
    prompt7_index = {
        str(row.get("pipeline_id")): row
        for row in prompt7_candidates
        if isinstance(row, Mapping)
    }
    final_index = {
        str(row.get("pipeline_id")): row
        for row in candidates
        if isinstance(row, Mapping)
    }
    for pipeline_id in candidate_ids:
        desktop = final_index[pipeline_id].get("current_desktop_accuracy")
        if not isinstance(desktop, Mapping) or desktop.get(
            "prompt7_frozen_value"
        ) != prompt7_index[pipeline_id].get("current_desktop_accuracy"):
            raise ProductionCandidateError(
                f"Pi final desktop context loses Prompt-7 evidence: {pipeline_id}"
            )
        for field in PI_CANDIDATE_FIELDS:
            if field == "current_desktop_accuracy":
                continue
            if final_index[pipeline_id].get(field) != prompt7_index[pipeline_id].get(
                field
            ):
                raise ProductionCandidateError(
                    f"Pi final candidate rewrites Prompt-7 authority: "
                    f"{pipeline_id} {field}"
                )

    deployment = value.get("deployment_attributes_by_pipeline")
    if not isinstance(deployment, Mapping) or set(deployment) != set(candidate_ids):
        raise ProductionCandidateError("Pi deployment-attribute coverage differs")
    for pipeline_id, raw in deployment.items():
        if not isinstance(raw, Mapping) or set(raw) != set(PI_DEPLOYMENT_ATTRIBUTES):
            raise ProductionCandidateError(
                f"Pi exact deployment attributes differ: {pipeline_id}"
            )
        for attribute, evidence in raw.items():
            _validate_explicit_evidence(
                evidence, label=f"{pipeline_id} deployment attribute {attribute}"
            )
    feasibility = value.get("two_gib_feasibility_evidence_by_pipeline")
    if not isinstance(feasibility, Mapping) or set(feasibility) != set(candidate_ids):
        raise ProductionCandidateError("Pi feasibility-evidence coverage differs")
    for pipeline_id, raw in feasibility.items():
        if (
            not isinstance(raw, Mapping)
            or raw.get("class") not in PI_FEASIBILITY_CLASSES
            or not str(raw.get("evidence_status") or "").strip()
            or not str(raw.get("rationale_code") or "").strip()
            or raw.get("used_as_filter") is not False
            or raw.get("arm_measurement") is not False
        ):
            raise ProductionCandidateError(
                f"Pi feasibility evidence differs: {pipeline_id}"
            )

    tests = value.get("future_target_hardware_tests")
    if (
        not isinstance(tests, list)
        or tuple(
            str(row.get("test_id") or "") for row in tests if isinstance(row, Mapping)
        )
        != PI_FUTURE_TESTS
        or any(
            not isinstance(row, Mapping)
            or row.get("order") != index
            or row.get("required") is not True
            for index, row in enumerate(tests, start=1)
        )
    ):
        raise ProductionCandidateError("Pi exact 14-test handoff differs")
    linux_tests = value.get("future_linux_arm64_validation")
    if (
        not isinstance(linux_tests, list)
        or tuple(
            str(row.get("test_id") or "")
            for row in linux_tests
            if isinstance(row, Mapping)
        )
        != PI_FUTURE_LINUX_ARM64_TESTS
        or any(
            not isinstance(row, Mapping)
            or row.get("order") != index
            or row.get("required") is not True
            for index, row in enumerate(linux_tests, start=1)
        )
    ):
        raise ProductionCandidateError("Pi exact 7-test Linux ARM64 handoff differs")
    boundary = value.get("target_hardware_decision_boundary")
    policy = value.get("selection_policy")
    if (
        not isinstance(boundary, Mapping)
        or boundary.get("final_raspberry_pi_winner") is not None
        or boundary.get("final_raspberry_pi_winner_claimed") is not False
        or boundary.get("requires_export_optimization_and_real_arm_measurement")
        is not True
        or boundary.get("desktop_measurements_are_arm_measurements") is not False
        or not isinstance(policy, Mapping)
        or policy.get("scientific_rankings_changed") is not False
        or policy.get("weighted_composite_used") is not False
        or policy.get("universal_within_one_percent_equivalence_rule_used") is not False
        or policy.get("two_gib_used_as_premature_hard_filter") is not False
        or policy.get("desktop_rtf_used_as_pi_rtf") is not False
        or policy.get("desktop_winner_used_as_pi_winner") is not False
        or policy.get("candidate_membership_consumed_from_prompt7_without_reselection")
        is not True
    ):
        raise ProductionCandidateError("Pi decision-boundary policy differs")
    authority = value.get("steering_authority")
    if (
        not isinstance(authority, Mapping)
        or authority.get("embedded_document") != steering
        or authority.get("embedded_canonical_sha256")
        != sha256_bytes(canonical_json_bytes(steering))
    ):
        raise ProductionCandidateError("Pi steering authority embedding differs")


def _validate_live_artifact_ref(value: object, *, label: str):
    if not isinstance(value, Mapping):
        raise ProductionCandidateError(f"{label} reference is absent")
    path = ensure_c(str(value.get("path") or ""), label=label, must_exist=True)
    if not path.is_file() or value.get("sha256") != sha256_file(path):
        raise ProductionCandidateError(f"{label} reference hash differs")
    return path


def _validate_upstream_deployment_evidence(
    *,
    bundle: EvidenceBundle,
    rankings: RankingResult,
    matrix: FullPipelineMatrix,
    credible: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Validate P5/P6 deployment evidence and P7's sole shortlist authority."""

    steering = bundle.pi_deployment_steering
    expected_p5_ids = tuple(matrix.pipeline_ids)
    if expected_p5_ids != bundle.pipeline_ids:
        raise IncompleteEvidenceError("matrix/P5 deployment pipeline order differs")
    expected_p6_ids = _frozen_extended_ids(bundle, expected_p5_ids)

    p5_path = bundle.completions[5].one("all18_deployment_evidence.json")
    p6_path = bundle.completions[6].one("extended_deployment_evidence.json")
    p7_path = bundle.completions[7].one("raspberry_pi_candidate_shortlist.json")
    try:
        p5_document = validate_deployment_evidence_document(
            read_json(p5_path),
            schema_version="full-pipeline-all18-deployment-evidence.v1",
            prompt_index=5,
            expected_pipeline_ids=expected_p5_ids,
            steering=steering,
        )
        p6_document = validate_deployment_evidence_document(
            read_json(p6_path),
            schema_version="full-pipeline-extended-deployment-evidence.v1",
            prompt_index=6,
            expected_pipeline_ids=expected_p6_ids,
            steering=steering,
        )
    except DeploymentEvidenceError as exc:
        raise IncompleteEvidenceError(
            f"upstream deployment-evidence validation failed: {exc}"
        ) from exc
    _validate_scope(p5_document, label="Prompt-5 deployment evidence")
    _validate_scope(p6_document, label="Prompt-6 deployment evidence")
    _validate_steering_ref(
        p5_document.get("steering_authority"), bundle=bundle, label="Prompt-5"
    )
    _validate_steering_ref(
        p6_document.get("steering_authority"), bundle=bundle, label="Prompt-6"
    )
    _validate_exact_artifact_ref(
        p6_document.get("prompt5_deployment_evidence"),
        path=p5_path,
        label="Prompt-6 Prompt-5 deployment evidence",
    )
    _validate_prompt5_deployment_context(bundle, p5_document)
    _validate_prompt6_deployment_context(
        bundle,
        p6_document,
        expected_ids=expected_p6_ids,
    )

    p5_rows = _deployment_rows(p5_document, expected_p5_ids, label="Prompt-5")
    p6_rows = _deployment_rows(p6_document, expected_p6_ids, label="Prompt-6")
    for pipeline_id in expected_p6_ids:
        p5_row = p5_rows[pipeline_id]
        p6_row = p6_rows[pipeline_id]
        if p6_row.get("prompt5_pipeline_evidence_sha256") not in {
            None,
            sha256_bytes(canonical_json_bytes(p5_row)),
        }:
            raise IncompleteEvidenceError(
                f"Prompt-6/P5 per-pipeline evidence binding differs: {pipeline_id}"
            )
        # Prompt 6 may add serial measurements, but it may not rewrite already
        # measured P5 evidence without an explicit upstream reference.
        for key in (
            "windows_specific_assumptions",
            "linux_arm64_dependency_status",
            "required_platform_replacements",
        ):
            _validate_explicit_evidence(p6_row.get(key), label=f"{pipeline_id} {key}")

    p7_document = read_json(p7_path)
    _validate_scope(p7_document, label="Prompt-7 Pi shortlist")
    if (
        p7_document.get("schema_version")
        != "full-pipeline-raspberry-pi-candidate-shortlist.v1"
        or p7_document.get("status") != "PASS"
        or int(p7_document.get("prompt_index") or -1) != 7
    ):
        raise ProductionCandidateError("Prompt-7 Pi shortlist core contract differs")
    _validate_steering_ref(
        p7_document.get("steering_authority"), bundle=bundle, label="Prompt-7"
    )
    _validate_exact_artifact_ref(
        p7_document.get("prompt5_deployment_evidence"),
        path=p5_path,
        label="Prompt-7 Prompt-5 deployment evidence",
    )
    _validate_exact_artifact_ref(
        p7_document.get("prompt6_deployment_evidence"),
        path=p6_path,
        label="Prompt-7 Prompt-6 deployment evidence",
    )
    _validate_exact_artifact_ref(
        p7_document.get("desktop_roles_source"),
        path=bundle.completions[7].one("production_candidate_catalog.yaml"),
        label="Prompt-7 desktop roles source",
    )
    extended_reference = bundle.frozen_policy_refs.get("extended_set")
    if not isinstance(extended_reference, Mapping):
        raise IncompleteEvidenceError("Prompt-7 candidate-pool authority is absent")
    _validate_exact_artifact_ref(
        p7_document.get("candidate_pool_source"),
        path=extended_reference["path"],
        label="Prompt-7 frozen candidate pool",
    )
    if p7_document.get("candidate_pool_pipeline_ids") != list(expected_p6_ids):
        raise ProductionCandidateError("Prompt-7 Pi candidate pool differs")
    if p7_document.get("desktop_roles_changed_for_pi") is not False:
        raise ProductionCandidateError("Prompt-7 desktop roles changed for Pi")
    expected_roles = {
        "PRIMARY": rankings.primary,
        "FALLBACK": rankings.fallback,
        "ALTERNATIVE": rankings.alternative,
    }
    if p7_document.get("desktop_roles") != expected_roles:
        raise ProductionCandidateError("Prompt-7 Pi desktop-role binding differs")

    raw_candidates = p7_document.get("candidates")
    if not isinstance(raw_candidates, list) or not 2 <= len(raw_candidates) <= 4:
        raise ProductionCandidateError("Prompt-7 Pi candidate count differs")
    if int(p7_document.get("candidate_count") or -1) != len(raw_candidates):
        raise ProductionCandidateError("Prompt-7 Pi candidate-count binding differs")
    prompt7_candidates: dict[str, Mapping[str, object]] = {}
    for raw in raw_candidates:
        if not isinstance(raw, Mapping) or set(raw) != set(PI_CANDIDATE_FIELDS):
            raise ProductionCandidateError("Prompt-7 exact Pi candidate fields differ")
        pipeline_id = str(raw.get("pipeline_id") or "")
        if (
            not pipeline_id
            or pipeline_id in prompt7_candidates
            or pipeline_id not in expected_p6_ids
            or pipeline_id not in credible
        ):
            raise ProductionCandidateError(
                f"Prompt-7 Pi candidate membership is invalid: {pipeline_id}"
            )
        prompt7_candidates[pipeline_id] = raw
    if rankings.primary not in prompt7_candidates:
        raise ProductionCandidateError("Prompt-7 Pi shortlist omits desktop primary")

    prompt7_attributes = p7_document.get("deployment_attributes_by_pipeline")
    prompt7_feasibility = p7_document.get("two_gib_classification_evidence_by_pipeline")
    if (
        not isinstance(prompt7_attributes, Mapping)
        or set(prompt7_attributes) != set(prompt7_candidates)
        or not isinstance(prompt7_feasibility, Mapping)
        or set(prompt7_feasibility) != set(prompt7_candidates)
    ):
        raise ProductionCandidateError(
            "Prompt-7 Pi deployment/feasibility coverage differs"
        )
    for pipeline_id, candidate in prompt7_candidates.items():
        p6_row = p6_rows[pipeline_id]
        attributes = prompt7_attributes[pipeline_id]
        feasibility = prompt7_feasibility[pipeline_id]
        if not isinstance(attributes, Mapping) or attributes != p6_row.get(
            "deployment_attributes"
        ):
            raise ProductionCandidateError(
                f"Prompt-7/P6 deployment attributes differ: {pipeline_id}"
            )
        try:
            for key in PI_DEPLOYMENT_ATTRIBUTES:
                validate_evidence(attributes[key])
        except (DeploymentEvidenceError, KeyError, TypeError) as exc:
            raise ProductionCandidateError(
                f"Prompt-7 deployment attributes are invalid: {pipeline_id}: {exc}"
            ) from exc
        if not isinstance(feasibility, Mapping) or feasibility != p6_row.get(
            "two_gib_feasibility"
        ):
            raise ProductionCandidateError(
                f"Prompt-7/P6 2-GiB classification differs: {pipeline_id}"
            )
        portability = p6_row.get("linux_arm64_portability")
        if (
            not isinstance(portability, Mapping)
            or candidate.get("two_gib_feasibility_class") != feasibility.get("class")
            or candidate.get("linux_arm64_portability_class")
            != portability.get("class")
        ):
            raise ProductionCandidateError(
                f"Prompt-7 candidate deployment classes differ: {pipeline_id}"
            )
        for key in (
            "windows_specific_assumptions",
            "linux_arm64_dependency_status",
            "required_platform_replacements",
        ):
            if candidate.get(key) != p6_row.get(key):
                raise ProductionCandidateError(
                    f"Prompt-7/P6 platform evidence differs: {pipeline_id} {key}"
                )

    policy = p7_document.get("selection_policy")
    if (
        not isinstance(policy, Mapping)
        or policy.get("weighted_composite_used") is not False
        or policy.get("universal_within_one_percent_equivalence_rule_used") is not False
        or policy.get("deployment_evidence_used_to_rewrite_scientific_ranks")
        is not False
        or policy.get("two_gib_used_as_hard_filter") is not False
        or policy.get("final_pi_winner_selected") is not False
    ):
        raise ProductionCandidateError("Prompt-7 Pi selection policy differs")
    if (
        p7_document.get("final_raspberry_pi_winner") is not None
        or p7_document.get("final_raspberry_pi_winner_claimed") is not False
    ):
        raise ProductionCandidateError("Prompt-7 improperly claims a final Pi winner")
    if _test_ids(p7_document.get("future_target_hardware_tests")) != PI_FUTURE_TESTS:
        raise ProductionCandidateError("Prompt-7 exact 14 ARM tests differ")
    if (
        _test_ids(p7_document.get("future_linux_arm64_validation"))
        != PI_FUTURE_LINUX_ARM64_TESTS
    ):
        raise ProductionCandidateError("Prompt-7 exact 7 Linux ARM64 tests differ")
    architecture = p7_document.get("architecture_tradeoff_audit")
    if (
        not isinstance(architecture, Mapping)
        or architecture.get("final_arm_preference_claimed") is not False
    ):
        raise ProductionCandidateError("Prompt-7 architecture tradeoff audit differs")
    return {
        "prompt5_document": p5_document,
        "prompt6_document": p6_document,
        "prompt7_document": p7_document,
        "prompt7_candidates": prompt7_candidates,
        "prompt7_attributes": prompt7_attributes,
        "prompt7_feasibility": prompt7_feasibility,
        "architecture_tradeoff_audit": architecture,
    }


def _validate_prompt7_candidate_binding(
    candidate: Mapping[str, object],
    *,
    prompt7_candidate: Mapping[str, object],
    selection: PipelineSelection,
    row: Mapping[str, object],
    deployment: Mapping[str, object],
    feasibility: Mapping[str, object],
) -> None:
    pipeline_id = selection.pipeline_id
    if candidate.get("pipeline_id") != pipeline_id:
        raise ProductionCandidateError(f"Prompt-7 candidate ID differs: {pipeline_id}")
    for key in PI_CANDIDATE_FIELDS:
        if key not in {"current_desktop_accuracy", "two_gib_feasibility_class"} and (
            candidate.get(key) != prompt7_candidate.get(key)
        ):
            raise ProductionCandidateError(
                f"Prompt-8 rewrote Prompt-7 Pi candidate field: {pipeline_id} {key}"
            )
    _validate_component_alias(
        candidate.get("asr"),
        expected=selection.asr_alias,
        label=f"{pipeline_id} ASR",
    )
    _validate_component_alias(
        candidate.get("diarization_embedding"),
        expected=selection.diarization_alias,
        label=f"{pipeline_id} diarization embedding",
    )
    _validate_component_alias(
        candidate.get("identity_embedding"),
        expected=selection.identity_alias,
        label=f"{pipeline_id} identity embedding",
    )
    _validate_descriptor_values(
        candidate.get("asr"),
        expected={
            "component_id": selection.asr.get("component_id"),
            "registry_id": selection.asr.get("registry_id"),
            "environment_profile": selection.asr.get("environment_profile"),
        },
        label=f"{pipeline_id} ASR",
    )
    _validate_descriptor_values(
        candidate.get("diarization_embedding"),
        expected={
            "backend_id": selection.diarization_embedding.get("backend_id"),
            "model_id": selection.diarization_embedding.get("model_id"),
            "embedding_dimension": selection.diarization_embedding.get(
                "embedding_dimension"
            ),
            "environment_profile": selection.diarization_embedding.get(
                "environment_profile"
            ),
        },
        label=f"{pipeline_id} diarization embedding",
    )
    _validate_descriptor_values(
        candidate.get("identity_embedding"),
        expected={
            "backend_id": selection.identity.get("backend_id"),
            "model_id": selection.identity.get("model_id"),
            "embedding_dimension": selection.identity.get("embedding_dimension"),
            "environment_profile": selection.identity.get("environment_profile"),
        },
        label=f"{pipeline_id} identity embedding",
    )
    segmentation = candidate.get("segmentation")
    enrollment = candidate.get("enrollment_policy")
    if not isinstance(segmentation, Mapping) or segmentation.get(
        "segmentation_id"
    ) != selection.diarization.get("segmentation_id"):
        raise ProductionCandidateError(
            f"Prompt-7 segmentation identity differs: {pipeline_id}"
        )
    if not isinstance(enrollment, Mapping) or any(
        enrollment.get(key) != selection.enrollment_policy.get(key)
        for key in ("policy_id", "path", "sha256")
    ):
        raise ProductionCandidateError(
            f"Prompt-7 enrollment-policy identity differs: {pipeline_id}"
        )
    for field, metric in (
        ("wer", "wer"),
        ("der", "der"),
        ("wrong_known", "wrong_known_time_sec"),
        ("stranger_false_known", "stranger_false_known_time_sec"),
        ("rtf", "total_rtf"),
    ):
        evidence_cell = candidate.get(field)
        _validate_explicit_evidence(evidence_cell, label=f"{pipeline_id} {field}")
        expected = _number(row.get(metric))
        actual = _evidence_number(evidence_cell)
        if expected is not None and actual != expected:
            raise ProductionCandidateError(
                f"Prompt-7 candidate metric differs from P5/P6 evidence: "
                f"{pipeline_id} {field}"
            )
    # Prompt-7 intentionally uses Prompt-6's standardized serial resource
    # evidence for RAM/model footprint.  Those values need not equal the
    # Prompt-5 all-18 resource spot check used by the desktop ranking.
    if candidate.get("peak_ram") != deployment.get("total_pipeline_peak_rss_bytes"):
        raise ProductionCandidateError(
            f"Prompt-7 peak-RAM binding differs: {pipeline_id}"
        )
    if candidate.get("model_footprint") != deployment.get("model_file_size_bytes"):
        raise ProductionCandidateError(
            f"Prompt-7 model-footprint binding differs: {pipeline_id}"
        )
    if candidate.get("resident_model_count") != deployment.get(
        "simultaneously_resident_neural_model_count"
    ):
        raise ProductionCandidateError(
            f"Prompt-7 resident-model binding differs: {pipeline_id}"
        )
    if candidate.get("two_gib_feasibility_class") != feasibility.get("class"):
        raise ProductionCandidateError(
            f"Prompt-7 2-GiB candidate class differs: {pipeline_id}"
        )
    for field in (
        "resident_model_count",
        "windows_specific_assumptions",
        "linux_arm64_dependency_status",
        "required_platform_replacements",
    ):
        _validate_explicit_evidence(
            candidate.get(field), label=f"{pipeline_id} {field}"
        )
    latency = candidate.get("latency")
    if not isinstance(latency, Mapping):
        raise ProductionCandidateError(
            f"Prompt-7 latency evidence differs: {pipeline_id}"
        )
    for key in ("first_readable_partial", "stable_transcript", "stable_correct_name"):
        _validate_explicit_evidence(
            latency.get(key), label=f"{pipeline_id} latency {key}"
        )
    if not isinstance(candidate.get("reason_retained"), list) or not candidate.get(
        "reason_retained"
    ):
        raise ProductionCandidateError(
            f"Prompt-7 retention reasons absent: {pipeline_id}"
        )


def _validate_prompt5_deployment_context(
    bundle: EvidenceBundle, document: Mapping[str, object]
) -> None:
    binding = document.get("input_binding")
    if not isinstance(binding, Mapping):
        raise IncompleteEvidenceError("Prompt-5 deployment input binding is absent")
    expected = {
        "prompt5_authorization_path": bundle.completions[5].one(
            "prompt5_authorization.json"
        ),
        "serial_resources_path": bundle.completions[5].one("all18_resources.csv"),
    }
    for path_key, path in expected.items():
        _validate_path_hash_pair(
            binding,
            path_key=path_key,
            hash_key=path_key.replace("_path", "_sha256"),
            expected_path=path,
            label=f"Prompt-5 {path_key}",
        )
    policy = document.get("evidence_policy")
    classification = document.get("classification_policy")
    portability = document.get("platform_portability_policy")
    if (
        not isinstance(policy, Mapping)
        or policy.get("unknown_or_unsupported_explicit") is not True
        or policy.get("desktop_measurement_relabelled_as_arm") is not False
        or policy.get("model_or_scientific_execution_modified_to_measure") is not False
        or policy.get("uncertainty_separate_from_feasibility_class") is not True
        or not isinstance(classification, Mapping)
        or classification.get("two_gib_is_design_constraint_not_prompt5_filter")
        is not True
        or classification.get("final_raspberry_pi_winner_claimed") is not False
        or not isinstance(portability, Mapping)
        or portability.get("current_platform") != "WINDOWS_X86_64"
        or portability.get("future_target_platform")
        != "LINUX_DEBIAN_RASPBERRY_PI_OS_ARM64"
        or portability.get("desktop_rank_used_as_final_arm_rank") is not False
    ):
        raise IncompleteEvidenceError("Prompt-5 deployment evidence policy differs")


def _validate_prompt6_deployment_context(
    bundle: EvidenceBundle,
    document: Mapping[str, object],
    *,
    expected_ids: Sequence[str],
) -> None:
    extended_ref = bundle.frozen_policy_refs.get("extended_set")
    predeclared = document.get("predeclared_membership")
    if not isinstance(extended_ref, Mapping) or not isinstance(predeclared, Mapping):
        raise IncompleteEvidenceError(
            "Prompt-6 predeclared deployment membership is absent"
        )
    if (
        predeclared.get("source_prompt_index") != 4
        or predeclared.get("pipeline_ids") != list(expected_ids)
        or int(predeclared.get("pipeline_count") or -1) != len(expected_ids)
        or predeclared.get("frozen_before_prompt5_heldout_opened") is not True
        or predeclared.get("membership_changed_after_heldout") is not False
        or predeclared.get("deployment_evidence_used_as_filter") is not False
    ):
        raise IncompleteEvidenceError(
            "Prompt-6 predeclared deployment membership differs"
        )
    _validate_exact_artifact_ref(
        predeclared.get("extended_set"),
        path=extended_ref["path"],
        label="Prompt-6 frozen extended set",
    )
    serial = document.get("serial_resource_evidence")
    if not isinstance(serial, Mapping):
        raise IncompleteEvidenceError("Prompt-6 serial deployment evidence is absent")
    _validate_exact_artifact_ref(
        serial,
        path=bundle.completions[6].one("serial_resources.csv"),
        label="Prompt-6 serial resource evidence",
    )
    statuses = serial.get("pipeline_statuses")
    if (
        serial.get("measurement_context") != "WINDOWS_X86_64_DESKTOP"
        or serial.get("arm_measurement") is not False
        or serial.get("resource_concurrency") != 1
        or serial.get("used_as_filter") is not False
        or not isinstance(statuses, list)
        or [
            str(item.get("pipeline_id") or "")
            for item in statuses
            if isinstance(item, Mapping)
        ]
        != list(expected_ids)
    ):
        raise IncompleteEvidenceError(
            "Prompt-6 serial deployment-resource policy differs"
        )


def _frozen_extended_ids(
    bundle: EvidenceBundle, pipeline_ids: Sequence[str]
) -> tuple[str, ...]:
    reference = bundle.frozen_policy_refs.get("extended_set")
    if not isinstance(reference, Mapping):
        raise IncompleteEvidenceError("frozen extended-set reference is absent")
    path = str(reference.get("path") or "")
    document = load_yaml(path)
    values = tuple(str(item) for item in document.get("extended_pipeline_ids", []))
    if (
        not 6 <= len(values) <= 8
        or len(values) != len(set(values))
        or set(values) - set(pipeline_ids)
    ):
        raise IncompleteEvidenceError("frozen extended-set membership differs")
    return values


def _deployment_rows(
    document: Mapping[str, object], expected_ids: Sequence[str], *, label: str
) -> dict[str, Mapping[str, object]]:
    raw = document.get("pipelines")
    if not isinstance(raw, list):
        raise IncompleteEvidenceError(f"{label} deployment rows are absent")
    rows = {
        str(item.get("pipeline_id") or ""): item
        for item in raw
        if isinstance(item, Mapping)
    }
    if set(rows) != set(expected_ids) or "" in rows or len(rows) != len(raw):
        raise IncompleteEvidenceError(f"{label} deployment-row coverage differs")
    return rows


def _validate_scope(value: Mapping[str, object], *, label: str) -> None:
    expected = scope_fields()
    if any(
        value.get(key) != expected_value for key, expected_value in expected.items()
    ):
        raise IncompleteEvidenceError(f"{label} scope differs")


def _validate_steering_ref(
    value: object, *, bundle: EvidenceBundle, label: str
) -> None:
    if not isinstance(value, Mapping) or (
        value.get("path") != str(bundle.pi_deployment_steering_path)
        or value.get("sha256") != bundle.pi_deployment_steering_sha256
        or value.get("schema_version") != "full-pipeline-deployment-steering.v1"
        or value.get("steering_id") != "raspberry_pi_compute_module_2gb.v1"
    ):
        raise IncompleteEvidenceError(f"{label} deployment steering binding differs")


def _validate_exact_artifact_ref(value: object, *, path, label: str) -> None:
    if not isinstance(value, Mapping) or (
        value.get("path") != str(path) or value.get("sha256") != sha256_file(path)
    ):
        raise IncompleteEvidenceError(f"{label} artifact binding differs")


def _validate_path_hash_pair(
    value: Mapping[str, object],
    *,
    path_key: str,
    hash_key: str,
    expected_path,
    label: str,
) -> None:
    if value.get(path_key) != str(expected_path) or value.get(hash_key) != sha256_file(
        expected_path
    ):
        raise IncompleteEvidenceError(f"{label} path/hash binding differs")


def _test_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            result.append(str(item.get("test_id") or ""))
        else:
            result.append(str(item))
    return tuple(result)


def _validate_component_alias(value: object, *, expected: str, label: str) -> None:
    if not isinstance(value, Mapping):
        raise ProductionCandidateError(f"{label} descriptor is absent")
    aliases = {
        str(value.get(key) or "")
        for key in ("alias", "asr_alias", "diarization_alias", "identity_alias")
    }
    if expected not in aliases:
        raise ProductionCandidateError(f"{label} frozen alias differs")


def _validate_descriptor_values(
    value: object, *, expected: Mapping[str, object], label: str
) -> None:
    if not isinstance(value, Mapping) or any(
        value.get(key) != expected_value for key, expected_value in expected.items()
    ):
        raise ProductionCandidateError(f"{label} frozen identity differs")


def _evidence_number(value: object) -> float | None:
    if not isinstance(value, Mapping):
        return None
    return _number(value.get("value"))


def _scientifically_credible(row: Mapping[str, object]) -> bool:
    # The all-18 desktop "not worth continuing" label is a separate reporting
    # role and must not veto a Prompt-7-authorized Pi-only architecture.  Keep
    # this gate to objective evidence that Prompt 7 also requires.
    supported = (
        bool(row.get("selected_role"))
        or row.get("pareto_frontier") is True
        or row.get("extended_evidence_status") == "TESTED_IN_PREDECLARED_EXTENDED_SET"
    )
    rtf = _number(row.get("total_rtf"))
    return (
        supported
        and _number(row.get("wrong_known_time_sec")) is not None
        and _number(row.get("stranger_false_known_time_sec")) is not None
        and _number(row.get("reliability_failure_count")) == 0.0
        and rtf is not None
        and rtf <= 1.0
    )


def _statistical_context(
    *,
    pipeline_id: str,
    primary: str,
    bootstrap_rows: Sequence[Mapping[str, object]],
    paired_rows: Sequence[Mapping[str, object]],
    bootstrap_path,
    paired_path,
) -> dict[str, object]:
    intervals: list[dict[str, object]] = []
    for row in bootstrap_rows:
        if (
            row.get("pipeline_id") == pipeline_id
            and row.get("metric_id") in STATISTICAL_METRICS
        ):
            intervals.append(
                {
                    "category": row.get("category"),
                    "metric_id": row.get("metric_id"),
                    "analysis_scope": row.get("analysis_scope"),
                    "point_estimate": _number(row.get("point_estimate")),
                    "ci_lower_95": _number(row.get("ci_lower_95")),
                    "ci_upper_95": _number(row.get("ci_upper_95")),
                    "speaker_cluster_count": _int_or_none(
                        row.get("speaker_cluster_count")
                    ),
                    "status": "DESKTOP_SPEAKER_CLUSTER_BOOTSTRAP",
                }
            )
    comparisons: list[dict[str, object]] = []
    if pipeline_id != primary:
        for row in paired_rows:
            left = str(row.get("left_pipeline_id") or "")
            right = str(row.get("right_pipeline_id") or "")
            if row.get("metric_id") not in STATISTICAL_METRICS or {
                left,
                right,
            } != {pipeline_id, primary}:
                continue
            point = _number(row.get("left_minus_right"))
            lower = _number(row.get("ci_lower_95"))
            upper = _number(row.get("ci_upper_95"))
            if right == pipeline_id:
                point = -point if point is not None else None
                lower, upper = (
                    (-upper if upper is not None else None),
                    (-lower if lower is not None else None),
                )
            comparisons.append(
                {
                    "category": row.get("category"),
                    "metric_id": row.get("metric_id"),
                    "candidate_minus_desktop_primary": point,
                    "ci_lower_95": lower,
                    "ci_upper_95": upper,
                    "paired_speaker_cluster_count": _int_or_none(
                        row.get("paired_speaker_cluster_count")
                    ),
                    "higher_is_better": row.get("higher_is_better"),
                    "status": "DESKTOP_PAIRED_SPEAKER_CLUSTER_EFFECT_SIZE",
                }
            )
    return {
        "bootstrap_interval_source_consumed": True,
        "paired_effect_size_source_consumed": True,
        "bootstrap_interval_source": artifact_ref(bootstrap_path),
        "paired_effect_size_source": artifact_ref(paired_path),
        "bootstrap_intervals": intervals,
        "bootstrap_interval_status": (
            "AVAILABLE" if intervals else "UNKNOWN_NO_APPLICABLE_INTERVAL_ROW"
        ),
        "paired_against_desktop_primary": comparisons,
        "paired_effect_size_status": (
            "SELF_REFERENCE_NOT_APPLICABLE"
            if pipeline_id == primary
            else "AVAILABLE"
            if comparisons
            else "UNKNOWN_NO_APPLICABLE_PAIRED_ROW"
        ),
        "confidence_interval_used_as_universal_equivalence_threshold": False,
    }


def _deployment_attributes(
    selection: PipelineSelection, row: Mapping[str, object]
) -> dict[str, object]:
    extended = row.get("p6_extended_metrics")
    metrics = extended.get("metrics") if isinstance(extended, Mapping) else None
    p6 = metrics if isinstance(metrics, Mapping) else {}
    environments = sorted(
        {
            str(selection.asr.get("environment_profile") or "UNKNOWN"),
            str(
                selection.diarization.get("segmentation_environment_profile")
                or "UNKNOWN"
            ),
            str(
                selection.diarization.get("embedding_environment_profile") or "UNKNOWN"
            ),
            str(selection.identity.get("environment_profile") or "UNKNOWN"),
        }
    )
    same_speaker_backend = selection.diarization.get(
        "embedding_backend_id"
    ) == selection.identity.get("backend_id")
    asr_files = selection.asr.get("model_asset", {}).get("result_affecting_files", {})
    asr_onnx = isinstance(asr_files, Mapping) and any(
        str(name).casefold().endswith(".onnx") for name in asr_files
    )
    asr_int8 = isinstance(asr_files, Mapping) and any(
        "int8" in str(name).casefold() for name in asr_files
    )
    result = {
        "model_file_size_bytes": _desktop_measurement(row, "model_bytes", "bytes"),
        "loaded_model_memory_bytes": _p6_measurement(
            p6, "loaded_model_memory_bytes", "bytes"
        ),
        "peak_process_rss_bytes": _unknown(
            "bytes", "UNKNOWN_COMPONENT_PROCESS_BREAKDOWN_NOT_MEASURED"
        ),
        "total_pipeline_peak_rss_bytes": _desktop_measurement(
            row, "peak_rss_bytes", "bytes"
        ),
        "simultaneously_resident_neural_model_count": _unknown(
            "models", "UNKNOWN_RUNTIME_RESIDENCY_NOT_INSTRUMENTED"
        ),
        "worker_process_count": _p6_measurement(
            p6, "worker_process_count", "processes"
        ),
        "runtime_environment_count": _evidence(
            len(environments),
            "environments",
            "DERIVED_FROM_FROZEN_ENVIRONMENT_PROFILES_NOT_PROCESS_COUNT",
            details={"environment_profiles": environments},
        ),
        "embedding_dimensions": _evidence(
            {
                "diarization": selection.diarization_embedding.get(
                    "embedding_dimension"
                ),
                "identity": selection.identity.get("embedding_dimension"),
            },
            "dimensions",
            "FROZEN_COMPONENT_METADATA",
        ),
        "persistent_enrollment_template_memory_bytes": _unknown(
            "bytes", "UNKNOWN_PROFILE_DTYPE_AND_RETAINED_TEMPLATE_COUNT_NOT_MEASURED"
        ),
        "cache_requirements_bytes": _p6_measurement(p6, "cache_bytes", "bytes"),
        "initialization_time_sec": _p6_measurement(p6, "model_startup_sec", "seconds"),
        "warmup_time_sec": _p6_measurement(p6, "warmup_duration_sec", "seconds"),
        "native_onnx_availability": _evidence(
            {
                "asr": "AVAILABLE_CURRENT_ASSET" if asr_onnx else "UNKNOWN",
                "segmentation": "UNKNOWN_NOT_EXPORT_VALIDATED",
                "diarization_embedding": "UNKNOWN_NOT_EXPORT_VALIDATED",
                "identity_embedding": "UNKNOWN_NOT_EXPORT_VALIDATED",
            },
            None,
            "PARTIAL_COMPONENT_DECLARATION_NOT_FULL_PIPELINE_ARM_EXPORT",
        ),
        "pytorch_dependency": _evidence(
            {
                "asr": False if asr_onnx else "UNKNOWN",
                "segmentation": True,
                "diarization_embedding": True,
                "identity_embedding": True,
            },
            None,
            "CURRENT_DESKTOP_ASSET_AND_IMPLEMENTATION_METADATA",
        ),
        "arm_compatibility_status": _unknown(None, "UNKNOWN_NOT_TESTED_ON_ARM_TARGET"),
        "int8_status": _evidence(
            {
                "asr": "PARTIAL_INT8_ASSETS_PRESENT" if asr_int8 else "UNKNOWN",
                "other_components": "UNKNOWN_NOT_EVALUATED",
            },
            None,
            "DESKTOP_ASSET_FILENAME_EVIDENCE_ONLY",
        ),
        "fp16_status": _unknown(None, "UNKNOWN_NOT_EVALUATED"),
        "export_status": _unknown(
            None, "UNKNOWN_FULL_PIPELINE_ARM_EXPORT_NOT_IMPLEMENTED"
        ),
        "quantization_readiness": _unknown(
            None, "UNKNOWN_REQUIRES_COMPONENT_EXPORT_AND_PARITY_VALIDATION"
        ),
        "executorch_feasibility": _unknown(None, "UNKNOWN_NOT_EVALUATED"),
        "onnx_runtime_export_feasibility": _evidence(
            {
                "asr": "NATIVE_ONNX_CURRENTLY" if asr_onnx else "UNKNOWN",
                "speaker_and_segmentation": "UNKNOWN_REQUIRES_EXPORT_PARITY",
            },
            None,
            "PARTIAL_DESKTOP_EVIDENCE_NOT_ARM_VALIDATION",
        ),
        "model_instance_sharing_opportunities": _evidence(
            (
                "POTENTIAL_SAME_BACKEND_REUSE_NOT_IMPLEMENTED_OR_MEASURED"
                if same_speaker_backend
                else "DISTINCT_SPEAKER_BACKENDS_NO_CROSS_MODEL_REUSE_ASSUMED"
            ),
            None,
            "ARCHITECTURE_INSPECTION_ONLY",
        ),
        "embedding_reuse_opportunities": _evidence(
            (
                "POTENTIAL_REUSE_REQUIRES_TIMESTAMP_WINDOW_AND_PARITY_PROOF"
                if same_speaker_backend
                else "NO_REUSE_CLAIM_DISTINCT_EMBEDDING_BACKENDS"
            ),
            None,
            "ARCHITECTURE_INSPECTION_ONLY",
        ),
        "duplicated_feature_extraction": _unknown(
            None, "UNKNOWN_NOT_INSTRUMENTED_IN_CURRENT_RUNTIME"
        ),
        "dependency_complexity": _evidence(
            {
                "environment_profile_count": len(environments),
                "environment_profiles": environments,
            },
            None,
            "DERIVED_FROM_FROZEN_DESKTOP_ENVIRONMENT_PROFILES",
        ),
    }
    if set(result) != set(PI_DEPLOYMENT_ATTRIBUTES):
        raise ProductionCandidateError("internal Pi deployment attribute set differs")
    return result


def _asr_descriptor(selection: PipelineSelection) -> dict[str, object]:
    asset = selection.asr.get("model_asset")
    return {
        "alias": selection.asr_alias,
        "component_id": selection.asr.get("component_id"),
        "registry_id": selection.asr.get("registry_id"),
        "environment_profile": selection.asr.get("environment_profile"),
        "model_asset_id": asset.get("asset_id") if isinstance(asset, Mapping) else None,
        "model_asset_installed_bytes": (
            asset.get("installed_bytes") if isinstance(asset, Mapping) else None
        ),
        "status": "FROZEN_DESKTOP_COMPONENT_NOT_ARM_BENCHMARKED",
    }


def _segmentation_descriptor(
    matrix: FullPipelineMatrix, selection: PipelineSelection
) -> dict[str, object]:
    shared = matrix.matrix.get("shared_segmentation_asset")
    asset = shared if isinstance(shared, Mapping) else {}
    return {
        "segmentation_id": selection.diarization.get("segmentation_id"),
        "asset_id": asset.get("asset_id"),
        "installed_bytes": asset.get("installed_bytes"),
        "asset_sha256": selection.diarization.get("segmentation_model_asset_sha256"),
        "environment_profile": selection.diarization.get(
            "segmentation_environment_profile"
        ),
        "status": "FROZEN_SHARED_PYANNOTE_SEGMENTATION_NOT_ARM_BENCHMARKED",
    }


def _embedding_descriptor(
    component: Mapping[str, object], *, alias: str, role: str
) -> dict[str, object]:
    return {
        "alias": alias,
        "role": role,
        "backend_id": component.get("backend_id"),
        "model_id": component.get("model_id"),
        "embedding_dimension": component.get("embedding_dimension"),
        "environment_profile": component.get("environment_profile"),
        "status": "FROZEN_DESKTOP_COMPONENT_NOT_ARM_BENCHMARKED",
    }


def _export_path(selection: PipelineSelection) -> dict[str, object]:
    return {
        "status": "PARTIAL_ASR_ONNX_ONLY_FULL_PIPELINE_EXPORT_NOT_IMPLEMENTED",
        "asr": "REUSE_NATIVE_SHERPA_ONNX_AND_VALIDATE_ARM_PARITY",
        "segmentation": "UNKNOWN_SELECT_ONNX_OR_EXECUTORCH_AFTER_EXPORT_STUDY",
        "diarization_embedding": "UNKNOWN_EXPORT_AND_PARITY_REQUIRED",
        "identity_embedding": "UNKNOWN_EXPORT_AND_PARITY_REQUIRED",
        "clustering_and_policy": "PORT_DETERMINISTIC_CPU_LOGIC_AND_VALIDATE_PARITY",
        "arm_execution_validated": False,
    }


def _quantization_opportunities(
    selection: PipelineSelection,
) -> list[dict[str, object]]:
    same = selection.diarization.get("embedding_backend_id") == selection.identity.get(
        "backend_id"
    )
    return [
        {
            "component": "asr",
            "opportunity": "PRESERVE_EXISTING_INT8_ASSETS_WHERE_PRESENT",
            "status": "REQUIRES_ARM_PARITY_AND_LATENCY_VALIDATION",
        },
        {
            "component": "speaker_embedding",
            "opportunity": "EVALUATE_INT8_FP16_ONNX_OR_EXECUTORCH_EXPORT",
            "status": "UNKNOWN_NOT_ATTEMPTED",
        },
        {
            "component": "shared_speaker_model" if same else "dual_speaker_models",
            "opportunity": (
                "QUANTIZE_ONCE_IF_TRUE_RUNTIME_INSTANCE_REUSE_IS_PROVEN"
                if same
                else "QUANTIZE_EACH_MODEL_SEPARATELY_AND_MEASURE_SAFETY_REGRESSION"
            ),
            "status": "FUTURE_WORK_NO_CURRENT_GAIN_CLAIMED",
        },
    ]


def _sharing_opportunities(selection: PipelineSelection) -> list[dict[str, object]]:
    same = selection.diarization.get("embedding_backend_id") == selection.identity.get(
        "backend_id"
    )
    return [
        {
            "opportunity": "speaker_model_instance_sharing",
            "status": (
                "POTENTIAL_NOT_IMPLEMENTED_OR_MEASURED"
                if same
                else "NOT_APPLICABLE_DISTINCT_BACKENDS"
            ),
        },
        {
            "opportunity": "speaker_embedding_reuse",
            "status": (
                "POTENTIAL_REQUIRES_WINDOW_TIMESTAMP_AND_NUMERICAL_PARITY"
                if same
                else "NOT_CLAIMED"
            ),
        },
        {
            "opportunity": "feature_extraction_reuse",
            "status": "UNKNOWN_CURRENT_DUPLICATION_NOT_INSTRUMENTED",
        },
    ]


def _arm_risks(
    selection: PipelineSelection, deployment: Mapping[str, object]
) -> list[str]:
    risks = [
        "NO_ARM_NATIVE_RTF_RAM_LATENCY_OR_THERMAL_MEASUREMENT",
        "FULL_PIPELINE_EXPORT_AND_NUMERICAL_PARITY_UNPROVEN",
        "TWO_GIB_INCLUDES_OS_UI_QUEUES_AND_SESSION_STATE_NOT_DESKTOP_RSS_ALONE",
        "DESKTOP_WORKER_ENVIRONMENT_COMPLEXITY_MAY_NOT_MAP_TO_ARM_RUNTIME",
        "SEGMENTATION_AND_SPEAKER_MODEL_QUANTIZATION_SAFETY_REGRESSION_UNKNOWN",
    ]
    if selection.hybrid_label == "H2":
        risks.append("H2_SHARING_IS_POTENTIAL_ONLY_CURRENT_DUPLICATION_UNKNOWN")
    if selection.hybrid_label == "H5":
        risks.append("H5_REQUIRES_TWO_DISTINCT_SPEAKER_EMBEDDING_ARCHITECTURES")
    if selection.diarization_alias == "DW" or selection.identity_alias == "IW":
        risks.append("WESPEAKER_ARM_EXPORT_RUNTIME_AND_MEMORY_UNVALIDATED")
    if deployment["total_pipeline_peak_rss_bytes"]["value"] is None:
        risks.append("DESKTOP_TOTAL_PIPELINE_PEAK_RSS_UNKNOWN")
    return risks


def _tradeoff_audit(
    *,
    matrix: FullPipelineMatrix,
    selected_ids: set[str],
    credible_ids: set[str],
) -> dict[str, object]:
    rows = {
        pipeline_id: matrix.resolve(pipeline_id) for pipeline_id in matrix.pipeline_ids
    }

    def matching(predicate) -> dict[str, object]:
        credible = sorted(
            pipeline_id for pipeline_id in credible_ids if predicate(rows[pipeline_id])
        )
        shortlisted = sorted(set(credible) & selected_ids)
        return {
            "credible_pipeline_ids": credible,
            "shortlisted_pipeline_ids": shortlisted,
            "status": (
                "SHORTLIST_REPRESENTED"
                if shortlisted
                else "NOT_SHORTLISTED_WITHIN_FOUR_CANDIDATE_CAP"
                if credible
                else "UNSUPPORTED_NO_CREDIBLE_PIPELINE"
            ),
        }

    return {
        "H2_same_model": {
            **matching(lambda item: item.hybrid_label == "H2"),
            "sharing_claim": "POTENTIAL_ONLY_NOT_IMPLEMENTED_OR_MEASURED",
        },
        "H5_dual_embedding": {
            **matching(lambda item: item.hybrid_label == "H5"),
            "tradeoff": "MEASURED_SAFETY_VERSUS_TWO_MODEL_ARM_COST_REQUIRES_TARGET_TEST",
        },
        "wespeaker_paths": {
            **matching(
                lambda item: item.diarization_alias == "DW"
                or item.identity_alias == "IW"
            ),
            "tradeoff": "DESKTOP_ACCURACY_RESOURCE_EVIDENCE_DOES_NOT_PREDICT_ARM",
        },
        "asr_original_sherpa_AO": matching(lambda item: item.asr_alias == "AO"),
        "asr_sherpa_giga_AG": matching(lambda item: item.asr_alias == "AG"),
        "both_asrs_preserved_in_all18_desktop_ranking": True,
        "shortlist_asr_aliases": sorted(
            {rows[pipeline_id].asr_alias for pipeline_id in selected_ids}
        ),
        "final_arm_preference_claimed": False,
    }


def _two_gib_evidence(row: Mapping[str, object]) -> dict[str, object]:
    peak = _number(row.get("peak_rss_bytes"))
    if peak is None:
        return {
            "classification": "HIGH_RISK_FOR_2GB",
            "evidence_status": "UNKNOWN_INSUFFICIENT_EVIDENCE",
            "rationale": (
                "Desktop total-pipeline peak RSS is unavailable; risk is conservative, "
                "not a claim that the optimized pipeline cannot fit."
            ),
            "desktop_peak_rss_bytes": None,
            "used_as_scientific_hard_filter": False,
        }
    if peak > 2 * 1024**3:
        return {
            "classification": "HIGH_RISK_FOR_2GB",
            "evidence_status": "MEASURED_UNOPTIMIZED_DESKTOP_EXCEEDS_TARGET_RAM",
            "rationale": (
                "Desktop peak RSS exceeds 2 GiB; optimization may change this and ARM "
                "measurement is still required."
            ),
            "desktop_peak_rss_bytes": peak,
            "used_as_scientific_hard_filter": False,
        }
    return {
        "classification": "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION",
        "evidence_status": "MEASURED_DESKTOP_WITHIN_2GIB_BEFORE_OS_UI_RESERVE",
        "rationale": (
            "Desktop peak RSS is below 2 GiB, but OS, UI, queues, thermal behavior, "
            "and ARM runtime overhead remain unmeasured."
        ),
        "desktop_peak_rss_bytes": peak,
        "used_as_scientific_hard_filter": False,
    }


def _desktop_measurement(
    row: Mapping[str, object], metric: str, unit: str | None
) -> dict[str, object]:
    statuses = row.get("metric_statuses")
    raw_status = statuses.get(metric) if isinstance(statuses, Mapping) else None
    value = _number(row.get(metric))
    return _evidence(
        value,
        unit,
        (
            f"DESKTOP_P5_SERIAL_OR_HELDOUT_{raw_status or 'COMPUTED'}"
            if value is not None
            else f"UNKNOWN_DESKTOP_{raw_status or 'NOT_REPORTED'}"
        ),
        details={"arm_measurement": False},
    )


def _p6_measurement(
    metrics: Mapping[str, object], metric: str, unit: str | None
) -> dict[str, object]:
    raw = metrics.get(metric)
    if not isinstance(raw, Mapping):
        return _unknown(unit, "UNKNOWN_NOT_IN_P6_PREDECLARED_EXTENDED_EVIDENCE")
    value = _number(raw.get("value"))
    if value is None:
        return _unknown(unit, str(raw.get("status") or "UNKNOWN_P6_UNSUPPORTED"))
    return _evidence(
        value,
        unit,
        f"DESKTOP_P6_SERIAL_{raw.get('status') or 'COMPUTED'}",
        details={"source": raw.get("source"), "arm_measurement": False},
    )


def _unknown(unit: str | None, status: str) -> dict[str, object]:
    return _evidence(None, unit, status)


def _evidence(
    value: object,
    unit: str | None,
    status: str,
    *,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "value": value,
        "unit": unit,
        "status": status,
        "details": dict(details or {}),
    }


def _validate_explicit_evidence(value: object, *, label: str) -> None:
    if not isinstance(value, Mapping):
        raise ProductionCandidateError(f"Pi evidence is not explicit: {label}")
    try:
        validate_evidence(value)
    except DeploymentEvidenceError as exc:
        raise ProductionCandidateError(
            f"Pi evidence is not explicit: {label}: {exc}"
        ) from exc


def _number(value: object) -> float | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int_or_none(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


__all__ = ["build_pi_handoff", "validate_pi_handoff"]
