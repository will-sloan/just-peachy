"""Checksum-bound pre-held-out freeze launcher for the ten-hour H2 scope.

The original freeze requires long serial-resource jobs for all three product
modes. This launcher changes only that engineering prerequisite: it still
requires and verifies the three complete matched development-mode executions,
the frozen selector correction, app validation, and original policy choices.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping, NoReturn, Sequence


REVISION = "timeboxed_completion/scope_amendment.revision_3.json"
ORIGINAL_BOOTSTRAP = (
    "diagnostics/pre_freeze_selector_fix_staging/"
    "h2_prefreeze_selector_correction_bootstrap.py"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_revision(
    workspace: Path,
    launcher: Path,
    original: Path,
    corrected: ModuleType,
) -> dict[str, Any]:
    revision_path = workspace / REVISION
    revision = json.loads(revision_path.read_text(encoding="utf-8"))
    unsigned = dict(revision)
    claimed = unsigned.pop("receipt_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("timeboxed freeze revision checksum differs")
    bindings = revision.get("file_bindings")
    if not isinstance(bindings, Mapping):
        raise RuntimeError("timeboxed freeze revision bindings are missing")
    expected = {
        "timeboxed_freeze_bootstrap": sha256_file(launcher),
        "selector_correction_bootstrap": sha256_file(original),
        "patched_controller": sha256_file(Path(corrected.__file__).resolve()),
    }
    if dict(bindings) != expected:
        raise RuntimeError("timeboxed freeze executable bindings differ")
    state = json.loads(
        (workspace / "program_state.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (workspace / "job_manifest.json").read_text(encoding="utf-8")
    )
    by_id = {row["job_id"]: row for row in manifest["jobs"]}
    opened = [
        job_id
        for job_id, row in state["jobs"].items()
        if by_id[job_id].get("split") == "evaluation"
        and row.get("state")
        not in {"PENDING", "SUPERSEDED", "WAITING_PROMOTION"}
    ]
    if opened or revision.get("evaluation_material_inspected") is not False:
        raise RuntimeError(
            "timeboxed freeze override is ineligible after held-out opening: "
            f"{opened}"
        )
    if revision.get("retuning_permitted") is not False:
        raise RuntimeError("timeboxed freeze revision permits retuning")
    return revision


def install_validation_override(
    corrected: ModuleType, revision: Mapping[str, Any]
) -> None:
    def verify_mode_executions(
        paths: Any,
        state: Mapping[str, object],
        jobs: Sequence[Any],
        selected: Mapping[str, object],
    ) -> None:
        raw_tuning = selected.get("runtime_tuning")
        if not isinstance(raw_tuning, Mapping):
            raise corrected.H2ProgramError("selected runtime tuning is missing")
        checked: list[str] = []
        for logical in jobs:
            if logical.job_kind != "post_selection_mode_validation":
                continue
            if corrected._job_state(state, logical.job_id).get("state") != "COMPLETE":
                raise corrected.H2ProgramError(
                    "matched development-mode validation is incomplete: "
                    f"{logical.job_id}"
                )
            execution_manifest = corrected.read_json(
                corrected._dynamic_paths(paths, logical).workspace
                / "dynamic_execution.json"
            )
            raw_execution = execution_manifest.get("execution_job")
            if not isinstance(raw_execution, Mapping):
                raise corrected.H2ProgramError(
                    "matched development-mode execution is missing: "
                    f"{logical.job_id}"
                )
            execution = corrected.H2Job.from_jsonable(raw_execution)
            expected = corrected.H2RuntimeTuning.from_mapping(
                {**dict(raw_tuning), "product_mode": logical.mode}
            )
            actual = corrected.H2RuntimeTuning.from_mapping(
                execution.runtime_tuning
            )
            if actual.identity_sha256 != expected.identity_sha256:
                raise corrected.H2ProgramError(
                    "matched development mode measured stale tuning: "
                    f"{logical.job_id}"
                )
            checked.append(logical.job_id)
        if len(checked) != 3:
            raise corrected.H2ProgramError(
                "timeboxed freeze requires exactly three matched development "
                f"modes, got {checked}"
            )
        if isinstance(selected, dict):
            selected["timeboxed_freeze_scope"] = {
                "scope_revision_sha256": revision["receipt_sha256"],
                "matched_development_mode_jobs": checked,
                "serial_resources_required_before_freeze": False,
                "serial_resources_deferred_to_post_heldout_engineering": True,
            }

    corrected._verify_final_selected_execution_tuning = verify_mode_executions


def main(argv: Sequence[str] | None = None) -> NoReturn:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    launcher = Path(__file__).resolve()
    tool_root = launcher.parent.parent
    original = (
        tool_root
        / "automated_runs/h2_complete_product_pipeline_v17"
        / ORIGINAL_BOOTSTRAP
    )
    base = load_module(original, "h2_original_selector_bootstrap_for_timebox")
    action, paths, clean_args = base._parse_action_paths(raw_args, tool_root)
    workspace = Path(paths.workspace).resolve()
    manifest, manifest_file_sha256 = base._validate_manifest(
        original, tool_root=tool_root, workspace=workspace
    )
    base._assert_bound_program_identities(manifest, workspace)
    if action not in {"Run", "Resume"}:
        raise RuntimeError("timeboxed freeze launcher accepts only Run or Resume")
    receipt = base._validate_existing_receipt(
        base._activation_receipt_path(workspace),
        manifest=manifest,
        manifest_file_sha256=manifest_file_sha256,
        workspace=workspace,
    )
    if receipt is None:
        raise RuntimeError("the original selector correction must be activated first")
    base._continuation_preflight(workspace=workspace, receipt=receipt)
    base._install_windows_atomic_retry(tool_root, workspace)
    corrected = base._load_corrected_controller(original)
    base._install_bound_selector(
        corrected,
        manifest=manifest,
        manifest_file_sha256=manifest_file_sha256,
    )
    revision = validate_revision(workspace, launcher, original, corrected)
    install_validation_override(corrected, revision)
    from app.h2_product_program import cli

    cli.controller = corrected
    raise SystemExit(cli.main(clean_args))


if __name__ == "__main__":
    main()
