"""Checksum-bound portability handlers for the autonomous H2 controller.

The controller deliberately delegates these jobs here so model export and
parity logic stay outside scheduling code.  Large ONNX graphs live only under
``ProgramPaths.results_root``; the compact final package inventories the
workspace and summary roots and therefore never embeds the graphs.

Success in this module means one of three narrow things:

* both exact FP32 graphs exist with valid export manifests;
* both native-vs-ONNX component parity reports pass; or
* the Linux ARM64 *preparation package* is checksum-bound and internally
  consistent.

It never means that a Raspberry Pi was tested or that ARM64 is hardware-ready.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Mapping, Sequence

from app.h2_product_program.contracts import H2Job, ProgramPaths
from app.utils.paths import repository_root

from .contracts import (
    EXPORTER_DYNAMO,
    EXPORTER_LEGACY,
    FP32_ONLY,
    ONNX_OPSET,
    PARITY_TOLERANCES,
    PINNED_ONNX_TOOLCHAIN,
)
from .e2e_parity import (
    freeze_e2e_parity_protocol,
    run_fresh_factory_pair,
    tolerance_contract_sha256,
)
from .interpreters import resolve_worker_interpreter
from .onnx_tooling import (
    COMPONENTS,
    atomic_write_json,
    canonical_sha256,
    sha256_file,
)
from .parity import build_e2e_parity_hook, load_reports
from .platform_support import PORT_REQUIRES_WORK, arm64_diagnostic


SUPPORTED_JOB_KINDS = frozenset(
    {"onnx_export", "onnx_parity", "linux_portability"}
)
PORTABILITY_JOB_RESULT_SCHEMA = "h2-controller-portability-job-result.v1"
PORTABILITY_ARTIFACT_MANIFEST_SCHEMA = "h2-portability-artifact-manifest.v1"
GRAPH_FILENAMES: Mapping[str, str] = {
    "redimnet2_b2_speaker_embedding": "redimnet2_b2_fp32.onnx",
    "pyannote_segmentation_3_0": "pyannote_segmentation_3_0_fp32.onnx",
}
REQUIRED_ARM64_PACKAGE_FILES = (
    "README.md",
    "requirements-linux-arm64.txt",
    "requirements-linux-arm64-native-reference.txt",
    "asset_manifest.json",
    "install_linux_arm64.sh",
    "run_h2_service.sh",
    "h2-pipeline.service",
    "Dockerfile.arm64",
    "Dockerfile.arm64.dockerignore",
    "validate_arm64_package.py",
)


class PortabilityJobError(RuntimeError):
    """A portability job cannot produce the evidence required for completion."""


def _artifact_root(paths: ProgramPaths) -> Path:
    # This location is intentionally not paths.summary_root or paths.workspace.
    return (paths.results_root / "portability_artifacts").resolve(strict=False)


def _result_path(paths: ProgramPaths, job: H2Job) -> Path:
    return (
        paths.results_root
        / "jobs"
        / job.job_id
        / "artifacts"
        / "job_result.json"
    ).resolve(strict=False)


def _selected_snapshot(state: Mapping[str, object]) -> tuple[dict[str, object], str]:
    raw = state.get("selected_runtime_snapshot")
    if not isinstance(raw, Mapping):
        raise PortabilityJobError(
            "selected_runtime_snapshot is missing; portability must use the final "
            "development-selected H2 runtime"
        )
    snapshot = dict(raw)
    if snapshot.get("pipeline_id") != "fullpipe_v1_ag_dr_ir":
        raise PortabilityJobError("selected runtime snapshot is not the H2 AG pipeline")
    tuning = snapshot.get("runtime_tuning")
    if not isinstance(tuning, Mapping):
        raise PortabilityJobError("selected runtime snapshot lacks runtime_tuning")
    recorded = snapshot.get("runtime_tuning_identity_sha256")
    if not isinstance(recorded, str) or len(recorded) != 64:
        raise PortabilityJobError(
            "selected runtime snapshot lacks a runtime tuning identity"
        )
    return snapshot, canonical_sha256(snapshot)


def _state_row(state: Mapping[str, object], job_id: str) -> Mapping[str, object]:
    rows = state.get("jobs")
    if not isinstance(rows, Mapping) or not isinstance(rows.get(job_id), Mapping):
        raise PortabilityJobError(f"program state is missing job row {job_id}")
    return rows[job_id]  # type: ignore[return-value]


def _unique_job(jobs: Sequence[H2Job], kind: str) -> H2Job:
    values = [job for job in jobs if job.job_kind == kind]
    if len(values) != 1:
        raise PortabilityJobError(
            f"expected exactly one {kind} job, observed {len(values)}"
        )
    return values[0]


def _load_completed_job(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    kind: str,
    *,
    expected_snapshot_sha256: str,
) -> dict[str, object]:
    dependency = _unique_job(jobs, kind)
    row = _state_row(state, dependency.job_id)
    if row.get("state") != "COMPLETE":
        raise PortabilityJobError(f"required {kind} job is not complete")
    raw_path = row.get("result_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise PortabilityJobError(f"required {kind} result path is missing")
    result_path = Path(raw_path).resolve()
    if not result_path.is_file():
        raise PortabilityJobError(f"required {kind} result is missing: {result_path}")
    observed = sha256_file(result_path)
    if observed != row.get("result_sha256"):
        raise PortabilityJobError(f"required {kind} result checksum differs")
    value = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("status") != "COMPLETE":
        raise PortabilityJobError(f"required {kind} result is not complete")
    if value.get("selected_runtime_snapshot_sha256") != expected_snapshot_sha256:
        raise PortabilityJobError(
            f"required {kind} result belongs to a different selected runtime"
        )
    validate_portability_result_artifacts(value)
    return value


def _artifact_manifest_path(result_path: Path) -> Path:
    return result_path.with_name("artifact_manifest.json")


def _collect_artifact_paths(
    paths: ProgramPaths, payload: Mapping[str, object]
) -> list[Path]:
    """Collect only explicitly referenced evidence and bounded evidence roots."""

    found: set[Path] = set()
    visited_json: set[Path] = set()
    directory_keys = {
        "graph_storage_root",
        "package_root",
        "protected_store",
        "native_root",
        "portable_root",
    }
    allowed_roots = tuple(
        root.resolve()
        for root in {
            paths.evaluation_root,
            paths.results_root,
            repository_root().path,
        }
    )

    def allowed(path: Path) -> bool:
        return any(path.is_relative_to(root) for root in allowed_roots)

    def add_path(raw: str, key: str) -> None:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = paths.evaluation_root / candidate
        candidate = candidate.resolve(strict=False)
        if not allowed(candidate):
            return
        if candidate.is_file():
            found.add(candidate)
            if (
                candidate.suffix.casefold() == ".json"
                and candidate not in visited_json
                and any(token in key.casefold() for token in ("report", "manifest", "receipt", "freeze"))
            ):
                visited_json.add(candidate)
                try:
                    nested = json.loads(candidate.read_text(encoding="utf-8"))
                except Exception:
                    return
                walk(nested, key)
        elif candidate.is_dir() and key.casefold() in directory_keys:
            for child in candidate.rglob("*"):
                if child.is_file():
                    found.add(child.resolve())

    def walk(value: object, key: str = "") -> None:
        if isinstance(value, Mapping):
            for child_key, child in value.items():
                walk(child, str(child_key))
        elif isinstance(value, list):
            for child in value:
                walk(child, key)
        elif isinstance(value, str) and (
            "path" in key.casefold() or key.casefold() in directory_keys
        ):
            add_path(value, key)

    walk(payload)
    return sorted(found, key=lambda path: str(path).casefold())


def _write_artifact_manifest(
    paths: ProgramPaths,
    result_path: Path,
    payload: Mapping[str, object],
) -> dict[str, object]:
    rows = [
        {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in _collect_artifact_paths(paths, payload)
    ]
    if not rows:
        raise PortabilityJobError("portability completion has no bound artifacts")
    manifest = {
        "schema_version": PORTABILITY_ARTIFACT_MANIFEST_SCHEMA,
        "job_id": payload.get("job_id"),
        "job_kind": payload.get("job_kind"),
        "job_identity_sha256": payload.get("job_identity_sha256"),
        "selected_runtime_snapshot_sha256": payload.get(
            "selected_runtime_snapshot_sha256"
        ),
        "artifact_count": len(rows),
        "artifacts": rows,
        "artifact_set_sha256": canonical_sha256(rows),
        "graphs_copied_into_compact_zip": False,
    }
    manifest_path = _artifact_manifest_path(result_path)
    atomic_write_json(manifest_path, manifest)
    return {
        "artifact_manifest_path": str(manifest_path),
        "artifact_manifest_sha256": sha256_file(manifest_path),
        "artifact_count": len(rows),
        "artifact_set_sha256": manifest["artifact_set_sha256"],
    }


def validate_portability_result_artifacts(
    result: Mapping[str, object],
) -> dict[str, object]:
    """Fail if any completion-bound portability artifact was lost or changed."""

    raw_path = result.get("artifact_manifest_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise PortabilityJobError("portability result lacks an artifact manifest")
    manifest_path = Path(raw_path).resolve()
    if not manifest_path.is_file():
        raise PortabilityJobError(f"portability artifact manifest is missing: {manifest_path}")
    if sha256_file(manifest_path) != result.get("artifact_manifest_sha256"):
        raise PortabilityJobError("portability artifact manifest checksum differs")
    manifest = _read_json_object(manifest_path, label="portability artifact manifest")
    rows = manifest.get("artifacts")
    if (
        manifest.get("schema_version") != PORTABILITY_ARTIFACT_MANIFEST_SCHEMA
        or not isinstance(rows, list)
        or not rows
        or manifest.get("artifact_count") != len(rows)
        or manifest.get("job_id") != result.get("job_id")
        or manifest.get("job_kind") != result.get("job_kind")
        or manifest.get("job_identity_sha256")
        != result.get("job_identity_sha256")
        or manifest.get("selected_runtime_snapshot_sha256")
        != result.get("selected_runtime_snapshot_sha256")
        or manifest.get("artifact_set_sha256") != canonical_sha256(rows)
        or result.get("artifact_count") != len(rows)
        or result.get("artifact_set_sha256") != manifest.get("artifact_set_sha256")
    ):
        raise PortabilityJobError("portability artifact manifest contract differs")
    failures = []
    for row in rows:
        if not isinstance(row, Mapping):
            failures.append("invalid artifact row")
            continue
        path = Path(str(row.get("path"))).resolve()
        if (
            not path.is_file()
            or path.stat().st_size != row.get("bytes")
            or sha256_file(path) != row.get("sha256")
        ):
            failures.append(str(path))
    if failures:
        raise PortabilityJobError(
            f"portability artifacts are missing or changed: {failures[:10]}"
        )
    return {
        "status": "VALID",
        "artifact_manifest_path": str(manifest_path),
        "artifact_manifest_sha256": sha256_file(manifest_path),
        "artifact_count": len(rows),
        "artifact_set_sha256": manifest.get("artifact_set_sha256"),
    }


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _worker_environment(paths: ProgramPaths) -> dict[str, str]:
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(paths.evaluation_root)
        if not existing
        else os.pathsep.join((str(paths.evaluation_root), existing))
    )
    # Every model asset is local and checksum-pinned.  Fail rather than fetch.
    environment["HF_HUB_OFFLINE"] = "1"
    environment["TRANSFORMERS_OFFLINE"] = "1"
    environment["PYTHONUTF8"] = "1"
    return environment


def _run_worker(
    paths: ProgramPaths,
    *,
    profile: str,
    arguments: Sequence[str],
    log_prefix: Path,
) -> dict[str, object]:
    repo = repository_root().path
    resolution = resolve_worker_interpreter(profile, repository=repo)
    if resolution.path is None:  # pragma: no cover - resolver fails first.
        raise PortabilityJobError(f"no interpreter for {profile}")
    command = [str(resolution.path), "-m", "app.h2_portability", *arguments]
    completed = subprocess.run(
        command,
        cwd=paths.evaluation_root,
        env=_worker_environment(paths),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout_path = log_prefix.with_suffix(".stdout.log")
    stderr_path = log_prefix.with_suffix(".stderr.log")
    _atomic_write_text(stdout_path, completed.stdout)
    _atomic_write_text(stderr_path, completed.stderr)
    return {
        "profile": profile,
        "interpreter": str(resolution.path),
        "command": command,
        "returncode": completed.returncode,
        "stdout_path": str(stdout_path),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_path": str(stderr_path),
        "stderr_sha256": sha256_file(stderr_path),
    }


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PortabilityJobError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PortabilityJobError(f"{label} must be a JSON object: {path}")
    return value


def _validate_local_source_assets(component_id: str, repo: Path) -> None:
    for asset in COMPONENTS[component_id].required_assets:
        path = repo / asset.relative_path
        if not path.is_file():
            raise PortabilityJobError(f"required local model asset is missing: {path}")
        if sha256_file(path) != asset.sha256:
            raise PortabilityJobError(f"required local model asset hash differs: {path}")


def _validate_export_manifest(
    component_id: str, graph: Path, manifest_path: Path
) -> dict[str, object]:
    repo = repository_root().path
    _validate_local_source_assets(component_id, repo)
    if not graph.is_file() or not manifest_path.is_file():
        raise PortabilityJobError(
            f"graph/manifest pair is incomplete for {component_id}"
        )
    manifest = _read_json_object(manifest_path, label="export manifest")
    observed_graph_sha = sha256_file(graph)
    checks = {
        "status": manifest.get("status")
        == "EXPORTED_GRAPH_VALIDATED_PARITY_PENDING",
        "component": manifest.get("component_id") == component_id,
        "precision": manifest.get("precision") == FP32_ONLY,
        "opset": manifest.get("opset") == ONNX_OPSET,
        "path": Path(str(manifest.get("onnx_path"))).resolve() == graph.resolve(),
        "graph_sha256": manifest.get("onnx_sha256") == observed_graph_sha,
        "graph_bytes": manifest.get("onnx_bytes") == graph.stat().st_size,
        "no_downloads": manifest.get("implicit_downloads_allowed") is False,
        "parity_pending": manifest.get("parity_measured") is False,
        "not_arm64_measured": manifest.get("linux_arm64_measured") is False,
    }
    source_checks = manifest.get("source_asset_checks")
    checks["source_assets"] = isinstance(source_checks, list) and all(
        isinstance(row, Mapping) and row.get("status") == "MATCH"
        for row in source_checks
    )
    graph_validation = manifest.get("graph_validation")
    checks["fp32_graph"] = (
        isinstance(graph_validation, Mapping)
        and graph_validation.get("non_fp32_float_initializer_types") == []
    )
    environment = manifest.get("environment")
    packages = environment.get("packages") if isinstance(environment, Mapping) else None
    checks["pinned_toolchain"] = isinstance(packages, Mapping) and all(
        any(
            str(name).casefold() == package.casefold()
            and str(version).split("+")[0] == expected
            for name, version in packages.items()
        )
        for package, expected in PINNED_ONNX_TOOLCHAIN.items()
    )
    execution = manifest.get("export_execution")
    exporter = execution.get("exporter") if isinstance(execution, Mapping) else None
    checks["known_exporter"] = exporter in {EXPORTER_DYNAMO, EXPORTER_LEGACY}
    if exporter == EXPORTER_LEGACY:
        fallback = manifest.get("fallback_evidence")
        failure_path = (
            Path(str(fallback.get("failure_evidence_path"))).resolve()
            if isinstance(fallback, Mapping)
            and isinstance(fallback.get("failure_evidence_path"), str)
            else None
        )
        checks["explicit_fallback"] = (
            manifest.get("fallback_attempted") is True
            and isinstance(fallback, Mapping)
            and fallback.get("preferred_exporter") == EXPORTER_DYNAMO
            and fallback.get("preferred_exporter_status") == "EXPORT_FAILED"
            and failure_path is not None
            and failure_path.is_file()
            and sha256_file(failure_path) == fallback.get("failure_evidence_sha256")
        )
    else:
        checks["explicit_fallback"] = manifest.get("fallback_attempted") is False
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PortabilityJobError(
            f"export manifest validation failed for {component_id}: {failed}"
        )
    return {
        "component_id": component_id,
        "graph_path": str(graph),
        "graph_sha256": observed_graph_sha,
        "graph_bytes": graph.stat().st_size,
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "exporter": exporter,
        "fallback_evidence": manifest.get("fallback_evidence"),
        "validation_checks": checks,
    }


def _retained_dynamo_failure(graph: Path, component_id: str) -> bool:
    failure_path = graph.parent / f"{graph.stem}.export_evidence" / "export_failure.json"
    if not failure_path.is_file():
        return False
    value = _read_json_object(failure_path, label="Dynamo failure evidence")
    return (
        value.get("status") == "EXPORT_FAILED"
        and value.get("component_id") == component_id
        and value.get("exporter") == EXPORTER_DYNAMO
        and value.get("fallback_attempted") is False
    )


def _export_one(
    paths: ProgramPaths,
    *,
    component_id: str,
    graph: Path,
    logs: Path,
) -> dict[str, object]:
    manifest_path = graph.with_suffix(graph.suffix + ".manifest.json")
    if graph.exists() or manifest_path.exists():
        if not (graph.is_file() and manifest_path.is_file()):
            raise PortabilityJobError(
                f"refusing to overwrite partial graph evidence for {component_id}"
            )
        value = _validate_export_manifest(component_id, graph, manifest_path)
        value["reused"] = True
        value["worker_executions"] = []
        return value

    profile = COMPONENTS[component_id].native_environment_profile
    executions: list[dict[str, object]] = []
    failure_reused = _retained_dynamo_failure(graph, component_id)
    if not failure_reused:
        dynamo_receipt = logs / f"{component_id}.dynamo.receipt.json"
        dynamo = _run_worker(
            paths,
            profile=profile,
            arguments=(
                "export",
                "--component",
                component_id,
                "--onnx-path",
                str(graph),
                "--exporter",
                EXPORTER_DYNAMO,
                "--output",
                str(dynamo_receipt),
            ),
            log_prefix=logs / f"{component_id}.dynamo",
        )
        executions.append(dynamo)
        if dynamo["returncode"] == 0:
            value = _validate_export_manifest(component_id, graph, manifest_path)
            value["reused"] = False
            value["worker_executions"] = executions
            return value
        if not _retained_dynamo_failure(graph, component_id):
            raise PortabilityJobError(
                f"Dynamo failed for {component_id} without valid retained evidence"
            )

    # This is a named, auditable second execution, never a hidden exporter swap.
    legacy_receipt = logs / f"{component_id}.legacy.receipt.json"
    legacy = _run_worker(
        paths,
        profile=profile,
        arguments=(
            "export",
            "--component",
            component_id,
            "--onnx-path",
            str(graph),
            "--exporter",
            EXPORTER_LEGACY,
            "--output",
            str(legacy_receipt),
        ),
        log_prefix=logs / f"{component_id}.legacy",
    )
    executions.append(legacy)
    if legacy["returncode"] != 0:
        raise PortabilityJobError(
            f"explicit legacy export failed for {component_id}; inspect {legacy['stderr_path']}"
        )
    value = _validate_export_manifest(component_id, graph, manifest_path)
    value["reused"] = False
    value["preferred_dynamo_failure_reused"] = failure_reused
    value["worker_executions"] = executions
    return value


def _handle_export(
    paths: ProgramPaths,
    job: H2Job,
    snapshot: Mapping[str, object],
    snapshot_sha256: str,
) -> dict[str, object]:
    root = _artifact_root(paths)
    graphs = root / "graphs"
    logs = root / "logs" / job.job_id
    graphs.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    rows = {
        component_id: _export_one(
            paths,
            component_id=component_id,
            graph=graphs / GRAPH_FILENAMES[component_id],
            logs=logs,
        )
        for component_id in COMPONENTS
    }
    return {
        "schema_version": PORTABILITY_JOB_RESULT_SCHEMA,
        "status": "COMPLETE",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "job_identity_sha256": job.identity_sha256,
        "selected_runtime_snapshot": dict(snapshot),
        "selected_runtime_snapshot_sha256": snapshot_sha256,
        "component_artifacts": rows,
        "required_component_count": len(COMPONENTS),
        "validated_component_count": len(rows),
        "graphs_outside_compact_zip": True,
        "graph_storage_root": str(graphs),
        "implicit_downloads_allowed": False,
        "parity_measured": False,
        "arm64_hardware_validated": False,
    }


def _engineering_audio_paths() -> tuple[Path, ...]:
    repo = repository_root().path
    root = (
        repo
        / "models/cache/sherpa_onnx/asr"
        / "sherpa-onnx-streaming-zipformer-en-2023-06-21/test_wavs"
    )
    candidates = (root / "0.wav", root / "1.wav")
    return tuple(path for path in candidates if path.is_file())


def _validate_parity_report(
    component_id: str,
    report_path: Path,
    *,
    expected_graph_sha256: str,
) -> dict[str, object]:
    if not report_path.is_file():
        raise PortabilityJobError(f"parity report is missing: {report_path}")
    report = _read_json_object(report_path, label="parity report")
    checks = {
        "status": report.get("status") == "PARITY_PASS",
        "component": report.get("component_id") == component_id,
        "graph_sha256": report.get("onnx_sha256") == expected_graph_sha256,
        "parity_measured": report.get("parity_measured") is True,
        "parity_passed": report.get("parity_passed") is True,
        "tolerances": report.get("tolerances") == PARITY_TOLERANCES[component_id],
        "tolerance_hash": report.get("tolerance_contract_sha256")
        == canonical_sha256(PARITY_TOLERANCES[component_id]),
        "not_arm64_measured": report.get("linux_arm64_measured") is False,
        "not_production_claim": report.get("production_usable") is False,
        "cases_present": isinstance(report.get("case_results"), list)
        and bool(report.get("case_results")),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PortabilityJobError(
            f"parity report validation failed for {component_id}: {failed}"
        )
    return {
        "component_id": component_id,
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "onnx_sha256": report.get("onnx_sha256"),
        "case_manifest_sha256": report.get("case_manifest_sha256"),
        "tolerance_contract_sha256": report.get("tolerance_contract_sha256"),
        "case_count": len(report["case_results"]),
        "summary": report.get("summary"),
        "validation_checks": checks,
    }


def _file_set_sha256(root: Path) -> str:
    rows = []
    for path in sorted((row for row in root.rglob("*") if row.is_file())):
        rows.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if not rows:
        raise PortabilityJobError(f"checksum-bound file set is empty: {root}")
    return canonical_sha256(rows)


def _bounded_e2e_enrollment(paths: ProgramPaths, root: Path) -> dict[str, object]:
    """Create or validate one bounded native ReDimNet2 enrollment profile."""

    receipt_path = root / "enrollment_smoke.json"
    if not receipt_path.is_file():
        from app.full_pipeline.cli import run_enrollment_smoke

        audio = (
            paths.evaluation_root
            / "artifacts/realtime_test_audio/aew_rxr_eey_arctic_a0301_concat.wav"
        )
        value = run_enrollment_smoke(
            argparse.Namespace(
                backend=["redimnet2_b2_speaker_embedding"],
                input=audio,
                output_root=root,
            )
        )
    else:
        value = _read_json_object(receipt_path, label="bounded E2E enrollment")
    rows = value.get("backends")
    checks = {
        "status": value.get("status") == "PASS",
        "one_backend": isinstance(rows, list) and len(rows) == 1,
        "backend": isinstance(rows, list)
        and len(rows) == 1
        and isinstance(rows[0], Mapping)
        and rows[0].get("backend_id") == "redimnet2_b2_speaker_embedding",
        "profile_status": isinstance(rows, list)
        and len(rows) == 1
        and isinstance(rows[0], Mapping)
        and rows[0].get("status") == "PASS",
        "protected_store": (root / "protected_store").is_dir(),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PortabilityJobError(f"bounded E2E enrollment is invalid: {failed}")
    return {
        "receipt_path": str(receipt_path.resolve()),
        "receipt_sha256": sha256_file(receipt_path),
        "protected_store": str((root / "protected_store").resolve()),
        "protected_store_file_set_sha256": _file_set_sha256(root / "protected_store"),
        "profile": rows[0],
        "validation_checks": checks,
    }


def _validate_e2e_report(
    path: Path,
    *,
    expected_snapshot_sha256: str,
    expected_graph_sha256: Mapping[str, str],
    require_identity: bool,
) -> dict[str, object]:
    report = _read_json_object(path, label="full-pipeline E2E parity report")
    case = report.get("case_identity")
    exact = report.get("exact_checks")
    tolerance = report.get("tolerance_checks")
    checks = {
        "status": report.get("status") == "E2E_PARITY_PASS",
        "measured": report.get("full_live_pipeline_parity_measured") is True,
        "identity": report.get("identity_path_exercised") is require_identity,
        "identity_required": report.get("identity_path_required_for_case")
        is require_identity,
        "no_retune": report.get("scientific_thresholds_retuned") is False,
        "contract_hash": report.get("tolerance_contract_sha256")
        == tolerance_contract_sha256(),
        "snapshot": isinstance(case, Mapping)
        and case.get("selected_runtime_snapshot_sha256")
        == expected_snapshot_sha256,
        "graphs": isinstance(case, Mapping)
        and case.get("graph_sha256") == dict(sorted(expected_graph_sha256.items())),
        "exact": isinstance(exact, Mapping)
        and bool(exact)
        and all(value is True for value in exact.values()),
        "tolerance": isinstance(tolerance, Mapping)
        and bool(tolerance)
        and all(
            isinstance(value, Mapping) and value.get("passed") is True
            for value in tolerance.values()
        ),
        "not_arm64": report.get("arm64_hardware_validated") is False,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PortabilityJobError(f"full-pipeline E2E parity is invalid: {failed}")
    return {
        "report_path": str(path.resolve()),
        "report_sha256": sha256_file(path),
        "identity_path_exercised": report.get("identity_path_exercised"),
        "exact_checks": exact,
        "tolerance_checks": tolerance,
        "validation_checks": checks,
    }


def _run_or_reuse_e2e_case(
    *,
    paths: ProgramPaths,
    case_root: Path,
    freeze_path: Path,
    input_path: Path,
    enrollment_root: Path,
    graph_paths: Mapping[str, Path],
    graph_sha256: Mapping[str, str],
    snapshot: Mapping[str, object],
    snapshot_sha256: str,
    require_identity: bool,
) -> dict[str, object]:
    report_path = case_root / "e2e_parity_report.json"
    invalid_previous: dict[str, object] | None = None
    if report_path.is_file():
        try:
            return _validate_e2e_report(
                report_path,
                expected_snapshot_sha256=snapshot_sha256,
                expected_graph_sha256=graph_sha256,
                require_identity=require_identity,
            )
        except PortabilityJobError as exc:
            invalid_previous = {
                "path": str(report_path.resolve()),
                "sha256": sha256_file(report_path),
                "validation_error": str(exc),
                "preserved": True,
            }
    if case_root.exists():
        # Preserve incomplete evidence.  A deterministic numbered fresh attempt
        # avoids silently treating a partially cached execution as parity.
        attempt = 2
        while (case_root.parent / f"{case_root.name}_attempt_{attempt:03d}").exists():
            attempt += 1
        case_root = case_root.parent / f"{case_root.name}_attempt_{attempt:03d}"
        report_path = case_root / "e2e_parity_report.json"
    tuning = snapshot.get("runtime_tuning")
    if not isinstance(tuning, Mapping):
        raise PortabilityJobError("selected runtime snapshot lacks runtime tuning")
    product_mode = str(tuning.get("product_mode", "H2_SESSION_MEMORY_ENHANCED"))
    report = run_fresh_factory_pair(
        input_path=input_path,
        enrollment_root=enrollment_root,
        output_root=case_root,
        freeze_receipt_path=freeze_path,
        graph_paths=graph_paths,
        graph_sha256=graph_sha256,
        pipeline_id=str(snapshot["pipeline_id"]),
        duration_sec=10.0,
        product_mode=product_mode,
        runtime_tuning=dict(tuning),
        selected_runtime_snapshot_sha256=snapshot_sha256,
        require_identity_exercised=require_identity,
    )
    if report.get("status") != "E2E_PARITY_PASS":
        raise PortabilityJobError(
            f"fresh full-pipeline E2E parity failed: {report_path}"
        )
    validated = _validate_e2e_report(
        report_path,
        expected_snapshot_sha256=snapshot_sha256,
        expected_graph_sha256=graph_sha256,
        require_identity=require_identity,
    )
    if invalid_previous is not None:
        validated["superseded_invalid_report"] = invalid_previous
    return validated


def _handle_parity(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    job: H2Job,
    snapshot: Mapping[str, object],
    snapshot_sha256: str,
) -> dict[str, object]:
    expected_cases = (
        "h2_onnx_enrolled_same_input_10s",
        "h2_onnx_empty_enrollment_same_input_10s",
    )
    if (
        job.split != "none"
        or job.pipeline_id != "NOT_APPLICABLE"
        or job.mode != "NOT_APPLICABLE"
        or job.configuration_id
        != "H2_PORTABLE_ONNX_FP32_FROZEN_FIXTURE_PARITY"
        or tuple(job.case_ids) != expected_cases
        or abs(float(job.audio_duration_sec) - 20.0) > 1.0e-9
    ):
        raise PortabilityJobError(
            "onnx_parity job contract must declare the exact two-case frozen "
            "fixture panel; development protocol cases are not executed here"
        )
    export = _load_completed_job(
        paths,
        state,
        jobs,
        "onnx_export",
        expected_snapshot_sha256=snapshot_sha256,
    )
    components = export.get("component_artifacts")
    if not isinstance(components, Mapping) or set(components) != set(COMPONENTS):
        raise PortabilityJobError("ONNX export result does not contain both components")
    root = _artifact_root(paths)
    output = root / "parity"
    logs = root / "logs" / job.job_id
    output.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    audio_paths = _engineering_audio_paths()
    rows: dict[str, object] = {}
    report_paths: list[Path] = []
    executions: list[dict[str, object]] = []
    for component_id, artifact in components.items():
        if not isinstance(artifact, Mapping):
            raise PortabilityJobError(f"invalid export artifact for {component_id}")
        graph = Path(str(artifact.get("graph_path"))).resolve()
        expected_sha = str(artifact.get("graph_sha256"))
        if not graph.is_file() or sha256_file(graph) != expected_sha:
            raise PortabilityJobError(f"export graph differs before parity: {component_id}")
        report_path = output / f"{component_id}.parity.json"
        if not report_path.exists():
            arguments = [
                "parity",
                "--component",
                component_id,
                "--onnx-path",
                str(graph),
                "--output-dir",
                str(output),
                "--output",
                str(logs / f"{component_id}.receipt.json"),
            ]
            for audio in audio_paths:
                arguments.extend(("--audio", str(audio)))
            execution = _run_worker(
                paths,
                profile=COMPONENTS[component_id].native_environment_profile,
                arguments=arguments,
                log_prefix=logs / component_id,
            )
            executions.append(execution)
            if execution["returncode"] != 0:
                raise PortabilityJobError(
                    f"parity worker failed for {component_id}; inspect "
                    f"{execution['stderr_path']}"
                )
        row = _validate_parity_report(
            component_id, report_path, expected_graph_sha256=expected_sha
        )
        rows[component_id] = row
        report_paths.append(report_path)
    if len(report_paths) != len(COMPONENTS):
        raise PortabilityJobError("both component parity reports are required")
    hook_path = output / "h2_e2e_parity_hook.json"
    hook = build_e2e_parity_hook(load_reports(report_paths), output_path=hook_path)
    if (
        hook.get("status") != "E2E_CONTRACT_PARITY_PASS"
        or hook.get("component_parity_passed") is not True
        or hook.get("h2_controller_may_claim_arm64_ready") is not False
    ):
        raise PortabilityJobError("E2E component parity binding did not pass")
    graph_paths = {
        component_id: Path(str(artifact["graph_path"])).resolve()
        for component_id, artifact in components.items()
        if isinstance(artifact, Mapping)
    }
    graph_sha256 = {
        component_id: str(artifact["graph_sha256"])
        for component_id, artifact in components.items()
        if isinstance(artifact, Mapping)
    }
    if set(graph_paths) != set(COMPONENTS) or set(graph_sha256) != set(COMPONENTS):
        raise PortabilityJobError("full-pipeline E2E parity requires both graphs")
    e2e_root = root / "full_pipeline_e2e" / snapshot_sha256
    freeze_path = e2e_root / "protocol_freeze.json"
    freeze = freeze_e2e_parity_protocol(
        freeze_path,
        planned_cases=(
            {
                "case_id": "enrolled_same_input_10s",
                "required_for_completion": True,
                "identity_required": True,
            },
            {
                "case_id": "empty_enrollment_same_input_10s",
                "required_for_completion": True,
                "identity_required": False,
            },
        ),
        engineering_smokes_excluded=(
            "native_factory_run_smoke",
            "portable_factory_run_smoke",
        ),
    )
    input_path = (
        paths.evaluation_root
        / "artifacts/realtime_test_audio/aew_rxr_eey_arctic_a0301_concat.wav"
    ).resolve()
    if not input_path.is_file():
        raise PortabilityJobError(f"bounded E2E input is missing: {input_path}")
    enrollment = _bounded_e2e_enrollment(paths, e2e_root / "enrollment")
    enrolled_case = _run_or_reuse_e2e_case(
        paths=paths,
        case_root=e2e_root / "case_enrolled_same_input_10s",
        freeze_path=freeze_path,
        input_path=input_path,
        enrollment_root=Path(str(enrollment["protected_store"])),
        graph_paths=graph_paths,
        graph_sha256=graph_sha256,
        snapshot=snapshot,
        snapshot_sha256=snapshot_sha256,
        require_identity=True,
    )
    empty_enrollment = e2e_root / "empty_enrollment"
    empty_enrollment.mkdir(parents=True, exist_ok=True)
    empty_case = _run_or_reuse_e2e_case(
        paths=paths,
        case_root=e2e_root / "case_empty_enrollment_same_input_10s",
        freeze_path=freeze_path,
        input_path=input_path,
        enrollment_root=empty_enrollment,
        graph_paths=graph_paths,
        graph_sha256=graph_sha256,
        snapshot=snapshot,
        snapshot_sha256=snapshot_sha256,
        require_identity=False,
    )
    return {
        "schema_version": PORTABILITY_JOB_RESULT_SCHEMA,
        "status": "COMPLETE",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "job_identity_sha256": job.identity_sha256,
        "selected_runtime_snapshot": dict(snapshot),
        "selected_runtime_snapshot_sha256": snapshot_sha256,
        "component_reports": rows,
        "required_component_count": len(COMPONENTS),
        "passed_component_count": len(rows),
        "worker_executions": executions,
        "engineering_audio_paths": [str(path) for path in audio_paths],
        "engineering_audio_sha256": {
            str(path): sha256_file(path) for path in audio_paths
        },
        "declared_fixture_case_ids": list(job.case_ids),
        "declared_fixture_audio_duration_sec": job.audio_duration_sec,
        "declared_fixture_case_count": len(job.case_ids),
        "e2e_component_hook_path": str(hook_path),
        "e2e_component_hook_sha256": sha256_file(hook_path),
        "component_parity_passed": True,
        "e2e_protocol_freeze_path": str(freeze_path),
        "e2e_protocol_freeze_sha256": sha256_file(freeze_path),
        "e2e_protocol_freeze": freeze,
        "e2e_input_path": str(input_path),
        "e2e_input_sha256": sha256_file(input_path),
        "e2e_enrollment": enrollment,
        "e2e_enrolled_case": enrolled_case,
        "e2e_empty_enrollment_case": empty_case,
        "e2e_required_case_count": 2,
        "e2e_passed_case_count": 2,
        "full_live_pipeline_parity_measured": True,
        "full_live_pipeline_parity_passed": True,
        "transcript_rttm_cluster_identity_event_parity_measured": True,
        "engineering_smokes_used_for_final_parity_decision": False,
        "scientific_thresholds_retuned": False,
        "arm64_hardware_validated": False,
    }


def _arm64_package_rows(package_root: Path) -> list[dict[str, object]]:
    rows = []
    for relative in REQUIRED_ARM64_PACKAGE_FILES:
        path = package_root / relative
        if not path.is_file():
            raise PortabilityJobError(f"ARM64 package file is missing: {path}")
        rows.append(
            {
                "relative_path": relative,
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def _validate_package_graph_hashes(
    package_root: Path, component_artifacts: Mapping[str, object]
) -> dict[str, str]:
    manifest = _read_json_object(
        package_root / "asset_manifest.json", label="ARM64 asset manifest"
    )
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        raise PortabilityJobError("ARM64 asset manifest lacks assets")
    by_id = {
        str(row.get("id")): row
        for row in assets
        if isinstance(row, Mapping) and row.get("id")
    }
    expected_ids = {
        "redimnet2_b2_speaker_embedding": "redimnet2_b2_fp32_onnx",
        "pyannote_segmentation_3_0": "pyannote_segmentation_3_0_fp32_onnx",
    }
    values: dict[str, str] = {}
    for component_id, asset_id in expected_ids.items():
        artifact = component_artifacts.get(component_id)
        row = by_id.get(asset_id)
        if not isinstance(artifact, Mapping) or not isinstance(row, Mapping):
            raise PortabilityJobError(
                f"ARM64 manifest lacks graph binding for {component_id}"
            )
        graph_sha = str(artifact.get("graph_sha256"))
        if row.get("sha256") != graph_sha:
            raise PortabilityJobError(
                f"ARM64 package graph hash differs for {component_id}"
            )
        values[component_id] = graph_sha
    return values


def _handle_linux_portability(
    paths: ProgramPaths,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    job: H2Job,
    snapshot: Mapping[str, object],
    snapshot_sha256: str,
) -> dict[str, object]:
    export = _load_completed_job(
        paths,
        state,
        jobs,
        "onnx_export",
        expected_snapshot_sha256=snapshot_sha256,
    )
    parity = _load_completed_job(
        paths,
        state,
        jobs,
        "onnx_parity",
        expected_snapshot_sha256=snapshot_sha256,
    )
    if (
        parity.get("component_parity_passed") is not True
        or parity.get("full_live_pipeline_parity_passed") is not True
    ):
        raise PortabilityJobError(
            "Linux preparation requires component and full-pipeline parity passes"
        )
    components = export.get("component_artifacts")
    reports = parity.get("component_reports")
    if not isinstance(components, Mapping) or set(components) != set(COMPONENTS):
        raise PortabilityJobError("Linux preparation requires both exported graphs")
    if not isinstance(reports, Mapping) or set(reports) != set(COMPONENTS):
        raise PortabilityJobError("Linux preparation requires both component reports")
    package_root = (paths.evaluation_root / "deployment/h2_arm64").resolve()
    package_rows = _arm64_package_rows(package_root)
    graph_hashes = _validate_package_graph_hashes(package_root, components)
    graph_paths = {
        component_id: Path(str(artifact["graph_path"])).resolve()
        for component_id, artifact in components.items()
        if isinstance(artifact, Mapping)
    }
    diagnostic = arm64_diagnostic(
        repository=repository_root().path,
        graph_paths=graph_paths,
        require_linux_arm64=False,
        require_graphs=True,
        probe_audio=False,
    )
    if diagnostic.get("status") != "DIAGNOSTIC_PASS":
        raise PortabilityJobError("desktop ARM64 preparation diagnostic did not pass")
    if (
        diagnostic.get("candidate_classification") != PORT_REQUIRES_WORK
        or diagnostic.get("linux_arm64_ready_claimed") is not False
    ):
        raise PortabilityJobError("ARM64 diagnostic made an unsupported readiness claim")
    return {
        "schema_version": PORTABILITY_JOB_RESULT_SCHEMA,
        "status": "COMPLETE",
        "completion_scope": "LINUX_ARM64_PACKAGE_PREPARATION_ONLY",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "job_identity_sha256": job.identity_sha256,
        "selected_runtime_snapshot": dict(snapshot),
        "selected_runtime_snapshot_sha256": snapshot_sha256,
        "package_root": str(package_root),
        "package_files": package_rows,
        "package_file_set_sha256": canonical_sha256(package_rows),
        "component_graph_sha256": graph_hashes,
        "component_parity_report_sha256": {
            component_id: row.get("report_sha256")
            for component_id, row in reports.items()
            if isinstance(row, Mapping)
        },
        "desktop_preparation_diagnostic": diagnostic,
        "candidate_classification": PORT_REQUIRES_WORK,
        "linux_arm64_ready_claimed": False,
        "raspberry_pi_hardware_validated": False,
        "arm64_numerical_parity_measured": False,
        "arm64_audio_capture_validated": False,
        "arm64_sustained_streaming_validated": False,
        "core_h2_factory_wired_to_onnx": True,
        "desktop_full_pipeline_onnx_parity_measured": True,
        "desktop_full_pipeline_onnx_parity_report_sha256": {
            "enrolled": parity.get("e2e_enrolled_case", {}).get("report_sha256")
            if isinstance(parity.get("e2e_enrolled_case"), Mapping)
            else None,
            "empty_enrollment": parity.get("e2e_empty_enrollment_case", {}).get(
                "report_sha256"
            )
            if isinstance(parity.get("e2e_empty_enrollment_case"), Mapping)
            else None,
        },
        "remaining_hardware_gate": (
            "Run install, model loading, ALSA/PipeWire capture, numerical parity, "
            "process/restart, GUI/headless, serial resource, and sustained-streaming "
            "tests on the exact Raspberry Pi/Compute Module target."
        ),
    }


def _failure_payload(
    job: H2Job,
    snapshot_sha256: str | None,
    error: str,
) -> dict[str, object]:
    return {
        "schema_version": PORTABILITY_JOB_RESULT_SCHEMA,
        "status": "FAILED",
        "job_id": job.job_id,
        "job_kind": job.job_kind,
        "job_identity_sha256": job.identity_sha256,
        "selected_runtime_snapshot_sha256": snapshot_sha256,
        "error": error,
        "marked_complete": False,
        "arm64_hardware_validated": False,
        "linux_arm64_ready_claimed": False,
    }


def execute_portability_job(
    paths: ProgramPaths,
    job: H2Job,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    """Execute one controller portability job and return its result receipt.

    The return contract is the controller's standard ``state``, ``result_path``,
    ``result_sha256``, and ``error`` mapping.  All failures are materialized as
    checksum-bound JSON and returned as ``state='failed'``.
    """

    result_path = _result_path(paths, job)
    snapshot_sha256: str | None = None
    try:
        if job.job_kind not in SUPPORTED_JOB_KINDS:
            raise PortabilityJobError(
                f"unsupported portability job kind: {job.job_kind}"
            )
        snapshot, snapshot_sha256 = _selected_snapshot(state)
        if job.job_kind == "onnx_export":
            payload = _handle_export(paths, job, snapshot, snapshot_sha256)
        elif job.job_kind == "onnx_parity":
            payload = _handle_parity(
                paths, state, jobs, job, snapshot, snapshot_sha256
            )
        else:
            payload = _handle_linux_portability(
                paths, state, jobs, job, snapshot, snapshot_sha256
            )
        payload = {
            **payload,
            **_write_artifact_manifest(paths, result_path, payload),
        }
        atomic_write_json(result_path, payload)
        return {
            "state": "complete",
            "result_path": str(result_path),
            "result_sha256": sha256_file(result_path),
            "error": None,
        }
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        payload = _failure_payload(job, snapshot_sha256, error)
        atomic_write_json(result_path, payload)
        return {
            "state": "failed",
            "result_path": str(result_path),
            "result_sha256": sha256_file(result_path),
            "error": error,
        }


__all__ = [
    "PORTABILITY_ARTIFACT_MANIFEST_SCHEMA",
    "PORTABILITY_JOB_RESULT_SCHEMA",
    "PortabilityJobError",
    "SUPPORTED_JOB_KINDS",
    "execute_portability_job",
    "validate_portability_result_artifacts",
]
