"""Adapter from H2 program jobs to the shared full-pipeline queue/runtime.

This module deliberately contains no inference logic.  Runtime jobs are
translated into the existing :mod:`app.full_pipeline_evaluation` contracts and
executed by its checksum-validating worker.  Non-runtime research jobs must
have an explicit handler in the H2 controller; an unknown kind fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import threading
import time
from typing import Callable, Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.product_modes import H2RuntimeTuning
from app.full_pipeline_evaluation import controller as evaluation_controller
from app.full_pipeline_evaluation.io import sha256_file as evaluation_sha256_file
from app.full_pipeline_evaluation.planning import (
    MATRIX_PATH,
    RUNTIME_CONFIG_PATH,
)
from app.full_pipeline_evaluation.results import result_tree_reusable
from app.full_pipeline_evaluation.schema import normalize_reuse_identity
from app.full_pipeline_evaluation.store import EvaluationJobSpec, EvaluationStateStore
from app.full_pipeline_evaluation.worker import execute_evaluation_job

from .contracts import H2Job, H2ProgramError, ProgramPaths
from .io import canonical_sha256, read_jsonl, sha256_file, write_json_atomic
from .planning import PREPARED_PROTOCOL_ROOT


RUNTIME_QUEUE_DATABASE = "campaign.sqlite3"
RUNTIME_QUEUE_MANIFEST = "campaign_manifest.json"
RUNTIME_QUEUE_PATHS = "campaign_paths.json"
RUNTIME_KINDS = frozenset(
    {
        "runtime_accuracy",
        "runtime_qualification",
        "successive_halving_runtime",
        "resource_runtime",
        "diagnostic_runtime",
    }
)
_ENVIRONMENT_CACHE: tuple[float, dict[str, object]] | None = None


def runtime_jobs(jobs: Sequence[H2Job]) -> tuple[H2Job, ...]:
    return tuple(job for job in jobs if job.job_kind in RUNTIME_KINDS)


def validate_runtime_tuning(job: H2Job) -> H2RuntimeTuning:
    """Return the strict executable tuning object for an H2 runtime job."""

    if job.job_kind not in RUNTIME_KINDS:
        raise H2ProgramError(f"job is not a runtime job: {job.job_id}")
    if job.pipeline_id not in {"fullpipe_v1_ag_dr_ir", "fullpipe_v1_ao_dr_ir"}:
        raise H2ProgramError(f"runtime job is not H2: {job.job_id}")
    try:
        tuning = H2RuntimeTuning.from_mapping(job.runtime_tuning)
    except (TypeError, ValueError) as exc:
        raise H2ProgramError(
            f"runtime tuning is not executable for {job.job_id}: {exc}"
        ) from exc
    if tuning.redim_execution_strategy not in {
        "R1_TWO_INDEPENDENT_MODELS",
        "R2_ONE_SHARED_MODEL",
        "R3_EXACT_WINDOW_EMBEDDING_REUSE",
        "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
    }:
        raise H2ProgramError(
            f"unqualified ReDim reuse escaped into runtime job {job.job_id}"
        )
    if tuning.redim_execution_strategy.startswith(("R3_", "R4_")) and (
        tuning.embedding_reuse_qualification_sha256 is None
    ):
        raise H2ProgramError(
            f"unqualified ReDim reuse escaped into runtime job {job.job_id}"
        )
    return tuning


def build_runtime_specs(
    jobs: Sequence[H2Job],
    *,
    protocol: Mapping[str, object],
    seed: int,
) -> tuple[EvaluationJobSpec, ...]:
    """Build queue identities that include H2 tuning and implementation code."""

    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    implementation = runtime_implementation_identity()
    specs: list[EvaluationJobSpec] = []
    for job in runtime_jobs(jobs):
        tuning = validate_runtime_tuning(job)
        selection = matrix.resolve(job.pipeline_id)
        partition = job.split
        if partition not in {"development", "evaluation"}:
            raise H2ProgramError(f"runtime job has invalid split: {job.job_id}")
        case_identity = canonical_sha256(
            {
                "h2_job_identity_sha256": job.identity_sha256,
                "runtime_tuning_identity_sha256": tuning.identity_sha256,
                "implementation": implementation,
                "prepared_case_manifest_sha256": sha256_file(
                    PREPARED_PROTOCOL_ROOT / partition / "case_manifest.jsonl"
                ),
            }
        )
        reuse_identity = normalize_reuse_identity(
            {
                "program_id": "just_peachy_full_pipeline_program_v1",
                "evaluation_protocol_id": str(protocol["protocol_id"]),
                "evaluation_protocol_sha256": str(protocol["protocol_sha256"]),
                "pipeline_id": job.pipeline_id,
                "pipeline_config_sha256": selection.pipeline_config_sha256,
                "case_manifest_id": f"{job.job_id}:{job.configuration_id}",
                "case_manifest_sha256": case_identity,
                "runtime_config_sha256": selection.runtime_config_sha256,
                "partition": partition,
                "seed": int(seed),
            }
        )
        measurement_mode = (
            "resources" if job.job_kind == "resource_runtime" else "accuracy"
        )
        specs.append(
            EvaluationJobSpec(
                job_id=job.job_id,
                pipeline_id=job.pipeline_id,
                protocol_id=str(protocol["protocol_id"]),
                split=partition,
                source_key=job.configuration_id.casefold(),
                measurement_mode=measurement_mode,
                seed=int(seed),
                case_count=len(job.case_ids),
                audio_duration_sec=job.audio_duration_sec,
                protocol_identity=str(protocol["protocol_sha256"]),
                pipeline_identity=selection.pipeline_config_sha256,
                reuse_identity=reuse_identity,
                case_ids=job.case_ids,
                result_relative_path=f"jobs/{job.job_id}/result",
            )
        )
    return tuple(specs)


def prepare_runtime_queue(
    paths: ProgramPaths,
    jobs: Sequence[H2Job],
    *,
    protocol: Mapping[str, object],
    job_manifest_sha256: str,
    seed: int,
) -> dict[str, object]:
    """Prepare the shared durable queue without opening held-out references."""

    specs = build_runtime_specs(jobs, protocol=protocol, seed=seed)
    manifest = {
        "schema_version": "h2-product-runtime-queue.v1",
        "campaign_id": str(protocol["protocol_id"]),
        "protocol_sha256": str(protocol["protocol_sha256"]),
        "job_manifest_sha256": job_manifest_sha256,
        "jobs": [spec.to_jsonable() for spec in specs],
        "case_index_persisted": False,
        "heldout_references_opened": False,
        "runtime_inference_implemented_by": "app.full_pipeline_evaluation.worker",
    }
    manifest_path = paths.workspace / RUNTIME_QUEUE_MANIFEST
    if manifest_path.is_file():
        from .io import read_json

        if read_json(manifest_path) != manifest:
            raise H2ProgramError(
                "runtime queue identity changed; use a new H2 workspace"
            )
    else:
        write_json_atomic(manifest_path, manifest)
    write_json_atomic(
        paths.workspace / RUNTIME_QUEUE_PATHS,
        {
            "schema_version": "full-pipeline-evaluation-paths.v1",
            "campaign_id": protocol["protocol_id"],
            "workspace_root": str(paths.workspace),
            "results_root": str(paths.results_root),
            "summary_root": str(paths.summary_root),
        },
    )
    store = EvaluationStateStore(paths.workspace / RUNTIME_QUEUE_DATABASE)
    prepared = store.prepare(
        specs,
        campaign_id=str(protocol["protocol_id"]),
        manifest_sha256=evaluation_sha256_file(manifest_path),
    )
    store.assert_integrity()
    return {
        "runtime_job_count": len(specs),
        "queue": prepared,
        "database": str(paths.workspace / RUNTIME_QUEUE_DATABASE),
    }


def run_runtime_job(
    paths: ProgramPaths,
    job: H2Job,
    *,
    protocol: Mapping[str, object],
    stop_event: threading.Event,
    progress_lock: threading.Lock,
    additional_execution_contract: Mapping[str, object] | None = None,
    storage_reserve_callback: Callable[[], None] | None = None,
    external_stop_path: Path | None = None,
) -> dict[str, object]:
    """Execute/reuse one H2 runtime job through the existing queue worker."""

    tuning = validate_runtime_tuning(job)
    store = EvaluationStateStore(paths.workspace / RUNTIME_QUEUE_DATABASE)
    states = {row.spec.job_id: row for row in store.list_jobs()}
    try:
        queued = states[job.job_id]
    except KeyError as exc:
        raise H2ProgramError(f"runtime job is absent from queue: {job.job_id}") from exc
    spec = queued.spec
    cases = load_cases_for_job(job, open_evaluation=job.split == "evaluation")
    ephemeral_manifest = {
        "campaign_id": str(protocol["protocol_id"]),
        "case_index": {_case_id(row): row for row in cases},
    }

    execution_contract = {
        "schema_version": "h2-product-execution-contract.v1",
        "h2_job_id": job.job_id,
        "h2_job_identity_sha256": job.identity_sha256,
        "h2_protocol_id": protocol["protocol_id"],
        "h2_protocol_sha256": protocol["protocol_sha256"],
        "case_boundary_stop_only": True,
        "target_wall_hours": 192.0,
        "automatic_time_cutoff": False,
        "storage_drive": "C:",
        "product_mode": tuning.product_mode.value,
        "runtime_tuning_identity_sha256": tuning.identity_sha256,
    }
    extra_contract = dict(additional_execution_contract or {})
    overlap = set(execution_contract) & set(extra_contract)
    if overlap:
        raise H2ProgramError(
            f"additional execution contract overrides reserved fields: {sorted(overlap)}"
        )
    execution_contract.update(extra_contract)
    durable_stop_path = (
        Path(external_stop_path).resolve()
        if external_stop_path is not None
        else paths.stop_path
    )

    def require_storage_reserve() -> None:
        if storage_reserve_callback is None:
            return
        try:
            storage_reserve_callback()
        except Exception:
            # The shared queue classifies this as a graceful boundary stop,
            # preserving all checksum-valid case shards for Resume.
            stop_event.set()
            raise

    def executor(
        runtime_spec: EvaluationJobSpec,
        runtime_cases: Sequence[Mapping[str, object]],
        output_root: Path,
        progress: Callable[..., None],
        stop_requested: Callable[[], bool],
    ) -> Mapping[str, object]:
        def boundary_stop_requested() -> bool:
            # The direct durable-file check is an independent fallback for the
            # controller poller.  It is evaluated only at bounded worker stop
            # checkpoints, so a poller failure cannot silently start another
            # atomic case after an operator stop request.
            return (
                stop_requested() or stop_event.is_set() or durable_stop_path.is_file()
            )

        return execute_evaluation_job(
            runtime_spec,
            runtime_cases,
            output_root,
            progress,
            boundary_stop_requested,
            execution_contract=execution_contract,
            runtime_tuning=tuning.to_jsonable(),
            stop_at_case_boundary=True,
            storage_reserve_callback=(
                require_storage_reserve
                if storage_reserve_callback is not None
                else None
            ),
        )

    outcome = evaluation_controller._run_one(  # noqa: SLF001 - shared queue adapter
        paths.workspace,
        ephemeral_manifest,
        spec,
        executor,
        progress_lock,
        stop_event,
    )
    state = str(outcome.get("state") or "failed")
    latest = next(row for row in store.list_jobs() if row.spec.job_id == job.job_id)
    return {
        **dict(outcome),
        "state": state,
        "completed_cases": latest.completed_cases,
        "completed_audio_sec": latest.completed_audio_sec,
        "cache_hits": latest.cache_hits,
        "result_sha256": latest.result_sha256,
        "result_root": str(paths.results_root / spec.result_relative_path),
    }


def load_cases_for_job(
    job: H2Job, *, open_evaluation: bool
) -> tuple[dict[str, object], ...]:
    """Materialize exact cases, enforcing the held-out opening gate."""

    if job.split == "evaluation" and not open_evaluation:
        raise H2ProgramError("held-out case materialization is forbidden before freeze")
    if job.split not in {"development", "evaluation"}:
        raise H2ProgramError(f"job has no protocol case split: {job.job_id}")
    rows = read_jsonl(PREPARED_PROTOCOL_ROOT / job.split / "case_manifest.jsonl")
    index = {_case_id(row): dict(row) for row in rows}
    missing = [case_id for case_id in job.case_ids if case_id not in index]
    if missing:
        raise H2ProgramError(
            f"job cases are missing from prepared protocol: {job.job_id}: {missing[:3]}"
        )
    return tuple(index[case_id] for case_id in job.case_ids)


def runtime_result_reusable(paths: ProgramPaths, job: H2Job) -> bool:
    if job.job_kind not in RUNTIME_KINDS:
        return False
    store = EvaluationStateStore(paths.workspace / RUNTIME_QUEUE_DATABASE)
    row = next(
        (value for value in store.list_jobs() if value.spec.job_id == job.job_id),
        None,
    )
    if row is None:
        return False
    root = paths.results_root / row.spec.result_relative_path
    return result_tree_reusable(root, row.spec.reuse_identity)


def runtime_implementation_identity() -> dict[str, object]:
    """Return one portable identity for every result-affecting runtime source."""

    evaluation_root = Path(__file__).resolve().parents[2]
    repository_root = evaluation_root.parents[1]
    arm64_bundle = evaluation_root / "deployment/h2_arm64"
    stable_arm64_files = tuple(
        sorted(
            path
            for path in arm64_bundle.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix.casefold() not in {".pyc", ".pyo", ".tmp", ".lock"}
            and not path.name.endswith(("~", ".partial"))
        )
    )
    groups = {
        # This conservative aggregate closes transitive-source gaps. The
        # granular groups below remain useful when diagnosing which component
        # changed, while this group guarantees that every application module
        # used by demo, development, evaluation, reporting, telemetry, or
        # portability work is bound to the scientific runtime identity.
        "complete_application_source_tree": tuple(
            sorted((evaluation_root / "app").rglob("*.py"))
        ),
        # The ARM64 preparation job consumes scripts, manifests, service files,
        # and dependency pins as well as Python. Bind the complete stable bundle
        # and deliberately exclude generated bytecode and transient lock files.
        "h2_arm64_deployment_bundle": stable_arm64_files,
        "h2_controller": tuple(sorted(Path(__file__).resolve().parent.glob("*.py"))),
        "streaming_runtime": tuple(
            sorted((evaluation_root / "app/full_pipeline").glob("*.py"))
        ),
        "evaluation_and_scorers": tuple(
            sorted((evaluation_root / "app/full_pipeline_evaluation").glob("*.py"))
        ),
        "inference_pipeline": tuple(
            sorted((evaluation_root / "app/inference_pipeline").rglob("*.py"))
        ),
        "speaker_protocol": tuple(
            sorted((evaluation_root / "app/speaker_protocol").rglob("*.py"))
        ),
        "worker_external_adapters": (
            evaluation_root / "app/controlled_diarization/runner.py",
            evaluation_root / "app/diarization_product_v2/cross_environment.py",
            evaluation_root / "app/hybrid_speaker_attribution/embedding_cache.py",
        ),
        "shared_path_audio_utilities": tuple(
            sorted((evaluation_root / "app/utils").rglob("*.py"))
        ),
        "environment_definitions": tuple(
            sorted((repository_root / "requirements").rglob("*.txt"))
        )
        + (
            repository_root / "requirements.txt",
            evaluation_root / "requirements.txt",
            evaluation_root
            / "configs/automated_evaluation/environment_profiles.v1.yaml",
        ),
    }
    components = {
        name: canonical_sha256(
            {
                path.resolve()
                .relative_to(repository_root)
                .as_posix(): (sha256_file(path) if path.is_file() else "MISSING")
                for path in paths
            }
        )
        for name, paths in groups.items()
    }
    environments = _installed_worker_environment_identities(repository_root)
    core = {
        "schema_version": "h2-runtime-implementation-identity.v2",
        "components": components,
        "installed_worker_environments": environments,
    }
    return {**core, "identity_sha256": canonical_sha256(core)}


def _installed_worker_environment_identities(
    repository_root: Path,
) -> dict[str, object]:
    global _ENVIRONMENT_CACHE
    now = time.monotonic()
    if _ENVIRONMENT_CACHE is not None and now - _ENVIRONMENT_CACHE[0] < 60.0:
        return dict(_ENVIRONMENT_CACHE[1])
    from app.controlled_diarization.runner import interpreter_for_profile

    probe = (
        "import importlib.metadata as m,json,platform,sys;"
        "rows=sorted(({\"name\":(d.metadata.get('Name') or d.name),"
        '"version":d.version} for d in m.distributions()),'
        "key=lambda x:x['name'].casefold());"
        'print(json.dumps({"python_version":platform.python_version(),'
        '"implementation":platform.python_implementation(),'
        "\"packages\":rows},sort_keys=True,separators=(',',':')))"
    )
    identities: dict[str, object] = {}
    for profile in (
        "core-cpu",
        "onnx",
        "credential-diarization",
        "redimnet2",
    ):
        interpreter = interpreter_for_profile(profile)
        if interpreter is None or not interpreter.is_file():
            raise H2ProgramError(
                f"required H2 worker environment is unavailable: {profile}"
            )
        completed = subprocess.run(
            [str(interpreter), "-c", probe],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60.0,
        )
        if completed.returncode != 0:
            raise H2ProgramError(
                f"cannot fingerprint H2 worker environment {profile}: "
                f"exit {completed.returncode}"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise H2ProgramError(
                f"invalid package fingerprint from H2 worker environment {profile}"
            ) from exc
        if not isinstance(payload, Mapping) or not isinstance(
            payload.get("packages"), list
        ):
            raise H2ProgramError(
                f"incomplete package fingerprint from H2 worker environment {profile}"
            )
        identities[profile] = {
            "interpreter_path": str(interpreter.resolve()),
            "interpreter_sha256": sha256_file(interpreter),
            "python_version": payload.get("python_version"),
            "implementation": payload.get("implementation"),
            "package_freeze_sha256": canonical_sha256(payload["packages"]),
            "package_count": len(payload["packages"]),
        }
    _ENVIRONMENT_CACHE = (now, identities)
    return dict(identities)


def _case_id(row: Mapping[str, object]) -> str:
    value = (
        row.get("case_id")
        or row.get("protocol_case_id")
        or row.get("recording_id")
        or row.get("utt_id")
    )
    if value is None or not str(value).strip():
        raise H2ProgramError("prepared protocol case lacks a case ID")
    return str(value)


__all__ = [
    "RUNTIME_KINDS",
    "RUNTIME_QUEUE_DATABASE",
    "build_runtime_specs",
    "load_cases_for_job",
    "prepare_runtime_queue",
    "run_runtime_job",
    "runtime_jobs",
    "runtime_result_reusable",
    "runtime_implementation_identity",
    "validate_runtime_tuning",
]
