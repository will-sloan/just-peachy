"""Metadata-only development/evaluation panel *selection* for the H2 program.

The prepared case-manifest rows also contain scoring references, so the parser
necessarily reads those JSON rows.  This module never accesses reference
fields, predictions, metrics, embeddings, or transcripts when selecting
membership.  The exact membership and full row hashes are then sealed, and the
controller forbids held-out execution until a development policy is frozen.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from pathlib import Path
from typing import Mapping, Sequence

from .contracts import H2ProgramError
from .io import canonical_sha256, sha256_file


OVERLAYS = ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN")

# This identifier is bound into every development selector and the protocol
# specification.  It makes the safety order machine-checkable instead of
# leaving it only in prose: naming the wrong enrolled person is minimized
# before the separate stranger-to-known exposure family.
SAFETY_PRIORITY_CONTRACT_ID = "wrong_known_before_stranger_false_known.v1"
SAFETY_PRIORITY_ORDERED_RISK_FAMILIES = (
    "wrong_known",
    "stranger_false_known",
)


def build_panel_manifest(
    development: Sequence[Mapping[str, object]],
    evaluation: Sequence[Mapping[str, object]],
    *,
    tool_root: Path,
    seed: int = 3800,
) -> dict[str, object]:
    dev_core = _core_panel(development, split="development", seed=seed)
    dev_all = _all_development_panel(development)
    eval_core = _core_panel(evaluation, split="evaluation", seed=seed)
    dev_long = _long_session_panel(
        development, split="development", expected_source_count=4
    )
    eval_long = _long_session_panel(
        evaluation, split="evaluation", expected_source_count=8
    )
    eval_reduced = _nested_panel(eval_core, 60, seed=seed, label="evaluation-reduced")
    dev_medium = _nested_development_panel(
        dev_core,
        72,
        seed=seed,
        label="development-medium",
    )
    dev_small = _nested_development_panel(
        dev_medium,
        36,
        seed=seed,
        label="development-small",
    )
    integration_partition = _integration_partition(dev_all, seed=seed)
    integration_case_ids = {
        *map(str, integration_partition["calibration_case_ids"]),
        *map(str, integration_partition["selection_case_ids"]),
    }
    dev_integration = tuple(
        row for row in dev_all if _case_id(row) in integration_case_ids
    )
    if len(dev_integration) != len(integration_case_ids):
        raise H2ProgramError("integration-eligible development panel lost cases")
    diagnostics = {
        "commonvoice_60plus_asr": _diagnostic_panel(
            evaluation,
            scoring_stratum="commonvoice_60plus_asr",
            count=60,
            seed=seed,
        ),
        "chime6_diarization_only": _diagnostic_panel(
            evaluation,
            scoring_stratum="chime6_diarization_only",
            count=24,
            seed=seed,
        ),
        "voices_asr": _diagnostic_panel(
            evaluation,
            scoring_stratum="voices_asr",
            count=24,
            seed=seed,
        ),
    }
    short_turn_qualification = {
        "small": _audit_short_turn_reference_coverage(dev_small, tool_root=tool_root),
        "medium": _audit_short_turn_reference_coverage(dev_medium, tool_root=tool_root),
        "core": _audit_short_turn_reference_coverage(dev_core, tool_root=tool_root),
    }
    for panel_name in ("small", "medium"):
        panel_audit = short_turn_qualification[panel_name]
        if not bool(panel_audit["all_required_bins_have_evidence"]):
            raise H2ProgramError(
                f"development {panel_name} panel lacks evidence in one or more "
                "required short-turn duration bins"
            )
    core = {
        "schema_version": "h2-product-panel-selection.v1",
        "seed": seed,
        "selection_inputs": [
            "case_identity",
            "source_key",
            "scenario_id",
            "scenario profile/cadence metadata",
            "overlay_id",
            "gallery_metadata",
            "audio_hash",
            "duration",
            "pseudonymous_global_speaker_ids_for_development_firewall_only",
        ],
        "prediction_inputs_used": False,
        "metric_inputs_used": False,
        "reference_speaker_identity_metadata_used_for_development_firewall": True,
        "reference_transcript_or_audio_content_used_for_selection": False,
        "development_reference_turn_durations_used_for_post_selection_qualification": True,
        "source_manifest_rows_may_contain_reference_fields": True,
        "evaluation_predictions_or_metrics_inspected": False,
        "development": {
            "small": _panel_summary(dev_small),
            "medium": _panel_summary(dev_medium),
            "core": _panel_summary(dev_core),
            "all": _panel_summary(dev_all),
            "integration_eligible": _panel_summary(dev_integration),
            "long_session": _long_session_summary(dev_long, split="development"),
            "integration_partition": integration_partition,
            "successive_halving_panel_strategy": {
                "selection_basis": "development scenario metadata only",
                "membership_selection_reference_turn_durations_inspected": False,
                "post_selection_development_reference_duration_qualification_performed": True,
                "evaluation_reference_content_inspected": False,
                "small_source_scenario_audio_counts": _scenario_audio_counts(dev_small),
                "medium_source_scenario_audio_counts": _scenario_audio_counts(
                    dev_medium
                ),
                "required_runtime_short_turn_metrics": [
                    "short_turn_der_lt_0_5_sec",
                    "short_turn_der_0_5_to_1_0_sec",
                    "short_turn_der_1_0_to_2_0_sec",
                ],
                "promotion_fails_closed_when_a_required_short_turn_metric_is_unavailable": True,
                "development_reference_turn_duration_qualification": short_turn_qualification,
            },
        },
        "evaluation": {
            "core": _panel_summary(eval_core),
            "reduced_paired": _panel_summary(eval_reduced),
            "long_session": _long_session_summary(eval_long, split="evaluation"),
            "diagnostics": {
                key: _panel_summary(value) for key, value in diagnostics.items()
            },
            "execution_gate": "FROZEN_DEVELOPMENT_POLICY_REQUIRED",
        },
        "nesting": {
            "development_small_subset_of_medium": _ids(dev_small) <= _ids(dev_medium),
            "development_medium_subset_of_core": _ids(dev_medium) <= _ids(dev_core),
            "development_core_subset_of_all": _ids(dev_core) <= _ids(dev_all),
        },
    }
    if not all(core["nesting"].values()):  # type: ignore[union-attr]
        raise H2ProgramError("development panels are not nested")
    return {**core, "selection_identity_sha256": canonical_sha256(core)}


def _all_development_panel(
    rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    selected = tuple(
        sorted(
            (
                dict(row)
                for row in rows
                if str(row.get("partition") or "") == "development"
                and str(row.get("source_key") or "") in {"controlled_v1", "product_v2"}
                and str(row.get("scoring_stratum") or "") == "controlled_end_to_end"
            ),
            key=_case_id,
        )
    )
    if len(selected) != 807:
        raise H2ProgramError(
            f"all-development H2 integration panel must contain 807 cases, got {len(selected)}"
        )
    return selected


def _long_session_panel(
    rows: Sequence[Mapping[str, object]],
    *,
    split: str,
    expected_source_count: int,
) -> tuple[dict[str, object], ...]:
    """Preseal every full-gallery truth overlay for each long source."""

    eligible = [
        dict(row)
        for row in rows
        if str(row.get("partition") or "") == split
        and str(row.get("source_key") or "") == "product_v2"
        and isinstance(row.get("scenario"), Mapping)
        and row["scenario"].get("long_session") is True  # type: ignore[index]
    ]
    groups = _audio_groups(eligible)
    if len(groups) != expected_source_count:
        raise H2ProgramError(
            f"{split} long-session source count differs: "
            f"expected={expected_source_count} observed={len(groups)}"
        )
    selected: list[dict[str, object]] = []
    for audio_id, group in sorted(groups.items()):
        for overlay in OVERLAYS:
            candidates = [
                row
                for row in group
                if str(row.get("overlay_id") or "") == overlay
                and str(row.get("gallery_requested_size") or "").casefold() == "full"
            ]
            if len(candidates) != 1:
                raise H2ProgramError(
                    f"{split} long-session source {audio_id} must have exactly "
                    f"one full-gallery {overlay} row"
                )
            selected.append(dict(candidates[0]))
    return tuple(sorted(selected, key=_case_id))


def _long_session_summary(
    rows: Sequence[Mapping[str, object]], *, split: str
) -> dict[str, object]:
    summary = _panel_summary(rows)
    audio_ids = sorted({_audio_id(row) for row in rows})
    source_ids = sorted({str(row.get("source_case_id") or "") for row in rows})
    core = {
        **summary,
        "split": split,
        "source_count": len(audio_ids),
        "overlay_policy": "all_three_truth_overlays_full_gallery_per_source",
        "required_overlays": list(OVERLAYS),
        "metadata_only_selection": True,
        "prediction_or_metric_inputs_used": False,
        "reference_content_used": False,
        "source_audio_identities": audio_ids,
        "source_recording_ids": source_ids,
        "source_membership_sha256": canonical_sha256(
            {
                "split": split,
                "source_audio_identities": audio_ids,
                "source_recording_ids": source_ids,
                "case_ids": summary["case_ids"],
            }
        ),
    }
    return core


def _integration_partition(
    rows: Sequence[Mapping[str, object]], *, seed: int
) -> dict[str, object]:
    """Build a source- and speaker-disjoint development firewall.

    The prepared mixtures form one connected speaker graph, so retaining every
    recording would necessarily place the same probe speakers in calibration
    and selection.  We therefore run a bounded deterministic metadata-only
    search over whole-audio assignments and explicitly exclude recordings that
    bridge the two speaker cohorts.  No prediction, metric, transcript, or
    acoustic value is read.  Pseudonymous reference speaker IDs are used only
    to enforce the grouping firewall.
    """

    audio_groups = _audio_groups(rows)
    source_metadata: dict[str, dict[str, object]] = {}
    for audio_id, group in sorted(audio_groups.items()):
        speaker_sets = {tuple(sorted(_reference_speaker_ids(row))) for row in group}
        source_keys = {str(row.get("source_key") or "") for row in group}
        if len(speaker_sets) != 1 or not next(iter(speaker_sets)):
            raise H2ProgramError(
                f"integration source {audio_id} lacks one stable speaker set"
            )
        if len(source_keys) != 1 or not next(iter(source_keys)):
            raise H2ProgramError(
                f"integration source {audio_id} lacks one stable source key"
            )
        source_metadata[audio_id] = {
            "speaker_ids": next(iter(speaker_sets)),
            "source_key": next(iter(source_keys)),
            "case_count": len(group),
        }

    trial_count = 256
    candidates = [
        _speaker_disjoint_trial(
            source_metadata,
            seed=seed,
            trial_index=trial_index,
        )
        for trial_index in range(trial_count)
    ]
    chosen = min(candidates, key=_speaker_partition_objective)
    calibration_audio = set(chosen["calibration_audio_ids"])
    selection_audio = set(chosen["selection_audio_ids"])
    excluded_audio = set(chosen["excluded_audio_ids"])
    calibration_speakers = set(chosen["calibration_speaker_ids"])
    selection_speakers = set(chosen["selection_speaker_ids"])
    if calibration_audio & selection_audio:
        raise H2ProgramError("integration source audio leaked across development roles")
    if calibration_speakers & selection_speakers:
        raise H2ProgramError(
            "integration probe speaker leaked across development roles"
        )
    if calibration_audio | selection_audio | excluded_audio != set(audio_groups):
        raise H2ProgramError("integration source partition is not exhaustive")

    case_roles = {}
    for row in rows:
        audio_id = _audio_id(row)
        if audio_id in calibration_audio:
            role = "calibration"
        elif audio_id in selection_audio:
            role = "selection"
        else:
            role = "excluded_cross_cohort"
        case_roles[_case_id(row)] = role
    calibration_cases = sorted(
        case_id for case_id, role in case_roles.items() if role == "calibration"
    )
    selection_cases = sorted(
        case_id for case_id, role in case_roles.items() if role == "selection"
    )
    excluded_cases = sorted(
        case_id
        for case_id, role in case_roles.items()
        if role == "excluded_cross_cohort"
    )
    strata: dict[str, dict[str, int]] = {}
    for source_key in sorted(
        {str(value["source_key"]) for value in source_metadata.values()}
    ):
        source_ids = {
            audio_id
            for audio_id, value in source_metadata.items()
            if value["source_key"] == source_key
        }
        strata[source_key] = {
            "original_source_count": len(source_ids),
            "calibration_source_count": len(source_ids & calibration_audio),
            "selection_source_count": len(source_ids & selection_audio),
            "excluded_cross_cohort_source_count": len(source_ids & excluded_audio),
        }
    all_speakers = {
        speaker_id
        for value in source_metadata.values()
        for speaker_id in value["speaker_ids"]  # type: ignore[union-attr]
    }
    unassigned_speakers = sorted(
        all_speakers - calibration_speakers - selection_speakers
    )
    core = {
        "schema_version": "h2-development-integration-partition.v2",
        "seed": seed,
        "grouping_unit": "whole_source_audio_and_pseudonymous_probe_speaker",
        "assignment": "bounded_deterministic_speaker_disjoint_greedy_search",
        "trial_count": trial_count,
        "selected_trial_index": chosen["trial_index"],
        "outcomes_used": False,
        "prediction_or_metric_inputs_used": False,
        "reference_speaker_identity_metadata_used": True,
        "reference_transcript_or_audio_content_used": False,
        "evaluation_material_used": False,
        "speaker_disjoint_scope": "probe_audio_speakers",
        "fixed_enrollment_gallery_shared_between_roles": True,
        "fixed_gallery_reason": (
            "open-set calibration and selection must compare against the same "
            "predeclared enrolled decision population; gallery profiles are not "
            "probe recordings"
        ),
        "original_source_count": len(audio_groups),
        "independent_source_count": len(calibration_audio | selection_audio),
        "calibration_source_count": len(calibration_audio),
        "selection_source_count": len(selection_audio),
        "excluded_cross_cohort_source_count": len(excluded_audio),
        "calibration_case_count": len(calibration_cases),
        "selection_case_count": len(selection_cases),
        "excluded_cross_cohort_case_count": len(excluded_cases),
        "calibration_case_ids": calibration_cases,
        "selection_case_ids": selection_cases,
        "excluded_cross_cohort_case_ids": excluded_cases,
        "calibration_speaker_count": len(calibration_speakers),
        "selection_speaker_count": len(selection_speakers),
        "unassigned_speaker_count": len(unassigned_speakers),
        "calibration_speaker_ids": sorted(calibration_speakers),
        "selection_speaker_ids": sorted(selection_speakers),
        "unassigned_speaker_ids": unassigned_speakers,
        "speaker_overlap_count": len(calibration_speakers & selection_speakers),
        "source_overlap_count": len(calibration_audio & selection_audio),
        "excluded_cases_used_for_calibration_or_selection": False,
        "strata": strata,
        "case_roles_sha256": canonical_sha256(case_roles),
        "speaker_roles_sha256": canonical_sha256(
            {
                "calibration": sorted(calibration_speakers),
                "selection": sorted(selection_speakers),
                "unassigned": unassigned_speakers,
            }
        ),
    }
    if set(calibration_cases) | set(selection_cases) | set(excluded_cases) != _ids(
        rows
    ):
        raise H2ProgramError("integration development partition lost cases")
    if not calibration_cases or not selection_cases:
        raise H2ProgramError("integration speaker-disjoint role is empty")
    return {**core, "assignment_sha256": canonical_sha256(core)}


def _speaker_disjoint_trial(
    sources: Mapping[str, Mapping[str, object]],
    *,
    seed: int,
    trial_index: int,
) -> dict[str, object]:
    """Assign whole sources without ever crossing an existing speaker cohort."""

    ordered = sorted(
        sources,
        key=lambda audio_id: (
            _rank(
                seed,
                "h2-speaker-disjoint-integration",
                str(trial_index),
                audio_id,
            ),
            audio_id,
        ),
    )
    role_audio: dict[str, list[str]] = {
        "calibration": [],
        "selection": [],
        "excluded_cross_cohort": [],
    }
    role_speakers: dict[str, set[str]] = {
        "calibration": set(),
        "selection": set(),
    }
    role_case_counts = {"calibration": 0, "selection": 0}
    for audio_id in ordered:
        metadata = sources[audio_id]
        speakers = set(str(value) for value in metadata["speaker_ids"])  # type: ignore[union-attr]
        calibration_overlap = bool(speakers & role_speakers["calibration"])
        selection_overlap = bool(speakers & role_speakers["selection"])
        if calibration_overlap and selection_overlap:
            role = "excluded_cross_cohort"
        elif calibration_overlap:
            role = "calibration"
        elif selection_overlap:
            role = "selection"
        else:
            role = min(
                ("calibration", "selection"),
                key=lambda value: (
                    role_case_counts[value],
                    len(role_audio[value]),
                    value,
                ),
            )
        role_audio[role].append(audio_id)
        if role != "excluded_cross_cohort":
            role_speakers[role].update(speakers)
            role_case_counts[role] += int(metadata["case_count"])
    return {
        "trial_index": trial_index,
        "calibration_audio_ids": tuple(sorted(role_audio["calibration"])),
        "selection_audio_ids": tuple(sorted(role_audio["selection"])),
        "excluded_audio_ids": tuple(sorted(role_audio["excluded_cross_cohort"])),
        "calibration_speaker_ids": tuple(sorted(role_speakers["calibration"])),
        "selection_speaker_ids": tuple(sorted(role_speakers["selection"])),
        "calibration_case_count": role_case_counts["calibration"],
        "selection_case_count": role_case_counts["selection"],
    }


def _speaker_partition_objective(value: Mapping[str, object]) -> tuple[object, ...]:
    """Prefer balanced evidence first, then maximum retained evidence."""

    calibration_cases = int(value["calibration_case_count"])
    selection_cases = int(value["selection_case_count"])
    calibration_sources = len(value["calibration_audio_ids"])  # type: ignore[arg-type]
    selection_sources = len(value["selection_audio_ids"])  # type: ignore[arg-type]
    calibration_speakers = len(value["calibration_speaker_ids"])  # type: ignore[arg-type]
    selection_speakers = len(value["selection_speaker_ids"])  # type: ignore[arg-type]
    return (
        -min(calibration_cases, selection_cases),
        -(calibration_cases + selection_cases),
        -min(calibration_sources, selection_sources),
        -min(calibration_speakers, selection_speakers),
        abs(calibration_cases - selection_cases),
        int(value["trial_index"]),
    )


def _reference_speaker_ids(row: Mapping[str, object]) -> tuple[str, ...]:
    raw = row.get("global_speaker_ids")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise H2ProgramError(
            f"case {_case_id(row)} lacks pseudonymous speaker grouping metadata"
        )
    values = tuple(sorted({str(value) for value in raw if str(value).strip()}))
    if not values:
        raise H2ProgramError(
            f"case {_case_id(row)} has an empty pseudonymous speaker set"
        )
    return values


def resolve_panel(
    rows: Sequence[Mapping[str, object]], panel: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    by_id = {_case_id(row): dict(row) for row in rows}
    requested = tuple(str(value) for value in panel.get("case_ids", ()))
    missing = sorted(set(requested) - set(by_id))
    if missing:
        raise H2ProgramError(
            f"panel cases missing from prepared protocol: {missing[:3]}"
        )
    selected = tuple(by_id[value] for value in requested)
    if canonical_sha256(selected) != str(panel.get("case_manifest_sha256") or ""):
        raise H2ProgramError("panel case-manifest identity differs")
    return selected


def _core_panel(
    rows: Sequence[Mapping[str, object]], *, split: str, seed: int
) -> tuple[dict[str, object], ...]:
    eligible = [
        dict(row)
        for row in rows
        if str(row.get("partition") or "") == split
        and str(row.get("source_key") or "") in {"controlled_v1", "product_v2"}
        and str(row.get("scoring_stratum") or "") == "controlled_end_to_end"
    ]
    controlled = [row for row in eligible if row["source_key"] == "controlled_v1"]
    product = [row for row in eligible if row["source_key"] == "product_v2"]
    chosen = [
        *_select_controlled(controlled, seed=seed, audio_target=24),
        *_select_product(product, seed=seed, audio_target=36),
    ]
    chosen.sort(key=_case_id)
    if len(chosen) != 180:
        raise H2ProgramError(f"{split} core panel must contain 180 cases")
    return tuple(chosen)


def _select_controlled(
    rows: Sequence[Mapping[str, object]], *, seed: int, audio_target: int
) -> tuple[dict[str, object], ...]:
    groups = _audio_groups(rows)
    by_scenario: dict[str, list[str]] = defaultdict(list)
    for audio_id, group in groups.items():
        overlays = {str(row.get("overlay_id") or "") for row in group}
        scenarios = {str(row.get("scenario_id") or "") for row in group}
        if overlays != set(OVERLAYS) or len(group) != 3 or len(scenarios) != 1:
            raise H2ProgramError(
                "controlled audio lacks exact scenario/overlay contract"
            )
        by_scenario[next(iter(scenarios))].append(audio_id)
    if audio_target % len(by_scenario):
        raise H2ProgramError("controlled audio target cannot balance scenario strata")
    per_scenario = audio_target // len(by_scenario)
    selected_audio: list[str] = []
    for scenario, values in sorted(by_scenario.items()):
        ranked = sorted(
            values,
            key=lambda value: (_rank(seed, "controlled", scenario, value), value),
        )
        if len(ranked) < per_scenario:
            raise H2ProgramError(f"controlled scenario lacks audio: {scenario}")
        selected_audio.extend(ranked[:per_scenario])
    return tuple(
        sorted(
            (dict(row) for audio_id in selected_audio for row in groups[audio_id]),
            key=_case_id,
        )
    )


def _select_product(
    rows: Sequence[Mapping[str, object]], *, seed: int, audio_target: int
) -> tuple[dict[str, object], ...]:
    groups = _audio_groups(rows)
    audio_ids = sorted(
        groups, key=lambda value: (_rank(seed, "product-audio", value), value)
    )[:audio_target]
    gallery_counts: Counter[str] = Counter()
    full_overlay_counts: Counter[str] = Counter()
    selected: list[dict[str, object]] = []
    for audio_id in audio_ids:
        group = groups[audio_id]
        by_overlay = {
            overlay: [
                row for row in group if str(row.get("overlay_id") or "") == overlay
            ]
            for overlay in OVERLAYS
        }
        if any(not values for values in by_overlay.values()):
            raise H2ProgramError(f"Product audio lacks truth overlay: {audio_id}")
        full_candidates = [row for row in group if _gallery(row) == "full"]
        if not full_candidates:
            raise H2ProgramError(f"Product audio lacks full gallery: {audio_id}")
        full = min(
            full_candidates,
            key=lambda row: (
                full_overlay_counts[str(row["overlay_id"])],
                _rank(seed, "product-full", audio_id, _case_id(row)),
                _case_id(row),
            ),
        )
        local = [dict(full)]
        chosen_overlay = str(full["overlay_id"])
        full_overlay_counts[chosen_overlay] += 1
        gallery_counts["full"] += 1
        used = {"full"}
        for overlay in OVERLAYS:
            if overlay == chosen_overlay:
                continue
            candidate = min(
                by_overlay[overlay],
                key=lambda row: (
                    _gallery(row) in used,
                    gallery_counts[_gallery(row)],
                    _rank(seed, "product-variant", audio_id, overlay, _case_id(row)),
                    _case_id(row),
                ),
            )
            local.append(dict(candidate))
            gallery_counts[_gallery(candidate)] += 1
            used.add(_gallery(candidate))
        selected.extend(local)
    if len(selected) != audio_target * 3:
        raise H2ProgramError("Product panel cardinality differs")
    return tuple(sorted(selected, key=_case_id))


def _nested_panel(
    core: Sequence[Mapping[str, object]], count: int, *, seed: int, label: str
) -> tuple[dict[str, object], ...]:
    if count % 3:
        raise H2ProgramError(
            "nested panel count must preserve three overlays per audio"
        )
    groups = _audio_groups(core)
    target_audio = count // 3
    controlled = [
        key
        for key, value in groups.items()
        if str(value[0].get("source_key")) == "controlled_v1"
    ]
    product = [
        key
        for key, value in groups.items()
        if str(value[0].get("source_key")) == "product_v2"
    ]
    controlled_target = round(target_audio * 24 / 60)
    product_target = target_audio - controlled_target
    chosen = [
        *sorted(controlled, key=lambda value: (_rank(seed, label, "c", value), value))[
            :controlled_target
        ],
        *sorted(product, key=lambda value: (_rank(seed, label, "p", value), value))[
            :product_target
        ],
    ]
    rows = tuple(
        sorted(
            (dict(row) for audio_id in chosen for row in groups[audio_id]), key=_case_id
        )
    )
    if len(rows) != count:
        raise H2ProgramError(f"nested panel {label} cardinality differs")
    return rows


def _nested_development_panel(
    core: Sequence[Mapping[str, object]],
    count: int,
    *,
    seed: int,
    label: str,
) -> tuple[dict[str, object], ...]:
    """Build nested halving panels with explicit short-turn scenario coverage.

    Membership uses development scenario metadata only.  Reference RTTM turn
    durations are deliberately not read here; runtime promotion later fails
    closed unless every predeclared duration-bin metric is actually computed.
    """

    if count not in {36, 72}:
        raise H2ProgramError(f"development halving panel count is unsupported: {count}")
    groups = _audio_groups(core)
    controlled = {
        key: value
        for key, value in groups.items()
        if str(value[0].get("source_key") or "") == "controlled_v1"
    }
    product = {
        key: value
        for key, value in groups.items()
        if str(value[0].get("source_key") or "") == "product_v2"
    }
    quotas = _development_scenario_quotas(count)
    selected_audio = [
        *_select_scenario_quota_audio(
            controlled,
            quotas=quotas["controlled_v1"],
            seed=seed,
            label=label,
            source_key="controlled_v1",
        ),
        *_select_scenario_quota_audio(
            product,
            quotas=quotas["product_v2"],
            seed=seed,
            label=label,
            source_key="product_v2",
        ),
    ]
    rows = tuple(
        sorted(
            (dict(row) for audio_id in selected_audio for row in groups[audio_id]),
            key=_case_id,
        )
    )
    if len(rows) != count:
        raise H2ProgramError(f"nested development panel {label} cardinality differs")
    return rows


def _development_scenario_quotas(count: int) -> dict[str, dict[str, int]]:
    if count == 36:
        return {
            "controlled_v1": {
                "rapid:1": 1,
                "rapid:2": 1,
                "rapid:3": 2,
                "rapid:5": 1,
            },
            "product_v2": {
                "short_response_rare_reentry": 3,
                "rapid_backchannel": 1,
                "interrupted_monologue": 1,
                "normal_alternation": 1,
                "long_session_reentry_drift": 1,
            },
        }
    if count == 72:
        return {
            "controlled_v1": {
                "rapid:1": 2,
                "rapid:2": 2,
                "rapid:3": 2,
                "rapid:5": 2,
                "standard:1": 1,
                "relaxed:1": 1,
            },
            "product_v2": {
                "short_response_rare_reentry": 4,
                "rapid_backchannel": 3,
                "interrupted_monologue": 3,
                "normal_alternation": 2,
                "long_session_reentry_drift": 2,
            },
        }
    raise H2ProgramError(f"development scenario quotas are undefined for {count}")


def _select_scenario_quota_audio(
    groups: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    quotas: Mapping[str, int],
    seed: int,
    label: str,
    source_key: str,
) -> tuple[str, ...]:
    by_scenario: dict[str, list[str]] = defaultdict(list)
    for audio_id, rows in groups.items():
        scenarios = {str(row.get("scenario_id") or "") for row in rows}
        if len(scenarios) != 1 or not next(iter(scenarios)):
            raise H2ProgramError(
                f"{source_key} development audio lacks one stable scenario"
            )
        by_scenario[next(iter(scenarios))].append(audio_id)
    selected: list[str] = []
    for scenario, target in quotas.items():
        candidates = sorted(
            by_scenario.get(scenario, ()),
            key=lambda value: (
                _rank(seed, label, source_key, scenario, value),
                value,
            ),
        )
        if len(candidates) < target:
            raise H2ProgramError(
                f"{label} lacks {source_key}/{scenario} audio: "
                f"required={target} available={len(candidates)}"
            )
        selected.extend(candidates[:target])
    if len(selected) != len(set(selected)):
        raise H2ProgramError(f"{label} selected duplicate source audio")
    return tuple(selected)


def _scenario_audio_counts(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, int]]:
    groups = _audio_groups(rows)
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for group in groups.values():
        source_key = str(group[0].get("source_key") or "")
        scenario_id = str(group[0].get("scenario_id") or "")
        counts[source_key][scenario_id] += 1
    return {
        source_key: dict(sorted(values.items()))
        for source_key, values in sorted(counts.items())
    }


def _audit_short_turn_reference_coverage(
    rows: Sequence[Mapping[str, object]],
    *,
    tool_root: Path,
) -> dict[str, object]:
    """Qualify a metadata-selected development panel against frozen bins.

    This is intentionally a post-selection development-only audit.  It never
    changes membership and never reads evaluation references.  Three overlay
    cases can share one RTTM, so each reference file is counted exactly once.
    """

    resolved_root = Path(tool_root).resolve()
    references: dict[str, tuple[Path, str]] = {}
    for row in rows:
        logical = str(row.get("reference_rttm_logical_path") or "")
        expected_sha256 = str(row.get("reference_rttm_sha256") or "").lower()
        if not logical or len(expected_sha256) != 64:
            raise H2ProgramError(
                f"development case {_case_id(row)} lacks a sealed RTTM reference"
            )
        normalized = Path(*logical.replace("\\", "/").split("/"))
        path = (resolved_root / normalized).resolve()
        if not path.is_relative_to(resolved_root):
            raise H2ProgramError(f"development RTTM escapes the tool root: {logical}")
        existing = references.get(logical)
        if existing is not None and existing != (path, expected_sha256):
            raise H2ProgramError(
                f"development RTTM identity differs across overlays: {logical}"
            )
        references[logical] = (path, expected_sha256)

    bin_definitions = (
        ("short_turn_der_lt_0_5_sec", 0.0, 0.5, False),
        ("short_turn_der_0_5_to_1_0_sec", 0.5, 1.0, False),
        ("short_turn_der_1_0_to_2_0_sec", 1.0, 2.0, True),
    )
    counts = {metric_id: 0 for metric_id, *_rest in bin_definitions}
    durations = {metric_id: 0.0 for metric_id, *_rest in bin_definitions}
    total_turn_count = 0
    for logical, (path, expected_sha256) in sorted(references.items()):
        if not path.is_file():
            raise H2ProgramError(f"development RTTM is missing: {logical}")
        if sha256_file(path).lower() != expected_sha256:
            raise H2ProgramError(f"development RTTM checksum differs: {logical}")
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            fields = stripped.split()
            if len(fields) < 5 or fields[0].upper() != "SPEAKER":
                raise H2ProgramError(
                    f"invalid development RTTM row at {logical}:{line_number}"
                )
            try:
                duration_sec = float(fields[4])
            except ValueError as exc:
                raise H2ProgramError(
                    f"invalid development RTTM duration at {logical}:{line_number}"
                ) from exc
            if duration_sec <= 0:
                raise H2ProgramError(
                    f"non-positive development RTTM duration at {logical}:{line_number}"
                )
            total_turn_count += 1
            for metric_id, lower_sec, upper_sec, include_upper in bin_definitions:
                if duration_sec < lower_sec:
                    continue
                if duration_sec < upper_sec or (
                    include_upper and duration_sec <= upper_sec
                ):
                    counts[metric_id] += 1
                    durations[metric_id] += duration_sec
                    break

    bins = {
        metric_id: {
            "turn_count": counts[metric_id],
            "reference_speech_duration_sec": round(durations[metric_id], 9),
            "has_evidence": counts[metric_id] > 0 and durations[metric_id] > 0,
            "duration_lower_sec_inclusive": lower_sec,
            "duration_upper_sec": upper_sec,
            "duration_upper_inclusive": include_upper,
        }
        for metric_id, lower_sec, upper_sec, include_upper in bin_definitions
    }
    core = {
        "qualification_role": "post-selection development-only evidence check",
        "membership_changed_by_audit": False,
        "evaluation_reference_content_inspected": False,
        "unique_reference_rttm_count": len(references),
        "total_reference_turn_count": total_turn_count,
        "bins": bins,
        "all_required_bins_have_evidence": all(
            bool(value["has_evidence"]) for value in bins.values()
        ),
    }
    return {**core, "audit_sha256": canonical_sha256(core)}


def _diagnostic_panel(
    rows: Sequence[Mapping[str, object]], *, scoring_stratum: str, count: int, seed: int
) -> tuple[dict[str, object], ...]:
    eligible = [
        dict(row)
        for row in rows
        if str(row.get("partition") or "") == "evaluation"
        and str(row.get("scoring_stratum") or "") == scoring_stratum
    ]
    if len(eligible) < count:
        raise H2ProgramError(
            f"diagnostic stratum {scoring_stratum} has {len(eligible)} < {count}"
        )
    return tuple(
        sorted(
            sorted(
                eligible,
                key=lambda row: (
                    _rank(seed, "diagnostic", scoring_stratum, _case_id(row)),
                    _case_id(row),
                ),
            )[:count],
            key=_case_id,
        )
    )


def _panel_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    values = tuple(dict(row) for row in rows)
    return {
        "case_count": len(values),
        "audio_duration_sec": sum(_duration(row) for row in values),
        "case_ids": [_case_id(row) for row in values],
        "case_manifest_sha256": canonical_sha256(values),
        "source_counts": dict(
            sorted(Counter(str(row.get("source_key")) for row in values).items())
        ),
        "overlay_counts": dict(
            sorted(Counter(str(row.get("overlay_id")) for row in values).items())
        ),
        "scenario_count": len({str(row.get("scenario_id")) for row in values}),
        "unique_audio_count": len({_audio_id(row) for row in values}),
    }


def _audio_groups(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        result[_audio_id(row)].append(dict(row))
    return dict(result)


def _audio_id(row: Mapping[str, object]) -> str:
    value = str(row.get("pcm_sha256") or row.get("audio_sha256") or "").lower()
    if len(value) == 64:
        return value
    logical = str(row.get("audio_logical_path") or "")
    recording = str(row.get("source_recording_id") or row.get("source_case_id") or "")
    if not logical or not recording:
        raise H2ProgramError(f"case {_case_id(row)} lacks an audio identity")
    # Native diagnostic manifests intentionally omit a content hash.  This is
    # a metadata selection key only; runtime preflight still hashes/verifies
    # the installed audio before it can enter a scientific result.
    return hashlib.sha256(
        "\x1f".join(
            (
                logical,
                recording,
                str(row.get("source_start_sec") or ""),
                str(row.get("source_end_sec") or ""),
            )
        ).encode("utf-8")
    ).hexdigest()


def _case_id(row: Mapping[str, object]) -> str:
    value = str(row.get("protocol_case_id") or row.get("case_id") or "")
    if not value:
        raise H2ProgramError("case lacks identity")
    return value


def _duration(row: Mapping[str, object]) -> float:
    value = float(row.get("duration_sec") or row.get("audio_duration_sec") or 0.0)
    if value <= 0:
        raise H2ProgramError(f"case {_case_id(row)} lacks positive duration")
    return value


def _gallery(row: Mapping[str, object]) -> str:
    value = row.get("gallery_requested_size")
    return "full" if str(value).lower() == "full" else str(int(value))


def _rank(seed: int, *parts: str) -> str:
    payload = "\x1f".join((str(seed), *map(str, parts))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ids(rows: Sequence[Mapping[str, object]]) -> set[str]:
    return {_case_id(row) for row in rows}


__all__ = ["build_panel_manifest", "resolve_panel"]
