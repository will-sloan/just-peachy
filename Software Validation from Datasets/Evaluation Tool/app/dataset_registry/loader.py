"""Load normalized metadata and create evaluation selections."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from app.dataset_registry.registry import DatasetDefinition, validate_required_tables
from app.utils.paths import metadata_path_to_project_relative, resolve_metadata_path


@dataclass(frozen=True)
class DatasetSelection:
    """Selected dataset rows and a JSON-friendly summary."""

    dataframe: pd.DataFrame
    summary: dict[str, object]


def parse_subset_filters(
    filter_items: Iterable[str] | None,
    definition: DatasetDefinition,
) -> dict[str, list[str]]:
    """Parse ``key=value`` subset filter CLI arguments.

    Values may be comma-separated so the GUI can serialize multi-select
    dropdown choices through the existing ``--subset`` option.
    """

    parsed: dict[str, list[str]] = {}
    for item in filter_items or []:
        if "=" not in item:
            raise ValueError(f"Subset filter must be key=value, got {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"Subset filter must be key=value, got {item!r}")
        if key not in definition.supported_subset_filters:
            valid = ", ".join(definition.supported_subset_filters) or "none"
            raise ValueError(
                f"Filter {key!r} is not supported for {definition.display_name}. "
                f"Supported filters: {valid}"
            )
        values = [part.strip() for part in value.split(",") if part.strip()]
        if not values:
            raise ValueError(f"Subset filter must include at least one value, got {item!r}")
        parsed.setdefault(key, [])
        for part in values:
            if part not in parsed[key]:
                parsed[key].append(part)
    return parsed


def load_dataset_selection(
    project_root: Path,
    definition: DatasetDefinition,
    subset_filters: dict[str, str | list[str] | tuple[str, ...]] | None = None,
    max_recordings: int | None = None,
) -> DatasetSelection:
    """Load and filter normalized metadata for a dataset evaluation run."""

    missing = validate_required_tables(project_root, definition)
    if missing:
        formatted = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing normalized metadata table(s):\n{formatted}")

    metadata_dir = project_root / definition.normalized_metadata_dir
    utterances_path = metadata_dir / "utterances.parquet"
    recordings_path = metadata_dir / "recordings.parquet"

    utterances = pd.read_parquet(utterances_path)
    recordings = pd.read_parquet(recordings_path)
    filters = _normalize_subset_filters(subset_filters)
    dataframe = _join_reference_and_recording_tables(
        utterances,
        recordings,
        definition,
        subset_filters=filters,
        max_rows=max_recordings,
    )
    dataframe = _attach_dataset_context_tables(dataframe, project_root, definition)
    dataframe = _attach_derived_filter_columns(dataframe)
    total_rows = len(dataframe)

    for key, values in filters.items():
        if key not in dataframe.columns:
            raise ValueError(f"Filter column {key!r} was not found in metadata")
        value_set = {str(value) for value in values}
        dataframe = dataframe[dataframe[key].astype(str).isin(value_set)]

    filtered_rows = len(dataframe)
    if max_recordings is not None:
        if max_recordings <= 0:
            raise ValueError("--max-recordings must be a positive integer")
        dataframe = dataframe.head(max_recordings)

    dataframe = dataframe.reset_index(drop=True)
    dataframe.insert(0, "_selection_index", range(len(dataframe)))
    dataframe = _attach_rebased_audio_paths(dataframe, project_root)
    dataframe = _attach_reference_fields(dataframe, definition)

    summary = {
        "dataset_key": definition.key,
        "dataset_name": definition.display_name,
        "dataset_id": definition.dataset_id,
        "normalized_metadata_dir": definition.normalized_metadata_dir.as_posix(),
        "reference_tables": {
            "utterances": utterances_path.relative_to(project_root).as_posix(),
            "recordings": recordings_path.relative_to(project_root).as_posix(),
        },
        "subset_filters": filters,
        "max_recordings": max_recordings,
        "total_metadata_rows": int(total_rows),
        "rows_after_filters": int(filtered_rows),
        "selected_recordings": int(len(dataframe)),
        "missing_audio_count": int((~dataframe["audio_exists"]).sum()),
        "evaluation_unit": definition.evaluation_unit,
        "audio_format": definition.audio_format,
    }
    if definition.split_column and definition.split_column in dataframe.columns:
        summary["selected_split_counts"] = (
            dataframe[definition.split_column].value_counts().sort_index().to_dict()
        )
    for column in definition.group_metric_columns:
        if column in dataframe.columns:
            summary[f"selected_{column}_counts"] = (
                dataframe[column].value_counts().sort_index().to_dict()
            )
    return DatasetSelection(dataframe=dataframe, summary=summary)


def load_filter_option_values(
    project_root: Path,
    definition: DatasetDefinition,
) -> dict[str, list[str]]:
    """Load real available values for each supported subset filter.

    This is intentionally lighter than a full selection: it reads the normalized
    metadata tables and derived convenience columns, but it does not resolve or
    stat every audio path.
    """

    missing = validate_required_tables(project_root, definition)
    if missing:
        formatted = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing normalized metadata table(s):\n{formatted}")

    metadata_dir = project_root / definition.normalized_metadata_dir
    utterances = pd.read_parquet(metadata_dir / "utterances.parquet")
    recordings = pd.read_parquet(metadata_dir / "recordings.parquet")
    if definition.key == "chime6":
        return _load_chime6_filter_option_values(utterances, recordings, definition)

    dataframe = _join_reference_and_recording_tables(utterances, recordings, definition)
    dataframe = _attach_dataset_context_tables(dataframe, project_root, definition)
    dataframe = _attach_derived_filter_columns(dataframe)

    options: dict[str, list[str]] = {}
    for filter_name in definition.supported_subset_filters:
        if filter_name not in dataframe.columns:
            options[filter_name] = []
            continue
        series = dataframe[filter_name].dropna().astype(str).map(str.strip)
        values = sorted(
            {
                value
                for value in series.tolist()
                if value and value.lower() not in {"nan", "null"}
            },
            key=_natural_sort_key,
        )
        options[filter_name] = values
    return options


def selection_records(dataframe: pd.DataFrame) -> list[dict[str, object]]:
    """Return selected rows as JSON-friendly dictionaries."""

    keep_columns = [
        "_selection_index",
        "recording_id",
        "utt_id",
        "speaker_label",
        "start_sec",
        "end_sec",
        "reference_text",
        "audio_path_project_relative",
        "audio_path_resolved",
        "audio_exists",
    ]
    optional_columns = [
        "dataset",
        "dataset_id",
        "split",
        "subset_group",
        "session_id",
        "speaker_id",
        "speaker_id_ref",
        "recording_speaker_id_ref",
        "speaker_code",
        "gender",
        "speaker_sex",
        "accent",
        "accent_group",
        "speaker_variant_group",
        "query_name",
        "speaker_id_padded",
        "room",
        "distractor",
        "mic",
        "device",
        "device_id",
        "channel_id",
        "microphone_id",
        "position",
        "degrees",
        "ref_device",
        "location",
        "location_hint",
        "distance_distractor_1",
        "distance_distractor_2",
        "distance_distractor_3",
        "distance_floor",
        "distance_foreground",
        "distance_foreground_class",
        "pesq_nb",
        "pesq_wb",
        "pesq_wb_class",
        "stoi",
        "stoi_class",
        "siib",
        "srmr",
        "srmr_class",
        "distant_audio_path",
        "source_audio_path",
        "distant_audio_path_project_relative",
        "distant_audio_path_resolved",
        "distant_audio_exists",
        "source_audio_path_project_relative",
        "source_audio_path_resolved",
        "source_audio_exists",
        "meeting_id",
        "stream_type",
        "stream_id",
        "agent",
        "speaker_global_name",
        "speaker_role",
        "headset_channel",
        "meeting_type",
        "visibility",
        "seen_type",
        "utterance_key",
        "segment_ref_id",
        "segment_id",
        "word_start_id",
        "word_end_id",
        "has_overlap_candidate",
        "participant_sex",
        "native_language",
        "education",
        "reader_id",
        "reader_name",
        "reader_split",
        "audio_quality",
        "clean_vs_other",
        "chapter_id",
        "book_id",
        "utterance_id",
        "audio_filepath_relative",
        "duration_sec",
        "duration_sec_audio",
        "duration_sec_manifest",
        "distant_duration_sec",
        "source_duration_sec",
        "manifest_noisy_time",
        "manifest_source_time",
        "normalization_status",
    ]
    for column in optional_columns:
        if column in dataframe.columns and column not in keep_columns:
            keep_columns.append(column)

    rows = dataframe[keep_columns].where(pd.notna(dataframe[keep_columns]), None)
    return rows.to_dict(orient="records")


def _join_reference_and_recording_tables(
    utterances: pd.DataFrame,
    recordings: pd.DataFrame,
    definition: DatasetDefinition,
    subset_filters: dict[str, list[str]] | None = None,
    max_rows: int | None = None,
) -> pd.DataFrame:
    if definition.key == "chime6":
        return _join_chime6_reference_and_recording_tables(
            utterances,
            recordings,
            subset_filters=subset_filters,
            max_rows=max_rows,
        )

    if "recording_id" not in utterances.columns or "recording_id" not in recordings.columns:
        raise ValueError("Both utterances.parquet and recordings.parquet need recording_id")

    recording_columns = ["recording_id"]
    for column in recordings.columns:
        if column == "recording_id":
            continue
        if column not in utterances.columns:
            recording_columns.append(column)
        elif column in {
            "normalization_status",
            "sample_rate_hz",
        "duration_sec",
        "duration_sec_audio",
        "duration_sec_manifest",
        "distant_sample_rate_hz",
        "distant_duration_sec",
        "source_sample_rate_hz",
        "source_duration_sec",
        "manifest_noisy_time",
        "manifest_source_time",
        "num_channels",
            "raw_transcript_path",
            "text_source",
        }:
            recording_columns.append(column)

    return utterances.merge(
        recordings[recording_columns],
        on="recording_id",
        how="left",
        suffixes=("", "_recording"),
    )


def _join_chime6_reference_and_recording_tables(
    utterances: pd.DataFrame,
    recordings: pd.DataFrame,
    subset_filters: dict[str, list[str]] | None = None,
    max_rows: int | None = None,
) -> pd.DataFrame:
    """Project CHiME-6 session-level utterances onto concrete audio streams.

    CHiME-6 normalized utterances are keyed by split/session rather than by a
    single recording stream. Far-field array streams receive all utterances for
    the session. Participant-close streams receive only the utterances for the
    matching participant, keeping close-talk scoring speaker-attributed.
    """

    join_keys = {"split", "session_id"}
    if not join_keys.issubset(utterances.columns) or not join_keys.issubset(recordings.columns):
        raise ValueError("CHiME-6 utterances and recordings need split and session_id columns")
    if "recording_id" not in recordings.columns:
        raise ValueError("CHiME-6 recordings.parquet needs recording_id")

    recording_columns = [
        column
        for column in (
            "recording_id",
            "split",
            "session_id",
            "stream_type",
            "speaker_id_ref",
            "device_id",
            "channel_id",
            "audio_path",
            "sample_rate_hz",
            "duration_sec",
            "num_channels",
            "location_hint",
        )
        if column in recordings.columns
    ]
    recording_streams = recordings[recording_columns].rename(
        columns={
            "speaker_id_ref": "recording_speaker_id_ref",
            "duration_sec": "duration_sec_audio",
        }
    )
    utterance_rows = utterances.copy()
    recording_streams = _attach_derived_filter_columns(recording_streams)
    utterance_rows = _attach_derived_filter_columns(utterance_rows)
    utterance_rows, recording_streams = _prefilter_chime6_tables(
        utterance_rows,
        recording_streams,
        subset_filters or {},
    )
    if max_rows is not None:
        return _join_chime6_limited_rows(
            utterance_rows,
            recording_streams,
            subset_filters or {},
            max_rows,
        )
    dataframe = utterance_rows.merge(recording_streams, on=["split", "session_id"], how="inner")

    if {"stream_type", "recording_speaker_id_ref", "speaker_id_ref"}.issubset(dataframe.columns):
        is_close_talk = dataframe["stream_type"].fillna("").astype(str).eq("participant_close")
        same_speaker = (
            dataframe["recording_speaker_id_ref"].fillna("").astype(str)
            == dataframe["speaker_id_ref"].fillna("").astype(str)
        )
        dataframe = dataframe[(~is_close_talk) | same_speaker]

    sort_columns = [
        column
        for column in ("split", "session_id", "recording_id", "start_sec", "end_sec")
        if column in dataframe.columns
    ]
    if sort_columns:
        dataframe = dataframe.sort_values(sort_columns, kind="stable")
    return dataframe.reset_index(drop=True)


def _prefilter_chime6_tables(
    utterances: pd.DataFrame,
    recordings: pd.DataFrame,
    subset_filters: dict[str, list[str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply simple CHiME-6 filters before the potentially large stream projection."""

    utterance_rows = utterances
    recording_rows = recordings
    for key, values in subset_filters.items():
        value_set = {str(value) for value in values}
        if key in utterance_rows.columns:
            utterance_rows = utterance_rows[utterance_rows[key].astype(str).isin(value_set)]
        if key in recording_rows.columns:
            recording_rows = recording_rows[recording_rows[key].astype(str).isin(value_set)]
    return utterance_rows, recording_rows


