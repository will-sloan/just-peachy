"""Create simple evaluation plots."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from app.dataset_registry.registry import get_dataset


def build_plots(run_dir: Path, dataset_key: str, logger: logging.Logger) -> list[Path]:
    """Build Phase 1 plots from saved metrics."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics_path = run_dir / "metrics" / "per_recording_metrics.csv"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Cannot build plots; missing {metrics_path}")

    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    metrics_df = _sanitize_metrics_for_plotting(pd.read_csv(metrics_path))
    if metrics_df.empty:
        logger.warning("No metric rows found; skipping plots")
        return []

    created: list[Path] = []
    scored_df = _scored_metrics(metrics_df)
    if scored_df.empty:
        logger.warning("No scored prediction rows found; skipping transcript metric plots")
    else:
        _append_plot(created, logger, "WER histogram", lambda: _plot_wer_histogram(scored_df, plots_dir, plt))
        _append_plot(
            created,
            logger,
            "substitution histogram",
            lambda: _plot_substitution_histogram(scored_df, plots_dir, plt),
        )
        _append_plot(created, logger, "worst recordings", lambda: _plot_worst_recordings(scored_df, plots_dir, plt))
        _append_plot(
            created,
            logger,
            "worst substitutions",
            lambda: _plot_worst_substitutions(scored_df, plots_dir, plt),
        )

    definition = get_dataset(dataset_key)
    group_columns = [
        *definition.group_metric_columns,
        "augmentation_condition_id",
        "augmentation_mode",
        "snr_db",
        "rir_label",
        "noise_type",
    ]
    for group_column in dict.fromkeys(group_columns):
        group_metrics_path = run_dir / "metrics" / f"{group_column}_metrics.csv"
        if group_metrics_path.exists():
            group_df = pd.read_csv(group_metrics_path)
            if not group_df.empty:
                _append_plot(
                    created,
                    logger,
                    f"{group_column} group summary",
                    lambda group_df=group_df, group_column=group_column: _plot_group_summary(
                        group_df=group_df,
                        group_column=group_column,
                        plots_dir=plots_dir,
                        plt=plt,
                        dataset_key=definition.key,
                    ),
                )
    speaker_confusion_path = run_dir / "metrics" / "speaker_label_confusion.csv"
    if speaker_confusion_path.exists():
        confusion_df = pd.read_csv(speaker_confusion_path)
        if not confusion_df.empty:
            _append_plot(
                created,
                logger,
                "speaker label confusion summary",
                lambda: _plot_speaker_confusion_summary(confusion_df, plots_dir, plt),
            )

    logger.info("Created %d plots", len(created))
    return created


def _sanitize_metrics_for_plotting(metrics_df: pd.DataFrame) -> pd.DataFrame:
    result = metrics_df.copy()
    if "missing_prediction" not in result.columns:
        result["missing_prediction"] = False
    result["missing_prediction"] = result["missing_prediction"].fillna(False).astype(bool)
    if "transcript_scored" not in result.columns:
        result["transcript_scored"] = ~result["missing_prediction"]
    result["transcript_scored"] = result["transcript_scored"].fillna(False).astype(bool)
    for column in ("wer", "errors", "substitutions", "insertions", "deletions"):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _scored_metrics(metrics_df: pd.DataFrame) -> pd.DataFrame:
    scored = metrics_df[
        (metrics_df["missing_prediction"] == False)  # noqa: E712
        & (metrics_df["transcript_scored"] == True)  # noqa: E712
    ].copy()
    if "wer" in scored.columns:
        scored = scored[scored["wer"].notna()]
    return scored


def _append_plot(created: list[Path], logger: logging.Logger, label: str, build) -> None:
    try:
        path = build()
    except Exception as exc:  # pragma: no cover - defensive plotting boundary
        logger.warning("Skipping %s plot: %s", label, exc)
        return
    if path is not None:
        created.append(path)


def _plot_wer_histogram(metrics_df: pd.DataFrame, plots_dir: Path, plt) -> Path:
    path = plots_dir / "wer_histogram.png"
    values = pd.to_numeric(metrics_df["wer"], errors="coerce").dropna()
    if values.empty:
        raise ValueError("no valid WER values")
    plt.figure(figsize=(8, 5))
    plt.hist(values.clip(lower=0, upper=max(1.0, values.max())), bins=30)
    plt.xlabel("Per-recording WER")
    plt.ylabel("Recording count")
    plt.title("Distribution of per-recording WER")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path


