"""Deterministic small/standard/large benchmark manifest construction."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd
import yaml

from app.benchmark_contracts.canonical import stable_rank
from app.benchmark_contracts.manifest_io import (
    manifest_row,
    rows_summary,
    validate_manifest_rows,
    write_manifest,
)
from app.benchmark_contracts.rir_registry import RIRRegistry
from app.benchmark_contracts.versions import MANIFEST_SCHEMA_VERSION, SELECTION_SEED
from app.dataset_registry import get_dataset
from app.dataset_registry.loader import load_dataset_selection, selection_records
from app.utils.json_utils import write_json


TIERS = ("small", "standard", "large")


class BenchmarkBuildError(ValueError):
    """Raised when normalized metadata cannot satisfy a safe manifest contract."""


@dataclass(frozen=True)
class BenchmarkBuildResult:
    """Paths and identities emitted by one manifest build."""

    output_dir: Path
    manifest_paths: Mapping[str, Path]
    manifest_identities: Mapping[str, Mapping[str, object]]
    summary_path: Path
    audit_path: Path
    rir_audit_path: Path


class BenchmarkManifestBuilder:
    """Build manifests from actual normalized metadata with stable hash ranks."""

    def __init__(
        self,
        project_root: Path,
        *,
        targets_path: Path | None = None,
        rir_registry: RIRRegistry | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.tool_root = Path(__file__).resolve().parents[2]
        self.targets_path = targets_path or (
            self.tool_root
            / "configs"
            / "automated_evaluation"
            / "benchmark_targets.v1.yaml"
        )
        self.targets = _yaml_mapping(self.targets_path)
        if self.targets.get("schema_version") != "benchmark-targets.v1":
            raise BenchmarkBuildError("unsupported benchmark target schema")
        if self.targets.get("selection_seed") != SELECTION_SEED:
            raise BenchmarkBuildError("benchmark targets must use seed 3800")
        self.rir_registry = rir_registry or RIRRegistry.load()
        self.audit_rows: list[dict[str, object]] = []
        self._raw_cache: dict[tuple[str, str], pd.DataFrame] = {}

    def build_all(self, output_dir: Path) -> BenchmarkBuildResult:
        """Create all canonical Parquet manifests, summaries, and audits."""

        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        self.audit_rows = []
        rows_by_tier: dict[str, list[dict[str, object]]] = {}
        for tier in TIERS:
            rows = self._build_source_tier(tier)
            validate_manifest_rows(rows, project_root=self.project_root)
            rows_by_tier[tier] = rows
        speaker_rows = self._build_speaker_protocol()
        validate_manifest_rows(speaker_rows, project_root=self.project_root)

        paths: dict[str, Path] = {}
        identities: dict[str, Mapping[str, object]] = {}
        for tier, rows in rows_by_tier.items():
            path = output_dir / f"{tier}_source_manifest.parquet"
            identity = write_manifest(path, rows)
            paths[tier] = path
            identities[tier] = {**identity, "path": path.name}
        speaker_path = output_dir / "speaker_protocol.parquet"
        speaker_identity = write_manifest(speaker_path, speaker_rows)
        paths["speaker_protocol"] = speaker_path
        identities["speaker_protocol"] = {**speaker_identity, "path": speaker_path.name}

        rir_audit_path = output_dir / "rir_registry_audit.json"
        write_json(rir_audit_path, self.rir_registry.audit(self.project_root))
        audit_path = output_dir / "selection_audit.csv"
        self._write_audit(audit_path)
        summary_path = output_dir / "manifest_summary.json"
        write_json(
            summary_path,
            self._build_summary(rows_by_tier, speaker_rows, identities),
        )
        return BenchmarkBuildResult(
            output_dir=output_dir,
            manifest_paths=paths,
            manifest_identities=identities,
            summary_path=summary_path,
            audit_path=audit_path,
            rir_audit_path=rir_audit_path,
        )

    def _build_source_tier(self, tier: str) -> list[dict[str, object]]:
        target = self._tier_target(tier)
        rows: list[dict[str, object]] = []
        controlled = _mapping(target, "controlled_clean")
        rows.extend(self._select_cmu_controlled(tier, _mapping(controlled, "cmu_arctic")))
        rows.extend(
            self._select_librispeech(
                tier,
                panel="controlled_clean",
                target=_mapping(controlled, "librispeech"),
            )
        )
        rows.extend(
            self._select_hifitts(
                tier,
                panel="controlled_clean",
                target=_mapping(controlled, "hifitts"),
            )
        )
        native = _mapping(target, "native_robustness")
        rows.extend(self._select_ami(tier, _mapping(native, "ami")))
        rows.extend(self._select_voices(tier, _mapping(native, "voices")))
        rows.extend(self._select_chime6(tier, _mapping(native, "chime6")))
        rows.extend(
            self._select_librispeech(
                tier,
                panel="native_robustness",
                target=_mapping(native, "librispeech"),
            )
        )
        rows.extend(
            self._select_hifitts(
                tier,
                panel="native_robustness",
                target=_mapping(native, "hifitts"),
            )
        )
        return rows

    def _select_cmu_controlled(
        self,
        tier: str,
        target: Mapping[str, object],
    ) -> list[dict[str, object]]:
        frame = self._whole_file_frame("cmu_arctic")
        frame = self._eligible(frame, 2.0, 8.0, 4, 25)
        core_speakers = int(target["core_speakers"])
        core_per = int(target["core_items_per_speaker"])
        extension_per = int(target["extension_items_per_speaker"])
        selected_speakers = self._balanced_speakers(
            frame,
            speaker_column="speaker_id",
            gender_column="gender",
            requested=core_speakers,
            minimum_rows=core_per,
            dataset="cmu_arctic",
        )
        intersections: set[str] | None = None
        for speaker in selected_speakers:
            values = set(
                frame.loc[frame["speaker_id"].astype(str) == speaker, "_utt_id"].astype(str)
            )
            intersections = values if intersections is None else intersections & values
        shared = sorted(
            intersections or set(),
            key=lambda value: stable_rank(SELECTION_SEED, "cmu_arctic", "shared", value),
        )[:core_per]
        selected_parts: list[pd.DataFrame] = []
        for speaker in selected_speakers:
            part = frame[
                (frame["speaker_id"].astype(str) == speaker)
                & (frame["_utt_id"].astype(str).isin(shared))
            ].copy()
            part["_selection_stratum"] = "balanced_core_shared_prompts"
            selected_parts.append(part)
        excluded = sorted(
            set(frame["speaker_id"].astype(str)) - set(selected_speakers),
            key=lambda value: stable_rank(SELECTION_SEED, "cmu_arctic", value, "speaker"),
        )
        for speaker in excluded:
            part = self._ranked_rows(
                frame[frame["speaker_id"].astype(str) == speaker],
                "cmu_arctic",
            ).head(extension_per).copy()
            part["_selection_stratum"] = "accent_extension"
            selected_parts.append(part)
        selected = _concat(selected_parts)
        requested = core_speakers * core_per + len(excluded) * extension_per
        return self._finalize_whole_selection(
            tier,
            "controlled_clean",
            "cmu_arctic",
            selected,
            requested=requested,
            shortfall_reason=(
                "shared-prompt or per-speaker eligibility pool exhausted under duration/text filters"
            ),
        )

    def _select_librispeech(
        self,
        tier: str,
        *,
        panel: str,
        target: Mapping[str, object],
    ) -> list[dict[str, object]]:
        split = str(target["split"])
        frame = self._whole_file_frame("librispeech")
        frame = frame[frame["split"].astype(str) == split]
        frame = self._eligible(frame, 3.0, 12.0, 5, 35)
        speaker_target = int(target["speakers"])
        per_speaker = int(target["items_per_speaker"])
        speakers = self._balanced_speakers(
            frame,
            speaker_column="speaker_id",
            gender_column="speaker_sex",
            requested=speaker_target,
            minimum_rows=per_speaker,
            dataset="librispeech",
        )
        selected_parts: list[pd.DataFrame] = []
        for speaker in speakers:
            candidates = self._ranked_rows(
                frame[frame["speaker_id"].astype(str) == speaker],
                "librispeech",
            )
            chosen = self._prefer_multiple_groups(candidates, "chapter_id", per_speaker)
            chosen["_selection_stratum"] = f"{split}:speaker"
            selected_parts.append(chosen)
        selected = _concat(selected_parts)
        requested = speaker_target * per_speaker
        return self._finalize_whole_selection(
            tier,
            panel,
            "librispeech",
            selected,
            requested=requested,
            shortfall_reason=(
                f"{split} cannot meet balanced speaker/utterance quota under eligibility rules"
            ),
        )

    def _select_hifitts(
        self,
        tier: str,
        *,
        panel: str,
        target: Mapping[str, object],
    ) -> list[dict[str, object]]:
        quality = str(target["quality"])
        per_reader = int(target["items_per_reader"])
        all_quality_rows = self._whole_file_frame("hifitts")
        all_readers = set(all_quality_rows["reader_id"].astype(str))
        frame = all_quality_rows[all_quality_rows["audio_quality"].astype(str) == quality]
        frame = self._eligible(frame, 3.0, 15.0, 5, 45)
        readers = sorted(
            set(frame["reader_id"].astype(str)),
            key=lambda value: stable_rank(SELECTION_SEED, "hifitts", value, "reader"),
        )
        selected_parts: list[pd.DataFrame] = []
        for reader in readers:
            candidates = self._ranked_rows(
                frame[frame["reader_id"].astype(str) == reader],
                "hifitts",
            )
            chosen = self._prefer_multiple_groups(candidates, "book_id", per_reader)
            chosen["_selection_stratum"] = f"{quality}:reader"
            selected_parts.append(chosen)
        selected = _concat(selected_parts)
        requested = len(all_readers) * per_reader
        return self._finalize_whole_selection(
            tier,
            panel,
            "hifitts",
            selected,
            requested=requested,
            shortfall_reason=f"{quality} reader pool exhausted under eligibility rules",
        )

    def _select_ami(
        self,
        tier: str,
        target: Mapping[str, object],
    ) -> list[dict[str, object]]:
        raw = self._raw("ami", "utterances")
        raw = self._attach_candidate_fields(raw, "ami")
        raw = self._eligible(raw, 2.0, 12.0, 3, 35)
        arrays = [str(value) for value in target["array_streams"]]
        allowed_streams = set(arrays) | {"headset"}
        raw = raw[
            raw.apply(
                lambda row: str(row.get("stream_type")) == "headset"
                or str(row.get("stream_id")) in allowed_streams,
                axis=1,
            )
        ]
        meeting_target = int(target["meetings"])
        speakers_per = int(target["speakers_per_meeting"])
        segments_per = int(target["segments_per_speaker"])
        meeting_meta = self._raw("ami", "recordings")
        meeting_meta = meeting_meta.drop_duplicates("meeting_id")
        meetings = self._stratified_ids(
            meeting_meta,
            id_column="meeting_id",
            stratum_column="meeting_type",
            requested=meeting_target,
            dataset="ami",
            preferred_column="seen_type",
            preferred_values=("development", "training", ""),
        )
        selected_raw: list[pd.DataFrame] = []
        for meeting in meetings:
            meeting_rows = raw[raw["meeting_id"].astype(str) == meeting]
            speakers = sorted(
                set(meeting_rows["speaker_global_name"].astype(str)),
                key=lambda value: stable_rank(SELECTION_SEED, "ami", meeting, value),
            )[:speakers_per]
            for speaker in speakers:
                speaker_rows = meeting_rows[
                    meeting_rows["speaker_global_name"].astype(str) == speaker
                ]
                source_ids = self._qualified_source_ids(
                    speaker_rows,
                    source_column="_utt_id",
                    required_streams=arrays,
                    close_type="headset",
                    requested=segments_per,
                    dataset="ami",
                )
                chosen = speaker_rows[
                    speaker_rows["_utt_id"].astype(str).isin(source_ids)
                    & (
                        speaker_rows["stream_type"].astype(str).eq("headset")
                        | speaker_rows["stream_id"].astype(str).isin(arrays)
                    )
                ].copy()
                chosen["_selection_stratum"] = (
                    chosen["meeting_id"].astype(str)
                    + ":"
                    + chosen["speaker_global_name"].astype(str)
                    + ":"
                    + chosen["stream_type"].astype(str)
                    + ":"
                    + chosen["stream_id"].astype(str)
                )
                selected_raw.append(chosen)
        selected = _concat(selected_raw).drop_duplicates(["recording_id", "_utt_id"])
        requested = meeting_target * speakers_per * segments_per * (1 + len(arrays))
        return self._finalize_segment_selection(
            tier,
            "ami",
            selected,
            requested=requested,
            source_filter_name="segment_ref_id",
            shortfall_reason=(
                "insufficient eligible matched headset/array segments, speakers, or meetings"
            ),
        )

    def _select_voices(
        self,
        tier: str,
        target: Mapping[str, object],
    ) -> list[dict[str, object]]:
        split = str(target["split"])
        frame = self._whole_file_frame("voices")
        frame = frame[frame["split"].astype(str) == split]
        frame = self._eligible(frame, 2.0, 15.0, 4, 45)
        speaker_target = int(target["speakers"])
        source_per = int(target["source_utterances_per_speaker"])
        condition_per = int(target["conditions_per_source"])
        speakers = self._balanced_speakers(
            frame,
            speaker_column="speaker_id_padded",
            gender_column="gender",
            requested=speaker_target,
            minimum_rows=source_per * condition_per,
            dataset="voices",
        )
        selected_parts: list[pd.DataFrame] = []
        for speaker in speakers:
            speaker_rows = frame[frame["speaker_id_padded"].astype(str) == speaker].copy()
            speaker_rows["_source_key"] = (
                speaker_rows["speaker_id_padded"].astype(str)
                + ":"
                + speaker_rows["chapter_id"].astype(str)
                + ":"
                + speaker_rows["segment_id"].astype(str)
            )
            groups = [
                group
                for _, group in speaker_rows.groupby("_source_key", sort=False)
                if len(group) >= condition_per
            ]
            groups.sort(
                key=lambda group: stable_rank(
                    SELECTION_SEED,
                    "voices",
                    speaker,
                    str(group.iloc[0]["_source_key"]),
                )
            )
            for group in groups[:source_per]:
                chosen = self._diverse_conditions(group, condition_per)
                chosen["_selection_stratum"] = (
                    split + ":" + speaker + ":native_conditions"
                )
                chosen["_source_utterance_id"] = str(group.iloc[0]["_source_key"])
                selected_parts.append(chosen)
        selected = _concat(selected_parts)
        requested = speaker_target * source_per * condition_per
        return self._finalize_whole_selection(
            tier,
            "native_robustness",
            "voices",
            selected,
            requested=requested,
            shortfall_reason=(
                "test split cannot meet balanced speaker/source/native-condition quota"
            ),
        )

    def _select_chime6(
        self,
        tier: str,
        target: Mapping[str, object],
    ) -> list[dict[str, object]]:
        utterances = self._raw("chime6", "utterances")
        utterances = self._attach_candidate_fields(utterances, "chime6")
        utterances = self._eligible(utterances, 2.0, 12.0, 3, 35)
        recordings = self._raw("chime6", "recordings").copy()
        recordings["_microphone_id"] = recordings.apply(
            lambda row: (
                str(row.get("speaker_id_ref") or "")
                if str(row.get("stream_type")) == "participant_close"
                else f"{row.get('device_id')}_{row.get('channel_id')}"
            ),
            axis=1,
        )
        session_target = int(target["sessions"])
        speakers_per = int(target["speakers_per_session"])
        segments_per = int(target["segments_per_speaker"])
        microphones = [str(value) for value in target["farfield_microphones"]]
        session_meta = recordings.drop_duplicates(["split", "session_id"]).copy()
        session_meta["_priority"] = session_meta["split"].map(
            {"dev": 0, "train": 1, "eval": 2}
        ).fillna(3)
        session_meta["_rank"] = session_meta["session_id"].map(
            lambda value: stable_rank(SELECTION_SEED, "chime6", str(value), "session")
        )
        sessions = (
            session_meta.sort_values(["_priority", "_rank"], kind="stable")
            .head(session_target)["session_id"]
            .astype(str)
            .tolist()
        )
        selected_source_keys: list[str] = []
        selected_recording_ids: set[str] = set()
        selected_tuples: set[tuple[str, str]] = set()
        for session in sessions:
            session_rows = utterances[utterances["session_id"].astype(str) == session]
            speakers = sorted(
                set(session_rows["speaker_id_ref"].astype(str)),
                key=lambda value: stable_rank(SELECTION_SEED, "chime6", session, value),
            )[:speakers_per]
            session_recordings = recordings[recordings["session_id"].astype(str) == session]
            far_rows = session_recordings[
                session_recordings["_microphone_id"].astype(str).isin(microphones)
            ]
            selected_recording_ids.update(far_rows["recording_id"].astype(str))
            for speaker in speakers:
                close_rows = session_recordings[
                    (session_recordings["stream_type"].astype(str) == "participant_close")
                    & (session_recordings["speaker_id_ref"].astype(str) == speaker)
                ]
                if close_rows.empty or len(far_rows) < len(microphones):
                    continue
                close_id = str(close_rows.iloc[0]["recording_id"])
                selected_recording_ids.add(close_id)
                candidates = self._ranked_rows(
                    session_rows[session_rows["speaker_id_ref"].astype(str) == speaker],
                    "chime6",
                ).head(segments_per)
                for source_id in candidates["_utt_id"].astype(str):
                    selected_source_keys.append(source_id)
                    selected_tuples.add((close_id, source_id))
                    for far_id in far_rows["recording_id"].astype(str):
                        selected_tuples.add((far_id, source_id))
        loaded = self._load_records(
            "chime6",
            selected_recording_ids,
            extra_filters={"utterance_key": selected_source_keys},
        )
        selected_records = [
            record
            for record in loaded
            if (str(record["recording_id"]), str(record["utt_id"])) in selected_tuples
        ]
        rows = [
            manifest_row(
                record,
                tier=tier,
                panel="native_robustness",
                dataset="chime6",
                role="evaluation",
                selection_stratum=(
                    f"{record.get('session_id')}:{record.get('speaker_id_ref')}:"
                    f"{record.get('stream_type')}:{record.get('microphone_id')}"
                ),
                source_utterance_id=str(record["utt_id"]),
            )
            for record in selected_records
        ]
        requested = session_target * speakers_per * segments_per * (1 + len(microphones))
        self._audit(
            tier,
            "native_robustness",
            "chime6",
            "matched_close_farfield",
            requested,
            len(rows),
            "insufficient eligible sessions, speakers, source segments, or requested streams",
        )
        return rows

    def _build_speaker_protocol(self) -> list[dict[str, object]]:
        frame = self._eligible(self._whole_file_frame("cmu_arctic"), 2.0, 8.0, 4, 25)
        all_rows: list[dict[str, object]] = []
        for tier in TIERS:
            target = _mapping(self._tier_target(tier), "speaker_protocol")
            known_target = int(target["known_speakers"])
            unknown_target = int(target["unknown_speakers"])
            enrollment_per = int(target["enrollment_per_known_speaker"])
            probes_per = int(target["probes_per_speaker"])
            eligible_speakers = [
                speaker
                for speaker, group in frame.groupby("speaker_id", sort=False)
                if len(group) >= enrollment_per + probes_per
            ]
            eligible_speakers.sort(
                key=lambda value: stable_rank(SELECTION_SEED, "cmu_arctic", str(value), "protocol")
            )
            known = eligible_speakers[:known_target]
            unknown = eligible_speakers[known_target : known_target + unknown_target]
            selected_parts: list[pd.DataFrame] = []
            assignments: dict[str, tuple[str, str]] = {}
            for speaker in known:
                ranked = self._ranked_rows(
                    frame[frame["speaker_id"].astype(str) == str(speaker)],
                    "cmu_arctic",
                )
                enrollment = ranked.head(enrollment_per)
                probes = ranked.iloc[enrollment_per : enrollment_per + probes_per]
                for _, row in enrollment.iterrows():
                    assignments[str(row["recording_id"])] = ("enrollment", "clean")
                for _, row in probes.iterrows():
                    assignments[str(row["recording_id"])] = ("known_probe", "both")
                selected_parts.extend([enrollment, probes])
            for speaker in unknown:
                probes = self._ranked_rows(
                    frame[frame["speaker_id"].astype(str) == str(speaker)],
                    "cmu_arctic",
                ).head(probes_per)
                for _, row in probes.iterrows():
                    assignments[str(row["recording_id"])] = ("unknown_probe", "both")
                selected_parts.append(probes)
            selected = _concat(selected_parts).drop_duplicates("recording_id")
            loaded = self._load_records("cmu_arctic", selected["recording_id"].astype(str))
            rows: list[dict[str, object]] = []
            for record in loaded:
                role, condition = assignments[str(record["recording_id"])]
                conditions = ("clean", "degraded") if condition == "both" else ("clean",)
                for protocol_condition in conditions:
                    rows.append(
                        manifest_row(
                            record,
                            tier=tier,
                            panel="speaker_protocol",
                            dataset="cmu_arctic",
                            role=role,
                            protocol_condition=protocol_condition,
                            selection_stratum=f"{role}:{protocol_condition}",
                            source_utterance_id=str(record["utt_id"]),
                        )
                    )
            requested = (
                known_target * enrollment_per
                + known_target * probes_per * 2
                + unknown_target * probes_per * 2
            )
            self._audit(
                tier,
                "speaker_protocol",
                "cmu_arctic",
                "known_unknown_protocol",
                requested,
                len(rows),
                "insufficient disjoint eligible speakers or utterances for enrollment/probes",
            )
            all_rows.extend(rows)
        return all_rows

    def _whole_file_frame(self, dataset: str) -> pd.DataFrame:
        utterances = self._raw(dataset, "utterances")
        recordings = self._raw(dataset, "recordings")
        keep = [
            column
            for column in recordings.columns
            if column == "recording_id" or column not in utterances.columns
        ]
        frame = utterances.merge(recordings[keep], on="recording_id", how="left")
        return self._attach_candidate_fields(frame, dataset)

    def _attach_candidate_fields(self, frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
        result = frame.copy()
        result["_utt_id"] = _first_series(
            result,
            ("utterance_id", "utterance_key", "segment_ref_id", "segment_id", "recording_id"),
        )
        result["_reference_text"] = _first_series(
            result,
            ("text_norm", "text", "text_norm_eval", "text_normalized", "text_original"),
        )
        start = pd.to_numeric(result.get("start_sec"), errors="coerce")
        end = pd.to_numeric(result.get("end_sec"), errors="coerce")
        duration = end - start
        for field in (
            "duration_sec_audio",
            "duration_sec_manifest",
            "duration_sec",
            "distant_duration_sec",
            "source_duration_sec",
        ):
            if field in result.columns:
                fallback = pd.to_numeric(result[field], errors="coerce")
                duration = duration.where(duration > 0, fallback)
        result["_duration"] = duration
        result["_word_count"] = result["_reference_text"].fillna("").astype(str).str.split().str.len()
        rank_recording = (
            result["recording_id"]
            if "recording_id" in result.columns
            else _first_series(result, ("session_id", "meeting_id", "_utt_id"))
        )
        result["_rank"] = [
            stable_rank(SELECTION_SEED, dataset, str(recording), str(utt))
            for recording, utt in zip(rank_recording, result["_utt_id"], strict=False)
        ]
        return result

    def _eligible(
        self,
        frame: pd.DataFrame,
        min_duration: float,
        max_duration: float,
        min_words: int,
        max_words: int,
    ) -> pd.DataFrame:
        identity_column = "recording_id" if "recording_id" in frame.columns else "session_id"
        mask = (
            frame[identity_column].notna()
            & frame["_reference_text"].fillna("").astype(str).str.strip().ne("")
            & frame["_duration"].between(min_duration, max_duration, inclusive="both")
            & frame["_word_count"].between(min_words, max_words, inclusive="both")
        )
        if "audio_path" in frame.columns:
            mask &= frame["audio_path"].fillna("").astype(str).str.strip().ne("")
        if "normalization_status" in frame.columns:
            status = frame["normalization_status"].fillna("").astype(str).str.lower()
            mask &= ~status.str.contains("error|missing", regex=True)
        return frame[mask].copy()

    def _ranked_rows(self, frame: pd.DataFrame, dataset: str) -> pd.DataFrame:
        if "_rank" not in frame.columns:
            frame = self._attach_candidate_fields(frame, dataset)
        identity_column = "recording_id" if "recording_id" in frame.columns else "session_id"
        return frame.sort_values(
            ["_rank", identity_column, "_utt_id"], kind="stable"
        )

    def _balanced_speakers(
        self,
        frame: pd.DataFrame,
        *,
        speaker_column: str,
        gender_column: str,
        requested: int,
        minimum_rows: int,
        dataset: str,
    ) -> list[str]:
        counts = frame.groupby(speaker_column).size()
        candidates = frame[frame[speaker_column].isin(counts[counts >= minimum_rows].index)]
        speaker_gender = candidates.groupby(speaker_column)[gender_column].first()
        female = [
            str(value)
            for value, gender in speaker_gender.items()
            if str(gender).strip().lower() in {"f", "female"}
        ]
        male = [
            str(value)
            for value, gender in speaker_gender.items()
            if str(gender).strip().lower() in {"m", "male"}
        ]
        def rank(value: str) -> str:
            return stable_rank(SELECTION_SEED, dataset, value, "speaker")

        female.sort(key=rank)
        male.sort(key=rank)
        per_gender = requested // 2
        selected = female[:per_gender] + male[:per_gender]
        if requested % 2:
            remaining = sorted(
                set(female + male) - set(selected),
                key=rank,
            )
            selected.extend(remaining[:1])
        return sorted(selected, key=rank)

    def _prefer_multiple_groups(
        self,
        frame: pd.DataFrame,
        group_column: str,
        requested: int,
    ) -> pd.DataFrame:
        if group_column not in frame.columns or requested <= 1:
            return frame.head(requested).copy()
        chosen_indices: list[object] = []
        for _, group in frame.groupby(group_column, sort=False):
            chosen_indices.append(group.index[0])
            if len(chosen_indices) == min(2, requested):
                break
        remaining = [index for index in frame.index if index not in set(chosen_indices)]
        chosen_indices.extend(remaining[: max(0, requested - len(chosen_indices))])
        return frame.loc[chosen_indices].copy()

    def _qualified_source_ids(
        self,
        frame: pd.DataFrame,
        *,
        source_column: str,
        required_streams: list[str],
        close_type: str,
        requested: int,
        dataset: str,
    ) -> list[str]:
        qualified: list[str] = []
        for source_id, group in frame.groupby(source_column, sort=False):
            has_close = group["stream_type"].astype(str).eq(close_type).any()
            streams = set(group["stream_id"].astype(str))
            if has_close and set(required_streams).issubset(streams):
                qualified.append(str(source_id))
        qualified.sort(
            key=lambda value: stable_rank(SELECTION_SEED, dataset, value, value)
        )
        return qualified[:requested]

    def _diverse_conditions(self, frame: pd.DataFrame, requested: int) -> pd.DataFrame:
        remaining = self._ranked_rows(frame, "voices")
        selected: list[object] = []
        coverage: dict[str, set[str]] = {
            "room": set(),
            "distractor": set(),
            "position": set(),
        }
        while len(selected) < requested and not remaining.empty:
            scored: list[tuple[int, str, object]] = []
            for index, row in remaining.iterrows():
                gain = sum(
                    str(row.get(field)) not in coverage[field] for field in coverage
                )
                scored.append((-gain, str(row["_rank"]), index))
            _, _, winner = min(scored)
            selected.append(winner)
            row = remaining.loc[winner]
            for field in coverage:
                coverage[field].add(str(row.get(field)))
            remaining = remaining.drop(index=winner)
        return frame.loc[selected].copy()

    def _stratified_ids(
        self,
        frame: pd.DataFrame,
        *,
        id_column: str,
        stratum_column: str,
        requested: int,
        dataset: str,
        preferred_column: str,
        preferred_values: tuple[str, ...],
    ) -> list[str]:
        candidates = frame.copy()
        candidates["_preference"] = candidates[preferred_column].fillna("").astype(str).map(
            {value: index for index, value in enumerate(preferred_values)}
        ).fillna(len(preferred_values))
        candidates["_rank"] = candidates[id_column].map(
            lambda value: stable_rank(SELECTION_SEED, dataset, str(value), "group")
        )
        candidates = candidates.sort_values(["_preference", "_rank"], kind="stable")
        selected: list[str] = []
        strata = sorted(set(candidates[stratum_column].astype(str)))
        while len(selected) < requested:
            changed = False
            for stratum in strata:
                available = candidates[
                    (candidates[stratum_column].astype(str) == stratum)
                    & (~candidates[id_column].astype(str).isin(selected))
                ]
                if not available.empty:
                    selected.append(str(available.iloc[0][id_column]))
                    changed = True
                    if len(selected) == requested:
                        break
            if not changed:
                break
        return selected

    def _finalize_whole_selection(
        self,
        tier: str,
        panel: str,
        dataset: str,
        selected: pd.DataFrame,
        *,
        requested: int,
        shortfall_reason: str,
    ) -> list[dict[str, object]]:
        recording_ids = selected["recording_id"].astype(str).tolist() if not selected.empty else []
        loaded = self._load_records(dataset, recording_ids)
        selected_by_id = {
            str(row["recording_id"]): row for _, row in selected.iterrows()
        }
        rows = []
        for record in loaded:
            source = selected_by_id[str(record["recording_id"])]
            rows.append(
                manifest_row(
                    record,
                    tier=tier,
                    panel=panel,
                    dataset=dataset,
                    role="evaluation",
                    selection_stratum=str(source.get("_selection_stratum") or "evaluation"),
                    source_utterance_id=str(
                        source.get("_source_utterance_id") or source.get("_utt_id")
                    ),
                )
            )
        self._audit(
            tier,
            panel,
            dataset,
            "source_selection",
            requested,
            len(rows),
            shortfall_reason,
        )
        return rows

    def _finalize_segment_selection(
        self,
        tier: str,
        dataset: str,
        selected: pd.DataFrame,
        *,
        requested: int,
        source_filter_name: str,
        shortfall_reason: str,
    ) -> list[dict[str, object]]:
        recording_ids = set(selected["recording_id"].astype(str)) if not selected.empty else set()
        source_ids = set(selected["_utt_id"].astype(str)) if not selected.empty else set()
        selected_keys = set(zip(selected["recording_id"].astype(str), selected["_utt_id"].astype(str), strict=False))
        strata = {
            (str(row["recording_id"]), str(row["_utt_id"])): str(row["_selection_stratum"])
            for _, row in selected.iterrows()
        }
        loaded = self._load_records(
            dataset,
            recording_ids,
            extra_filters={source_filter_name: source_ids},
        )
        rows = [
            manifest_row(
                record,
                tier=tier,
                panel="native_robustness",
                dataset=dataset,
                role="evaluation",
                selection_stratum=strata[(str(record["recording_id"]), str(record["utt_id"]))],
                source_utterance_id=str(record["utt_id"]),
            )
            for record in loaded
            if (str(record["recording_id"]), str(record["utt_id"])) in selected_keys
        ]
        self._audit(
            tier,
            "native_robustness",
            dataset,
            "matched_native_streams",
            requested,
            len(rows),
            shortfall_reason,
        )
        return rows

    def _load_records(
        self,
        dataset: str,
        recording_ids: Iterable[str],
        *,
        extra_filters: Mapping[str, Iterable[str]] | None = None,
    ) -> list[dict[str, object]]:
        ids = sorted(set(str(value) for value in recording_ids if str(value)))
        if not ids:
            return []
        filters: dict[str, list[str]] = {"recording_id": ids}
        for key, values in (extra_filters or {}).items():
            filters[key] = sorted(set(str(value) for value in values if str(value)))
        selection = load_dataset_selection(
            self.project_root,
            get_dataset(dataset),
            filters,
        )
        rows = selection_records(selection.dataframe)
        missing = [row for row in rows if not row.get("audio_exists")]
        if missing:
            raise BenchmarkBuildError(
                f"{dataset} selection contains {len(missing)} missing audio path(s)"
            )
        return rows

    def _raw(self, dataset: str, table: str) -> pd.DataFrame:
        key = (dataset, table)
        if key not in self._raw_cache:
            definition = get_dataset(dataset)
            path = (
                self.project_root
                / definition.normalized_metadata_dir
                / f"{table}.parquet"
            )
            self._raw_cache[key] = pd.read_parquet(path)
        return self._raw_cache[key].copy()

    def _tier_target(self, tier: str) -> Mapping[str, object]:
        if tier not in TIERS:
            raise BenchmarkBuildError(f"unsupported benchmark tier {tier!r}")
        return _mapping(_mapping(self.targets, "tiers"), tier)

    def _audit(
        self,
        tier: str,
        panel: str,
        dataset: str,
        stratum: str,
        requested: int,
        realized: int,
        shortfall_reason: str,
    ) -> None:
        self.audit_rows.append(
            selection_audit_row(
                tier=tier,
                panel=panel,
                dataset=dataset,
                stratum=stratum,
                requested=requested,
                realized=realized,
                shortfall_reason=shortfall_reason,
            )
        )

    def _write_audit(self, path: Path) -> None:
        fields = (
            "manifest_schema_version",
            "benchmark_tier",
            "panel",
            "dataset",
            "selection_stratum",
            "requested_count",
            "realized_count",
            "shortfall_count",
            "shortfall_reason",
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(
                sorted(
                    self.audit_rows,
                    key=lambda row: (
                        str(row["benchmark_tier"]),
                        str(row["panel"]),
                        str(row["dataset"]),
                        str(row["selection_stratum"]),
                    ),
                )
            )

    def _build_summary(
        self,
        rows_by_tier: Mapping[str, list[dict[str, object]]],
        speaker_rows: list[dict[str, object]],
        identities: Mapping[str, Mapping[str, object]],
    ) -> dict[str, object]:
        summaries: dict[str, object] = {}
        for tier, rows in rows_by_tier.items():
            summaries[tier] = self._summary_groups(rows, tier)
        summaries["speaker_protocol"] = {
            tier: self._summary_groups(
                [row for row in speaker_rows if row["benchmark_tier"] == tier],
                tier,
            )
            for tier in TIERS
        }
        shortfalls = [
            row for row in self.audit_rows if int(row["shortfall_count"]) > 0
        ]
        return {
            "schema_version": "benchmark-manifest-summary.v1",
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "selection_seed": SELECTION_SEED,
            "authoritative_representation": "parquet",
            "manifest_identities": identities,
            "summaries": summaries,
            "shortfalls": shortfalls,
        }

    def _summary_groups(
        self,
        rows: list[dict[str, object]],
        tier: str,
    ) -> dict[str, object]:
        frame = pd.DataFrame(rows)
        groups: dict[str, object] = {}
        if not frame.empty:
            for (panel, dataset), group in frame.groupby(["panel", "dataset"], sort=True):
                summary = rows_summary(group.to_dict(orient="records"))
                audits = [
                    row
                    for row in self.audit_rows
                    if row["benchmark_tier"] == tier
                    and row["panel"] == panel
                    and row["dataset"] == dataset
                ]
                summary["requested_count"] = sum(int(row["requested_count"]) for row in audits)
                summary["shortfalls"] = [
                    row for row in audits if int(row["shortfall_count"]) > 0
                ]
                groups[f"{panel}/{dataset}"] = summary
        return {
            "overall": rows_summary(rows),
            "groups": groups,
        }


def _yaml_mapping(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise BenchmarkBuildError(f"expected YAML mapping in {path}")
    return data


def selection_audit_row(
    *,
    tier: str,
    panel: str,
    dataset: str,
    stratum: str,
    requested: int,
    realized: int,
    shortfall_reason: str | None,
) -> dict[str, object]:
    """Build one deterministic quota audit row and require shortfall reasoning."""

    if requested < 0 or realized < 0:
        raise BenchmarkBuildError("requested and realized counts must be non-negative")
    shortfall = max(0, requested - realized)
    reason = str(shortfall_reason or "").strip() or None
    if shortfall and reason is None:
        raise BenchmarkBuildError("every non-zero shortfall requires a reason")
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "benchmark_tier": tier,
        "panel": panel,
        "dataset": dataset,
        "selection_stratum": stratum,
        "requested_count": requested,
        "realized_count": realized,
        "shortfall_count": shortfall,
        "shortfall_reason": reason if shortfall else None,
    }


def _mapping(value: Mapping[str, object], key: str) -> Mapping[str, object]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise BenchmarkBuildError(f"expected mapping at {key}")
    return item


def _first_series(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
    for column in columns:
        if column in frame.columns:
            return frame[column].fillna("").astype(str)
    raise BenchmarkBuildError(f"metadata missing all required alternatives: {columns}")


def _concat(parts: Iterable[pd.DataFrame]) -> pd.DataFrame:
    materialized = [part for part in parts if not part.empty]
    return pd.concat(materialized, ignore_index=False) if materialized else pd.DataFrame()