def _join_chime6_limited_rows(
    utterances: pd.DataFrame,
    recordings: pd.DataFrame,
    subset_filters: dict[str, list[str]],
    max_rows: int,
) -> pd.DataFrame:
    """Materialize only enough CHiME-6 projected rows for smoke-test limits."""

    chunks: list[pd.DataFrame] = []
    remaining = max_rows
    sort_columns = [column for column in ("split", "session_id", "recording_id") if column in recordings.columns]
    recording_rows = recordings.sort_values(sort_columns, kind="stable") if sort_columns else recordings

    for recording in recording_rows.to_dict(orient="records"):
        if remaining <= 0:
            break
        candidates = utterances[
            (utterances["split"].astype(str) == str(recording.get("split")))
            & (utterances["session_id"].astype(str) == str(recording.get("session_id")))
        ].copy()
        if candidates.empty:
            continue
        if str(recording.get("stream_type") or "") == "participant_close":
            recording_speaker = str(recording.get("recording_speaker_id_ref") or "")
            candidates = candidates[candidates["speaker_id_ref"].fillna("").astype(str) == recording_speaker]
            if candidates.empty:
                continue
        for column, value in recording.items():
            if column not in {"split", "session_id"}:
                candidates[column] = value
        candidates = _attach_derived_filter_columns(candidates)
        for key, values in subset_filters.items():
            if key in candidates.columns:
                value_set = {str(value) for value in values}
                candidates = candidates[candidates[key].astype(str).isin(value_set)]
        if candidates.empty:
            continue
        sort_columns = [
            column
            for column in ("split", "session_id", "recording_id", "start_sec", "end_sec")
            if column in candidates.columns
        ]
        if sort_columns:
            candidates = candidates.sort_values(sort_columns, kind="stable")
        chunk = candidates.head(remaining)
        chunks.append(chunk)
        remaining -= len(chunk)

    if not chunks:
        return pd.DataFrame(columns=list(utterances.columns) + list(recordings.columns))
    return pd.concat(chunks, ignore_index=True)


