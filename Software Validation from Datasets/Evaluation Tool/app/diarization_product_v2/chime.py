"""Development-only CHiME-6 conversational timing statistics."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import statistics
from typing import Iterable

import pandas as pd

from app.controlled_diarization.contracts import sha256_file
from app.diarization_evaluation.artifacts import write_json_atomic
from app.diarization_product_v2.contracts import DEFAULT_PROTOCOL_ROOT, TOOL_ROOT
from app.utils.paths import data_root


def default_chime_table() -> Path:
    canonical = (
        data_root().path
        / "Normalized Metadata"
        / "CHiME_6"
        / "utterances.parquet"
    )
    candidates = [canonical] if canonical.is_file() else []
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"expected one normalized CHiME-6 utterance table, found {len(candidates)}"
        )
    return candidates[0].resolve()


def extract_chime_statistics(
    output: Path | None = None, source: Path | None = None
) -> dict[str, object]:
    """Use train/dev only; held-out CHiME evaluation rows are never selected."""

    table = (source or default_chime_table()).resolve()
    columns = [
        "split",
        "session_id",
        "speaker_id_ref",
        "start_sec",
        "end_sec",
        "duration_sec",
    ]
    rows = pd.read_parquet(
        table,
        columns=columns,
        filters=[("split", "in", ["train", "dev"])],
    )
    rows = rows[rows["split"].isin(["train", "dev"])].copy()
    rows = rows.sort_values(["session_id", "start_sec", "end_sec", "speaker_id_ref"])
    turn_durations = [float(value) for value in rows["duration_sec"] if float(value) > 0]
    gaps: list[float] = []
    silences: list[float] = []
    overlaps: list[float] = []
    reentry: list[float] = []
    turns_per_speaker: list[int] = []
    participation: list[float] = []
    dominant_shares: list[float] = []
    overlap_transitions = 0
    transitions = 0
    for _session, group in rows.groupby("session_id", sort=True):
        ordered = group.sort_values(["start_sec", "end_sec"]).to_dict("records")
        for left, right in zip(ordered, ordered[1:]):
            gap = float(right["start_sec"]) - float(left["end_sec"])
            gaps.append(gap)
            transitions += 1
            if gap >= 0:
                silences.append(gap)
            else:
                overlaps.append(-gap)
                overlap_transitions += 1
        speaker_totals = group.groupby("speaker_id_ref")["duration_sec"].sum()
        total = float(speaker_totals.sum())
        if total > 0:
            shares = [float(value) / total for value in speaker_totals]
            participation.extend(shares)
            dominant_shares.append(max(shares))
        turns_per_speaker.extend(int(value) for value in group.groupby("speaker_id_ref").size())
        by_speaker: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for row in ordered:
            by_speaker[str(row["speaker_id_ref"])].append(
                (float(row["start_sec"]), float(row["end_sec"]))
            )
        for turns in by_speaker.values():
            reentry.extend(max(0.0, right[0] - left[1]) for left, right in zip(turns, turns[1:]))
    short = [value for value in turn_durations if value <= 0.75]
    payload = {
        "schema_version": "chime6-conversation-statistics.v1",
        "source_table": str(table),
        "source_table_sha256": sha256_file(table),
        "included_splits": ["train", "dev"],
        "excluded_splits": ["eval"],
        "evaluation_rows_inspected": False,
        "utterances": len(rows),
        "sessions": int(rows["session_id"].nunique()),
        "speakers": int(rows[["session_id", "speaker_id_ref"]].drop_duplicates().shape[0]),
        "turn_duration_sec": _distribution(turn_durations),
        "inter_turn_gap_sec_signed": _distribution(gaps),
        "silence_duration_sec": _distribution(silences),
        "short_response_backchannel_sec": _distribution(short),
        "overlap_duration_sec": _distribution(overlaps),
        "overlap_transition_frequency": overlap_transitions / transitions if transitions else 0.0,
        "speaker_reentry_gap_sec": _distribution(reentry),
        "turns_per_speaker_session": _distribution(turns_per_speaker),
        "speaker_participation_share": _distribution(participation),
        "dominant_speaker_share": _distribution(dominant_shares),
        "use_statement": (
            "Development-only empirical timing guidance for deterministic synthetic "
            "sample placement; not spontaneous speech and not model training."
        ),
    }
    target = output or (DEFAULT_PROTOCOL_ROOT / "chime6_conversation_statistics.json")
    write_json_atomic(target, payload)
    return payload


def _distribution(values: Iterable[float | int]) -> dict[str, object]:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {"count": 0}
    return {
        "count": len(ordered),
        "minimum": ordered[0],
        "p05": _quantile(ordered, 0.05),
        "p25": _quantile(ordered, 0.25),
        "median": statistics.median(ordered),
        "mean": statistics.fmean(ordered),
        "p75": _quantile(ordered, 0.75),
        "p90": _quantile(ordered, 0.90),
        "p95": _quantile(ordered, 0.95),
        "maximum": ordered[-1],
    }


def _quantile(values: list[float], probability: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction
