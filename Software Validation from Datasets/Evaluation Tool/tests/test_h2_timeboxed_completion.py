from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_punctuation_insensitive_primitives() -> None:
    report = load_script("h2_timeboxed_report.py")
    assert report.normalize_words("Hello, WORLD — we're ready!") == [
        "hello",
        "world",
        "we",
        "re",
        "ready",
    ]
    assert report.edit_distance(["a", "b", "c"], ["a", "x", "c"]) == 1


def test_role_selection_does_not_treat_missing_safety_as_zero() -> None:
    report = load_script("h2_timeboxed_report.py")
    known, memory = report.PRIMARY_JOBS
    state = {"jobs": {known: {"state": "COMPLETE"}, memory: {"state": "COMPLETE"}}}
    rows = [
        {"job_id": known, "metric_id": "correct_transcribed_attributed_word_rate", "status": "computed", "value": 0.9},
        {"job_id": memory, "metric_id": "stranger_false_known_time_sec", "status": "computed", "value": 2.0},
        {"job_id": memory, "metric_id": "wrong_known_time_sec", "status": "computed", "value": 1.0},
        {"job_id": memory, "metric_id": "wrong_name_dwell_sec", "status": "computed", "value": 3.0},
        {"job_id": memory, "metric_id": "correct_transcribed_attributed_word_rate", "status": "computed", "value": 0.5},
    ]
    selected, _fallback, evidence = report.choose_roles(state, rows)
    assert selected == memory
    assert evidence == "held-out"


def test_scope_amendment_is_idempotent_and_preserves_complete_rows(tmp_path: Path) -> None:
    completion = load_script("h2_timeboxed_completion.py")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    launcher = workspace / "diagnostics/pre_freeze_selector_fix_staging/h2_prefreeze_selector_correction_bootstrap.py"
    patched = launcher.parent / "controller.py.patched"
    override = tmp_path / "scripts/h2_timeboxed_freeze_bootstrap.py"
    report = tmp_path / "scripts/h2_timeboxed_report.py"
    launcher.parent.mkdir(parents=True)
    override.parent.mkdir(parents=True)
    launcher.write_text("# original launcher\n", encoding="utf-8")
    patched.write_text("# patched controller\n", encoding="utf-8")
    override.write_text("# timeboxed launcher\n", encoding="utf-8")
    report.write_text("# timeboxed report\n", encoding="utf-8")
    all_ids = (
        set(completion.SCIENCE_JOBS)
        | set(completion.ENGINEERING_JOBS)
        | set(completion.FREEZE_RESOURCE_JOBS)
        | set(completion.DEFERRED_JOBS)
    )
    all_ids.add(completion.MEMORY_DEV)
    jobs = []
    state_jobs = {}
    for job_id in sorted(all_ids):
        split = "evaluation" if job_id in completion.HELDOUT_JOBS else "none"
        jobs.append({"job_id": job_id, "split": split})
        state_jobs[job_id] = {
            "state": "COMPLETE" if job_id == completion.MEMORY_DEV else "PENDING",
            "latest_activity": "prepared",
            "last_error": None,
            "completed_at_utc": None,
            "updated_at_utc": "2026-09-01T00:00:00Z",
        }
    (workspace / "job_manifest.json").write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
    (workspace / "program_state.json").write_text(json.dumps({"status": "STOPPED", "jobs": state_jobs}), encoding="utf-8")
    args = argparse.Namespace(
        tool_root=str(tmp_path), workspace=str(workspace), results_root=str(tmp_path / "results"),
        summary_root=str(tmp_path / "summary"), config=str(tmp_path / "config.yaml"),
        deadline_utc="2026-09-01T15:22:00Z", packaging_reserve_minutes=75,
    )
    controller = completion.Timebox(args)
    controller.apply_scope()
    first = completion.read_json(workspace / "program_state.json")
    receipt_hash = first["timeboxed_scope_receipt_sha256"]
    assert first["jobs"][completion.MEMORY_DEV]["state"] == "COMPLETE"
    assert all(first["jobs"][job]["state"] == "PENDING" for job in completion.SCIENCE_JOBS)
    assert all(first["jobs"][job]["state"] == "SUPERSEDED" for job in completion.ENGINEERING_JOBS)
    controller.apply_scope()
    second = completion.read_json(workspace / "program_state.json")
    assert second["timeboxed_scope_receipt_sha256"] == receipt_hash
    revision_sha = controller.prepare_timeboxed_freeze_override()
    revised = completion.read_json(workspace / "program_state.json")
    assert all(
        revised["jobs"][job]["state"] == "PENDING"
        for job in completion.SCIENCE_JOBS
    )
    assert all(
        revised["jobs"][job]["state"] == "SUPERSEDED"
        for job in completion.FREEZE_RESOURCE_JOBS
    )
    revision = workspace / "timeboxed_completion/scope_amendment.revision_3.json"
    assert revision.is_file()
    assert completion.read_json(revision)["receipt_sha256"] == revision_sha


def test_deadline_guard_tracks_only_unfinished_pass_and_fresh_package(tmp_path: Path) -> None:
    guard = load_script("h2_deadline_packaging_guard.py")
    events = tmp_path / "events.jsonl"
    events.write_text(
        "\n".join(
            [
                json.dumps({"kind": "PASS_LAUNCHED", "label": "science", "pid": 10}),
                json.dumps({"kind": "PASS_FINISHED", "label": "science"}),
                json.dumps({"kind": "PASS_LAUNCHED", "label": "engineering", "pid": 20}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert guard.active_pass(events) == ("engineering", 20)
    package = tmp_path / "result.zip"
    pointer = tmp_path / "pointer.txt"
    package.write_bytes(b"new package")
    digest = guard.sha256_file(package)
    pointer.write_text(f"SHA-256:\n{digest}\n", encoding="utf-8")
    assert guard.fresh_package(package, pointer, "old digest")
    assert not guard.fresh_package(package, pointer, digest)
