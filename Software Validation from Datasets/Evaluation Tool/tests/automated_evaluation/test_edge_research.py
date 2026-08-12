from __future__ import annotations

import json
from pathlib import Path

from app.campaign_executor.planner import load_scenario_catalog


TOOL_ROOT = Path(__file__).resolve().parents[2]
EDGE_ROOT = TOOL_ROOT / "benchmarks" / "edge_research"


def test_edge_queue_catalog_counts_and_profile_isolation() -> None:
    queue = json.loads((EDGE_ROOT / "edge_research_queue.json").read_text(encoding="utf-8"))
    asr_jobs = [row for row in queue["jobs"] if row["kind"] == "asr_campaign"]

    assert len(asr_jobs) == 10
    assert sum(int(row["expected_scenario_count"]) for row in asr_jobs) == 532
    assert sum(
        int(row["expected_scenario_count"])
        for row in asr_jobs
        if row["enabled_by_default"]
    ) == 84
    for job in asr_jobs:
        rows = load_scenario_catalog(TOOL_ROOT / job["catalog"])
        assert len(rows) == job["expected_scenario_count"]
        assert {
            row["pipeline"]["environment_profile"] for row in rows
        } == {job["environment_profile"]}


def test_streaming_catalogs_require_streaming_diagnostics() -> None:
    queue = json.loads((EDGE_ROOT / "edge_research_queue.json").read_text(encoding="utf-8"))
    for job in queue["jobs"]:
        if job.get("kind") != "asr_campaign" or not job.get("streaming"):
            continue
        rows = load_scenario_catalog(TOOL_ROOT / job["catalog"])
        assert all(
            "streaming_diagnostics" in row["artifact_contract"]["capabilities"]
            for row in rows
        )
