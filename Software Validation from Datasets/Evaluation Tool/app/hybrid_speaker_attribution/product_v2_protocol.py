"""Deterministic metadata-only overlays and scientific policies for Hybrid Product V2."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Mapping

import yaml

from app.hybrid_speaker_attribution.product_v2_contracts import (
    BACKEND_MINIMUM_SEC, COMBINATIONS, DIARIZATION_PIPELINES, EVIDENCE_CHECKPOINTS_SEC,
    FROZEN_DIARIZATION_SELECTION, GALLERY_SIZES, OPERATING_MODES, OVERLAYS,
    POLICY_ROOT, PRIMARY_GALLERY_SIZES, PRODUCT_PROTOCOL_ROOT, RESULT_ROOT, SCHEMA,
    SEED, UPSTREAM_DIARIZATION_ROOT, V1_BENCHMARK_ID, V1_BENCHMARK_ROOT,
    V1_OVERLAY_COUNTS, V1_PROTOCOL_ID, V1_PROTOCOL_ROOT, V2_BENCHMARK_ID,
    V2_BENCHMARK_ROOT, ProductV2Error, atomic_json, checksum_tree, file_sha256,
    now_utc, protocol_id, read_json, read_jsonl, speaker_band, stable_order,
    write_csv, write_jsonl, write_yaml,
)


EVIDENCE_ROOT = RESULT_ROOT.parent / "speaker_enrollment" / "speaker_enrollment_live_v2_5107db9ab304"
DEPLOYMENT_ROOT = RESULT_ROOT.parent.parent / "JustPeachyResearchSummaries" / "speaker_embedding_deployment_v1_4779270a5bf0"

BACKEND_POLICY = {
    "wespeaker": {
        "policy_id": "hybrid_product_v2_wespeaker_scientific_v1",
        "enrollment_utterance_count": 3,
        "enrollment_total_target_sec": 10.0,
        "aggregation_method": "multi_template_top2_mean",
        "environment_profile": "wespeaker",
        "evidence_reference": "speaker_enrollment_live_v2 FINAL_ANALYSIS: accuracy primary; three clean diverse utterances; multi-template top-2 mean tendency",
    },
    "redimnet2_b2_speaker_embedding": {
        "policy_id": "hybrid_product_v2_redimnet2_scientific_v1",
        "enrollment_utterance_count": 3,
        "enrollment_total_target_sec": 10.0,
        "aggregation_method": "multi_template_max",
        "environment_profile": "redimnet2",
        "evidence_reference": "speaker_enrollment_live_v2 FINAL_ANALYSIS: compact fallback; three clean diverse utterances; multi-template max tendency",
    },
    "speechbrain_ecapa": {
        "policy_id": "hybrid_product_v2_speechbrain_ecapa_scientific_v1",
        "enrollment_utterance_count": 3,
        "enrollment_total_target_sec": 10.0,
        "aggregation_method": "multi_template_top2_mean",
        "environment_profile": "core-cpu",
        "evidence_reference": "speaker_enrollment_live_v2 FINAL_ANALYSIS: speed alternative; three clean diverse utterances; top-2/max retained-template evidence",
    },
}


def prepare() -> dict[str, object]:
    """Create only metadata overlays; never copies or edits controlled audio."""

    _validate_v1_preserved()
    frozen = _validate_frozen_diarization()
    pools = _speaker_pools()
    identity_payload = {
        "schema": SCHEMA,
        "seed": SEED,
        "v1_protocol_id": V1_PROTOCOL_ID,
        "v1_benchmark_id": V1_BENCHMARK_ID,
        "v2_benchmark_id": V2_BENCHMARK_ID,
        "frozen_diarization_sha256": file_sha256(FROZEN_DIARIZATION_SELECTION).lower(),
        "overlay_conditions": list(OVERLAYS),
        "gallery_sizes": list(GALLERY_SIZES),
        "primary_gallery_sizes": list(PRIMARY_GALLERY_SIZES),
        "combination_ids": [row["combination_id"] for row in COMBINATIONS],
        "active_speaker_bands": ["1", "2", "3-5", "6-8", "9-12"],
    }
    product_protocol_id = protocol_id(identity_payload)
    PRODUCT_PROTOCOL_ROOT.mkdir(parents=True, exist_ok=True)
    overlays_by_corpus: dict[str, dict[str, int]] = {}
    for corpus, benchmark_root, benchmark_id in (
        ("v1", V1_BENCHMARK_ROOT, V1_BENCHMARK_ID),
        ("v2", V2_BENCHMARK_ROOT, V2_BENCHMARK_ID),
    ):
        overlays_by_corpus[corpus] = {}
        for tier in ("development", "evaluation"):
            cases = read_jsonl(benchmark_root / tier / "case_manifest.jsonl")
            rows = [_overlay(case, overlay, pools[tier], product_protocol_id, corpus) for case in cases for overlay in OVERLAYS]
            write_jsonl(PRODUCT_PROTOCOL_ROOT / corpus / tier / "identity_overlays.jsonl", rows)
            overlays_by_corpus[corpus][tier] = len(rows)
    policies = _write_policies(product_protocol_id)
    registry = {
        "schema_version": f"{SCHEMA}-combination-registry.v1",
        "protocol_id": product_protocol_id,
        "independent_identity_reembedding_required": True,
        "same_model_reuse_is_diagnostic_only": True,
        "combinations": [
            {**row, "diarization_configuration_sha256": DIARIZATION_PIPELINES[str(row["diarization_pipeline_id"])], "enrollment_policy_path": policies[str(row["identity_backend_id"])]["path"], "enrollment_policy_sha256": policies[str(row["identity_backend_id"])]["sha256"]}
            for row in COMBINATIONS
        ],
    }
    atomic_json(PRODUCT_PROTOCOL_ROOT / "combination_registry.json", registry)
    write_csv(PRODUCT_PROTOCOL_ROOT / "combination_registry.csv", list(registry["combinations"]))
    _prepare_chime_protocol(product_protocol_id)
    summary = {
        "schema_version": f"{SCHEMA}-protocol-summary.v1",
        "protocol_id": product_protocol_id,
        "seed": SEED,
        "created_at_utc": now_utc(),
        "identity_payload": identity_payload,
        "overlays": overlays_by_corpus,
        "active_speakers_are_distinct_from_gallery_size": True,
        "waveforms_copied": False,
        "waveforms_modified": False,
        "evaluation_only": True,
        "training_eligible": False,
        "EVALUATION_NOT_INSPECTED": True,
        "evaluation_authorized": True,
        "v1_preservation": {"protocol_id": V1_PROTOCOL_ID, "authoritative_overlay_counts": V1_OVERLAY_COUNTS},
        "frozen_diarization_selection_sha256": file_sha256(FROZEN_DIARIZATION_SELECTION).lower(),
        "frozen_diarization_selected_pipeline_ids": frozen["selected_pipeline_ids"],
        "scientific_policy_ids": {key: value["policy_id"] for key, value in policies.items()},
        "xvf_available": False,
        "xvf_aoa_available": False,
        "xvf_energy_available": False,
        "xvf_audio_variant": None,
        "xvf_metadata_version": None,
    }
    atomic_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json", summary)
    checksums = checksum_tree(PRODUCT_PROTOCOL_ROOT, exclude_names={"checksums.json"})
    atomic_json(PRODUCT_PROTOCOL_ROOT / "checksums.json", {"schema_version": f"{SCHEMA}-checksums.v1", "files": checksums})
    validation = validate()
    return {"status": "PREPARED", **summary, "validation": validation}


def audit() -> dict[str, object]:
    errors: list[str] = []
    details: dict[str, object] = {}
    for label, fn in (("v1", _validate_v1_preserved), ("frozen_diarization", _validate_frozen_diarization), ("enrollment_evidence", _validate_evidence)):
        try:
            details[label] = fn()
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    for version, cases in (("v1", 60), ("v2", 36)):
        for pipeline in DIARIZATION_PIPELINES:
            root = UPSTREAM_DIARIZATION_ROOT / version / "development" / pipeline
            observed = sum(1 for path in root.glob("*/predictions/segments.rttm") if not path.parent.parent.name.startswith("."))
            if observed != cases:
                errors.append(f"{version}/{pipeline}: expected {cases} frozen diarization cases, found {observed}")
    report = {"schema_version": f"{SCHEMA}-audit.v1", "status": "PASS" if not errors else "FAIL", "errors": errors, "details": details, "evaluation_results_inspected": False, "updated_at_utc": now_utc()}
    atomic_json(RESULT_ROOT / "audit.json", report)
    return report


def validate() -> dict[str, object]:
    errors: list[str] = []
    summary = read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")
    protocol = str(summary["protocol_id"])
    pools = _speaker_pools()
    counts: dict[str, dict[str, int]] = {}
    for corpus, benchmark_root in (("v1", V1_BENCHMARK_ROOT), ("v2", V2_BENCHMARK_ROOT)):
        counts[corpus] = {}
        dev_speakers: set[str] = set()
        eval_speakers: set[str] = set()
        for tier in ("development", "evaluation"):
            cases = {str(row["case_id"]): row for row in read_jsonl(benchmark_root / tier / "case_manifest.jsonl")}
            target_speakers = dev_speakers if tier == "development" else eval_speakers
            for case in cases.values():
                target_speakers.update(map(str, case["global_speaker_ids"]))
            rows = read_jsonl(PRODUCT_PROTOCOL_ROOT / corpus / tier / "identity_overlays.jsonl")
            counts[corpus][tier] = len(rows)
            grouped = Counter(str(row["case_id"]) for row in rows)
            if set(grouped) != set(cases) or any(value != len(OVERLAYS) for value in grouped.values()):
                errors.append(f"{corpus}/{tier} does not have exactly three overlays per case")
            for row in rows:
                case = cases[str(row["case_id"])]
                if row.get("protocol_id") != protocol or row.get("audio_sha256") != case.get("audio_sha256"):
                    errors.append(f"{corpus}/{tier}/{row.get('case_id')} overlay identity mismatch")
                    continue
                live = set(map(str, case["global_speaker_ids"]))
                gallery = {str(item["global_speaker_id"]) for item in row["enrollment_database"]}
                expected_known = {speaker for speaker, state in dict(row["speaker_states"]).items() if dict(state)["identity_state"] == "KNOWN"}
                if not expected_known.issubset(gallery) or any(item["database_role"] == "background_impostor" and str(item["global_speaker_id"]) in live for item in row["enrollment_database"]):
                    errors.append(f"{corpus}/{tier}/{row.get('case_id')}/{row.get('overlay_id')} gallery leakage")
                mixture_ids = _mixture_clip_ids(benchmark_root / str(case["recipe_path"]))
                enrollment_ids = {str(clip["source_clip_id"]) for item in row["enrollment_database"] for clip in item["reserved_enrollment_clips"]}
                if mixture_ids & enrollment_ids:
                    errors.append(f"{corpus}/{tier}/{row.get('case_id')} mixture/enrollment clip leakage")
        if dev_speakers & eval_speakers:
            errors.append(f"{corpus} development/evaluation speakers overlap")
    for backend in BACKEND_POLICY:
        path = POLICY_ROOT / f"{backend}.scientific.yaml"
        try:
            policy = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not policy.get("scientific") or policy.get("source_study_status") != "COMPLETE":
                errors.append(f"{backend} policy is not scientific")
            if float(policy["technical_minimum_evidence_sec"]) != BACKEND_MINIMUM_SEC[backend]:
                errors.append(f"{backend} technical duration policy changed")
        except Exception as exc:
            errors.append(f"{backend} policy invalid: {exc}")
    if set(pools["development"]) & set(pools["evaluation"]):
        errors.append("enrollment development/evaluation pools overlap")
    result = {"schema_version": f"{SCHEMA}-validation.v1", "status": "PASS" if not errors else "FAIL", "errors": errors, "protocol_id": protocol, "overlay_counts": counts, "evaluation_results_inspected": False, "updated_at_utc": now_utc()}
    atomic_json(RESULT_ROOT / "validation.json", result)
    if errors:
        raise ProductV2Error("; ".join(errors[:8]))
    return result


def plan() -> dict[str, object]:
    summary = read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")
    counts = {}
    durations = {}
    for corpus, benchmark_root in (("v1", V1_BENCHMARK_ROOT), ("v2", V2_BENCHMARK_ROOT)):
        cases = read_jsonl(benchmark_root / "development" / "case_manifest.jsonl")
        counts[corpus] = len(cases)
        durations[corpus] = sum(float(row["duration_sec"]) for row in cases)
    planned = {
        "schema_version": f"{SCHEMA}-plan.v1",
        "status": "READY",
        "protocol_id": summary["protocol_id"],
        "development_cases": counts,
        "development_audio_sec_per_diarizer": durations,
        "combinations": list(COMBINATIONS),
        "case_score_bundles": sum(counts.values()) * len(COMBINATIONS),
        "identity_backends": list(BACKEND_POLICY),
        "operating_modes": OPERATING_MODES,
        "evidence_checkpoints_sec": list(EVIDENCE_CHECKPOINTS_SEC),
        "policy_replay_units": sum(counts.values()) * len(COMBINATIONS) * len(OVERLAYS),
        "evaluation_planned": False,
        "evaluation_results_inspected": False,
        "run_sequence": ["independent_identity_embedding_cache", "case_score_bundles", "development_calibration", "policy_replay", "analysis", "selection", "freeze", "collect"],
    }
    atomic_json(RESULT_ROOT / "plan.json", planned)
    return planned


def _overlay(case: Mapping[str, object], overlay_id: str, pool: Mapping[str, Mapping[str, object]], product_protocol_id: str, corpus: str) -> dict[str, object]:
    live = list(map(str, case["global_speaker_ids"]))
    if overlay_id == "ALL_KNOWN":
        known = set(live)
    elif overlay_id == "ALL_UNKNOWN":
        known = set()
    else:
        ordered = stable_order(live, {"case": case["case_id"], "overlay": overlay_id})
        known = set(ordered[: max(1, len(ordered) // 2)]) if len(ordered) > 1 else set()
    background = stable_order((speaker for speaker in pool if speaker not in set(live)), {"case": case["case_id"], "overlay": overlay_id})
    ordered_gallery = stable_order(known, {"case": case["case_id"], "role": "live_known"}) + background
    database = [_database_row(pool[speaker], "live_known" if speaker in known else "background_impostor") for speaker in ordered_gallery]
    gallery_subsets = []
    for requested in GALLERY_SIZES:
        target = len(database) if requested == "full" else int(requested)
        if target < len(known):
            gallery_subsets.append({"requested_size": requested, "status": "NOT_APPLICABLE_LIVE_KNOWN_EXCEEDS_GALLERY", "enrolled_ids": []})
        else:
            selected = [row["enrolled_id"] for row in database[: min(target, len(database))]]
            gallery_subsets.append({"requested_size": requested, "realized_size": len(selected), "status": "VALID", "enrolled_ids": selected, "primary": requested in PRIMARY_GALLERY_SIZES})
    states = {}
    for index, speaker in enumerate(live):
        states[speaker] = {"identity_state": "KNOWN" if speaker in known else "UNKNOWN", "enrolled_id": pool[speaker]["enrolled_id"] if speaker in known else None, "unknown_reference_id": None if speaker in known else f"UNKNOWN_{case['case_id']}_{index:02d}"}
    return {
        "schema_version": f"{SCHEMA}-overlay.v1",
        "protocol_id": product_protocol_id,
        "source_protocol_id": V1_PROTOCOL_ID if corpus == "v1" else V2_BENCHMARK_ID,
        "benchmark_id": case["benchmark_id"],
        "corpus": corpus,
        "tier": case["tier"],
        "case_id": case["case_id"],
        "overlay_id": overlay_id,
        "speaker_count": case["speaker_count"],
        "active_speaker_band": speaker_band(int(case["speaker_count"])),
        "audio_logical_path": case["audio_logical_path"],
        "audio_sha256": case["audio_sha256"],
        "local_to_global_speaker": case["local_to_global_speaker"],
        "speaker_states": states,
        "enrollment_database": database,
        "gallery_subsets": gallery_subsets,
        "waveform_identity_unchanged": True,
        "anonymous_diarization_science_unchanged": True,
        "evaluation_only": True,
        "training_eligible": False,
    }


def _speaker_pools() -> dict[str, dict[str, Mapping[str, object]]]:
    pools: dict[str, dict[str, Mapping[str, object]]] = {"development": {}, "evaluation": {}}
    for tier in pools:
        for row in read_jsonl(V1_PROTOCOL_ROOT / tier / "identity_overlays.jsonl"):
            for item in row["enrollment_database"]:
                if item.get("reserved_enrollment_clips"):
                    pools[tier][str(item["global_speaker_id"])] = item
    return pools


def _database_row(source: Mapping[str, object], role: str) -> dict[str, object]:
    return {"enrolled_id": source["enrolled_id"], "global_speaker_id": source["global_speaker_id"], "database_role": role, "reserved_enrollment_clips": source["reserved_enrollment_clips"]}


def _write_policies(product_protocol_id: str) -> dict[str, dict[str, str]]:
    evidence = _validate_evidence()
    POLICY_ROOT.mkdir(parents=True, exist_ok=True)
    emitted = {}
    for backend, values in BACKEND_POLICY.items():
        identity = evidence["backend_identities"][backend]
        policy = {
            "schema_version": f"{SCHEMA}-scientific-enrollment-policy.v1",
            "policy_id": values["policy_id"],
            "protocol_id": product_protocol_id,
            "scientific": True,
            "source_study_status": "COMPLETE",
            "source_study_id": "speaker_enrollment_live_v2_5107db9ab304",
            "source_study_report": str(EVIDENCE_ROOT / "FINAL_ANALYSIS.md"),
            "source_study_report_sha256": evidence["final_analysis_sha256"],
            "source_deployment_report": str(DEPLOYMENT_ROOT / "REPORT.md"),
            "source_deployment_report_sha256": evidence["deployment_report_sha256"],
            "identity_backend_id": backend,
            "backend_identity": identity,
            "environment_profile": values["environment_profile"],
            "enrollment_utterance_count": values["enrollment_utterance_count"],
            "enrollment_total_target_sec": values["enrollment_total_target_sec"],
            "clip_selection": "first_three_frozen_reserved_clean_diverse_clips",
            "aggregation_method": values["aggregation_method"],
            "cluster_evidence_aggregation": "duration_weighted_normalized_mean",
            "technical_minimum_evidence_sec": BACKEND_MINIMUM_SEC[backend],
            "technical_duration_support": {str(value): ("VALID" if value >= BACKEND_MINIMUM_SEC[backend] else "TECHNICALLY_INVALID") for value in EVIDENCE_CHECKPOINTS_SEC},
            "no_audio_padding": True,
            "open_set_calibration": {"maximum_gallery_score": True, "top1_top2_margin": True, "target_fpir": [0.005, 0.01, 0.02, 0.05], "calibration_only": True},
            "evidence_reference": values["evidence_reference"],
        }
        path = POLICY_ROOT / f"{backend}.scientific.yaml"
        sha = write_yaml(path, policy)
        emitted[backend] = {"policy_id": str(values["policy_id"]), "path": str(path), "sha256": sha}
    return emitted


def _validate_v1_preserved() -> dict[str, object]:
    summary = read_json(V1_PROTOCOL_ROOT / "protocol_summary.json")
    if summary.get("protocol_id") != V1_PROTOCOL_ID or summary.get("overlay_counts") != V1_OVERLAY_COUNTS:
        raise ProductV2Error("Hybrid V1 identity/counts changed")
    checksums = read_json(V1_PROTOCOL_ROOT / "checksums.json")
    bad = []
    for relative, row in dict(checksums.get("entries") or {}).items():
        path = V1_PROTOCOL_ROOT / str(relative)
        if not path.is_file() or file_sha256(path).upper() != str(dict(row)["sha256"]).upper():
            bad.append(str(relative))
    if bad:
        raise ProductV2Error(f"Hybrid V1 checksum mismatch: {bad[:3]}")
    return {"protocol_id": V1_PROTOCOL_ID, "overlay_counts": summary["overlay_counts"], "checksums_valid": True}


def _validate_frozen_diarization() -> dict[str, object]:
    frozen = yaml.safe_load(FROZEN_DIARIZATION_SELECTION.read_text(encoding="utf-8"))
    if not frozen.get("EVALUATION_NOT_INSPECTED") or frozen.get("selected_pipeline_ids") != list(DIARIZATION_PIPELINES):
        raise ProductV2Error("frozen diarization selection is incompatible")
    selected = {str(row["pipeline_id"]): str(row["configuration_sha256"]) for row in frozen["selected_pipelines"]}
    if selected != DIARIZATION_PIPELINES:
        raise ProductV2Error("frozen diarization configuration hash mismatch")
    return {"selected_pipeline_ids": frozen["selected_pipeline_ids"], "configuration_hashes": selected, "sha256": file_sha256(FROZEN_DIARIZATION_SELECTION).lower(), "EVALUATION_NOT_INSPECTED": True}


def _validate_evidence() -> dict[str, object]:
    report = EVIDENCE_ROOT / "FINAL_ANALYSIS.md"
    deployment = DEPLOYMENT_ROOT / "REPORT.md"
    if not report.is_file() or not deployment.is_file():
        raise ProductV2Error("completed speaker enrollment evidence is missing")
    identities = {}
    for backend in BACKEND_POLICY:
        candidates = list((EVIDENCE_ROOT / backend).glob("**/backend_identity.json")) + list((EVIDENCE_ROOT / backend).glob("**/speaker_backend_identity.json"))
        if not candidates:
            candidates = list((EVIDENCE_ROOT / backend).glob("**/*identity*.json"))
        selected = None
        for path in candidates:
            value = read_json(path)
            if value.get("backend_id") == backend and value.get("identity_hash"):
                selected = value
                break
        if selected is None:
            # The completed study stores the canonical identity beside cached observations.
            summaries = list((EVIDENCE_ROOT / backend).glob("**/cache_summary.json"))
            for path in summaries:
                value = read_json(path)
                identity = value.get("backend_identity")
                if isinstance(identity, dict) and identity.get("backend_id") == backend:
                    selected = identity
                    break
        if selected is None:
            raise ProductV2Error(f"canonical completed-study identity missing for {backend}")
        identities[backend] = selected
    return {"status": "COMPLETE", "final_analysis_sha256": file_sha256(report).lower(), "deployment_report_sha256": file_sha256(deployment).lower(), "backend_identities": identities}


def _mixture_clip_ids(recipe_path: Path) -> set[str]:
    value = read_json(recipe_path)
    found: set[str] = set()
    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key in {"source_clip_id", "clip_id"} and isinstance(child, str):
                    found.add(child)
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    return found


def _prepare_chime_protocol(product_protocol_id: str) -> None:
    # Current installed CHiME metadata is recording/session-level and cannot prove
    # utterance-disjoint close-mic enrollment against synchronized far-field probes.
    # We preserve that limitation instead of manufacturing a scientific split.
    value = {
        "schema_version": f"{SCHEMA}-chime6-preparation.v1",
        "status": "CHIME6_HYBRID_PREPARED_WITH_LIMITATIONS",
        "protocol_id": product_protocol_id,
        "scientific_final_evaluation_runnable": False,
        "engineering_smoke_run": False,
        "limitation": "installed metadata does not prove utterance/time-disjoint participant-close enrollment versus synchronized far-field probes",
        "required_future_split": ["disjoint enrollment/probe intervals", "no synchronized close/far utterance reuse", "prefer different sessions", "speaker/session-disjoint calibration and evaluation"],
        "final_native_evaluation_run": False,
    }
    atomic_json(PRODUCT_PROTOCOL_ROOT / "native_chime6" / "protocol_preparation.json", value)
