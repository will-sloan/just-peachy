"""Universal Prompt-7 completion envelope and independent validation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import yaml

from app.full_pipeline_evaluation.io import (
    checksum_map,
    read_json,
    sha256_file,
    write_json_atomic,
)

from . import (
    DEFAULT_PROGRAM_STATE,
    PROMPT5_MARKER,
    PROMPT5_REQUIRED_FILES,
    PROMPT6_MARKER,
    PROMPT6_REQUIRED_FILES,
    PROMPT7_MARKER,
    PROMPT_INDEX,
    PI_SHORTLIST_FILE,
    REPORT_CHECKSUMS_FILE,
    REQUIRED_PROMPT7_REPORTS,
    scope_fields,
)
from .controller import Layout, layout
from .io import HardeningError, artifact_ref, ensure_c, storage_guard
from .packaging import validate_candidate_bundle
from .universal import validate_completion as validate_universal_completion


EXTRA_REQUIRED_REPORTS = (
    "technical_ranking.csv",
    "licensing_ranking.csv",
    "pareto_frontier.csv",
    "licensing_provenance.json",
    "failure_inventory.csv",
    "acceptance_summary.csv",
    "evidence_index.json",
    "h2_simplicity_measurement.csv",
    "common_demo_production_catalog.yaml",
)


def finalize(
    *,
    workspace_root: Path,
    predecessor_record_path: Path | str,
    adapter_id: str,
    adapter_contract_sha256: str,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    completion_record_path: Path | str | None = None,
) -> dict[str, object]:
    paths = layout(workspace_root)
    storage_guard(paths.root)
    authorization = _require_core_artifacts(paths)
    predecessor = ensure_c(
        predecessor_record_path,
        label="Prompt-6 predecessor completion",
        must_exist=True,
    )
    expected_p6 = authorization.get("prompt6_completion")
    if not isinstance(expected_p6, Mapping):
        raise HardeningError("authorization Prompt-6 reference is absent")
    if str(predecessor) != str(expected_p6.get("path")):
        raise HardeningError("Prompt-6 predecessor path differs from authorization")
    if sha256_file(predecessor) != expected_p6.get("sha256"):
        raise HardeningError("Prompt-6 predecessor checksum differs from authorization")
    validate_universal_completion(
        predecessor,
        prompt_index=6,
        marker=PROMPT6_MARKER,
        required_basenames=PROMPT6_REQUIRED_FILES,
    )
    _require_sha(adapter_contract_sha256, "adapter contract SHA-256")
    if not adapter_id.strip():
        raise HardeningError("adapter_id is required")
    completion_path = ensure_c(
        completion_record_path or paths.completion,
        label="Prompt-7 completion record",
    )
    if completion_path != paths.completion:
        raise HardeningError(
            "Prompt-7 completion must use the canonical workspace completion_marker.json"
        )
    if completion_path.is_file():
        existing = validate_universal_completion(
            completion_path,
            prompt_index=7,
            marker=PROMPT7_MARKER,
            required_basenames=(*REQUIRED_PROMPT7_REPORTS, *EXTRA_REQUIRED_REPORTS),
        )
        existing_predecessor = existing.record.get("predecessor")
        if (
            existing.record.get("adapter_id") != adapter_id
            or existing.record.get("adapter_contract_sha256")
            != adapter_contract_sha256.casefold()
            or not isinstance(existing_predecessor, Mapping)
            or existing_predecessor.get("completion_record_path") != str(predecessor)
            or existing_predecessor.get("completion_record_sha256")
            != sha256_file(predecessor)
        ):
            raise HardeningError("existing immutable Prompt-7 completion differs")
        _update_state(
            ensure_c(program_state_path, label="program state", must_exist=True),
            completion_path=completion_path,
        )
        return dict(existing.record)

    gates_root = paths.root / "gate_records"
    gates_root.mkdir(parents=True, exist_ok=True)
    selection = read_json(paths.selection)
    evidence = read_json(paths.evidence_index)
    packaging = read_json(paths.packaging)
    shortlist = _validate_pi_shortlist(paths, authorization, selection)
    hash_gate = _write_gate(
        gates_root / "hash_validation.json",
        gate="hash_validation",
        evidence={
            "authorization_sha256": sha256_file(paths.authorization),
            "selection_sha256": sha256_file(paths.selection),
            "acceptance_plan_sha256": sha256_file(paths.plan),
            "evidence_index_sha256": sha256_file(paths.evidence_index),
            "candidate_bundles": _validate_bundles(packaging),
            "compact_zip_sha256": packaging.get("compact_zip_sha256"),
            "raspberry_pi_candidate_shortlist_path": str(
                (paths.report / PI_SHORTLIST_FILE).resolve()
            ),
            "raspberry_pi_candidate_shortlist_sha256": sha256_file(
                paths.report / PI_SHORTLIST_FILE
            ),
        },
    )
    firewall_gate = _write_gate(
        gates_root / "firewall_validation.json",
        gate="firewall_validation",
        evidence={
            "frozen_thresholds_changed": False,
            "production_threshold_retuning_performed": selection.get(
                "production_threshold_retuning_performed"
            ),
            "weighted_score_used": selection.get("weighted_score_used"),
            "technical_and_licensing_rankings_separate": selection.get(
                "technical_and_licensing_rankings_separate"
            ),
            "xvf_hooks_enabled": False,
            "fine_tuning_hooks_enabled": False,
            "final_beaker_hardware_readiness_claimed": False,
            "selected_roles_frozen_anchor_bound": True,
            "unknown_only_policy_executed": False,
            "elapsed_time_kill_switch_enabled": False,
        },
    )
    prerequisite_gate = _write_gate(
        gates_root / "prerequisite_validation.json",
        gate="prerequisite_validation",
        evidence={
            "prompt5_completion": authorization.get("prompt5_completion"),
            "prompt6_completion": authorization.get("prompt6_completion"),
            "predecessor_record_path": str(predecessor),
            "predecessor_record_sha256": sha256_file(predecessor),
            "predecessor_completion_marker": PROMPT6_MARKER,
            "authorization_path": str(paths.authorization),
            "authorization_sha256": sha256_file(paths.authorization),
        },
    )
    gate_records = {
        "hash_validation": artifact_ref(hash_gate),
        "firewall_validation": artifact_ref(firewall_gate),
        "prerequisite_validation": artifact_ref(prerequisite_gate),
    }
    artifact_paths = _artifact_paths(paths, packaging, tuple(gate_records.values()))
    artifact_manifest = {
        "schema_version": "full-pipeline-eight-day-artifact-manifest.v1",
        **scope_fields(),
        "prompt_index": PROMPT_INDEX,
        "artifacts": [
            {**artifact_ref(path), "required": True} for path in artifact_paths
        ],
    }
    manifest_path = paths.root / "artifact_manifest.json"
    write_json_atomic(manifest_path, artifact_manifest)
    roles = selection.get("roles")
    if not isinstance(roles, Mapping):
        raise HardeningError("selection roles are absent")
    completion = {
        "schema_version": "full-pipeline-eight-day-stage-completion.v1",
        **scope_fields(),
        "prompt_index": PROMPT_INDEX,
        "status": "COMPLETE",
        "completion_marker": PROMPT7_MARKER,
        "completed_at_utc": _utc(),
        "adapter_id": adapter_id,
        "adapter_contract_sha256": adapter_contract_sha256.casefold(),
        "predecessor": {
            "prompt_index": 6,
            "completion_marker": PROMPT6_MARKER,
            "completion_record_path": str(predecessor),
            "completion_record_sha256": sha256_file(predecessor),
        },
        "artifact_manifest": artifact_ref(manifest_path),
        "gate_records": gate_records,
        "native_completion": {
            "selected_roles": dict(roles),
            "selected_pipeline_count": selection.get("selected_pipeline_count"),
            "acceptance_task_count": read_json(paths.plan).get("task_count"),
            "software_ready_candidate_count": sum(
                bool(row.get("software_ready"))
                for row in evidence.get("candidates", [])
                if isinstance(row, Mapping)
            ),
            "compact_zip_path": packaging.get("compact_zip_path"),
            "compact_zip_sha256": packaging.get("compact_zip_sha256"),
            "restart_policy": "RERUN_IDEMPOTENT",
            "raspberry_pi_candidate_count": shortlist.get("candidate_count"),
            "raspberry_pi_candidate_shortlist": {
                "path": str((paths.report / PI_SHORTLIST_FILE).resolve()),
                "sha256": sha256_file(paths.report / PI_SHORTLIST_FILE),
            },
            "final_raspberry_pi_winner_claimed": False,
        },
    }
    write_json_atomic(completion_path, completion)
    _update_state(
        ensure_c(program_state_path, label="program state", must_exist=True),
        completion_path=completion_path,
    )
    return completion


def validate_completion(
    *,
    workspace_root: Path,
    completion_record_path: Path | str,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    expected_adapter_id: str | None = None,
    expected_adapter_contract_sha256: str | None = None,
) -> dict[str, object]:
    paths = layout(workspace_root)
    completion_path = ensure_c(
        completion_record_path,
        label="Prompt-7 completion record",
        must_exist=True,
    )
    if completion_path != paths.completion:
        raise HardeningError("Prompt-7 completion is not at its canonical path")
    evidence = validate_universal_completion(
        completion_path,
        prompt_index=7,
        marker=PROMPT7_MARKER,
        required_basenames=(*REQUIRED_PROMPT7_REPORTS, *EXTRA_REQUIRED_REPORTS),
    )
    record = evidence.record
    if expected_adapter_id and record.get("adapter_id") != expected_adapter_id:
        raise HardeningError("completion adapter_id differs")
    if (
        expected_adapter_contract_sha256
        and record.get("adapter_contract_sha256")
        != expected_adapter_contract_sha256.casefold()
    ):
        raise HardeningError("completion adapter contract hash differs")
    authorization = _require_core_artifacts(paths)
    _revalidate_upstream(authorization, record)
    _revalidate_inputs(authorization)
    plan = read_json(paths.plan)
    selection = read_json(paths.selection)
    shortlist = _validate_pi_shortlist(paths, authorization, selection)
    selected_count = int(selection.get("selected_pipeline_count") or 0)
    if not 1 <= selected_count <= 3:
        raise HardeningError("selection did not retain one to three candidates")
    if int(plan.get("task_count") or -1) != selected_count * 17:
        raise HardeningError("acceptance plan is not exact 17 tasks per candidate")
    selected_ids = {
        str(pipeline)
        for pipeline in dict(selection.get("roles") or {}).values()
        if pipeline is not None
    }
    candidate_rows = selection.get("candidates")
    if not isinstance(candidate_rows, list):
        raise HardeningError("selection candidate attestations are absent")
    selected_rows = [
        row
        for row in candidate_rows
        if isinstance(row, Mapping) and str(row.get("pipeline_id")) in selected_ids
    ]
    if len(selected_rows) != selected_count or any(
        row.get("production_role_eligible") is not True
        or row.get("runtime_binding_status") != "BOUND_FROZEN_ANCHOR"
        or row.get("unknown_only_policy_executed") is not False
        for row in selected_rows
    ):
        raise HardeningError("selected role includes an unresolved runtime policy")
    index = read_json(paths.evidence_index)
    candidates = index.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != selected_count:
        raise HardeningError("acceptance candidate inventory differs")
    if any(
        not isinstance(row, Mapping) or row.get("software_ready") is not True
        for row in candidates
    ):
        raise HardeningError("one or more selected candidates is not software-ready")
    packaging = read_json(paths.packaging)
    bundles = _validate_bundles(packaging)
    catalog = yaml.safe_load(
        (paths.report / "production_candidate_catalog.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(catalog, Mapping) or catalog.get("status") != "PASS":
        raise HardeningError("candidate catalog is invalid")
    catalog_candidates = catalog.get("candidates")
    if (
        not isinstance(catalog_candidates, list)
        or len(catalog_candidates) != selected_count
    ):
        raise HardeningError("candidate catalog count differs")
    if any(
        not isinstance(row, Mapping) or row.get("software_ready") is not True
        for row in catalog_candidates
    ):
        raise HardeningError("candidate catalog includes a non-ready selection")
    state = read_json(
        ensure_c(program_state_path, label="program state", must_exist=True)
    )
    if (
        state.get("status") != PROMPT7_MARKER
        or int(state.get("current_prompt_index") or -1) != 7
    ):
        raise HardeningError("PROGRAM_STATE has not reached bounded Prompt 7")
    if state.get("prompt_7_completion_record_sha256") != sha256_file(completion_path):
        raise HardeningError("PROGRAM_STATE Prompt-7 completion binding differs")
    _validate_completed_state(state, completion_path=completion_path)
    return {
        "schema_version": "full-pipeline-production-hardening-completion-validation.v1",
        **scope_fields(),
        "status": "PASS",
        "prompt_index": 7,
        "completion_marker": PROMPT7_MARKER,
        "completion_record_path": str(completion_path),
        "completion_record_sha256": sha256_file(completion_path),
        "selected_pipeline_count": selected_count,
        "acceptance_task_count": int(plan["task_count"]),
        "validated_candidate_bundles": bundles,
        "raspberry_pi_candidate_count": shortlist.get("candidate_count"),
        "raspberry_pi_candidate_shortlist_sha256": sha256_file(
            paths.report / PI_SHORTLIST_FILE
        ),
    }


def _require_core_artifacts(paths: Layout) -> dict[str, object]:
    required = (
        paths.authorization,
        paths.selection,
        paths.plan,
        paths.root / "run_budget.json",
        paths.execution,
        paths.evidence_index,
        paths.packaging,
    )
    for path in required:
        if not path.is_file():
            raise HardeningError(f"Prompt-7 required artifact is missing: {path}")
    authorization = read_json(paths.authorization)
    selection = read_json(paths.selection)
    if selection.get("authorization_sha256") != sha256_file(paths.authorization):
        raise HardeningError("selection authorization binding differs")
    plan = read_json(paths.plan)
    if plan.get("selection_sha256") != sha256_file(paths.selection):
        raise HardeningError("acceptance plan selection binding differs")
    if plan.get("threshold_changes_allowed") is not False:
        raise HardeningError("acceptance plan permits threshold changes")
    roles = selection.get("roles")
    candidates = selection.get("candidates")
    if not isinstance(roles, Mapping) or not isinstance(candidates, list):
        raise HardeningError("selection roles/candidate attestations are absent")
    selected = {str(value) for value in roles.values() if value is not None}
    selected_rows = [
        row
        for row in candidates
        if isinstance(row, Mapping) and str(row.get("pipeline_id")) in selected
    ]
    if len(selected_rows) != len(selected) or any(
        row.get("production_role_eligible") is not True
        or row.get("runtime_binding_status") != "BOUND_FROZEN_ANCHOR"
        or row.get("unknown_only_policy_executed") is not False
        for row in selected_rows
    ):
        raise HardeningError("selection includes an unresolved production role")
    budget = read_json(paths.root / "run_budget.json")
    _validate_advisory_run_budget(budget)
    execution = read_json(paths.execution)
    if execution.get("status") != "PASS":
        raise HardeningError("acceptance execution did not pass")
    evidence = read_json(paths.evidence_index)
    if evidence.get("status") != "PASS":
        raise HardeningError("acceptance validation did not pass")
    for name in (*REQUIRED_PROMPT7_REPORTS, *EXTRA_REQUIRED_REPORTS):
        if not (paths.report / name).is_file():
            raise HardeningError(f"Prompt-7 report is missing: {name}")
    _validate_pi_shortlist(paths, authorization, selection)
    _validate_report_checksums(paths)
    return authorization


def _validate_pi_shortlist(
    paths: Layout,
    authorization: Mapping[str, object],
    selection: Mapping[str, object],
) -> dict[str, object]:
    shortlist_path = paths.report / PI_SHORTLIST_FILE
    if not shortlist_path.is_file():
        raise HardeningError("Prompt-7 Raspberry Pi shortlist is missing")
    from .controller import _evidence_files
    from .pi_shortlist import validate_pi_shortlist

    return validate_pi_shortlist(
        read_json(shortlist_path),
        authorization=authorization,
        desktop_selection=selection,
        evidence_files=_evidence_files(authorization),
        desktop_roles_source=paths.report / "production_candidate_catalog.yaml",
    )


def _validate_report_checksums(paths: Layout) -> None:
    checksum_path = paths.report / REPORT_CHECKSUMS_FILE
    value = read_json(checksum_path)
    expected = checksum_map(paths.report, exclude=(REPORT_CHECKSUMS_FILE,))
    if (
        value.get("schema_version") != "full-pipeline-production-report-checksums.v1"
        or value.get("status") != "PASS"
        or value.get("entries") != expected
        or value.get("raspberry_pi_candidate_shortlist")
        != {
            "path": str((paths.report / PI_SHORTLIST_FILE).resolve()),
            "sha256": sha256_file(paths.report / PI_SHORTLIST_FILE),
        }
    ):
        raise HardeningError("Prompt-7 report checksum inventory differs")


def _validate_advisory_run_budget(budget: Mapping[str, object]) -> None:
    """Validate planning metadata without turning it into an elapsed deadline."""

    if (
        budget.get("schema_version")
        != "full-pipeline-production-hardening-run-budget.v1"
        or int(budget.get("nominal_planning_seconds") or 0) != 12 * 3600
        or float(budget.get("nominal_planning_hours") or 0) != 12.0
        or budget.get("elapsed_time_kill_switch_enabled") is not False
        or budget.get("completion_policy") != "run_to_terminal_or_operator_stop"
        or budget.get("scope_id") != scope_fields()["scope_id"]
        or budget.get("scope_class") != scope_fields()["scope_class"]
        or budget.get("original_full_scope_complete") is not False
    ):
        raise HardeningError("Prompt-7 advisory planning-budget evidence differs")
    if "deadline_at_utc" in budget or "budget_seconds" in budget:
        raise HardeningError("Prompt-7 planning metadata contains a kill deadline")
    datetime.fromisoformat(
        str(budget.get("started_at_utc") or "").replace("Z", "+00:00")
    )


def _write_gate(path: Path, *, gate: str, evidence: Mapping[str, object]) -> Path:
    value = {
        "schema_version": "full-pipeline-eight-day-gate.v1",
        **scope_fields(),
        "prompt_index": 7,
        "gate": gate,
        "status": "PASS",
        "evidence": dict(evidence),
    }
    write_json_atomic(path, value)
    return path.resolve()


def _artifact_paths(
    paths: Layout,
    packaging: Mapping[str, object],
    gate_refs: tuple[Mapping[str, str], ...],
) -> list[Path]:
    result = [
        paths.authorization,
        paths.selection,
        paths.plan,
        paths.root / "run_budget.json",
        paths.execution,
        paths.packaging,
        *(paths.report / name for name in REQUIRED_PROMPT7_REPORTS),
        *(paths.report / name for name in EXTRA_REQUIRED_REPORTS),
    ]
    zip_path = ensure_c(
        str(packaging.get("compact_zip_path") or ""),
        label="Prompt-7 compact ZIP",
        must_exist=True,
    )
    if packaging.get("compact_zip_sha256") != sha256_file(zip_path):
        raise HardeningError("Prompt-7 compact ZIP checksum differs")
    result.append(zip_path)
    raw_bundles = packaging.get("candidate_bundles")
    if not isinstance(raw_bundles, list):
        raise HardeningError("candidate bundle inventory is absent")
    for raw in raw_bundles:
        if not isinstance(raw, Mapping):
            raise HardeningError("candidate bundle inventory row is invalid")
        result.append(
            ensure_c(str(raw["path"]), label="candidate bundle") / "checksums.json"
        )
    result.extend(ensure_c(ref["path"], label="gate record") for ref in gate_refs)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in result:
        resolved = ensure_c(path, label="Prompt-7 artifact", must_exist=True)
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _validate_bundles(packaging: Mapping[str, object]) -> list[dict[str, object]]:
    raw = packaging.get("candidate_bundles")
    if not isinstance(raw, list) or not raw:
        raise HardeningError("candidate bundle inventory is empty")
    output: list[dict[str, object]] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise HardeningError("candidate bundle row is invalid")
        value = validate_candidate_bundle(
            Path(str(row.get("path") or "")),
            pipeline_id=str(row.get("pipeline_id") or ""),
        )
        if row.get("checksums_sha256") != value["checksums_sha256"]:
            raise HardeningError("candidate bundle checksum reference differs")
        output.append(value)
    from .packaging import validate_compact_package

    package = ensure_c(
        str(packaging.get("compact_zip_path") or ""),
        label="Prompt-7 compact ZIP",
        must_exist=True,
    )
    if packaging.get("compact_zip_sha256") != sha256_file(package):
        raise HardeningError("Prompt-7 compact ZIP binding differs")
    validate_compact_package(package.parents[1], package)
    return output


def _revalidate_upstream(
    authorization: Mapping[str, object], completion: Mapping[str, object]
) -> None:
    p5_ref = authorization.get("prompt5_completion")
    p6_ref = authorization.get("prompt6_completion")
    if not isinstance(p5_ref, Mapping) or not isinstance(p6_ref, Mapping):
        raise HardeningError("authorization upstream completion references are absent")
    p5 = validate_universal_completion(
        str(p5_ref["path"]),
        prompt_index=5,
        marker=PROMPT5_MARKER,
        required_basenames=PROMPT5_REQUIRED_FILES,
    )
    p6 = validate_universal_completion(
        str(p6_ref["path"]),
        prompt_index=6,
        marker=PROMPT6_MARKER,
        required_basenames=PROMPT6_REQUIRED_FILES,
    )
    if p5.sha256 != p5_ref.get("sha256") or p6.sha256 != p6_ref.get("sha256"):
        raise HardeningError("upstream completion bytes changed")
    predecessor = completion.get("predecessor")
    expected = {
        "prompt_index": 6,
        "completion_marker": PROMPT6_MARKER,
        "completion_record_path": str(p6.path),
        "completion_record_sha256": p6.sha256,
    }
    if not isinstance(predecessor, Mapping) or any(
        predecessor.get(key) != value for key, value in expected.items()
    ):
        raise HardeningError("Prompt-7 predecessor binding differs")


def _revalidate_inputs(authorization: Mapping[str, object]) -> None:
    hardening = authorization.get("hardening_inputs")
    if not isinstance(hardening, Mapping):
        raise HardeningError("hardening input authorization is absent")
    for row in hardening.get("inputs", []):
        if not isinstance(row, Mapping):
            raise HardeningError("hardening input authorization row is invalid")
        path = ensure_c(
            str(row.get("path") or ""),
            label="hardening input",
            must_exist=True,
        )
        if row.get("sha256") != sha256_file(path):
            raise HardeningError(f"hardening input bytes changed: {path}")
        from .gate import _wav_metadata

        observed = _wav_metadata(path)
        if (
            row.get("audio_format") != observed
            or abs(
                float(row.get("duration_sec") or 0.0) - float(observed["duration_sec"])
            )
            > 0.01
        ):
            raise HardeningError(f"hardening input WAV metadata changed: {path}")


def _update_state(path: Path, *, completion_path: Path) -> None:
    value = read_json(path)
    if value.get("status") == PROMPT7_MARKER:
        _validate_completed_state(value, completion_path=completion_path)
        return
    if (
        value.get("status") != PROMPT6_MARKER
        or int(value.get("current_prompt_index") or -1) != 6
    ):
        raise HardeningError("PROGRAM_STATE moved away from completed Prompt 6")
    state = dict(value)
    completion_state = dict(state.get("completion_state") or {})
    completion_state.update(
        {
            "prompt_7": PROMPT7_MARKER,
            "prompt_7_scope_id": scope_fields()["scope_id"],
            "prompt_7_original_full_scope_complete": False,
        }
    )
    state.update(
        {
            "status": PROMPT7_MARKER,
            "current_prompt_index": 7,
            "remaining_prompt_indices": [8],
            "remaining_prompt_status": "PENDING_AUTOMATIC",
            "completion_state": completion_state,
            "prompt_7_completion_record": str(completion_path),
            "prompt_7_completion_record_sha256": sha256_file(completion_path),
            **scope_fields(),
        }
    )
    write_json_atomic(path, state)
    _validate_completed_state(read_json(path), completion_path=completion_path)


def _validate_completed_state(
    value: Mapping[str, object], *, completion_path: Path
) -> None:
    if (
        value.get("status") != PROMPT7_MARKER
        or int(value.get("current_prompt_index") or -1) != 7
        or value.get("remaining_prompt_indices") != [8]
        or value.get("remaining_prompt_status") != "PENDING_AUTOMATIC"
        or value.get("scope_id") != scope_fields()["scope_id"]
        or value.get("scope_class") != scope_fields()["scope_class"]
        or value.get("original_full_scope_complete") is not False
        or value.get("prompt_7_completion_record") != str(completion_path)
        or value.get("prompt_7_completion_record_sha256")
        != sha256_file(completion_path)
    ):
        raise HardeningError("completed Prompt-7 PROGRAM_STATE contract differs")
    completion = value.get("completion_state")
    if not isinstance(completion, Mapping):
        raise HardeningError("completed Prompt-7 completion_state is absent")
    expected_markers = {
        "prompt_5": PROMPT5_MARKER,
        "prompt_6": PROMPT6_MARKER,
        "prompt_7": PROMPT7_MARKER,
        "prompt_5_scope_id": scope_fields()["scope_id"],
        "prompt_6_scope_id": scope_fields()["scope_id"],
        "prompt_7_scope_id": scope_fields()["scope_id"],
        "prompt_5_original_full_scope_complete": False,
        "prompt_6_original_full_scope_complete": False,
        "prompt_7_original_full_scope_complete": False,
    }
    for key, item in expected_markers.items():
        if completion.get(key) != item:
            raise HardeningError(f"completed Prompt-7 completion_state {key} differs")


def _require_sha(value: str, label: str) -> None:
    text = str(value).casefold()
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise HardeningError(f"{label} must be a SHA-256 digest")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["EXTRA_REQUIRED_REPORTS", "finalize", "validate_completion"]
