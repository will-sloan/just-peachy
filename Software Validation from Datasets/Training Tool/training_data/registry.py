"""Freeze a portable training-data inventory without decoding, training, or downloading.

The builder deliberately uses the repository's normalized metadata.  It never
opens a waveform, probes every source file, or creates training splits.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


SCHEMA = "training-data-registry.v1"
EXCLUSION_SCHEMA = "evaluation-exclusion-index.v1"
FREEZE_SCHEMA = "training-data-freeze.v1"

DATASETS = {
    "CMU_Arctic": "cmu_arctic",
    "LibriSpeech": "librispeech",
    "HiFiTTS": "hifitts",
    "AMI": "ami",
    "CHiME_6": "chime6",
    "VOiCES": "voices",
}

REGISTRY_COLUMNS = [
    "registry_schema_version", "dataset_id", "dataset_version", "upstream_split",
    "source_item_id", "source_recording_id", "source_utterance_id",
    "source_audio_logical_path", "resolved_audio_path", "transcript",
    "transcript_sha256", "speaker_id", "speaker_group_id", "session_id",
    "meeting_id", "chapter_id", "book_id", "reader_id", "source_corpus_id",
    "source_parent_utterance_id", "cross_source_key", "language",
    "duration_seconds", "sample_rate_hz", "channels", "gender", "accent",
    "age_metadata", "license_id", "license_policy_status",
    "commercial_training_status", "technical_training_status",
    "commercial_release_review_status", "attribution_required", "sharealike_flag",
    "source_available", "evaluation_exact_match", "evaluation_group_match",
    "evaluation_cross_dataset_match", "technical_training_eligible",
    "commercial_training_eligible", "review_gated_training_eligible",
    "strict_training_eligible", "relaxed_training_eligible", "exclusion_reason",
]


def _json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest().upper()


def _frame_hash(frame: pd.DataFrame, *, omit: Iterable[str] = ()) -> str:
    """Hash sorted logical fields in chunks; local absolute paths are always omitted.

    Pandas' stable row hashing avoids serializing a second giant JSON copy of
    the registry.  The selected column order is part of the digest.
    """
    omitted = set(omit)
    columns = [column for column in frame.columns if column not in omitted]
    digest = hashlib.sha256()
    digest.update(json.dumps(columns, separators=(",", ":")).encode("utf-8"))
    for start in range(0, len(frame), 100_000):
        chunk = frame.iloc[start : start + 100_000][columns]
        row_hashes = pd.util.hash_pandas_object(chunk, index=False, categorize=True)
        digest.update(row_hashes.to_numpy(dtype="uint64", copy=False).tobytes())
    return digest.hexdigest().upper()


def _text_hash(value: pd.Series) -> pd.Series:
    return value.fillna("").map(
        lambda text: hashlib.sha256(str(text).encode("utf-8")).hexdigest().upper() if text else None
    )


def _column(frame: pd.DataFrame, name: str, default: object = pd.NA) -> pd.Series:
    if name in frame:
        return frame[name]
    return pd.Series(default, index=frame.index)


def _logical(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).replace("\\", "/")
    marker = "Raw Datasets (Not formatted)/"
    return text[text.index(marker) :] if marker in text else text


def _logical_series(value: pd.Series) -> pd.Series:
    return value.map(_logical)


def _as_string(value: pd.Series) -> pd.Series:
    return value.astype("string").replace({"<NA>": pd.NA, "nan": pd.NA})


def _cross_key(dataset: str, frame: pd.DataFrame) -> pd.Series:
    """Return a proven VOiCES/LibriSpeech original-source key when available."""
    if dataset == "librispeech":
        parts = _as_string(_column(frame, "utterance_id")).str.split("-", expand=True)
        if parts.shape[1] < 3:
            return pd.Series(pd.NA, index=frame.index, dtype="string")
        speaker = pd.to_numeric(parts[0], errors="coerce").astype("Int64").astype("string")
        chapter = pd.to_numeric(parts[1], errors="coerce").astype("Int64").astype("string")
        segment = pd.to_numeric(parts[2], errors="coerce").astype("Int64").astype("string")
    elif dataset == "voices":
        speaker = pd.to_numeric(_column(frame, "speaker_id_padded", _column(frame, "speaker_id")), errors="coerce").astype("Int64").astype("string")
        chapter = pd.to_numeric(_column(frame, "chapter_id"), errors="coerce").astype("Int64").astype("string")
        segment = pd.to_numeric(_column(frame, "segment_id"), errors="coerce").astype("Int64").astype("string")
    else:
        return pd.Series(pd.NA, index=frame.index, dtype="string")
    result = "librispeech-source:" + speaker + ":" + chapter + ":" + segment
    return result.where(speaker.notna() & chapter.notna() & segment.notna(), pd.NA)


def _strict_group(dataset: str, frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    fields = {
        "cmu_arctic": ("speaker", "speaker_id"),
        "librispeech": ("speaker", "speaker_id"),
        "hifitts": ("reader", "reader_id"),
        "ami": ("meeting", "meeting_id"),
        "chime6": ("session", "session_id"),
        "voices": ("source_speaker", "speaker_id_padded"),
    }
    group_type, field = fields[dataset]
    value = _as_string(_column(frame, field))
    if dataset == "voices":
        value = value.str.lstrip("0").replace("", "0")
    group_id = (dataset + ":" + group_type + ":" + value).where(value.notna(), pd.NA)
    return pd.Series(group_type, index=frame.index), group_id


def _relative_resolved(data_root: Path, logical_paths: pd.Series) -> pd.Series:
    return logical_paths.map(lambda value: str(data_root / Path(value)) if pd.notna(value) else None)


def load_policy(source_root: Path) -> dict[str, Any]:
    return json.loads((source_root / "license_policy.v1.json").read_text(encoding="utf-8"))


def _policy_evidence(policy: dict[str, Any], data_root: Path) -> dict[str, Any]:
    """Validate only small local licence files, never raw audio."""
    records: dict[str, Any] = {}
    for dataset, value in policy["datasets"].items():
        record = {key: content for key, content in value.items() if key != "notes"}
        logical = value.get("local_license_logical_path")
        if logical:
            path = data_root / logical
            if not path.is_file():
                raise FileNotFoundError(f"Required local licence evidence is missing for {dataset}: {path}")
            observed = hashlib.sha256(path.read_bytes()).hexdigest().upper()
            if observed != value.get("local_license_sha256"):
                raise ValueError(f"Local licence evidence changed for {dataset}: {logical}")
            record["local_license_verified_sha256"] = observed
        records[dataset] = record
    return records


def _manifest_frame(path: Path) -> pd.DataFrame | None:
    probe = pd.read_parquet(path)
    if not {"dataset", "source_recording_id"}.issubset(probe.columns):
        return None
    wanted = [
        "dataset", "source_recording_id", "source_utterance_id", "audio_path_project_relative",
        "source_audio_path_project_relative", "speaker_id", "speaker_id_ref", "reader_id",
        "session_id", "meeting_id", "chapter_id", "book_id", "segment_id", "start_sec", "end_sec",
    ]
    selected = pd.DataFrame(index=probe.index)
    for name in wanted:
        selected[name] = _column(probe, name)
    return selected


def evaluation_inputs(tool_root: Path) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Discover every benchmark parquet that contains authoritative source IDs."""
    benchmark_root = tool_root / "benchmarks"
    parts: list[pd.DataFrame] = []
    identities: list[dict[str, Any]] = []
    for path in sorted(benchmark_root.rglob("*.parquet")):
        frame = _manifest_frame(path)
        if frame is None:
            continue
        relative = path.relative_to(tool_root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        identities.append(
            {
                "manifest_id": f"manifest_{digest[:12].lower()}",
                "canonical_path": relative,
                "sha256": digest,
                "row_count": int(len(frame)),
                "dataset_composition": {str(key): int(value) for key, value in frame.groupby("dataset").size().items()},
            }
        )
        frame["manifest_reference"] = relative
        parts.append(frame)
    if not parts:
        raise FileNotFoundError(f"No source-identified benchmark parquet files found under {benchmark_root}")
    raw = pd.concat(parts, ignore_index=True)
    raw["dataset"] = _as_string(raw["dataset"])
    raw["source_recording_id"] = _as_string(raw["source_recording_id"])
    raw["source_utterance_id"] = _as_string(raw["source_utterance_id"])
    raw["source_audio_logical_path"] = _logical_series(raw["audio_path_project_relative"])
    raw["source_original_audio_logical_path"] = _logical_series(raw["source_audio_path_project_relative"])
    raw["speaker_id"] = _as_string(raw["speaker_id"]).fillna(_as_string(raw["speaker_id_ref"]))
    raw["reader_id"] = _as_string(raw["reader_id"])
    raw["strict_group_type"], raw["strict_group_id"] = _strict_group(raw["dataset"].iloc[0], raw) if raw["dataset"].nunique() == 1 else (None, None)
    grouped_parts = []
    for dataset, dataset_frame in raw.groupby("dataset", sort=True, dropna=False):
        group_type, group_id = _strict_group(str(dataset), dataset_frame)
        copy = dataset_frame.copy()
        copy["strict_group_type"] = group_type
        copy["strict_group_id"] = group_id
        # _cross_key expects normalized names, which the manifest shares for these two datasets.
        copy["cross_source_key"] = _cross_key(str(dataset), copy.rename(columns={"source_utterance_id": "utterance_id"}))
        grouped_parts.append(copy)
    raw = pd.concat(grouped_parts, ignore_index=True)
    keys = ["dataset", "source_recording_id", "source_utterance_id", "source_audio_logical_path"]
    keep = [
        "source_original_audio_logical_path", "speaker_id", "reader_id", "session_id", "meeting_id",
        "chapter_id", "book_id", "strict_group_type", "strict_group_id", "cross_source_key",
    ]
    aggregate = {column: "first" for column in keep}
    aggregate["manifest_reference"] = lambda values: ",".join(sorted(set(map(str, values))))
    index = raw.groupby(keys, dropna=False, as_index=False).agg(aggregate)
    index.insert(0, "exclusion_schema_version", EXCLUSION_SCHEMA)
    return index.sort_values(keys, kind="stable").reset_index(drop=True), identities


def _base_frame(dataset: str, recordings: pd.DataFrame, utterances: pd.DataFrame, data_root: Path) -> pd.DataFrame:
    """Turn trusted normalized metadata into a segment-level registry frame."""
    if dataset in {"cmu_arctic", "librispeech", "hifitts", "voices"}:
        text_column = {"cmu_arctic": "text_original", "librispeech": "text_original", "hifitts": "text", "voices": "text_original"}[dataset]
        utterance_columns = ["recording_id", text_column]
        for name in ("utterance_id", "audio_path", "distant_audio_path", "source_audio_path"):
            if name in utterances and name not in utterance_columns:
                utterance_columns.append(name)
        frame = recordings.merge(utterances[utterance_columns], on="recording_id", how="left", suffixes=("", "_utterance"), validate="one_to_one")
    elif dataset == "ami":
        recording_columns = ["recording_id", "audio_path", "sample_rate_hz", "num_channels", "duration_sec"]
        frame = utterances.merge(recordings[recording_columns], on="recording_id", how="left", validate="many_to_one")
    elif dataset == "chime6":
        close = recordings.loc[recordings["stream_type"].eq("participant_close"), [
            "split", "session_id", "speaker_id_ref", "recording_id", "audio_path", "sample_rate_hz", "num_channels",
        ]]
        frame = utterances.merge(close, on=["split", "session_id", "speaker_id_ref"], how="left", validate="many_to_one")
    else:  # pragma: no cover - guarded by DATASETS
        raise ValueError(dataset)

    out = pd.DataFrame(index=frame.index)
    out["registry_schema_version"] = SCHEMA
    out["dataset_id"] = dataset
    out["upstream_split"] = _column(frame, "split", _column(frame, "seen_type"))
    out["source_recording_id"] = _as_string(_column(frame, "recording_id"))
    if dataset == "ami":
        out["source_utterance_id"] = _as_string(_column(frame, "segment_ref_id"))
        out["source_item_id"] = out["source_recording_id"] + ":" + out["source_utterance_id"]
        audio = _column(frame, "audio_path")
        transcript = _column(frame, "text_original")
        duration = pd.to_numeric(_column(frame, "end_sec"), errors="coerce") - pd.to_numeric(_column(frame, "start_sec"), errors="coerce")
        out["speaker_id"] = _column(frame, "speaker_global_name")
    elif dataset == "chime6":
        out["source_utterance_id"] = _as_string(_column(frame, "utterance_key"))
        out["source_item_id"] = out["source_utterance_id"]
        audio = _column(frame, "audio_path")
        transcript = _column(frame, "text_original")
        duration = pd.to_numeric(_column(frame, "duration_sec"), errors="coerce")
        out["speaker_id"] = _column(frame, "speaker_id_ref")
    else:
        utterance_id = _column(frame, "utterance_id", _column(frame, "recording_id"))
        if dataset == "hifitts":
            utterance_id = _column(frame, "recording_id")
        if dataset == "voices":
            utterance_id = _as_string(_column(frame, "speaker_id_padded")) + ":" + _as_string(_column(frame, "chapter_id")) + ":" + _as_string(_column(frame, "segment_id"))
        out["source_utterance_id"] = _as_string(utterance_id)
        out["source_item_id"] = out["source_recording_id"]
        audio = _column(frame, "distant_audio_path", _column(frame, "audio_path"))
        transcript = _column(frame, text_column)
        duration = pd.to_numeric(_column(frame, "duration_sec", _column(frame, "duration_sec_audio", _column(frame, "distant_duration_sec"))), errors="coerce")
        out["speaker_id"] = _column(frame, "speaker_id", _column(frame, "reader_id"))

    out["source_audio_logical_path"] = _logical_series(audio)
    out["resolved_audio_path"] = _relative_resolved(data_root, out["source_audio_logical_path"])
    out["transcript"] = transcript
    out["transcript_sha256"] = _text_hash(out["transcript"])
    out["session_id"] = _column(frame, "session_id")
    out["meeting_id"] = _column(frame, "meeting_id")
    out["chapter_id"] = _column(frame, "chapter_id")
    out["book_id"] = _column(frame, "book_id")
    out["reader_id"] = _column(frame, "reader_id")
    out["source_corpus_id"] = dataset
    # CMU Arctic deliberately reuses prompt IDs for different speakers; the
    # recording is the distinct source-speech identity there. AMI and VOiCES
    # intentionally share a parent identity across microphone copies.
    out["source_parent_utterance_id"] = (
        out["source_recording_id"] if dataset == "cmu_arctic" else out["source_utterance_id"]
    )
    out["cross_source_key"] = _cross_key(dataset, frame)
    out["language"] = "en"
    out["duration_seconds"] = duration
    out["sample_rate_hz"] = _column(frame, "sample_rate_hz", _column(frame, "distant_sample_rate_hz"))
    out["channels"] = _column(frame, "num_channels")
    out["gender"] = _column(frame, "gender", _column(frame, "speaker_sex"))
    out["accent"] = _column(frame, "accent")
    out["age_metadata"] = pd.NA
    group_type, group_id = _strict_group(dataset, out)
    out["speaker_group_id"] = group_id
    return out


def _apply_policy_and_firewall(frame: pd.DataFrame, policy: dict[str, Any], exclusion: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    dataset = str(out["dataset_id"].iloc[0])
    terms = policy["datasets"][dataset]
    same_dataset = exclusion.loc[exclusion["dataset"].eq(dataset)]
    exact_utterances = set(same_dataset["source_utterance_id"].dropna().astype(str))
    exact_recordings = set(
        same_dataset.loc[same_dataset["source_utterance_id"].isna(), "source_recording_id"].dropna().astype(str)
    )
    strict_groups = set(same_dataset["strict_group_id"].dropna().astype(str))
    cross_datasets: dict[str, set[str]] = defaultdict(set)
    for item in exclusion.loc[exclusion["cross_source_key"].notna(), ["dataset", "cross_source_key"]].itertuples(index=False):
        cross_datasets[str(item.cross_source_key)].add(str(item.dataset))
    out["evaluation_exact_match"] = out["source_utterance_id"].astype(str).isin(exact_utterances) | out["source_recording_id"].astype(str).isin(exact_recordings)
    out["evaluation_group_match"] = out["speaker_group_id"].astype(str).isin(strict_groups)
    out["evaluation_cross_dataset_match"] = out["cross_source_key"].map(
        lambda key: pd.notna(key) and bool(cross_datasets.get(str(key), set()) - {dataset})
    )
    out["dataset_version"] = terms["dataset_version"]
    out["license_id"] = terms["license_id"]
    out["license_policy_status"] = terms["commercial_training_status"]
    out["commercial_training_status"] = terms["commercial_training_status"]
    out["technical_training_status"] = terms["technical_training_status"]
    out["commercial_release_review_status"] = terms["commercial_release_review_status"]
    out["attribution_required"] = terms["attribution_required"]
    out["sharealike_flag"] = terms["sharealike_flag"]
    # Presence means normalized metadata provides a rebasable source path.  No per-file stat is run here.
    out["source_available"] = out["source_audio_logical_path"].notna()
    no_hard_leakage = ~(out["evaluation_exact_match"] | out["evaluation_cross_dataset_match"])
    out["technical_training_eligible"] = out["source_available"] & no_hard_leakage
    out["relaxed_training_eligible"] = out["technical_training_eligible"]
    out["strict_training_eligible"] = out["technical_training_eligible"] & ~out["evaluation_group_match"]
    commercial_allowed = terms["commercial_training_status"] in {"allowed", "allowed_with_attribution"}
    review_gated = terms["commercial_training_status"] == "allowed_but_release_review_required"
    out["commercial_training_eligible"] = out["strict_training_eligible"] & commercial_allowed
    out["review_gated_training_eligible"] = out["strict_training_eligible"] & review_gated
    out["exclusion_reason"] = pd.NA
    out.loc[out["evaluation_exact_match"], "exclusion_reason"] = "evaluation_exact_or_linked_source"
    out.loc[out["evaluation_cross_dataset_match"], "exclusion_reason"] = "cross_dataset_source_match"
    out.loc[out["evaluation_group_match"] & out["exclusion_reason"].isna(), "exclusion_reason"] = "strict_group"
    out.loc[~out["source_available"], "exclusion_reason"] = "metadata_has_no_resolvable_audio_path"
    return out


def _duration_summary(frame: pd.DataFrame) -> dict[str, Any]:
    source_unique = frame.sort_values("duration_seconds", ascending=False, kind="stable").drop_duplicates(
        ["dataset_id", "source_parent_utterance_id"], keep="first"
    )
    return {
        "records": int(len(frame)),
        "resolved_records": int(frame["source_available"].sum()),
        "missing_records": int((~frame["source_available"]).sum()),
        "physical_audio_hours": round(float(frame["duration_seconds"].fillna(0).sum()) / 3600, 3),
        "unique_source_hours": round(float(source_unique["duration_seconds"].fillna(0).sum()) / 3600, 3),
        "unique_speakers": int(frame["speaker_id"].nunique(dropna=True)),
        "unique_sessions": int(frame["session_id"].nunique(dropna=True)),
        "unique_meetings": int(frame["meeting_id"].nunique(dropna=True)),
        "upstream_split_distribution": {str(key): int(value) for key, value in frame.groupby("upstream_split", dropna=False).size().items()},
        "evaluation_exact_records": int(frame["evaluation_exact_match"].sum()),
        "evaluation_strict_group_records": int(frame["evaluation_group_match"].sum()),
        "evaluation_cross_dataset_records": int(frame["evaluation_cross_dataset_match"].sum()),
        "exact_policy_eligible_records": int(frame["relaxed_training_eligible"].sum()),
        "exact_policy_eligible_hours": round(float(frame.loc[frame["relaxed_training_eligible"], "duration_seconds"].fillna(0).sum()) / 3600, 3),
        "strict_policy_eligible_records": int(frame["strict_training_eligible"].sum()),
        "strict_policy_eligible_hours": round(float(frame.loc[frame["strict_training_eligible"], "duration_seconds"].fillna(0).sum()) / 3600, 3),
        "commercially_straightforward_hours": round(float(frame.loc[frame["commercial_training_eligible"], "duration_seconds"].fillna(0).sum()) / 3600, 3),
        "review_gated_hours": round(float(frame.loc[frame["review_gated_training_eligible"], "duration_seconds"].fillna(0).sum()) / 3600, 3),
        "license_id": str(frame["license_id"].iloc[0]),
        "commercial_training_status": str(frame["commercial_training_status"].iloc[0]),
        "commercial_release_review_status": str(frame["commercial_release_review_status"].iloc[0]),
    }


def _pool_preview(frame: pd.DataFrame, datasets: set[str]) -> dict[str, Any]:
    selection = frame.loc[frame["dataset_id"].isin(datasets) & frame["strict_training_eligible"]]
    unique = selection.sort_values("duration_seconds", ascending=False, kind="stable").drop_duplicates(
        ["dataset_id", "source_parent_utterance_id"], keep="first"
    )
    return {
        "datasets": sorted(datasets),
        "records": int(len(selection)),
        "unique_source_hours": round(float(unique["duration_seconds"].fillna(0).sum()) / 3600, 3),
        "speakers": int(selection["speaker_id"].nunique(dropna=True)),
        "commercially_straightforward_records": int(selection["commercial_training_eligible"].sum()),
        "review_gated_records": int(selection["review_gated_training_eligible"].sum()),
        "release_review_required": bool(selection["review_gated_training_eligible"].any()),
    }


def _summary(frame: pd.DataFrame) -> dict[str, Any]:
    datasets = {dataset: _duration_summary(group) for dataset, group in frame.groupby("dataset_id", sort=True)}
    return {
        "schema_version": SCHEMA,
        "datasets": datasets,
        "cross_dataset": {
            "voices_librispeech_source_matches": int(
                frame.loc[frame["evaluation_cross_dataset_match"], "cross_source_key"].nunique(dropna=True)
            ),
            "records_removed": int(frame["evaluation_cross_dataset_match"].sum()),
            "hours_removed": round(float(frame.loc[frame["evaluation_cross_dataset_match"], "duration_seconds"].fillna(0).sum()) / 3600, 3),
        },
        "future_pool_previews": {
            "robust_core": _pool_preview(frame, {"ami", "voices"}),
            "robust_plus_chime": _pool_preview(frame, {"ami", "voices", "chime6"}),
            "read_speech_support": _pool_preview(frame, {"cmu_arctic", "librispeech", "hifitts"}),
        },
        "additional_normalized_dataset_families": [],
        "limitations": [
            "source_available means normalized metadata supplied a rebasable path; this freeze intentionally performs no per-audio filesystem probe.",
            "HiFiTTS/LibriSpeech shared audiobook lineage is recorded as provenance only because local metadata lacks a reliable item-level crosswalk.",
        ],
    }


def _audit_markdown(summary: dict[str, Any], freeze: dict[str, Any]) -> str:
    lines = [
        "# Phase-2 training-data audit",
        "",
        "This local inventory freezes metadata, licence policy, and evaluation exclusions. It does not train a model, download data, or create train/dev/test splits.",
        "",
        f"Training freeze: `{freeze['training_data_freeze_id']}`",
        "",
        "## Dataset summary",
        "",
        "| Dataset | Records | Physical h | Unique-source h | Exact eligible h | Strict eligible h | Commercial policy |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for dataset, value in summary["datasets"].items():
        lines.append(
            f"| {dataset} | {value['records']:,} | {value['physical_audio_hours']:.3f} | {value['unique_source_hours']:.3f} | {value['exact_policy_eligible_hours']:.3f} | {value['strict_policy_eligible_hours']:.3f} | {value['commercial_training_status']} |"
        )
    lines.extend([
        "",
        "## Policy notes",
        "",
        "- AMI is marked `prohibited_for_intended_commercial_use`: its local `LICENCE.txt` identifies CC BY-NC-SA 2.5, which overrides the prompt's starting expectation.",
        "- CHiME-6 is technically eligible but only through the review-gated branch; this is not a conclusion about trained-model licence consequences.",
        "- CMU Arctic's CC0 entry is an operator-supplied local licence assertion, recorded as such rather than treated as independent legal advice.",
        "- VOiCES/LibriSpeech source keys are compared across dataset IDs. HiFiTTS/LibriSpeech has no fabricated item-level link.",
        "",
        "## Canonicalization",
        "",
        "Rows are sorted by portable source identifiers. The canonical registry digest excludes `resolved_audio_path`; changing a drive letter or configured data root therefore does not change the freeze identity.",
    ])
    return "\n".join(lines) + "\n"


def build_freeze(source_root: Path, tool_root: Path, data_root: Path, output_root: Path) -> dict[str, Any]:
    policy = load_policy(source_root)
    evidence = _policy_evidence(policy, data_root)
    exclusion, manifests = evaluation_inputs(tool_root)
    parts = []
    metadata_root = data_root / "Normalized Metadata"
    for folder, dataset in DATASETS.items():
        root = metadata_root / folder
        recordings = pd.read_parquet(root / "recordings.parquet")
        utterances = pd.read_parquet(root / "utterances.parquet")
        source = _base_frame(dataset, recordings, utterances, data_root)
        parts.append(_apply_policy_and_firewall(source, policy, exclusion))
    frame = pd.concat(parts, ignore_index=True)[REGISTRY_COLUMNS]
    frame = frame.sort_values(["dataset_id", "source_item_id", "source_recording_id", "source_utterance_id"], kind="stable").reset_index(drop=True)
    registries = output_root / "registries"
    audits = output_root / "audits"
    license_evidence = output_root / "license_evidence"
    for path in (registries, audits, license_evidence):
        path.mkdir(parents=True, exist_ok=True)
    registry_path = registries / "training_data_registry.parquet"
    exclusion_path = registries / "evaluation_exclusion_index.parquet"
    frame.to_parquet(registry_path, index=False)
    exclusion.to_parquet(exclusion_path, index=False)
    # Parquet canonicalizes nullable dtypes. Hash that persisted, portable
    # representation so an independently run verifier sees the same identity.
    registry_hash = _frame_hash(pd.read_parquet(registry_path), omit=("resolved_audio_path",))
    exclusion_hash = _frame_hash(pd.read_parquet(exclusion_path))
    policy_hash = _json_hash(policy)
    summary = _summary(frame)
    summary.update({
        "training_data_registry_id": f"training_registry_{registry_hash[:12].lower()}",
        "training_data_registry_sha256": registry_hash,
        "records": int(len(frame)),
    })
    freeze = {
        "schema_version": FREEZE_SCHEMA,
        "registry": {
            "id": summary["training_data_registry_id"],
            "sha256": registry_hash,
            "canonical_hash_excludes": ["resolved_audio_path"],
        },
        "evaluation_exclusion_index": {
            "id": f"evaluation_exclusion_{exclusion_hash[:12].lower()}",
            "sha256": exclusion_hash,
        },
        "license_policy_id": policy["policy_id"],
        "license_policy_sha256": policy_hash,
        "evaluation_manifests": manifests,
        "code_schema_versions": {"registry": SCHEMA, "exclusion": EXCLUSION_SCHEMA},
    }
    freeze["training_data_freeze_sha256"] = _json_hash(freeze)
    freeze["training_data_freeze_id"] = f"training_freeze_{freeze['training_data_freeze_sha256'][:12].lower()}"
    _write_json(registries / "training_data_registry_summary.json", summary)
    _write_json(registries / "evaluation_exclusion_summary.json", {
        "schema_version": EXCLUSION_SCHEMA,
        "evaluation_exclusion_index_id": freeze["evaluation_exclusion_index"]["id"],
        "evaluation_exclusion_index_sha256": exclusion_hash,
        "rows": int(len(exclusion)),
        "manifest_count": int(len(manifests)),
    })
    _write_json(registries / "training_data_freeze_manifest.json", freeze)
    _write_json(audits / "training_data_audit.json", {"freeze": freeze, "summary": summary, "license_evidence": evidence})
    (audits / "training_data_audit.md").write_text(_audit_markdown(summary, freeze), encoding="utf-8")
    for dataset, value in evidence.items():
        _write_json(license_evidence / f"{dataset}.json", value)
    return freeze


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def verify_freeze_details(path: Path, tool_root: Path) -> dict[str, Any]:
    freeze = json.loads(path.read_text(encoding="utf-8"))
    expected_hash = freeze.get("training_data_freeze_sha256")
    payload = dict(freeze)
    payload.pop("training_data_freeze_sha256", None)
    payload.pop("training_data_freeze_id", None)
    reasons: list[str] = []
    if expected_hash != _json_hash(payload):
        reasons.append("freeze manifest self-hash does not match")
    registry_path = path.parent / "training_data_registry.parquet"
    exclusion_path = path.parent / "evaluation_exclusion_index.parquet"
    if not registry_path.is_file():
        reasons.append("frozen training-data registry is missing")
    elif freeze.get("registry", {}).get("sha256") != _frame_hash(
        pd.read_parquet(registry_path), omit=("resolved_audio_path",)
    ):
        reasons.append("frozen training-data registry hash does not match")
    if not exclusion_path.is_file():
        reasons.append("frozen evaluation exclusion index is missing")
    elif freeze.get("evaluation_exclusion_index", {}).get("sha256") != _frame_hash(pd.read_parquet(exclusion_path)):
        reasons.append("frozen evaluation exclusion index hash does not match")
    _, observed_manifests = evaluation_inputs(tool_root)
    if observed_manifests != freeze.get("evaluation_manifests"):
        reasons.append("one or more frozen evaluation benchmark manifests changed")
    return {"valid": not reasons, "reasons": reasons, "freeze_id": freeze.get("training_data_freeze_id")}


def verify_freeze(path: Path, tool_root: Path) -> bool:
    return bool(verify_freeze_details(path, tool_root)["valid"])


def select_records(
    frame: pd.DataFrame,
    *,
    datasets: Iterable[str] | None = None,
    strict: bool = True,
    commercial_policy: str = "any",
) -> pd.DataFrame:
    """Return deterministic future-manifest candidates without creating a manifest.

    ``commercial_policy`` is one of ``any``, ``straightforward``, or
    ``review_gated``.  Callers receive source metadata only and remain
    responsible for building a later, separately versioned split.
    """
    selected = frame.copy()
    if datasets is not None:
        selected = selected.loc[selected["dataset_id"].isin(set(datasets))]
    selected = selected.loc[selected["strict_training_eligible"] if strict else selected["relaxed_training_eligible"]]
    if commercial_policy == "straightforward":
        selected = selected.loc[selected["commercial_training_eligible"]]
    elif commercial_policy == "review_gated":
        selected = selected.loc[selected["review_gated_training_eligible"]]
    elif commercial_policy != "any":
        raise ValueError("commercial_policy must be any, straightforward, or review_gated")
    return selected.sort_values(["dataset_id", "source_item_id"], kind="stable").reset_index(drop=True)
