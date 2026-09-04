from __future__ import annotations

import json
from pathlib import Path
import random
import shutil
import subprocess
from unittest.mock import patch

from app.speaker_protocol.evaluation import (
    _eer_bootstrap,
    evaluate_protocol_rows,
    load_protocol_core_rows,
    observations_from_npz,
    validate_protocol_results,
)
from app.speaker_protocol.extraction import load_backend_identity
from app.speaker_protocol.metrics import equal_error_rate, threshold_sweep
from app.speaker_protocol.progress import EvaluationProgress


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]


def test_sorted_threshold_sweep_matches_legacy_reference_exactly() -> None:
    trials = [
        {"score": score, "is_target": target}
        for score, target in (
            (0.9, True), (0.9, False), (0.8, True), (0.4, False), (0.1, False)
        )
    ]
    assert threshold_sweep(trials, split="test") == _legacy_threshold_sweep(trials, "test")


def test_bootstrap_workers_one_and_six_are_exactly_deterministic() -> None:
    trials = [
        {"score": random.Random(index).random(), "is_target": index % 3 == 0}
        for index in range(120)
    ]
    serial = _eer_bootstrap(trials, seed=3800, repetitions=40, workers=1)
    parallel = _eer_bootstrap(trials, seed=3800, repetitions=40, workers=6)
    assert serial == parallel


def test_progress_is_atomic_and_contains_defensible_eta(tmp_path: Path) -> None:
    progress = EvaluationProgress(tmp_path, backend="test_backend", workers=6)
    progress.update("BOOTSTRAP", completed=0, total=100, force=True)
    progress.phase_clock -= 10.0
    progress.update("BOOTSTRAP", completed=25, total=100, force=True)
    payload = json.loads((tmp_path / "evaluation_progress.json").read_text(encoding="utf-8"))
    assert payload["workers"] == 6
    assert payload["bootstrap_percent"] == 25.0
    assert payload["estimated_remaining_sec"] > 0
    assert not list(tmp_path.glob("*.tmp"))


def test_progress_retries_transient_windows_reader_lock(tmp_path: Path) -> None:
    from app.speaker_protocol import progress as progress_module

    real_replace = progress_module.os.replace
    attempts = 0

    def transient_lock(source: Path, destination: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, "simulated Windows sharing violation")
        real_replace(source, destination)

    with patch.object(progress_module.os, "replace", side_effect=transient_lock):
        progress = EvaluationProgress(tmp_path, backend="test_backend", workers=6)
        progress.update("BOOTSTRAP", completed=1, total=2, force=True)

    assert attempts >= 3
    assert (tmp_path / "evaluation_progress.json").is_file()
    assert not list(tmp_path.glob("*.tmp"))


