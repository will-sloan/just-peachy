from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.campaign_executor import runtime


class _PublishedArtifacts:
    def __init__(self, *_args, **_kwargs) -> None:
        self.json: dict[str, object] = {}
        self.jsonl: dict[str, list[dict[str, object]]] = {}

    def publish_json(self, path: str, value: object) -> None:
        self.json[path] = value

    def publish_jsonl(self, path: str, rows) -> None:
        self.jsonl[path] = list(rows)

    def publish_parquet(self, _path: str, _table) -> None:
        return None

    def publish_text(self, _path: str, _value: str) -> None:
        return None


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_publication_materializes_jsonl_iterators_before_counting(
    tmp_path: Path, monkeypatch
) -> None:
    scenario_root = tmp_path / "scenario"
    work_dir = tmp_path / "work"
    (scenario_root / "logs").mkdir(parents=True)
    (work_dir / "metrics").mkdir(parents=True)
    (work_dir / "report").mkdir(parents=True)
    _write_jsonl(
        work_dir / "predictions" / "utterances.jsonl",
        [{"recording_id": "recording-1", "utt_id": "utterance-1", "text": "hello"}],
    )
    _write_jsonl(
        work_dir / "predictions" / "diagnostics.jsonl",
        [{"recording_id": "recording-1", "utt_id": "utterance-1"}],
    )
    _write_jsonl(work_dir / "predictions" / "failures.jsonl", [])
    (work_dir / "metrics" / "per_recording_metrics.csv").write_text(
        "recording_id,utt_id,wer\nrecording-1,utterance-1,0.0\n",
        encoding="utf-8",
    )
    (work_dir / "report" / "report.md").write_text(
        "# Evaluation Report\n",
        encoding="utf-8",
    )

    published = _PublishedArtifacts()
    monkeypatch.setattr(runtime, "ScenarioArtifactStore", lambda *_a, **_k: published)
    runtime._publish_final_artifacts(
        scenario_root,
        {
            "scenario_id": "scenario_123456789abc",
            "scenario_hash": "A" * 64,
        },
        work_dir,
        runner_result=SimpleNamespace(
            attempted_count=1,
            written_count=1,
            failed_count=0,
        ),
        aggregate_metrics={"wer": 0.0},
        records=[{"recording_id": "recording-1", "utt_id": "utterance-1"}],
        completion_state="complete",
        registry=SimpleNamespace(schema_version="artifact-registry.v2"),
    )

    summary = published.json["metrics/summary.json"]
    assert summary["counts"] == {
        "selected_items": 1,
        "successful_items": 1,
        "failed_items": 0,
        "predictions": 1,
        "diagnostics": 1,
        "item_metrics": 1,
        "grouped_metrics": 1,
        "error_records": 0,
    }
    assert published.jsonl["predictions/utterances.jsonl"][0]["text"] == "hello"
