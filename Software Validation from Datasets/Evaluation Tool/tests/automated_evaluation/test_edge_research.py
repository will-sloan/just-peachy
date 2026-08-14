from __future__ import annotations

import json
from pathlib import Path

from app.artifact_contracts.atomic import file_sha256
from app.campaign_executor.planner import load_scenario_catalog


TOOL_ROOT = Path(__file__).resolve().parents[2]
EDGE_ROOT = TOOL_ROOT / "benchmarks" / "edge_research"


EXISTING_LARGE_CATALOGS = {
    "campaign_edge_lg_mtiny_v1": (
        "benchmarks/edge_research/scenarios_edge_large_moon_tiny.jsonl",
        "A1FDF81CC793F7A96167387DEDDAE0DB6E9B38A2A8C9B23C7BDB0F082EA3B6B5",
        "moonshine-edge",
    ),
    "campaign_edge_lg_msmall_v1": (
        "benchmarks/edge_research/scenarios_edge_large_moon_small.jsonl",
        "8E5DC97269CDBCD7B29A19FD8E7AA9F40CBAF355527FA313B585908E2719E893",
        "moonshine-edge",
    ),
    "campaign_edge_lg_mmed_v1": (
        "benchmarks/edge_research/scenarios_edge_large_moon_medium.jsonl",
        "0C6142DB4DC524643A0DCDC635C61BE6DF775950151EA3E80280A8D360CBFB84",
        "moonshine-edge",
    ),
    "campaign_edge_lg_sh20_v1": (
        "benchmarks/edge_research/scenarios_edge_large_sherpa20.jsonl",
        "F6DF09D181528951FE198AB2D57B72EEAE51D3C2C6080E6FB9F79AA0F670CC3C",
        "onnx",
    ),
    "campaign_edge_lg_wbase_v1": (
        "benchmarks/edge_research/scenarios_edge_large_whisper_base_control.jsonl",
        "D3B0902E7837E4556DA9704647B375E868F2095C5A336743483C4D195BD13B71",
        "core-cpu",
    ),
}


def test_edge_queue_catalog_counts_and_profile_isolation() -> None:
    queue = json.loads((EDGE_ROOT / "edge_research_queue.json").read_text(encoding="utf-8"))
    asr_jobs = [row for row in queue["jobs"] if row["kind"] == "asr_campaign"]

    assert len(asr_jobs) == 12
    assert sum(int(row["expected_scenario_count"]) for row in asr_jobs) == 596
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


def test_existing_large_catalogs_remain_frozen() -> None:
    queue = json.loads((EDGE_ROOT / "edge_research_queue.json").read_text(encoding="utf-8"))
    jobs = {row["campaign_id"]: row for row in queue["jobs"] if row["kind"] == "asr_campaign"}

    for campaign_id, (relative_path, expected_sha256, profile) in EXISTING_LARGE_CATALOGS.items():
        job = jobs[campaign_id]
        assert job["catalog"] == relative_path
        assert job["catalog_sha256"] == expected_sha256
        assert job["environment_profile"] == profile
        assert job["expected_scenario_count"] == 32
        assert file_sha256(TOOL_ROOT / relative_path) == expected_sha256


def test_new_large_asr_isolation_catalogs() -> None:
    queue = json.loads((EDGE_ROOT / "edge_research_queue.json").read_text(encoding="utf-8"))
    jobs = {row["campaign_id"]: row for row in queue["jobs"] if row["kind"] == "asr_campaign"}
    expected = {
        "campaign_edge_lg_shorig_v1": (
            "benchmarks/edge_research/scenarios_edge_large_sherpa_original.jsonl",
            "sherpa_onnx",
            "onnx",
        ),
        "campaign_edge_lg_wsmall_v1": (
            "benchmarks/edge_research/scenarios_edge_large_whisper_small.jsonl",
            "whisper_small",
            "core-cpu",
        ),
    }

    for campaign_id, (relative_path, asr_name, profile) in expected.items():
        job = jobs[campaign_id]
        assert job["catalog"] == relative_path
        assert job["environment_profile"] == profile
        assert job["expected_scenario_count"] == 32
        assert not job["enabled_by_default"]
        assert not job["streaming"]
        rows = load_scenario_catalog(TOOL_ROOT / relative_path)
        assert len(rows) == 32
        for row in rows:
            assert row["benchmark_manifest"]["manifest_id"] == "manifest_bc207e61b820"
            assert row["benchmark_manifest"]["sha256"] == (
                "BC207E61B82052F06CCB9FFFE038B6DFE7B1C65C21843D08905946114238DE88"
            )
            assert row["pipeline"]["environment_profile"] == profile
            assert row["pipeline"]["components"]["asr"]["name"] == asr_name
            assert {
                family: row["pipeline"]["components"][family]["name"]
                for family in (
                    "vad",
                    "segmentation",
                    "speaker_embedding",
                    "speaker_matching",
                    "diarization",
                )
            } == {
                "vad": "no_op_vad",
                "segmentation": "no_op_segmentation",
                "speaker_embedding": "no_op_speaker_embedding",
                "speaker_matching": "no_op_speaker_matching",
                "diarization": "no_op_diarization",
            }
            assert "streaming_diagnostics" not in row["artifact_contract"]["capabilities"]


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
