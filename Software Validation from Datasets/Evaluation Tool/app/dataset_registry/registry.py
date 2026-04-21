"""Dataset registry for normalized metadata-backed evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class TextNormalizationSpec:
    """Dataset-specific prediction text normalization options."""

    lowercase: bool = True
    strip_whitespace: bool = True
    collapse_whitespace: bool = True
    remove_punctuation: bool = False


@dataclass(frozen=True)
class DatasetDefinition:
    """Static dataset configuration used by the evaluation pipeline."""

    key: str
    display_name: str
    dataset_id: str
    normalized_metadata_dir: Path
    aliases: tuple[str, ...]
    required_tables: tuple[str, ...]
    optional_tables: tuple[str, ...]
    supported_subset_filters: tuple[str, ...]
    supported_evaluation_modes: tuple[str, ...]
    evaluation_unit: str
    audio_format: str
    text_normalization: TextNormalizationSpec
    reference_text_columns: tuple[str, ...] = ("text_norm", "text_original")
    speaker_label_columns: tuple[str, ...] = ("speaker_id", "speaker_code")
    group_metric_columns: tuple[str, ...] = ()
    split_column: str | None = None
    supports_augmentation: bool = True
    supports_speaker_attribution: bool = False


DATASETS: dict[str, DatasetDefinition] = {
    "ami": DatasetDefinition(
        key="ami",
        display_name="AMI Meeting Corpus",
        dataset_id="ami",
        normalized_metadata_dir=Path("Normalized Metadata") / "AMI",
        aliases=("ami", "ami meeting corpus", "AMI", "AMI Meeting Corpus"),
        required_tables=("recordings.parquet", "utterances.parquet"),
        optional_tables=(
            "words.parquet",
            "segments.parquet",
            "meetings.parquet",
            "participants.parquet",
        ),
        supported_subset_filters=(
            "meeting_id",
            "recording_id",
            "stream_type",
            "stream_id",
            "meeting_type",
            "visibility",
            "seen_type",
            "agent",
            "speaker_global_name",
            "speaker_role",
            "gender",
        ),
        supported_evaluation_modes=(
            "transcription",
            "speaker_attributed_transcription",
            "segment_speaker_overlap",
        ),
        evaluation_unit="one speaker-attributed meeting segment projected onto one WAV stream",
        audio_format="wav",
        text_normalization=TextNormalizationSpec(remove_punctuation=False),
        reference_text_columns=("text_norm", "text_original"),
        speaker_label_columns=("speaker_global_name", "agent"),
        group_metric_columns=(
            "stream_type",
            "stream_id",
            "meeting_id",
            "meeting_type",
            "visibility",
            "seen_type",
            "speaker_global_name",
            "speaker_role",
            "agent",
            "gender",
        ),
        split_column="seen_type",
        supports_augmentation=False,
        supports_speaker_attribution=True,
    ),
    "chime6": DatasetDefinition(
        key="chime6",
        display_name="CHiME-6",
        dataset_id="chime6",
        normalized_metadata_dir=Path("Normalized Metadata") / "CHiME_6",
        aliases=(
            "chime6",
            "chime-6",
            "chime 6",
            "CHiME-6",
            "CHiME 6",
            "CHiME_6",
        ),
        required_tables=("recordings.parquet", "utterances.parquet"),
        optional_tables=("segments.parquet", "words.parquet", "conditions.parquet"),
        supported_subset_filters=(
            "split",
            "session_id",
            "stream_type",
            "speaker_id_ref",
            "recording_speaker_id_ref",
            "device_id",
            "channel_id",
            "microphone_id",
            "ref_device",
            "location",
            "location_hint",
            "recording_id",
        ),
        supported_evaluation_modes=(
            "transcription",
            "speaker_attributed_transcription",
            "segment_speaker_overlap",
        ),
        evaluation_unit="one speaker-attributed conversation segment projected onto one WAV stream",
        audio_format="wav",
        text_normalization=TextNormalizationSpec(remove_punctuation=False),
        reference_text_columns=("text_norm", "text_original"),
        speaker_label_columns=("speaker_id_ref",),
        group_metric_columns=(
            "split",
            "session_id",
            "stream_type",
            "speaker_id_ref",
            "recording_speaker_id_ref",
            "device_id",
            "channel_id",
            "microphone_id",
            "ref_device",
            "location",
            "location_hint",
        ),
        split_column="split",
        supports_augmentation=False,
        supports_speaker_attribution=True,
    ),
    "cmu_arctic": DatasetDefinition(
        key="cmu_arctic",
        display_name="CMU Arctic",
        dataset_id="cmu_arctic",
        normalized_metadata_dir=Path("Normalized Metadata") / "CMU_Arctic",
        aliases=("cmu_arctic", "cmu arctic", "cmu-arctic", "CMU_Arctic"),
        required_tables=("recordings.parquet", "utterances.parquet"),
        optional_tables=(),
        supported_subset_filters=(
            "speaker_id",
            "speaker_code",
            "gender",
            "accent",
            "accent_group",
            "speaker_variant_group",
        ),
        supported_evaluation_modes=("transcription",),
        evaluation_unit="one utterance WAV file",
        audio_format="wav",
        text_normalization=TextNormalizationSpec(remove_punctuation=True),
        reference_text_columns=("text_norm", "text_original"),
        speaker_label_columns=("speaker_id", "speaker_code"),
        group_metric_columns=(
            "gender",
            "accent",
            "accent_group",
            "speaker_variant_group",
        ),
    ),
    "librispeech": DatasetDefinition(
        key="librispeech",
        display_name="LibriSpeech",
        dataset_id="librispeech",
        normalized_metadata_dir=Path("Normalized Metadata") / "LibriSpeech",
        aliases=("librispeech", "libri speech", "libri-speech", "LibriSpeech"),
        required_tables=("recordings.parquet", "utterances.parquet"),
        optional_tables=("speakers.parquet", "chapters.parquet", "books.parquet"),
        supported_subset_filters=(
            "split",
            "subset_group",
            "speaker_id",
            "chapter_id",
            "book_id",
            "gender",
        ),
        supported_evaluation_modes=("transcription",),
        evaluation_unit="one utterance FLAC file",
        audio_format="flac",
        text_normalization=TextNormalizationSpec(remove_punctuation=False),
        reference_text_columns=("text_norm", "text_original"),
        speaker_label_columns=("speaker_id",),
        group_metric_columns=(
            "split",
            "subset_group",
            "gender",
            "speaker_id",
            "chapter_id",
            "book_id",
        ),
        split_column="split",
    ),
    "hifitts": DatasetDefinition(
        key="hifitts",
        display_name="HiFiTTS",
        dataset_id="hifitts",
        normalized_metadata_dir=Path("Normalized Metadata") / "HiFiTTS",
        aliases=("hifitts", "hi fi tts", "hi-fi-tts", "HiFiTTS", "Hi Fi TTS"),
        required_tables=("recordings.parquet", "utterances.parquet"),
        optional_tables=("readers.parquet", "reader_books.parquet", "book_bandwidth.parquet"),
        supported_subset_filters=(
            "reader_id",
            "reader_split",
            "split",
            "clean_vs_other",
            "audio_quality",
            "book_id",
            "gender",
        ),
        supported_evaluation_modes=("transcription",),
        evaluation_unit="one utterance FLAC file",
        audio_format="flac",
        text_normalization=TextNormalizationSpec(remove_punctuation=False),
        reference_text_columns=("text", "text_norm_eval", "text_normalized"),
        speaker_label_columns=("reader_id",),
        group_metric_columns=(
            "split",
            "reader_split",
            "clean_vs_other",
            "gender",
            "reader_id",
            "audio_quality",
            "book_id",
        ),
        split_column="split",
    ),
    "voices": DatasetDefinition(
        key="voices",
        display_name="VOiCES DevKit",
        dataset_id="voices",
        normalized_metadata_dir=Path("Normalized Metadata") / "VOiCES",
        aliases=("voices", "VOiCES", "voices devkit", "VOiCES DevKit", "voices-devkit"),
        required_tables=("recordings.parquet", "utterances.parquet"),
        optional_tables=("conditions.parquet", "speakers.parquet", "source_map.parquet"),
        supported_subset_filters=(
            "split",
            "room",
            "distractor",
            "mic",
            "device",
            "position",
            "degrees",
            "speaker_id",
            "speaker_id_padded",
            "gender",
            "chapter_id",
            "segment_id",
            "query_name",
            "distance_foreground_class",
            "stoi_class",
            "pesq_wb_class",
            "srmr_class",
        ),
        supported_evaluation_modes=("transcription", "native_condition_robustness"),
        evaluation_unit="one far-field single-speaker WAV utterance",
        audio_format="wav",
        text_normalization=TextNormalizationSpec(remove_punctuation=False),
        reference_text_columns=("text_norm", "text_original"),
        speaker_label_columns=("speaker_id_padded", "speaker_id"),
        group_metric_columns=(
            "split",
            "room",
            "distractor",
            "mic",
            "device",
            "position",
            "degrees",
            "gender",
            "speaker_id_padded",
            "chapter_id",
            "segment_id",
            "distance_foreground_class",
            "stoi_class",
            "pesq_wb_class",
            "srmr_class",
        ),
        split_column="split",
        supports_augmentation=False,
        supports_speaker_attribution=False,
    ),
}


def _normalize_name(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def list_datasets() -> list[DatasetDefinition]:
    """Return registered datasets in stable display order."""

    return [DATASETS[key] for key in sorted(DATASETS)]


def resolve_dataset_key(name: str) -> str:
    """Resolve a user-facing dataset name or alias to the registry key."""

    wanted = _normalize_name(name)
    for key, definition in DATASETS.items():
        candidates = {key, definition.display_name, definition.dataset_id, *definition.aliases}
        if wanted in {_normalize_name(candidate) for candidate in candidates}:
            return key
    valid = ", ".join(dataset.display_name for dataset in list_datasets())
    raise KeyError(f"Unknown dataset {name!r}. Supported datasets: {valid}")


def get_dataset(name: str) -> DatasetDefinition:
    """Return a dataset definition by key, display name, or alias."""

    return DATASETS[resolve_dataset_key(name)]


def validate_required_tables(project_root: Path, definition: DatasetDefinition) -> list[Path]:
    """Validate that the normalized metadata tables required by a dataset exist."""

    missing: list[Path] = []
    metadata_dir = project_root / definition.normalized_metadata_dir
    for table in definition.required_tables:
        path = metadata_dir / table
        if not path.exists():
            missing.append(path)
    return missing


def filter_help(definition: DatasetDefinition) -> str:
    """Return a concise filter help string for CLI output."""

    if not definition.supported_subset_filters:
        return "none"
    return ", ".join(definition.supported_subset_filters)


def mode_help(definition: DatasetDefinition) -> str:
    """Return a concise mode help string for CLI output."""

    return ", ".join(definition.supported_evaluation_modes)


def definitions_to_jsonable(definitions: Iterable[DatasetDefinition]) -> list[dict[str, object]]:
    """Return registry entries in a JSON-friendly form."""

    rows: list[dict[str, object]] = []
    for definition in definitions:
        rows.append(
            {
                "key": definition.key,
                "display_name": definition.display_name,
                "dataset_id": definition.dataset_id,
                "normalized_metadata_dir": definition.normalized_metadata_dir.as_posix(),
                "required_tables": list(definition.required_tables),
                "optional_tables": list(definition.optional_tables),
                "supported_subset_filters": list(definition.supported_subset_filters),
                "supported_evaluation_modes": list(definition.supported_evaluation_modes),
                "group_metric_columns": list(definition.group_metric_columns),
                "evaluation_unit": definition.evaluation_unit,
                "audio_format": definition.audio_format,
                "supports_augmentation": definition.supports_augmentation,
                "supports_speaker_attribution": definition.supports_speaker_attribution,
            }
        )
    return rows
