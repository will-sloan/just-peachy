"""Deterministic metadata-only development selection for bounded Prompt 4.

No prediction, score, embedding, transcript, or model runtime is opened here.
The selector balances the two development sources independently across
``scenario_id`` x ``overlay_id`` and uses only a seeded hash plus gallery
metadata to choose within a stratum.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    sha256_bytes,
    write_json_atomic,
)


SELECTION_SCHEMA_VERSION = "full-pipeline-prompt4-reduced-selection.v1"
SCOPE_ID = "full_pipeline_prompts_4_8_eight_day_c_only.v1"
SCOPE_CLASS = "BOUNDED_REDUCED"
COMPLETION_MARKER = "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE_REDUCED_8DAY_V1"
ORIGINAL_FULL_SCOPE_COMPLETE = False
SELECTION_SEED = 5107
SOURCE_TARGETS = {"controlled_v1": 72, "product_v2": 108}
EXPECTED_SOURCE_COUNTS = {"controlled_v1": 180, "product_v2": 627}
STRATUM_FIELDS = ("scenario_id", "overlay_id")


class BoundedSelectionError(RuntimeError):
    """The frozen bounded selection contract cannot be satisfied."""


def build_selection_manifest(
    development_rows: Sequence[Mapping[str, object]],
    *,
    seed: int = SELECTION_SEED,
) -> dict[str, object]:
    """Build the fixed 180-case development panel from metadata only.

    Controlled-v1 selects two unique source recordings per each of its 12
    scenario strata and retains all three identity overlays (72 cases over 24
    unique recordings).  Product-v2 retains every one of its 36 unique source
    recordings and selects exactly one ALL_KNOWN, MIXED_KNOWN_UNKNOWN, and
    ALL_UNKNOWN variant per recording (108 cases).  One selected Product-v2
    variant per recording is full-gallery; the other galleries are balanced by
    a seed-bound metadata-only rank.  This gives broad scenario, truth-overlay,
    gallery, and physical-audio coverage without consulting system output.
    """

    rows = tuple(dict(row) for row in development_rows)
    _require_development_only(rows)
    _require_unique_case_ids(rows)
    by_source = {
        source_key: [
            row for row in rows if str(row.get("source_key") or "") == source_key
        ]
        for source_key in SOURCE_TARGETS
    }
    for source_key, expected in EXPECTED_SOURCE_COUNTS.items():
        if len(by_source[source_key]) != expected:
            raise BoundedSelectionError(
                f"{source_key} development inventory changed: expected={expected}, "
                f"observed={len(by_source[source_key])}"
            )
    controlled, controlled_audit = _controlled_selection(
        by_source["controlled_v1"], seed=seed
    )
    product, product_audit = _product_selection(
        by_source["product_v2"], seed=seed
    )
    selected = [*controlled, *product]
    source_audits = [controlled_audit, product_audit]

    selected.sort(key=_case_id)
    selected_ids = {_case_id(row) for row in selected}
    eligible = [
        row
        for row in rows
        if str(row.get("source_key") or "") in SOURCE_TARGETS
    ]
    excluded = sorted(
        (row for row in eligible if _case_id(row) not in selected_ids),
        key=_case_id,
    )
    selected_inventory = [_inventory_row(row) for row in selected]
    excluded_inventory = [_inventory_row(row) for row in excluded]
    selection_core: dict[str, object] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": "FROZEN_METADATA_ONLY_SELECTION",
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": ORIGINAL_FULL_SCOPE_COMPLETE,
        "completion_marker_on_success": COMPLETION_MARKER,
        "selection_seed": int(seed),
        "selection_inputs": ["development_case_metadata", "reference_hashes"],
        "prediction_or_score_inputs_used": False,
        "result_dependent_sampling": False,
        "inclusion_rule": {
            "eligible_split": "development",
            "eligible_sources": list(SOURCE_TARGETS),
            "source_targets": dict(SOURCE_TARGETS),
            "stratum_fields": list(STRATUM_FIELDS),
            "controlled_v1_rule": (
                "two_seeded_unique_audio_sources_per_scenario_then_all_three_overlays"
            ),
            "product_v2_rule": (
                "all_36_unique_audio_sources_x_exact_three_truth_overlays_with_one_"
                "full_gallery_variant_per_audio_and_seeded_gallery_balance"
            ),
        },
        "selected_case_count": len(selected),
        "excluded_case_count": len(excluded),
        "selected_case_ids": [_case_id(row) for row in selected],
        "selected_case_inventory": selected_inventory,
        "excluded_case_inventory": excluded_inventory,
        "source_audits": source_audits,
        "case_manifest_sha256": sha256_bytes(canonical_json_bytes(selected)),
        "reference_sha256": sha256_bytes(
            canonical_json_bytes([_reference_row(row) for row in selected])
        ),
        "achieved_coverage": _coverage(selected),
        "original_requested_coverage": {
            "development_case_count": sum(EXPECTED_SOURCE_COUNTS.values()),
            "source_case_counts": dict(EXPECTED_SOURCE_COUNTS),
        },
        "development_only": True,
        "held_out_evaluation_allowed": False,
        "evaluation_material_inspected": False,
    }
    return {
        **selection_core,
        "selection_identity_sha256": sha256_bytes(
            canonical_json_bytes(selection_core)
        ),
    }


def selected_rows(
    development_rows: Sequence[Mapping[str, object]],
    manifest: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    """Resolve and revalidate the exact selected rows from a frozen manifest."""

    expected = build_selection_manifest(
        development_rows, seed=int(manifest.get("selection_seed", SELECTION_SEED))
    )
    if canonical_json_bytes(expected) != canonical_json_bytes(dict(manifest)):
        raise BoundedSelectionError("selection manifest differs from deterministic rebuild")
    by_id = {_case_id(row): dict(row) for row in development_rows}
    result = tuple(by_id[str(case_id)] for case_id in manifest["selected_case_ids"])
    _require_development_only(result)
    return result


def write_selection_manifest(path: Path, value: Mapping[str, object]) -> None:
    """Write once, or verify that the existing immutable selection is identical."""

    destination = Path(path).resolve()
    if destination.is_file():
        import json

        existing = json.loads(destination.read_text(encoding="utf-8"))
        if canonical_json_bytes(existing) != canonical_json_bytes(dict(value)):
            raise BoundedSelectionError(
                f"selection is immutable and differs at {destination}"
            )
        return
    write_json_atomic(destination, dict(value))


def _controlled_selection(
    rows: Sequence[Mapping[str, object]], *, seed: int
) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_audio = _audio_groups(rows, expected_unique=60, source_key="controlled_v1")
    by_scenario: dict[str, list[str]] = defaultdict(list)
    for audio_id, group in by_audio.items():
        scenarios = {str(row.get("scenario_id") or "") for row in group}
        if len(scenarios) != 1 or "" in scenarios:
            raise BoundedSelectionError("controlled audio crosses/misses scenario metadata")
        overlays = {str(row.get("overlay_id") or "") for row in group}
        if overlays != {"ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"} or len(group) != 3:
            raise BoundedSelectionError("controlled audio lacks exact three overlays")
        by_scenario[next(iter(scenarios))].append(audio_id)
    if len(by_scenario) != 12 or any(len(values) < 2 for values in by_scenario.values()):
        raise BoundedSelectionError("controlled scenario/audio inventory changed")
    selected_audio: list[str] = []
    for scenario, audio_ids in sorted(by_scenario.items()):
        ranked = sorted(
            audio_ids,
            key=lambda audio_id: (
                _rank(seed, "controlled_v1", "audio", scenario, audio_id),
                audio_id,
            ),
        )
        selected_audio.extend(ranked[:2])
    selected = sorted(
        (dict(row) for audio_id in selected_audio for row in by_audio[audio_id]),
        key=_case_id,
    )
    if len(selected_audio) != 24 or len(selected) != SOURCE_TARGETS["controlled_v1"]:
        raise BoundedSelectionError("controlled bounded selection cardinality differs")
    return selected, _source_audit(
        "controlled_v1",
        rows,
        selected,
        selected_audio_ids=selected_audio,
        selection_unit="24_unique_audio_sources_x_all_3_overlays",
    )


def _product_selection(
    rows: Sequence[Mapping[str, object]], *, seed: int
) -> tuple[list[dict[str, object]], dict[str, object]]:
    by_audio = _audio_groups(rows, expected_unique=36, source_key="product_v2")
    overlay_names = ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN")
    gallery_counts: Counter[str] = Counter()
    full_overlay_counts: Counter[str] = Counter()
    selected: list[dict[str, object]] = []
    audio_order = sorted(
        by_audio,
        key=lambda audio_id: (_rank(seed, "product_v2", "audio", audio_id), audio_id),
    )
    for audio_id in audio_order:
        group = by_audio[audio_id]
        by_overlay = {
            overlay: [row for row in group if str(row.get("overlay_id") or "") == overlay]
            for overlay in overlay_names
        }
        if any(not values for values in by_overlay.values()):
            raise BoundedSelectionError(f"Product audio {audio_id} lacks a truth overlay")
        full_candidates = [row for row in group if _gallery(row) == "full"]
        if not full_candidates:
            raise BoundedSelectionError(f"Product audio {audio_id} lacks full gallery")
        full = min(
            full_candidates,
            key=lambda row: (
                full_overlay_counts[str(row["overlay_id"])],
                _rank(seed, "product_v2", "full", audio_id, _case_id(row)),
                _case_id(row),
            ),
        )
        local = [dict(full)]
        chosen_overlay = str(full["overlay_id"])
        full_overlay_counts[chosen_overlay] += 1
        gallery_counts["full"] += 1
        used_galleries = {"full"}
        for overlay in overlay_names:
            if overlay == chosen_overlay:
                continue
            chosen = min(
                by_overlay[overlay],
                key=lambda row: (
                    _gallery(row) in used_galleries,
                    gallery_counts[_gallery(row)],
                    _rank(seed, "product_v2", "variant", audio_id, overlay, _case_id(row)),
                    _case_id(row),
                ),
            )
            local.append(dict(chosen))
            gallery_counts[_gallery(chosen)] += 1
            used_galleries.add(_gallery(chosen))
        if {str(row["overlay_id"]) for row in local} != set(overlay_names):
            raise BoundedSelectionError(f"Product audio {audio_id} overlay selection differs")
        selected.extend(local)
    selected.sort(key=_case_id)
    if len(selected) != SOURCE_TARGETS["product_v2"]:
        raise BoundedSelectionError("Product bounded selection cardinality differs")
    audit = _source_audit(
        "product_v2",
        rows,
        selected,
        selected_audio_ids=audio_order,
        selection_unit="all_36_unique_audio_sources_x_3_truth_overlays",
    )
    audit["full_gallery_case_count"] = sum(_gallery(row) == "full" for row in selected)
    audit["full_gallery_overlay_counts"] = dict(sorted(full_overlay_counts.items()))
    return selected, audit


def _audio_groups(
    rows: Sequence[Mapping[str, object]], *, expected_unique: int, source_key: str
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        audio_id = str(row.get("pcm_sha256") or row.get("audio_sha256") or "")
        if len(audio_id) != 64:
            raise BoundedSelectionError(f"{source_key} case {_case_id(row)} lacks audio hash")
        grouped[audio_id].append(row)
    if len(grouped) != expected_unique:
        raise BoundedSelectionError(
            f"{source_key} unique audio inventory changed: expected={expected_unique}, "
            f"observed={len(grouped)}"
        )
    return dict(grouped)


def _source_audit(
    source_key: str,
    available: Sequence[Mapping[str, object]],
    selected: Sequence[Mapping[str, object]],
    *,
    selected_audio_ids: Sequence[str],
    selection_unit: str,
) -> dict[str, object]:
    available_counts = Counter(_stratum(row) for row in available)
    selected_counts = Counter(_stratum(row) for row in selected)
    return {
        "source_key": source_key,
        "selection_unit": selection_unit,
        "available_case_count": len(available),
        "target_case_count": SOURCE_TARGETS[source_key],
        "selected_case_count": len(selected),
        "available_duration_sec": round(sum(_duration(row) for row in available), 9),
        "selected_duration_sec": round(sum(_duration(row) for row in selected), 9),
        "available_unique_audio_count": len(
            {str(row.get("pcm_sha256") or row.get("audio_sha256")) for row in available}
        ),
        "selected_unique_audio_count": len(set(selected_audio_ids)),
        "selected_audio_sha256_ids": sorted(set(selected_audio_ids)),
        "stratum_count": len(available_counts),
        "strata": [
            {
                "stratum": dict(zip(STRATUM_FIELDS, key, strict=True)),
                "available": available_counts[key],
                "selected": selected_counts[key],
                "excluded": available_counts[key] - selected_counts[key],
            }
            for key in sorted(available_counts)
        ],
        "gallery_counts": dict(
            sorted(Counter(_gallery(row) for row in selected).items())
        ),
    }


def _coverage(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    speakers: set[str] = set()
    enrolled: set[str] = set()
    for row in rows:
        speakers.update(_strings(row.get("global_speaker_ids")))
        enrolled.update(_strings(row.get("gallery_enrolled_ids")))
    return {
        "case_count": len(rows),
        "duration_sec": round(sum(_duration(row) for row in rows), 9),
        "unique_audio_count": len(
            {str(row.get("pcm_sha256") or row.get("audio_sha256")) for row in rows}
        ),
        "source_unique_audio_counts": dict(
            sorted(
                (
                    source,
                    len(
                        {
                            str(row.get("pcm_sha256") or row.get("audio_sha256"))
                            for row in rows
                            if str(row.get("source_key") or "") == source
                        }
                    ),
                )
                for source in SOURCE_TARGETS
            )
        ),
        "source_case_counts": dict(
            sorted(Counter(str(row.get("source_key") or "") for row in rows).items())
        ),
        "scenario_counts": dict(
            sorted(Counter(str(row.get("scenario_id") or "") for row in rows).items())
        ),
        "overlay_counts": dict(
            sorted(Counter(str(row.get("overlay_id") or "") for row in rows).items())
        ),
        "gallery_requested_counts": dict(
            sorted(Counter(_gallery(row) for row in rows).items())
        ),
        "speaker_count": len(speakers),
        "speaker_ids": sorted(speakers),
        "enrolled_identity_count": len(enrolled),
        "enrolled_identity_ids": sorted(enrolled),
    }


def _inventory_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "case_id": _case_id(row),
        "source_key": str(row.get("source_key") or ""),
        "source_case_id": str(row.get("source_case_id") or ""),
        "scenario_id": str(row.get("scenario_id") or ""),
        "overlay_id": str(row.get("overlay_id") or ""),
        "gallery_requested_size": _gallery(row),
        "duration_sec": _duration(row),
        "pcm_sha256": row.get("pcm_sha256"),
        "global_speaker_ids": sorted(_strings(row.get("global_speaker_ids"))),
        "known_speaker_count": int(row.get("known_speaker_count") or 0),
        "unknown_speaker_count": int(row.get("unknown_speaker_count") or 0),
        "reference_rttm_sha256": row.get("reference_rttm_sha256"),
        "reference_uem_sha256": row.get("reference_uem_sha256"),
        "recipe_sha256": row.get("recipe_sha256"),
    }


def _reference_row(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "case_id": _case_id(row),
        "source_protocol_id": row.get("source_protocol_id"),
        "source_reference_id": row.get("source_reference_id"),
        "reference_rttm_sha256": row.get("reference_rttm_sha256"),
        "reference_uem_sha256": row.get("reference_uem_sha256"),
        "recipe_sha256": row.get("recipe_sha256"),
        "audio_sha256": row.get("audio_sha256"),
        "pcm_sha256": row.get("pcm_sha256"),
    }


def _require_development_only(rows: Sequence[Mapping[str, object]]) -> None:
    invalid = [
        _case_id(row)
        for row in rows
        if str(row.get("split") or row.get("partition") or "") != "development"
    ]
    if invalid:
        raise BoundedSelectionError(
            "held-out/evaluation cases are forbidden in bounded Prompt 4: "
            + ", ".join(sorted(invalid)[:5])
        )


def _require_unique_case_ids(rows: Sequence[Mapping[str, object]]) -> None:
    counts = Counter(_case_id(row) for row in rows)
    duplicate = sorted(case_id for case_id, count in counts.items() if count != 1)
    if duplicate:
        raise BoundedSelectionError("duplicate case IDs: " + ", ".join(duplicate[:5]))


def _case_id(row: Mapping[str, object]) -> str:
    value = str(row.get("protocol_case_id") or row.get("case_id") or "")
    if not value:
        raise BoundedSelectionError("case lacks protocol_case_id/case_id")
    return value


def _stratum(row: Mapping[str, object]) -> tuple[str, ...]:
    values = tuple(str(row.get(field) or "") for field in STRATUM_FIELDS)
    if any(not value for value in values):
        raise BoundedSelectionError(f"case {_case_id(row)} lacks selection stratum")
    return values


def _gallery(row: Mapping[str, object]) -> str:
    value = str(row.get("gallery_requested_size") or "")
    if not value:
        raise BoundedSelectionError(f"case {_case_id(row)} lacks gallery metadata")
    return value


def _duration(row: Mapping[str, object]) -> float:
    value = float(row.get("duration_sec") or 0.0)
    if value <= 0.0:
        raise BoundedSelectionError(f"case {_case_id(row)} has invalid duration")
    return value


def _strings(value: object) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if str(item)}
    return set()


def _rank(seed: int, *parts: object) -> str:
    payload = "\x1f".join([str(seed), *(str(part) for part in parts)])
    return sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "BoundedSelectionError",
    "COMPLETION_MARKER",
    "EXPECTED_SOURCE_COUNTS",
    "ORIGINAL_FULL_SCOPE_COMPLETE",
    "SCOPE_CLASS",
    "SCOPE_ID",
    "SELECTION_SEED",
    "SOURCE_TARGETS",
    "build_selection_manifest",
    "selected_rows",
    "write_selection_manifest",
]
