"""Environment-aware, restart-safe native Stage 11 campaign controller."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Mapping, Sequence
import zipfile

from app.controlled_diarization.contracts import TOOL_ROOT, sha256_file
from app.controlled_diarization.runner import interpreter_for_profile
from app.diarization_evaluation.analysis import aggregate_native_results
from app.diarization_evaluation.artifacts import write_json_atomic, write_text_atomic
from app.diarization_evaluation.execution import validate_diarization_result
from app.diarization_evaluation.manifests import (
    build_native_diarization_manifest,
    read_native_manifest,
)
from app.diarization_product_v2.contracts import DEFAULT_RESULT_ROOT


ROOT = DEFAULT_RESULT_ROOT / "native_campaign"
MANIFEST_ROOT = ROOT / "manifest"
RESULTS_ROOT = ROOT / "results"
PROGRESS = ROOT / "progress.json"
STOP = ROOT / "STOP_REQUESTED"


def audit() -> dict[str, object]:
    if not (MANIFEST_ROOT / "native_diarization_manifest.parquet").is_file():
        build_native_diarization_manifest(MANIFEST_ROOT, tier="small")
    rows = read_native_manifest(MANIFEST_ROOT / "native_diarization_manifest.parquet")
    onnx = interpreter_for_profile("onnx")
    result = {
        "schema_version": "diarization-native-campaign-audit.v2",
        "manifest_units": len(rows),
        "chime6_units": sum(row["dataset"] == "chime6" for row in rows),
        "voices_units": sum(row["dataset"] == "voices" for row in rows),
        "voices_der_jer_suppressed": all(
            not row["der_jer_eligible"] for row in rows if row["dataset"] == "voices"
        ),
        "onnx_environment": str(onnx) if onnx else None,
        "onnx_environment_exists": bool(onnx and onnx.is_file()),
        "final_chime_campaign_authorized": False,
    }
    write_json_atomic(ROOT / "audit.json", result)
    return result


def plan(
    *, dataset: Sequence[str] = ("chime6", "voices"),
    backend: Sequence[str] = ("sherpa_onnx_diarization",),
) -> dict[str, object]:
    audit()
    rows = [
        row
        for row in read_native_manifest(MANIFEST_ROOT / "native_diarization_manifest.parquet")
        if row["dataset"] in set(dataset)
    ]
    return {
        "schema_version": "diarization-native-campaign-plan.v2",
        "datasets": list(dataset),
        "backends": list(backend),
        "units": len(rows),
        "inference_units": len(rows) * len(backend),
        "audio_hours": sum(float(row["duration_sec"]) for row in rows) * len(backend) / 3600,
        "restart_safe": True,
        "result_root": str(RESULTS_ROOT),
        "task1_run_scope": "SMALL_ENGINEERING_SMOKE_ONLY",
    }


def validate() -> dict[str, object]:
    value = audit()
    result = {
        "schema_version": "diarization-native-campaign-validation.v2",
        "valid": value["manifest_units"] > 0 and value["onnx_environment_exists"],
        **value,
    }
    write_json_atomic(ROOT / "validation.json", result)
    return result


def smoke() -> dict[str, object]:
    audit()
    rows = read_native_manifest(MANIFEST_ROOT / "native_diarization_manifest.parquet")
    selected = []
    for dataset in ("chime6", "voices"):
        candidates = [row for row in rows if row["dataset"] == dataset]
        selected.append(min(candidates, key=lambda row: (float(row["duration_sec"]), str(row["evaluation_unit_id"]))))
    outputs = []
    for row in selected:
        root = RESULTS_ROOT / "smoke" / "sherpa_onnx_diarization" / str(row["evaluation_unit_id"])
        outputs.append(_run_unit(row, "sherpa_onnx_diarization", root))
    result = {
        "schema_version": "diarization-native-campaign-smoke.v2",
        "scientific": False,
        "units": outputs,
        "chime6_der_jer_scored": any(row["dataset"] == "chime6" and row["der_jer_eligible"] for row in outputs),
        "voices_der_jer_suppressed": all(not row["der_jer_eligible"] for row in outputs if row["dataset"] == "voices"),
        "final_chime_campaign_run": False,
    }
    write_json_atomic(ROOT / "smoke_summary.json", result)
    return result


def run(
    *, dataset: Sequence[str], backend: Sequence[str], max_units: int | None = None
) -> dict[str, object]:
    """Run an explicitly filtered native queue; Task 1 never calls this full action."""

    audit()
    STOP.unlink(missing_ok=True)
    rows = [row for row in read_native_manifest(MANIFEST_ROOT / "native_diarization_manifest.parquet") if row["dataset"] in set(dataset)]
    jobs = [(row, value) for value in backend for row in rows]
    if max_units is not None:
        jobs = jobs[:max_units]
    summary = {"planned": len(jobs), "valid": 0, "failed": 0, "reused": 0, "units": []}
    for index, (row, value) in enumerate(jobs):
        if STOP.is_file():
            break
        root = RESULTS_ROOT / "campaign" / value / str(row["evaluation_unit_id"])
        try:
            result = _run_unit(row, value, root)
            summary["valid"] += 1
            summary["reused"] += int(bool(result["reused"]))
            summary["units"].append(result)
        except Exception as exc:
            summary["failed"] += 1
            summary["units"].append({"evaluation_unit_id": row["evaluation_unit_id"], "backend": value, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        write_json_atomic(PROGRESS, {**summary, "completed": index + 1, "percentage": 100 * (index + 1) / len(jobs) if jobs else 100})
    return summary


def status() -> dict[str, object]:
    results = []
    for path in RESULTS_ROOT.rglob("run.json"):
        try:
            root = path.parent
            validation = validate_diarization_result(root)
            results.append({"root": str(root), "valid": True, **validation})
        except Exception as exc:
            results.append({"root": str(path.parent), "valid": False, "error": str(exc)})
    return {"schema_version": "diarization-native-campaign-status.v2", "results": results, "progress": _safe_json(PROGRESS), "stop_requested": STOP.is_file()}


def stop() -> dict[str, object]:
    write_text_atomic(STOP, "graceful stop requested\n")
    return {"status": "STOP_REQUESTED", "scope": "between native units"}


def analyze() -> dict[str, object]:
    roots = sorted({path.parent for path in RESULTS_ROOT.rglob("run.json")})
    output = ROOT / "analysis"
    if not roots:
        raise RuntimeError("no native results exist")
    return aggregate_native_results(roots, output)


def collect() -> dict[str, object]:
    destination = ROOT / "native_campaign_compact.zip"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in ROOT.rglob("*"):
            if path.is_file() and path != destination and path.suffix.lower() not in {".wav", ".mp3", ".onnx", ".pt"}:
                archive.write(path, path.relative_to(ROOT).as_posix())
    return {"path": str(destination), "sha256": sha256_file(destination)}


def _run_unit(row: Mapping[str, object], backend: str, root: Path) -> dict[str, object]:
    if (root / "run.json").is_file():
        validation = validate_diarization_result(root)
        return {"evaluation_unit_id": row["evaluation_unit_id"], "dataset": row["dataset"], "backend": backend, "reused": True, "der_jer_eligible": bool(row["der_jer_eligible"]), **validation}
    interpreter = interpreter_for_profile("onnx")
    if interpreter is None or not interpreter.is_file():
        raise RuntimeError("ONNX environment is unavailable")
    root.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [str(interpreter), str(TOOL_ROOT / "run_evaluation.py"), "diarization", "run", "--manifest-root", str(MANIFEST_ROOT), "--evaluation-unit-id", str(row["evaluation_unit_id"]), "--backend", backend, "--output-root", str(root)],
        cwd=TOOL_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout)[-4000:])
    validation = validate_diarization_result(root)
    return {"evaluation_unit_id": row["evaluation_unit_id"], "dataset": row["dataset"], "backend": backend, "reused": False, "der_jer_eligible": bool(row["der_jer_eligible"]), **validation}


def _safe_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