def _plot_worst_recordings(metrics_df: pd.DataFrame, plots_dir: Path, plt) -> Path:
    path = plots_dir / "worst_recordings.png"
    metrics_df = metrics_df[metrics_df["wer"].notna()]
    if metrics_df.empty:
        raise ValueError("no valid WER values")
    top = metrics_df.sort_values(["wer", "errors"], ascending=False).head(15)
    labels = _string_labels(top["recording_id"])
    plt.figure(figsize=(10, max(4, len(top) * 0.35)))
    plt.barh(labels[::-1], top["wer"].tolist()[::-1])
    plt.xlabel("WER")
    plt.ylabel("Recording")
    plt.title("Worst recordings by WER")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path


def _plot_substitution_histogram(metrics_df: pd.DataFrame, plots_dir: Path, plt) -> Path:
    path = plots_dir / "substitutions_histogram.png"
    values = pd.to_numeric(metrics_df["substitutions"], errors="coerce").dropna()
    if values.empty:
        raise ValueError("no valid substitution values")
    plt.figure(figsize=(8, 5))
    plt.hist(values, bins=min(30, max(5, int(values.max()) + 1)))
    plt.xlabel("Substitutions per recording")
    plt.ylabel("Recording count")
    plt.title("Distribution of substitutions")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path


def _plot_worst_substitutions(metrics_df: pd.DataFrame, plots_dir: Path, plt) -> Path:
    path = plots_dir / "worst_recordings_by_substitutions.png"
    metrics_df = metrics_df[metrics_df["substitutions"].notna()]
    if metrics_df.empty:
        raise ValueError("no valid substitution values")
    top = metrics_df.sort_values(["substitutions", "wer"], ascending=False).head(15)
    labels = _string_labels(top["recording_id"])
    plt.figure(figsize=(10, max(4, len(top) * 0.35)))
    plt.barh(labels[::-1], top["substitutions"].tolist()[::-1])
    plt.xlabel("Substitutions")
    plt.ylabel("Recording")
    plt.title("Worst recordings by substitutions")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path


def _plot_group_summary(
    group_df: pd.DataFrame,
    group_column: str,
    plots_dir: Path,
    plt,
    dataset_key: str,
) -> Path:
    path = plots_dir / f"{dataset_key}_{group_column}_summary.png"
    if group_column not in group_df.columns or "aggregate_wer" not in group_df.columns:
        raise ValueError(f"missing required group columns for {group_column}")
    group_df = group_df.copy()
    group_df[group_column] = _string_labels(group_df[group_column])
    group_df["aggregate_wer"] = pd.to_numeric(group_df["aggregate_wer"], errors="coerce")
    group_df["recordings"] = pd.to_numeric(group_df.get("recordings", group_df.get("file_count")), errors="coerce")
    group_df = group_df[group_df["aggregate_wer"].notna() & group_df["recordings"].notna()]
    if group_df.empty:
        raise ValueError(f"no valid group rows for {group_column}")
    plot_df = group_df.sort_values("recordings", ascending=False)
    plot_df = plot_df.sort_values(group_column)
    plt.figure(figsize=(max(9, min(32, len(plot_df) * 0.55)), 5))
    plt.bar(plot_df[group_column].astype(str), plot_df["aggregate_wer"])
    plt.xlabel(group_column.replace("_", " ").title())
    plt.ylabel("Aggregate WER")
    plt.title(f"{group_column.replace('_', ' ').title()} WER Summary")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path


def _plot_speaker_confusion_summary(confusion_df: pd.DataFrame, plots_dir: Path, plt) -> Path:
    path = plots_dir / "speaker_label_confusion_summary.png"
    plot_df = confusion_df.sort_values("file_count", ascending=False).head(20).copy()
    plot_df["pair"] = (
        _string_labels(plot_df["speaker_label"])
        + " -> "
        + _string_labels(plot_df["predicted_speaker_label"])
    )
    plt.figure(figsize=(10, max(4, len(plot_df) * 0.35)))
    plt.barh(plot_df["pair"].tolist()[::-1], plot_df["file_count"].tolist()[::-1])
    plt.xlabel("Segment count")
    plt.ylabel("Reference -> predicted speaker")
    plt.title("Speaker Label Pair Counts")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path


def _string_labels(series: pd.Series) -> pd.Series:
    return series.map(_string_label)


def _string_label(value: object) -> str:
    if value is None:
        return "(missing)"
    try:
        if pd.isna(value):
            return "(missing)"
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in {"nan", "null"}:
        return "(missing)"
    return text