def _load_chime6_filter_option_values(
    utterances: pd.DataFrame,
    recordings: pd.DataFrame,
    definition: DatasetDefinition,
) -> dict[str, list[str]]:
    """Load CHiME-6 filter choices without materializing the full stream projection."""

    utterance_values = _attach_derived_filter_columns(utterances)
    recording_values = _attach_derived_filter_columns(
        recordings.rename(columns={"speaker_id_ref": "recording_speaker_id_ref"}).copy()
    )
    options: dict[str, list[str]] = {}
    for filter_name in definition.supported_subset_filters:
        values: list[str] = []
        if filter_name in utterance_values.columns:
            values.extend(_series_option_values(utterance_values[filter_name]))
        if filter_name in recording_values.columns:
            values.extend(_series_option_values(recording_values[filter_name]))
        options[filter_name] = sorted(set(values), key=_natural_sort_key)
    return options


def _attach_dataset_context_tables(
    dataframe: pd.DataFrame,
    project_root: Path,
    definition: DatasetDefinition,
) -> pd.DataFrame:
    """Attach small optional context tables used by dataset-specific filters."""

    if definition.key == "voices":
        return _attach_voices_context_tables(dataframe, project_root, definition)
    if definition.key != "ami":
        return dataframe

    participants_path = project_root / definition.normalized_metadata_dir / "participants.parquet"
    if not participants_path.exists() or "speaker_global_name" not in dataframe.columns:
        return dataframe

    participants = pd.read_parquet(participants_path)
    if "global_name" not in participants.columns:
        return dataframe

    keep_columns = [
        column
        for column in ("global_name", "sex", "age_at_collection", "native_language", "education")
        if column in participants.columns
    ]
    participants = participants[keep_columns].copy()
    participants["global_name"] = participants["global_name"].fillna("").astype(str)
    participants = participants[participants["global_name"].str.strip() != ""]
    participants = participants.drop_duplicates(subset=["global_name"], keep="first")
    participants = participants.rename(
        columns={
            "global_name": "speaker_global_name",
            "sex": "participant_sex",
        }
    )
    return dataframe.merge(participants, on="speaker_global_name", how="left")