def test_status_treats_missing_protocol_run_as_partial_not_error(tmp_path: Path) -> None:
    protocol = TOOL_ROOT / "benchmarks" / "speaker_breadth" / "commonvoice_60plus_v1"
    summary = json.loads((protocol / "protocol_summary.json").read_text(encoding="utf-8"))
    result = tmp_path / summary["protocol_id"] / "speechbrain_ecapa" / "result"
    result.mkdir(parents=True)
    (result / "evaluation_progress.json").write_text(
        json.dumps({
            "status": "RUNNING", "phase": "BOOTSTRAP", "workers": 6,
            "bootstrap_completed": 10, "bootstrap_total": 500,
            "elapsed_sec": 5.0, "bootstrap_per_second": 2.0,
            "estimated_remaining_sec": 245.0,
        }),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            shutil.which("powershell") or "powershell",
            "-ExecutionPolicy", "Bypass", "-File",
            str(TOOL_ROOT / "scripts" / "run_speaker_breadth_commonvoice.ps1"),
            "-Action", "Status", "-ProtocolRoot", str(protocol),
            "-ResultBase", str(tmp_path), "-Backends", "speechbrain_ecapa",
            "-EvaluationWorkers", "6",
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "EVALUATING:BOOTSTRAP" in completed.stdout
    assert "10/500" in completed.stdout


def test_wrapper_preserves_interrupted_result_after_reusing_extraction() -> None:
    wrapper = (
        TOOL_ROOT / "scripts" / "run_speaker_breadth_commonvoice.ps1"
    ).read_text(encoding="utf-8")
    reuse = wrapper.index("if (Test-ValidExtraction $ExtractionRoot $Backend)", wrapper.index("'Run'"))
    preserve = wrapper.index("Move-Item -LiteralPath $ResultRoot -Destination $Quarantine", reuse)
    evaluate = wrapper.index("speaker-protocol evaluate", preserve)
    assert reuse < preserve < evaluate
    assert "result.partial" not in wrapper  # The label is inserted without deleting the original.
    assert "'partial'" in wrapper[preserve - 400:preserve]


def test_commonvoice_bounded_existing_speechbrain_extraction_smoke(tmp_path: Path) -> None:
    protocol = TOOL_ROOT / "benchmarks" / "speaker_breadth" / "commonvoice_60plus_v1"
    protocol_id = "commonvoice_60plus_v1_27e72793b4c0"
    extraction = (
        TOOL_ROOT / "JustPeachyResults" / "speaker_breadth" / "commonvoice_60plus_v1"
        / protocol_id / "speechbrain_ecapa" / "extraction"
    )
    identity = load_backend_identity(extraction / "backend_identity.json")
    observations = observations_from_npz(extraction / "observations.npz", identity)
    rows = load_protocol_core_rows(protocol)
    speaker_keys = list(dict.fromkeys(row["speaker_key"] for row in rows["enrollment"]))[:2]
    bounded = {
        "enrollment": [row for row in rows["enrollment"] if row["speaker_key"] in speaker_keys],
        "calibration": [
            row for row in rows["calibration"]
            if row["speaker_key"] in speaker_keys
        ][:4] + [row for row in rows["calibration"] if not row["known_speaker"]][:2],
        "known_evaluation": [
            row for row in rows["known_evaluation"]
            if row["speaker_key"] in speaker_keys
        ][:4],
        "unknown_evaluation": rows["unknown_evaluation"][:2],
    }
    wanted = {str(row["item_id"]) for values in bounded.values() for row in values}
    bounded_observations = [row for row in observations if row.item_id in wanted]
    progress = EvaluationProgress(tmp_path, backend=identity.backend_id, workers=6)
    evaluate_protocol_rows(
        bounded,
        bounded_observations,
        identity,
        tmp_path,
        scope="commonvoice_bounded_engineering_smoke",
        workers=6,
        progress=progress,
    )
    assert validate_protocol_results(tmp_path)["valid"] is True
    payload = json.loads((tmp_path / "evaluation_progress.json").read_text(encoding="utf-8"))
    assert payload["phase"] == "COMPLETE"
    assert payload["workers"] == 6


def _legacy_threshold_sweep(trials: list[dict[str, object]], split: str) -> list[dict[str, object]]:
    materialized = [(float(row["score"]), bool(row["is_target"])) for row in trials]
    positives = sum(target for _, target in materialized)
    negatives = len(materialized) - positives
    values = sorted({score for score, _ in materialized}, reverse=True)
    rows = []
    for threshold in [values[0] + 1e-12, *values, values[-1] - 1e-12]:
        tp = sum(score >= threshold and target for score, target in materialized)
        fp = sum(score >= threshold and not target for score, target in materialized)
        fn = positives - tp
        tn = negatives - fp
        far = fp / negatives
        frr = fn / positives
        rows.append({
            "schema_version": "speaker-threshold-sweep.v1", "split": split,
            "threshold": float(threshold), "true_accepts": tp, "false_accepts": fp,
            "true_rejects": tn, "false_rejects": fn, "positive_trials": positives,
            "negative_trials": negatives, "far": far, "frr": frr,
            "tar": tp / positives, "tpr": tp / positives, "fpr": far, "fnr": frr,
        })
    return rows
