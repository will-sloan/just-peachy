from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from app.full_pipeline_evaluation.io import sha256_file
from app.full_pipeline_extended_evaluation import scope_fields
from app.full_pipeline_extended_evaluation import execution


def _manifest(paths: list[Path]) -> dict[str, object]:
    return {
        "schema_version": "full-pipeline-hardening-input-manifest.v1",
        **scope_fields(),
        "outcome_independent": True,
        "inputs": [
            {
                "input_id": "long",
                "path": str(paths[0]),
                "sha256": sha256_file(paths[0]),
                "duration_sec": 3600.0,
                "roles": [
                    "deterministic_replay",
                    "controlled_loopback",
                    "repeated_session",
                    "soak",
                ],
            },
            *[
                {
                    "input_id": f"prompt6_long_stream_{index}",
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "duration_sec": 1800.0,
                    "roles": ["prompt6_long_stream"],
                    "source_evidence": {
                        "provenance_identity_sha256": str(index) * 64,
                    },
                }
                for index, path in enumerate(paths[1:3], start=1)
            ],
            *[
                {
                    "input_id": f"enrollment_{index}",
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "duration_sec": 1.0,
                    "roles": ["enrollment_sample"],
                }
                for index, path in enumerate(paths[3:], start=1)
            ],
        ],
    }


def test_hardening_validator_checks_true_wav_duration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = [tmp_path / f"input_{index}.wav" for index in range(6)]
    for path in paths:
        path.write_bytes(b"synthetic-wav-fixture")
    manifest = _manifest(paths)

    monkeypatch.setattr(
        execution,
        "_audio_duration",
        lambda path: (
            3600.0
            if Path(path) == paths[0]
            else 1800.0
            if Path(path) in paths[1:3]
            else 1.0
        ),
    )
    execution._validate_hardening_manifest(manifest)

    monkeypatch.setattr(execution, "_audio_duration", lambda path: 1.0)
    with pytest.raises(Exception, match="declared duration differs"):
        execution._validate_hardening_manifest(manifest)


def test_common_runtime_forwards_durable_stop_request() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self.stopped = threading.Event()
            self.request_count = 0

        def run(self) -> dict[str, object]:
            while not self.stopped.wait(0.01):
                pass
            return {"completion_state": "stopped"}

        def request_stop(self) -> None:
            self.request_count += 1
            self.stopped.set()

    runtime = FakeRuntime()
    requested_at = time.monotonic()
    result = execution._run_with_stop(
        runtime,
        stop_requested=lambda: time.monotonic() - requested_at > 0.03,
    )

    assert result["completion_state"] == "stopped"
    assert runtime.request_count == 1


def test_serial_resource_result_separates_warmup_and_unsupported_energy(
    tmp_path: Path,
) -> None:
    telemetry = tmp_path / "telemetry/resource_samples.jsonl"
    telemetry.parent.mkdir(parents=True)
    telemetry.write_text(
        "\n".join(
            json.dumps(
                {
                    "elapsed_sec": elapsed,
                    "process_cpu_percent": 25.0,
                    "process_rss_bytes": 1000 + elapsed,
                }
            )
            for elapsed in (30, 60, 180, 359)
        )
        + "\n",
        encoding="utf-8",
    )
    metrics = tmp_path / "metrics/runtime_metrics.json"
    metrics.parent.mkdir(parents=True)
    metrics.write_text(
        json.dumps(
            {
                "queue": {"maximum_observed_depth": 4, "dropped_frames": 0},
                "counts": {"deadline_miss_count": 0},
            }
        ),
        encoding="utf-8",
    )

    value = execution._resource_result(
        {"completion_state": "complete"},
        tmp_path,
        wall_sec=363.0,
        warmup_sec=60.0,
        measured_sec=300.0,
        startup_sec=3.0,
        model_bytes=1234,
        cache_bytes_before=100,
        cache_bytes_after=150,
    )

    assert value["total_rtf"] == 1.0
    assert value["model_bytes"] == 1234
    assert value["cache_bytes"] == 150
    assert value["cache_growth_bytes"] == 50
    assert value["measured_telemetry_sample_count"] == 3
    assert value["dropped_frames"] == 0
    assert value["deadline_miss_count"] == 0
    assert value["component_rtf"] is None
    assert value["component_rtf_measurement_status"] == (
        "UNSUPPORTED_NO_MEASURED_PROCESSING_AUDIO_PAIRS"
    )
    assert value["energy_proxy_status"].startswith("unsupported")
    assert value["beaker_power_claimed"] is False
