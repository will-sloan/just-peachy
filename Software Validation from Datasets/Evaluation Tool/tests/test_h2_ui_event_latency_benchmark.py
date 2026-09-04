from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.measure_h2_ui_event_latency import (
    build_receipt,
    measure_ui_latency,
    summarize_latencies,
    validate_receipt,
)


def _runtime_identity() -> dict[str, object]:
    return {
        "schema_version": "h2-runtime-implementation-identity.v2",
        "components": {},
        "installed_worker_environments": {},
        "identity_sha256": "a" * 64,
    }


def _sample(index: int, latency_ms: float) -> dict[str, object]:
    emitted = 1_000_000_000 + index * 10_000_000
    rendered = emitted + int(latency_ms * 1_000_000)
    return {
        "sample_index": index,
        "event_sequence": index,
        "injection_phase_offset_ms": 0,
        "emitted_monotonic_ns": emitted,
        "render_completed_monotonic_ns": rendered,
        "latency_ms": (rendered - emitted) / 1_000_000.0,
        "last_event_widget_value": f"#{index} IdentityLabelEvent",
        "last_event_widget_verified": True,
        "roster_widget_verified": True,
    }


def _metadata() -> dict[str, object]:
    return {
        "tk_patchlevel": "test",
        "configured_poll_interval_ms": 100,
        "phase_offsets_ms": [0],
        "durable_event_path_exercised": True,
        "coalescing_update_buffer_exercised": True,
        "background_task_runner_exercised": True,
        "tk_widget_render_verified": True,
    }


def test_latency_summary_uses_interpolated_percentiles() -> None:
    summary = summarize_latencies([10.0, 20.0, 30.0, 40.0])
    assert summary["sample_count"] == 4
    assert summary["median_ms"] == 25.0
    assert summary["p95_ms"] == pytest.approx(38.5)
    assert summary["p99_ms"] == pytest.approx(39.7)


def test_direct_script_launch_resolves_evaluation_tool_imports() -> None:
    tool_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(tool_root / "scripts/measure_h2_ui_event_latency.py"),
            "--help",
        ],
        cwd=tool_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30.0,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--workspace" in completed.stdout


def test_signed_receipt_recomputes_metrics_and_rejects_tampering() -> None:
    receipt = build_receipt(
        samples=[_sample(1, 10.0), _sample(2, 20.0), _sample(3, 30.0)],
        benchmark_metadata=_metadata(),
        runtime_identity=_runtime_identity(),
        runtime_identity_file_sha256="b" * 64,
        warmup_count=1,
        timeout_sec=1.0,
    )
    validated = validate_receipt(
        receipt, expected_runtime_identity_sha256="a" * 64
    )
    assert validated["metrics"]["mean_ms"] == 20.0
    changed = copy.deepcopy(receipt)
    changed["samples"][0]["latency_ms"] = 999.0
    with pytest.raises(ValueError, match="signature"):
        validate_receipt(changed)


def test_real_hidden_tk_durable_event_to_widget_path(tmp_path: Path) -> None:
    try:
        samples, metadata = measure_ui_latency(
            working_root=tmp_path,
            sample_count=2,
            warmup_count=1,
            timeout_sec=3.0,
            phase_offsets_ms=(0, 25),
        )
    except Exception as exc:
        if exc.__class__.__name__ == "UiLatencyBenchmarkError" and "Tk cannot" in str(
            exc
        ):
            pytest.skip(str(exc))
        raise
    assert len(samples) == 2
    assert all(float(row["latency_ms"]) >= 0.0 for row in samples)
    assert all(row["last_event_widget_verified"] is True for row in samples)
    assert all(row["roster_widget_verified"] is True for row in samples)
    assert metadata["durable_event_path_exercised"] is True
    assert metadata["background_task_runner_exercised"] is True
