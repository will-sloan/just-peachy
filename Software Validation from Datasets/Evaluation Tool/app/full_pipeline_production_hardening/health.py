"""Model-free candidate health/status endpoint."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from typing import Mapping

from . import scope_fields
from .controller import layout, status
from .io import HardeningError, read_json
from .packaging import validate_candidate_bundle


def health(
    *,
    workspace_root: Path,
    candidate_role: str | None = None,
    pipeline_id: str | None = None,
) -> dict[str, object]:
    root = layout(workspace_root).root
    reasons: list[str] = []
    result: dict[str, object] = {
        "schema_version": "full-pipeline-production-candidate-health.v1",
        **scope_fields(),
        "status": "DEGRADED",
        "state": "NOT_STARTED",
        "controller": status(workspace_root=root),
        "model_inference_performed": False,
        "physical_microphone_health_claimed": False,
        "health_basis": "persisted_acceptance_and_asset_integrity",
    }
    paths = layout(root)
    if not paths.authorization.is_file():
        reasons.append("prerequisites_not_validated")
    if paths.execution.is_file():
        execution = read_json(paths.execution)
        if execution.get("status") == "FAIL":
            result["status"] = "UNHEALTHY"
            result["state"] = "FAILED"
            reasons.append("acceptance_execution_failed")
    if paths.evidence_index.is_file():
        evidence = read_json(paths.evidence_index)
        if evidence.get("status") != "PASS":
            result["status"] = "UNHEALTHY"
            result["state"] = "FAILED"
            reasons.append("acceptance_validation_failed")
    if not paths.completion.is_file():
        if (
            paths.progress.is_file()
            and time.time() - paths.progress.stat().st_mtime > 900
        ):
            result["state"] = "STALE"
            reasons.append("progress_record_older_than_15_minutes")
        elif paths.plan.is_file():
            result["state"] = "PREPARED_OR_RUNNING"
            reasons.append("completion_not_yet_validated")
        result["reasons"] = reasons
        return result
    try:
        from .reporting import validate_completion

        completion = validate_completion(
            workspace_root=root,
            completion_record_path=paths.completion,
        )
        candidates = _validate_requested_candidates(
            root,
            candidate_role=candidate_role,
            pipeline_id=pipeline_id,
        )
    except Exception as exc:
        result["status"] = "UNHEALTHY"
        result["state"] = "TAMPERED_OR_INVALID"
        reasons.append(f"{type(exc).__name__}: {exc}")
    else:
        result["status"] = "HEALTHY"
        result["state"] = "VALIDATED_COMPLETE"
        result["completion_validation"] = completion
        result["candidates"] = candidates
        reasons.append("completion_acceptance_bundles_and_assets_validated")
    result["reasons"] = reasons
    return result


def _validate_requested_candidates(
    root: Path,
    *,
    candidate_role: str | None,
    pipeline_id: str | None,
) -> list[dict[str, object]]:
    bundle_root = root / "candidate_bundles"
    if candidate_role:
        bundle = bundle_root / candidate_role.casefold()
        if not bundle.is_dir():
            raise HardeningError(f"candidate role bundle is missing: {candidate_role}")
        return [validate_candidate_bundle(bundle, pipeline_id=pipeline_id)]
    matches: list[dict[str, object]] = []
    for bundle in bundle_root.glob("*"):
        if not bundle.is_dir():
            continue
        value = validate_candidate_bundle(bundle)
        if pipeline_id is None or value.get("pipeline_id") == pipeline_id:
            matches.append(value)
    if pipeline_id is not None and len(matches) != 1:
        raise HardeningError(
            f"pipeline ID must resolve to one candidate bundle; found {len(matches)}"
        )
    if not matches:
        raise HardeningError("no validated production candidate bundles exist")
    return matches


def serve(
    *,
    workspace_root: Path,
    bind: str = "127.0.0.1",
    port: int = 8767,
) -> None:
    root = Path(workspace_root)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") not in {"", "/health", "/status"}:
                self.send_error(404)
                return
            try:
                value: Mapping[str, object] = health(workspace_root=root)
                code = 200 if value.get("status") == "HEALTHY" else 503
            except Exception as exc:  # pragma: no cover - exercised operationally
                value = {"status": "UNHEALTHY", "error": f"{type(exc).__name__}: {exc}"}
                code = 503
            payload = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((bind, port), Handler)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


__all__ = ["health", "serve"]
