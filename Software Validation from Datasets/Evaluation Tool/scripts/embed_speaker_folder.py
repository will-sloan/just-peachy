"""Embed a folder of audio samples with a speaker embedding backend."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
import soundfile as sf


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.speaker_embedding import (
    DeterministicFakeSpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
    component_report_path,
    summarize_similarity_distribution,
    vector_l2_norm,
    write_speaker_embedding_report,
)
from app.inference_pipeline.speaker_embedding.speechbrain_adapter import (
    SpeechBrainECAPAAdapter,
)
from app.utils.json_utils import write_jsonl


AUDIO_SUFFIXES = {".wav", ".flac", ".ogg", ".aiff", ".aif"}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = args.run_id or time.strftime("m9_speaker_embedding_%Y%m%d_%H%M%S")
    input_dir = args.input_dir
    output_path = args.output
    report_path = (
        args.report
        if args.report is not None
        else component_report_path(TOOL_ROOT / "reports", run_id)
    )
    labels = load_labels(args.labels_csv, input_dir)
    adapter = build_adapter(args)
    rows = embed_folder(
        adapter,
        input_dir=input_dir,
        recursive=args.recursive,
        labels=labels,
        run_id=run_id,
        device=args.device,
    )
    write_embeddings(output_path, rows)
    similarity = summarize_similarity_distribution(rows)
    write_speaker_embedding_report(
        report_path,
        run_id=run_id,
        backend_name=adapter.model_name,
        real_adapter_status=real_adapter_status(args.backend, rows),
        files_changed=["scripts/embed_speaker_folder.py"],
        test_commands=[],
        smoke_commands=[command_summary(args, output_path, report_path)],
        dimension_summary=dimension_summary(rows),
        normalization_summary=normalization_summary(rows),
        runtime_summary=runtime_summary(rows),
        memory_summary=memory_summary(rows),
        short_segment_summary=short_segment_summary(rows),
        similarity_distribution=similarity,
        serialization_summary=f"wrote {len(rows)} row(s) to {output_path}",
        runner_contract=(
            "Standalone speaker embedding script does not modify predictions/utterances.jsonl "
            "or the Evaluation Tool runner contract."
        ),
        blockers=blockers_summary(args.backend, rows),
        incomplete=incomplete_summary(args.backend, labels),
    )
    print(f"Embeddings: {output_path}")
    print(f"Report: {report_path}")
    return 0 if any(row.get("status") == "ok" for row in rows) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Embed a folder of audio samples.")
    parser.add_argument("input_dir", type=Path, help="Folder containing audio samples.")
    parser.add_argument("--output", type=Path, required=True, help="Output .jsonl or .parquet path.")
    parser.add_argument(
        "--backend",
        choices=["fake", "speechbrain"],
        default="fake",
        help="Embedding backend. Defaults to fake for local smoke checks.",
    )
    parser.add_argument("--run-id", default=None, help="Run id for the report artifact.")
    parser.add_argument("--report", type=Path, default=None, help="Optional report output path.")
    parser.add_argument("--labels-csv", type=Path, default=None, help="Optional labels CSV.")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subdirectories.")
    parser.add_argument("--device", default="cpu", help="Torch device for embedding.")
    parser.add_argument("--dimension", type=int, default=16, help="Fake adapter dimension.")
    parser.add_argument("--min-duration-sec", type=float, default=0.75, help="Too-short threshold.")
    parser.add_argument(
        "--allow-model-downloads",
        action="store_true",
        help="Allow SpeechBrain to download model assets.",
    )
    parser.add_argument(
        "--model-source",
        default="speechbrain/spkrec-ecapa-voxceleb",
        help="SpeechBrain source name or local model directory.",
    )
    parser.add_argument(
        "--savedir",
        type=Path,
        default=Path("models/cache/speechbrain/spkrec-ecapa-voxceleb"),
        help="SpeechBrain local asset/cache directory.",
    )
    return parser


def build_adapter(args: argparse.Namespace) -> SpeakerEmbeddingBase:
    if args.backend == "fake":
        return DeterministicFakeSpeakerEmbedding(
            dimension=args.dimension,
            min_duration_sec=args.min_duration_sec,
            device=args.device,
        )
    return SpeechBrainECAPAAdapter(
        {
            "model_source": args.model_source,
            "savedir": str(args.savedir),
            "sample_rate_hz": 16000,
            "embedding_dim": 192,
            "min_duration_sec": args.min_duration_sec,
            "device": args.device,
            "allow_model_downloads": args.allow_model_downloads,
        }
    )


def embed_folder(
    adapter: SpeakerEmbeddingBase,
    *,
    input_dir: Path,
    recursive: bool,
    labels: Mapping[str, str],
    run_id: str,
    device: str,
) -> list[dict[str, object]]:
    paths = discover_audio(input_dir, recursive=recursive)
    rows: list[dict[str, object]] = []
    for index, audio_path in enumerate(paths):
        info = sf.info(audio_path)
        duration_sec = int(info.frames) / int(info.samplerate)
        segment = AudioSegment(
            audio_path=audio_path,
            start_sec=None,
            end_sec=None,
            sample_rate_hz=int(info.samplerate),
            channel_count=int(info.channels),
            duration_sec=duration_sec,
        )
        label = label_for_path(audio_path, input_dir, labels)
        context = SpeakerEmbeddingContext(
            recording_id=audio_path.stem,
            utt_id=audio_path.stem,
            source_audio_path=audio_path,
            segment_index=index,
            device=device,
            run_config={"run_id": run_id},
        )
        embedding = adapter.embed(segment, context)
        row = embedding.to_jsonable()
        row["audio_path"] = str(audio_path)
        row["speaker_label"] = label
        rows.append(row)
    return rows


def discover_audio(input_dir: Path, *, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in input_dir.glob(pattern)
        if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES
    )


def load_labels(labels_csv: Path | None, input_dir: Path) -> dict[str, str]:
    if labels_csv is None:
        return {}
    labels: dict[str, str] = {}
    with labels_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            label = row.get("speaker_label") or row.get("label") or row.get("speaker")
            path_value = row.get("path") or row.get("audio_path") or row.get("file_name")
            if not label or not path_value:
                continue
            path = Path(path_value)
            labels[path.name] = label
            labels[path.as_posix()] = label
            if not path.is_absolute():
                labels[(input_dir / path).resolve().as_posix()] = label
    return labels


def label_for_path(audio_path: Path, input_dir: Path, labels: Mapping[str, str]) -> str | None:
    relative = audio_path.relative_to(input_dir).as_posix()
    return (
        labels.get(audio_path.resolve().as_posix())
        or labels.get(relative)
        or labels.get(audio_path.name)
    )


def write_embeddings(output_path: Path, rows: Sequence[dict[str, object]]) -> None:
    if output_path.suffix.lower() == ".parquet":
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(output_path, index=False)
        return
    write_jsonl(output_path, rows)


def real_adapter_status(backend: str, rows: Sequence[Mapping[str, object]]) -> str:
    if backend != "speechbrain":
        return "not selected; fake backend used for deterministic smoke check"
    ok_count = sum(1 for row in rows if row.get("status") == "ok")
    return f"ran successfully for {ok_count} row(s)" if ok_count else "did not produce embeddings"


def blockers_summary(backend: str, rows: Sequence[Mapping[str, object]]) -> list[str]:
    if backend != "speechbrain":
        return [
            "SpeechBrain ECAPA was not executed by this script run. Use --backend speechbrain "
            "with installed package and local model assets to validate the real adapter."
        ]
    if any(row.get("status") == "ok" for row in rows):
        return []
    return ["SpeechBrain ECAPA did not produce successful embeddings in this run."]


def incomplete_summary(backend: str, labels: Mapping[str, str]) -> list[str]:
    items: list[str] = []
    if backend != "speechbrain":
        items.append("Real SpeechBrain ECAPA quality separation remains unvalidated in this run.")
    if not labels:
        items.append("No labels CSV was supplied, so same-speaker vs different-speaker separation is unavailable.")
    return items


def dimension_summary(rows: Sequence[Mapping[str, object]]) -> str:
    dimensions = sorted({int(row.get("dimension") or 0) for row in rows if row.get("status") == "ok"})
    return f"successful dimensions={dimensions}" if dimensions else "no successful embeddings"


def normalization_summary(rows: Sequence[Mapping[str, object]]) -> str:
    norms = [
        vector_l2_norm(row["vector"])
        for row in rows
        if row.get("status") == "ok" and isinstance(row.get("vector"), Sequence)
    ]
    if not norms:
        return "no successful embeddings"
    return f"min_norm={min(norms):.4f}, max_norm={max(norms):.4f}"


def runtime_summary(rows: Sequence[Mapping[str, object]]) -> str:
    rtfs = [
        float(runtime["realtime_factor"])
        for row in rows
        if isinstance((runtime := row.get("runtime")), Mapping)
        and runtime.get("realtime_factor") is not None
    ]
    if not rtfs:
        return "n/a"
    return f"mean={sum(rtfs) / len(rtfs):.4f}, max={max(rtfs):.4f}"


def memory_summary(rows: Sequence[Mapping[str, object]]) -> str:
    values = [
        float(runtime["cpu_memory_mb"])
        for row in rows
        if isinstance((runtime := row.get("runtime")), Mapping)
        and runtime.get("cpu_memory_mb") is not None
    ]
    if not values:
        return "n/a"
    return f"max_cpu_memory_mb={max(values):.2f}"


def short_segment_summary(rows: Sequence[Mapping[str, object]]) -> str:
    if not rows:
        return "n/a"
    short_count = sum(1 for row in rows if row.get("status") == "too_short")
    return f"{short_count}/{len(rows)} ({short_count / len(rows):.4f})"


def command_summary(args: argparse.Namespace, output_path: Path, report_path: Path) -> str:
    parts = [
        "python",
        "scripts/embed_speaker_folder.py",
        str(args.input_dir),
        "--backend",
        args.backend,
        "--output",
        str(output_path),
        "--report",
        str(report_path),
        "--dimension",
        str(args.dimension),
        "--min-duration-sec",
        str(args.min_duration_sec),
    ]
    if args.labels_csv is not None:
        parts.extend(["--labels-csv", str(args.labels_csv)])
    if args.run_id is not None:
        parts.extend(["--run-id", str(args.run_id)])
    if args.recursive:
        parts.append("--recursive")
    if args.allow_model_downloads:
        parts.append("--allow-model-downloads")
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
