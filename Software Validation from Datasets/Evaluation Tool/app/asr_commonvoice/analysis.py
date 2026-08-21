"""Deterministic analysis for completed Common Voice 60+ ASR results."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from app.diarization_evaluation.artifacts import (
    write_json_atomic,
    write_parquet_atomic,
    write_text_atomic,
)

from .contracts import (
    ANALYSIS_SCHEMA_VERSION,
    ASRCommonVoiceError,
    MODEL_COMPONENT_IDS,
    SEED,
    canonical_sha256,
)
from .protocol import read_manifest, validate_protocol
from .runner import validate_backend


def analyze(result_root: Path, protocol_root: Path) -> dict[str, object]:
    """Build every frozen comparison table without running inference."""

    result_root = result_root.resolve()
    protocol = validate_protocol(protocol_root)
    manifest = {str(row["item_id"]): row for row in read_manifest(protocol_root)}
    identities: dict[str, dict[str, object]] = {}
    results: dict[str, list[dict[str, object]]] = {}
    mode: str | None = None
    for component in MODEL_COMPONENT_IDS:
        backend = result_root / component
        validation = validate_backend(backend, protocol_root)
        if not validation["valid"]:
            raise ASRCommonVoiceError(f"cannot analyze incomplete backend: {component}")
        identity = _read_json(backend / "backend_identity.json")
        identities[component] = identity
        current_mode = str(identity["mode"])
        if mode is not None and current_mode != mode:
            raise ASRCommonVoiceError("backend result modes cannot be mixed")
        mode = current_mode
        results[component] = [
            dict(row) for row in pq.read_table(backend / "utterance_results.parquet").to_pylist()
        ]

    analysis_root = result_root / "analysis"
    analysis_root.mkdir(parents=True, exist_ok=True)
    utterances: list[dict[str, object]] = []
    for component in MODEL_COMPONENT_IDS:
        for result in results[component]:
            source = manifest[str(result["item_id"])]
            utterances.append({
                "component_id": component,
                "item_id": result["item_id"],
                "speaker_key": source["speaker_key"],
                "speaker_role": source["speaker_role"],
                "protocol_split": source["protocol_split"],
                "age_category": source["age_category"],
                "age_group": source["age_group"],
                "logical_audio_path": source["logical_audio_path"],
                "source_recording_id": source["source_recording_id"],
                "duration_sec": source["duration_sec"],
                "duration_bucket": source["duration_bucket"],
                "reference_words": result["reference_words"],
                "transcript_length_bucket": source["transcript_length_bucket"],
                "reference_text": result["reference_text"],
                "hypothesis_raw": result["hypothesis_raw"],
                "hypothesis_text": result["hypothesis_text"],
                "hypothesis_normalized": result["hypothesis_normalized"],
                "wer": result["wer"],
                "cer": result["cer"],
                "errors": result["errors"],
                "substitutions": result["substitutions"],
                "deletions": result["deletions"],
                "insertions": result["insertions"],
                "hypothesis_words": result["hypothesis_words"],
                "empty_output": not bool(result["hypothesis_normalized"]),
                "elapsed_sec": result["elapsed_sec"],
                "realtime_factor": result["realtime_factor"],
                "inference_status": result["status"],
                "environment_profile": identities[component]["model"]["environment_profile"],
                "runtime": identities[component]["model"]["runtime"],
                "device": identities[component]["model"]["device"],
                "precision": identities[component]["model"]["precision"],
            })

    overall = [_aggregate(component, results[component], manifest) for component in MODEL_COMPONENT_IDS]
    per_speaker = _group_table(utterances, ("component_id", "speaker_key"))
    by_age = _group_table(utterances, ("component_id", "age_category"))
    by_age_group = _group_table(utterances, ("component_id", "age_group"))
    by_duration = _group_table(utterances, ("component_id", "duration_bucket"))
    by_length = _group_table(utterances, ("component_id", "transcript_length_bucket"))
    error_distribution = [_error_distribution(row) for row in utterances]
    resources = [_resource(component, results[component], identities[component]) for component in MODEL_COMPONENT_IDS]
    reliability = [_reliability(component, results[component]) for component in MODEL_COMPONENT_IDS]
    pairwise = _pairwise_bootstrap(utterances)
    examples = _qualitative_examples(utterances)

    tables = {
        "overall_results": overall,
        "utterance_results": utterances,
        "speaker_results": per_speaker,
        "age_category_results": by_age,
        "age_group_results": by_age_group,
        "duration_results": by_duration,
        "transcript_length_results": by_length,
        "error_component_results": error_distribution,
        "resource_results": resources,
        "reliability_summary": reliability,
        "pairwise_results": pairwise,
        "error_examples": examples,
    }
    written: dict[str, dict[str, str]] = {}
    for name, rows in tables.items():
        if not rows:
            continue
        parquet_path = analysis_root / f"{name}.parquet"
        csv_path = analysis_root / f"{name}.csv"
        write_parquet_atomic(parquet_path, pa.Table.from_pylist(rows))
        _write_csv(csv_path, rows)
        written[name] = {"parquet": parquet_path.name, "csv": csv_path.name}

    summary = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "analysis_id": f"analysis_{canonical_sha256({'protocol': protocol['protocol_id'], 'mode': mode, 'overall': overall})[:16].lower()}",
        "protocol_id": protocol["protocol_id"],
        "campaign_id": identities[MODEL_COMPONENT_IDS[0]]["campaign_id"],
        "mode": mode,
        "scientific_use_prohibited": mode == "smoke_non_scientific",
        "models": list(MODEL_COMPONENT_IDS),
        "bootstrap": {
            "unit": "speaker",
            "repetitions": 500,
            "seed": SEED,
            "confidence_level": 0.95,
        },
        "overall": overall,
        "tables": written,
        "limitations": [
            "Common Voice is primarily prompted/read speech.",
            "Recording equipment and acoustic conditions vary.",
            "The self-reported 60+ cohort is not necessarily representative of product users.",
            "This campaign tests ASR generalization and does not replace prior ASR analysis.",
            "It does not measure far-field XVF3800 performance or conversational overlap.",
            "Resource comparisons are meaningful only on comparable machine/device conditions.",
        ],
    }
    write_json_atomic(analysis_root / "analysis_manifest.json", summary)
    write_json_atomic(analysis_root / "model_identities.json", identities)
    write_text_atomic(analysis_root / "report.md", _report(summary, pairwise, resources))
    return summary


def _aggregate(component: str, rows: Sequence[Mapping[str, object]], manifest: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    words = sum(int(row["reference_words"]) for row in rows)
    chars = sum(len(str(row["reference_normalized"]).replace(" ", "")) for row in rows)
    return {
        "component_id": component,
        "utterances": len(rows),
        "speakers": len({manifest[str(row["item_id"])]["speaker_key"] for row in rows}),
        "reference_words": words,
        "word_errors": sum(int(row["errors"]) for row in rows),
        "wer": sum(int(row["errors"]) for row in rows) / words if words else None,
        "cer": sum(float(row["cer"]) * len(str(row["reference_normalized"]).replace(" ", "")) for row in rows) / chars if chars else None,
        "empty_output_rate": sum(not str(row["hypothesis_normalized"]) for row in rows) / len(rows),
        "mean_utterance_wer": float(np.mean([float(row["wer"]) for row in rows])),
        "median_utterance_wer": float(np.median([float(row["wer"]) for row in rows])),
        "p90_utterance_wer": float(np.quantile([float(row["wer"]) for row in rows], 0.90)),
    }


def _group_table(rows: Sequence[Mapping[str, object]], keys: tuple[str, ...]) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[Mapping[str, object]]] = {}
    for row in rows:
        groups.setdefault(tuple(str(row[key]) for key in keys), []).append(row)
    result = []
    for values, group in sorted(groups.items()):
        words = sum(int(row["reference_words"]) for row in group)
        result.append({
            **dict(zip(keys, values)),
            "utterances": len(group),
            "speakers": len({str(row["speaker_key"]) for row in group}),
            "reference_words": words,
            "word_errors": sum(int(row["errors"]) for row in group),
            "wer": sum(int(row["errors"]) for row in group) / words if words else None,
            "mean_utterance_wer": float(np.mean([float(row["wer"]) for row in group])),
            "empty_output_rate": sum(bool(row["empty_output"]) for row in group) / len(group),
            "audio_duration_sec": sum(float(row["duration_sec"]) for row in group),
        })
    return result


def _error_distribution(row: Mapping[str, object]) -> dict[str, object]:
    if row["empty_output"]:
        category = "empty"
    elif int(row["errors"]) == 0:
        category = "exact"
    elif float(row["wer"]) <= 0.25:
        category = "wer_0_to_0.25"
    elif float(row["wer"]) <= 0.50:
        category = "wer_0.25_to_0.50"
    elif float(row["wer"]) <= 1.0:
        category = "wer_0.50_to_1.00"
    else:
        category = "wer_gt_1.00"
    return {"component_id": row["component_id"], "item_id": row["item_id"], "speaker_key": row["speaker_key"], "age_category": row["age_category"], "error_category": category, "wer": row["wer"], "errors": row["errors"]}


def _resource(component: str, rows: Sequence[Mapping[str, object]], identity: Mapping[str, object]) -> dict[str, object]:
    elapsed = sum(float(row["elapsed_sec"]) for row in rows)
    audio = sum(float(row["duration_sec"]) for row in rows)
    load_times = [
        float(runtime["load_sec"])
        for row in rows
        if isinstance((runtime := row.get("asr_backend_runtime")), Mapping)
        and runtime.get("load_sec") is not None
    ]
    return {
        "component_id": component,
        "environment_profile": identity["model"]["environment_profile"],
        "device": identity["model"]["device"],
        "precision": identity["model"]["precision"],
        "runtime": identity["model"]["runtime"],
        "utterances": len(rows),
        "audio_duration_sec": audio,
        "summed_item_elapsed_sec": elapsed,
        "realtime_factor": elapsed / audio,
        "mean_item_elapsed_sec": elapsed / len(rows),
        "max_reported_load_sec": max(load_times) if load_times else None,
        "throughput_clips_per_sec": len(rows) / elapsed if elapsed else None,
        "peak_process_rss_mb": max(float(row.get("process_rss_mb") or 0.0) for row in rows),
        "summed_process_cpu_sec": sum(float(row.get("process_cpu_sec") or 0.0) for row in rows),
        "model_asset_bytes": sum(int(asset.get("observed_bytes") or asset.get("expected_bytes") or 0) for asset in identity["model"]["model_assets"]),
        "host_node": identity["host"]["node"],
        "host_processor": identity["host"]["processor"],
    }


def _reliability(component: str, rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "component_id": component,
        "attempted_items": len(rows),
        "successful_items": sum(row["status"] == "ok" for row in rows),
        "failed_items": sum(row["status"] != "ok" for row in rows),
        "empty_output_count": sum(not str(row.get("hypothesis_normalized") or "") for row in rows),
        "warning_item_count": sum(bool(row.get("warnings")) for row in rows),
        "decode_error_count": sum(row.get("error_type") in {"LibsndfileError", "RuntimeError"} for row in rows if row.get("status") != "ok"),
        "scoring_error_count": 0,
        "valid_output_rate": sum(row["status"] == "ok" and bool(str(row.get("hypothesis_normalized") or "")) for row in rows) / len(rows),
    }


def _pairwise_bootstrap(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    by_model = {
        model: {str(row["item_id"]): row for row in rows if row["component_id"] == model}
        for model in MODEL_COMPONENT_IDS
    }
    result = []
    rng = np.random.default_rng(SEED)
    for left_index, left in enumerate(MODEL_COMPONENT_IDS):
        for right in MODEL_COMPONENT_IDS[left_index + 1 :]:
            common = sorted(set(by_model[left]) & set(by_model[right]))
            speakers: dict[str, list[str]] = {}
            for item_id in common:
                speaker = str(by_model[left][item_id]["speaker_key"])
                speakers.setdefault(speaker, []).append(item_id)
            speaker_ids = sorted(speakers)
            observed = _pair_delta(by_model[left], by_model[right], common)
            utterance_deltas = [float(by_model[left][item]["wer"]) - float(by_model[right][item]["wer"]) for item in common]
            replicates = []
            for _ in range(500):
                sampled = rng.choice(speaker_ids, size=len(speaker_ids), replace=True)
                item_ids = [item for speaker in sampled for item in speakers[str(speaker)]]
                replicates.append(_pair_delta(by_model[left], by_model[right], item_ids))
            result.append({
                "model_a": left,
                "model_b": right,
                "metric": "wer_a_minus_wer_b",
                "paired_items": len(common),
                "speaker_clusters": len(speaker_ids),
                "observed_difference": observed,
                "model_a_wins": sum(value < 0 for value in utterance_deltas),
                "ties": sum(value == 0 for value in utterance_deltas),
                "model_b_wins": sum(value > 0 for value in utterance_deltas),
                "ci95_lower": float(np.quantile(replicates, 0.025)),
                "ci95_upper": float(np.quantile(replicates, 0.975)),
                "bootstrap_probability_a_lower_wer": float(np.mean(np.asarray(replicates) < 0.0)),
                "bootstrap_repetitions": 500,
                "bootstrap_seed": SEED,
            })
    return result


def _pair_delta(left: Mapping[str, Mapping[str, object]], right: Mapping[str, Mapping[str, object]], items: Sequence[str]) -> float:
    left_words = sum(int(left[item]["reference_words"]) for item in items)
    right_words = sum(int(right[item]["reference_words"]) for item in items)
    left_wer = sum(int(left[item]["errors"]) for item in items) / left_words
    right_wer = sum(int(right[item]["errors"]) for item in items) / right_words
    return left_wer - right_wer


def _qualitative_examples(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    matrix: dict[str, dict[str, Mapping[str, object]]] = {}
    for row in rows:
        matrix.setdefault(str(row["item_id"]), {})[str(row["component_id"])] = row
    candidates: list[tuple[str, float, str, Mapping[str, Mapping[str, object]]]] = []
    for item_id, model_rows in matrix.items():
        if set(model_rows) != set(MODEL_COMPONENT_IDS):
            continue
        wers = [float(model_rows[model]["wer"]) for model in MODEL_COMPONENT_IDS]
        candidates.append(("largest_model_disagreement", max(wers) - min(wers), item_id, model_rows))
        if all(value > 0 for value in wers):
            candidates.append(("all_three_error", sum(wers), item_id, model_rows))
        if sum(value <= 0.10 for value in wers) == 1 and sum(value >= 0.50 for value in wers) >= 2:
            candidates.append(("only_one_substantially_right", max(wers) - min(wers), item_id, model_rows))
        for label, field in (("deletion_heavy", "deletions"), ("insertion_heavy", "insertions"), ("substitution_heavy", "substitutions")):
            score = sum(int(model_rows[model][field]) for model in MODEL_COMPONENT_IDS)
            if score:
                candidates.append((label, float(score), item_id, model_rows))
    result: list[dict[str, object]] = []
    for category in sorted({row[0] for row in candidates}):
        selected = sorted(
            (row for row in candidates if row[0] == category),
            key=lambda row: (-row[1], canonical_sha256({"seed": SEED, "item_id": row[2]})),
        )[:20]
        for rank, (_category, score, item_id, model_rows) in enumerate(selected, start=1):
            exemplar = model_rows[MODEL_COMPONENT_IDS[0]]
            result.append({
                "selection_category": category,
                "rank": rank,
                "selection_score": score,
                "item_id": item_id,
                "speaker_key": exemplar["speaker_key"],
                "age_category": exemplar["age_category"],
                "reference_text": exemplar["reference_text"],
                "original_sherpa_hypothesis": model_rows[MODEL_COMPONENT_IDS[0]]["hypothesis_text"],
                "original_sherpa_wer": model_rows[MODEL_COMPONENT_IDS[0]]["wer"],
                "sherpa_giga_hypothesis": model_rows[MODEL_COMPONENT_IDS[1]]["hypothesis_text"],
                "sherpa_giga_wer": model_rows[MODEL_COMPONENT_IDS[1]]["wer"],
                "whisper_small_hypothesis": model_rows[MODEL_COMPONENT_IDS[2]]["hypothesis_text"],
                "whisper_small_wer": model_rows[MODEL_COMPONENT_IDS[2]]["wer"],
            })
    return result


def _report(summary: Mapping[str, object], pairwise: Sequence[Mapping[str, object]], resources: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# Common Voice 60+ ASR generalization comparison",
        "",
        f"Protocol: `{summary['protocol_id']}`  ",
        f"Mode: `{summary['mode']}`  ",
        f"Scientific use prohibited: `{str(summary['scientific_use_prohibited']).lower()}`",
        "",
        "This comparison adds a controlled older-speaker generalization view for the three",
        "already-qualified ASR components. It does not replace their prior analyses.",
        "",
        "## Overall",
        "",
        "| Model | Utterances | Speakers | WER | CER | Empty rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary["overall"]:
        lines.append(f"| {row['component_id']} | {row['utterances']} | {row['speakers']} | {row['wer']:.4f} | {row['cer']:.4f} | {row['empty_output_rate']:.4f} |")
    lines.extend(["", "## Paired speaker-cluster bootstrap", "", "Differences are WER(model A) minus WER(model B); negative favors model A.", "", "| Model A | Model B | Difference | 95% CI | P(A lower) |", "|---|---|---:|---:|---:|"])
    for row in pairwise:
        lines.append(f"| {row['model_a']} | {row['model_b']} | {row['observed_difference']:.4f} | [{row['ci95_lower']:.4f}, {row['ci95_upper']:.4f}] | {row['bootstrap_probability_a_lower_wer']:.3f} |")
    lines.extend(["", "## Resource context", "", "Resource comparisons require the same host and device.", "", "| Model | Environment | RTF | Runtime |", "|---|---|---:|---|"])
    for row in resources:
        lines.append(f"| {row['component_id']} | {row['environment_profile']} | {row['realtime_factor']:.4f} | {row['runtime']} |")
    lines.extend(["", "## Limitations", ""] + [f"- {item}" for item in summary["limitations"]] + [""])
    return "\n".join(lines)


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    columns = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in columns})


def _csv_value(value: object) -> object:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return value


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ASRCommonVoiceError(f"expected JSON object: {path}")
    return value