def _attach_voices_context_tables(
    dataframe: pd.DataFrame,
    project_root: Path,
    definition: DatasetDefinition,
) -> pd.DataFrame:
    """Attach VOiCES condition quality metrics without duplicating columns."""

    conditions_path = project_root / definition.normalized_metadata_dir / "conditions.parquet"
    if not conditions_path.exists():
        return dataframe

    conditions = pd.read_parquet(conditions_path)
    if "recording_id" not in conditions.columns:
        return dataframe

    keep_columns = ["recording_id"]
    for column in (
        "distance_distractor_1",
        "distance_distractor_2",
        "distance_distractor_3",
        "distance_floor",
        "distance_foreground",
        "pesq_nb",
        "pesq_wb",
        "stoi",
        "siib",
        "srmr",
    ):
        if column in conditions.columns and column not in dataframe.columns:
            keep_columns.append(column)
    if len(keep_columns) == 1:
        return dataframe
    return dataframe.merge(conditions[keep_columns], on="recording_id", how="left")


def _attach_derived_filter_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Attach normalized convenience columns used by dataset filters.

    HiFiTTS stores reader and quality separately, while users commonly refer to
    the raw folder label such as ``6097_clean``. Keeping this derivation here
    means selection, scoring, and reporting all see the same value.
    """

    result = dataframe.copy()
    if {"reader_id", "audio_quality"}.issubset(result.columns) and "reader_split" not in result.columns:
        result["reader_split"] = (
            result["reader_id"].fillna("").astype(str)
            + "_"
            + result["audio_quality"].fillna("").astype(str)
        )
    if "audio_quality" in result.columns and "clean_vs_other" not in result.columns:
        result["clean_vs_other"] = result["audio_quality"].fillna("").astype(str)
    if "speaker_sex" in result.columns and "gender" not in result.columns:
        result["gender"] = result["speaker_sex"].fillna("").astype(str)
    if "participant_sex" in result.columns and "gender" not in result.columns:
        result["gender"] = result["participant_sex"].fillna("").astype(str)
    if "speaker_global_name" in result.columns:
        derived_gender = result["speaker_global_name"].fillna("").astype(str).str[0].str.upper()
        derived_gender = derived_gender.where(derived_gender.isin(["F", "M"]), "")
        if "gender" not in result.columns:
            result["gender"] = derived_gender
        else:
            result["gender"] = result["gender"].fillna("").astype(str)
            empty_gender = result["gender"].str.strip() == ""
            result.loc[empty_gender, "gender"] = derived_gender[empty_gender]
    if "distant_audio_path" in result.columns and "audio_path" not in result.columns:
        result["audio_path"] = result["distant_audio_path"]
    if {"stream_type", "device_id", "channel_id"}.intersection(result.columns) and "microphone_id" not in result.columns:
        result["microphone_id"] = result.apply(_chime6_microphone_id, axis=1)
    if "location" in result.columns and "location_hint" in result.columns:
        result["location"] = result["location"].fillna("").astype(str)
        empty_location = result["location"].str.strip() == ""
        result.loc[empty_location, "location"] = (
            result.loc[empty_location, "location_hint"].fillna("").astype(str)
        )
    if "distance_foreground" in result.columns and "distance_foreground_class" not in result.columns:
        result["distance_foreground_class"] = result["distance_foreground"].apply(_distance_class)
    if "stoi" in result.columns and "stoi_class" not in result.columns:
        result["stoi_class"] = result["stoi"].apply(lambda value: _quality_class(value, 0.45, 0.70))
    if "pesq_wb" in result.columns and "pesq_wb_class" not in result.columns:
        result["pesq_wb_class"] = result["pesq_wb"].apply(lambda value: _quality_class(value, 1.6, 2.4))
    if "srmr" in result.columns and "srmr_class" not in result.columns:
        result["srmr_class"] = result["srmr"].apply(lambda value: _quality_class(value, 3.0, 5.0))
    return result


def _normalize_subset_filters(
    subset_filters: dict[str, str | list[str] | tuple[str, ...]] | None,
) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for key, raw_values in (subset_filters or {}).items():
        if isinstance(raw_values, str):
            values = [part.strip() for part in raw_values.split(",") if part.strip()]
        else:
            values = [str(value).strip() for value in raw_values if str(value).strip()]
        if values:
            normalized[key] = list(dict.fromkeys(values))
    return normalized


def _series_option_values(series: pd.Series) -> list[str]:
    return [
        value
        for value in series.dropna().astype(str).map(str.strip).tolist()
        if value and value.lower() not in {"nan", "null", "none"}
    ]


def _natural_sort_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _chime6_microphone_id(row: pd.Series) -> str:
    stream_type = str(row.get("stream_type") or "").strip()
    recording_speaker = str(row.get("recording_speaker_id_ref") or "").strip()
    speaker = str(row.get("speaker_id_ref") or "").strip()
    device = str(row.get("device_id") or "").strip()
    channel = str(row.get("channel_id") or "").strip()
    if stream_type == "participant_close":
        return recording_speaker or speaker
    if device and channel:
        return f"{device}_{channel}"
    return device or channel or recording_speaker or speaker


def _distance_class(value: object) -> str:
    numeric = _optional_float(value)
    if numeric is None:
        return ""
    if numeric < 50:
        return "near"
    if numeric < 100:
        return "mid"
    return "far"


def _quality_class(value: object, low_cutoff: float, high_cutoff: float) -> str:
    numeric = _optional_float(value)
    if numeric is None:
        return ""
    if numeric < low_cutoff:
        return "low"
    if numeric < high_cutoff:
        return "mid"
    return "high"


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _attach_rebased_audio_paths(dataframe: pd.DataFrame, project_root: Path) -> pd.DataFrame:
    if "audio_path" not in dataframe.columns:
        raise ValueError("Metadata is missing required audio_path column")

    relative_values: list[str | None] = []
    resolved_values: list[str | None] = []
    exists_values: list[bool] = []

    for raw_path in dataframe["audio_path"].tolist():
        relative_path = metadata_path_to_project_relative(raw_path, project_root)
        resolved_path = resolve_metadata_path(raw_path, project_root)
        relative_values.append(relative_path.as_posix() if relative_path is not None else None)
        resolved_values.append(str(resolved_path) if resolved_path is not None else None)
        exists_values.append(bool(resolved_path and resolved_path.exists()))

    result = dataframe.copy()
    result["audio_path_project_relative"] = relative_values
    result["audio_path_resolved"] = resolved_values
    result["audio_exists"] = exists_values
    result = _attach_optional_audio_path_rebase(result, project_root, "distant_audio_path", "distant_audio")
    result = _attach_optional_audio_path_rebase(result, project_root, "source_audio_path", "source_audio")
    return result


def _attach_optional_audio_path_rebase(
    dataframe: pd.DataFrame,
    project_root: Path,
    source_column: str,
    output_prefix: str,
) -> pd.DataFrame:
    if source_column not in dataframe.columns:
        return dataframe
    relative_values: list[str | None] = []
    resolved_values: list[str | None] = []
    exists_values: list[bool] = []
    for raw_path in dataframe[source_column].tolist():
        relative_path = metadata_path_to_project_relative(raw_path, project_root)
        resolved_path = resolve_metadata_path(raw_path, project_root)
        relative_values.append(relative_path.as_posix() if relative_path is not None else None)
        resolved_values.append(str(resolved_path) if resolved_path is not None else None)
        exists_values.append(bool(resolved_path and resolved_path.exists()))
    result = dataframe.copy()
    result[f"{output_prefix}_path_project_relative"] = relative_values
    result[f"{output_prefix}_path_resolved"] = resolved_values
    result[f"{output_prefix}_exists"] = exists_values
    return result


def _attach_reference_fields(
    dataframe: pd.DataFrame,
    definition: DatasetDefinition,
) -> pd.DataFrame:
    if "recording_id" not in dataframe.columns:
        raise ValueError("Metadata is missing required recording_id column")

    result = dataframe.copy()
    for column in ("utterance_id", "utterance_key", "segment_ref_id", "segment_id", "word_ref_id"):
        if column in result.columns:
            result["utt_id"] = result[column].astype(str)
            break
    else:
        result["utt_id"] = result["recording_id"].astype(str)

    for column in definition.reference_text_columns:
        if column in result.columns:
            result["reference_text"] = result[column].fillna("").astype(str)
            break
    else:
        for column in ("text_norm", "text_original", "text", "text_norm_eval", "text_normalized"):
            if column in result.columns:
                result["reference_text"] = result[column].fillna("").astype(str)
                break
        else:
            raise ValueError(
                "Metadata needs one transcript reference column, such as text_norm, "
                "text_original, text, or text_norm_eval"
            )

    for column in definition.speaker_label_columns:
        if column in result.columns:
            result["speaker_label"] = result[column].fillna("").astype(str)
            break
    else:
        result["speaker_label"] = ""
    return result
