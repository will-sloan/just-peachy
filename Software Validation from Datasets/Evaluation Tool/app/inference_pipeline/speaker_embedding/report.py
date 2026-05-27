"""Speaker embedding report and similarity helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.inference_pipeline.speaker_embedding.base import vector_l2_norm


@dataclass(frozen=True)
class SimilarityDistribution:
    """Pairwise same-speaker and different-speaker similarity summary."""

    same_speaker_count: int
    different_speaker_count: int
    same_speaker_mean: float | None
    different_speaker_mean: float | None
    same_speaker_min: float | None
    same_speaker_max: float | None
    different_speaker_min: float | None
    different_speaker_max: float | None

    def to_markdown_rows(self) -> list[str]:
        return [
            f"- Same-speaker pairs: `{self.same_speaker_count}`",
            f"- Different-speaker pairs: `{self.different_speaker_count}`",
            f"- Same-speaker mean cosine: `{_format_metric(self.same_speaker_mean)}`",
            f"- Different-speaker mean cosine: `{_format_metric(self.different_speaker_mean)}`",
            (
                "- Same-speaker min/max cosine: "
                f"`{_format_metric(self.same_speaker_min)}` / "
                f"`{_format_metric(self.same_speaker_max)}`"
            ),
            (
                "- Different-speaker min/max cosine: "
                f"`{_format_metric(self.different_speaker_min)}` / "
                f"`{_format_metric(self.different_speaker_max)}`"
            ),
        ]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return cosine similarity, normalizing defensively when needed."""

    left_norm = vector_l2_norm(left)
    right_norm = vector_l2_norm(right)
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    return dot / (left_norm * right_norm)


def summarize_similarity_distribution(
    rows: Sequence[Mapping[str, object]],
    *,
    label_key: str = "speaker_label",
) -> SimilarityDistribution | None:
    """Summarize pairwise cosine scores for rows with labels and vectors."""

    labeled: list[tuple[str, tuple[float, ...]]] = []
    for row in rows:
        label = row.get(label_key)
        vector = row.get("vector")
        if not label or not isinstance(vector, Sequence) or isinstance(vector, str | bytes | bytearray):
            continue
        values = tuple(float(value) for value in vector)
        if not values:
            continue
        labeled.append((str(label), values))
    if len(labeled) < 2:
        return None

    same_scores: list[float] = []
    different_scores: list[float] = []
    for left_index, (left_label, left_vector) in enumerate(labeled):
        for right_label, right_vector in labeled[left_index + 1 :]:
            score = cosine_similarity(left_vector, right_vector)
            if left_label == right_label:
                same_scores.append(score)
            else:
                different_scores.append(score)
    return SimilarityDistribution(
        same_speaker_count=len(same_scores),
        different_speaker_count=len(different_scores),
        same_speaker_mean=_mean(same_scores),
        different_speaker_mean=_mean(different_scores),
        same_speaker_min=min(same_scores) if same_scores else None,
        same_speaker_max=max(same_scores) if same_scores else None,
        different_speaker_min=min(different_scores) if different_scores else None,
        different_speaker_max=max(different_scores) if different_scores else None,
    )


def write_speaker_embedding_report(
    path: Path,
    *,
    run_id: str,
    backend_name: str,
    real_adapter_status: str,
    files_changed: Sequence[str],
    test_commands: Sequence[str],
    smoke_commands: Sequence[str],
    dimension_summary: str,
    normalization_summary: str,
    runtime_summary: str,
    memory_summary: str,
    short_segment_summary: str,
    similarity_distribution: SimilarityDistribution | None,
    serialization_summary: str,
    runner_contract: str,
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the M9 speaker embedding component report artifact."""

    lines = [
        "# Speaker Embedding Component Report",
        "",
        "## Milestone",
        "",
        "M9 - Speaker Embedding Interface and First Adapter",
        "",
        f"- Run id: `{run_id}`",
        f"- Selected backend: `{backend_name}`",
        f"- Real adapter status: {real_adapter_status}",
        "",
        "## Files Changed",
        "",
        *[f"- `{file_path}`" for file_path in files_changed],
        "",
        "## Summary",
        "",
        "M9 adds a swappable speaker embedding interface, a deterministic fake adapter,",
        "and a lazy SpeechBrain ECAPA adapter boundary that produces normalized vectors",
        "when local model assets are available.",
        "",
        "## Runner Contract Preservation",
        "",
        runner_contract,
        "",
        "## Commands",
        "",
        *[f"- `{command}`" for command in test_commands],
        *[f"- `{command}`" for command in smoke_commands],
        "",
        "## Validation Checks",
        "",
        f"- Dimension checks: {dimension_summary}",
        f"- Normalization checks: {normalization_summary}",
        f"- Serialization checks: {serialization_summary}",
        f"- Runtime RTF: {runtime_summary}",
        f"- Memory: {memory_summary}",
        f"- Short-segment failure/flag rate: {short_segment_summary}",
        "",
        "## Similarity Distribution",
        "",
    ]
    if similarity_distribution is None:
        lines.append("- Not available for this run.")
    else:
        lines.extend(similarity_distribution.to_markdown_rows())
    lines.extend(["", "## Blockers", ""])
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- None known.")
    lines.extend(["", "## Incomplete", ""])
    if incomplete:
        lines.extend(f"- {item}" for item in incomplete)
    else:
        lines.append("- None known.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"
