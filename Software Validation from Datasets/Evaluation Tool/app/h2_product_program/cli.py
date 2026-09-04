"""Command-line surface for the restart-safe H2 product program."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Sequence

from . import controller
from .planning import default_paths


ACTIONS = {
    "audit": "Audit",
    "prepare": "Prepare",
    "validate": "Validate",
    "plan": "Plan",
    "smoke": "Smoke",
    "run": "Run",
    "resume": "Resume",
    "status": "Status",
    "monitor": "Status",
    "stop": "Stop",
    "analyze": "Analyze",
    "collect": "Collect",
    "exportportable": "ExportPortable",
    "export-portable": "ExportPortable",
    "launchdemo": "LaunchDemo",
    "launch-demo": "LaunchDemo",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    normalized = str(args.action).casefold()
    if normalized not in ACTIONS:
        parser.error(
            "action must be Audit, Prepare, Validate, Plan, Smoke, Run, Resume, Status, Stop, "
            "Analyze, Collect, ExportPortable, or LaunchDemo"
        )
    action = ACTIONS[normalized]
    paths = default_paths(
        workspace=args.workspace,
        results_root=args.results_root,
        summary_root=args.summary_root,
        config_path=args.config,
    )
    try:
        if action == "Audit":
            payload = controller.audit(paths)
        elif action == "Prepare":
            payload = controller.prepare(paths)
        elif action == "Validate":
            payload = controller.validate(
                paths, verify_results=not args.no_result_validation
            )
        elif action == "Plan":
            payload = controller.plan(paths)
        elif action == "Smoke":
            payload = controller.smoke(paths)
        elif action in {"Run", "Resume"}:
            payload = controller.run(
                paths,
                maximum_jobs=args.maximum_jobs,
                retry_failed=args.retry_failed,
            )
        elif action == "Status":
            if args.watch or normalized == "monitor":
                return _watch(paths, interval_sec=args.interval_sec, as_json=args.json)
            payload = controller.status(paths)
        elif action == "Stop":
            payload = controller.stop(paths, reason=args.reason)
        elif action == "Analyze":
            payload = controller.analyze(paths)
        elif action == "Collect":
            payload = controller.collect(paths)
        elif action == "ExportPortable":
            payload = controller.export_portable(paths)
        elif action == "LaunchDemo":
            payload = controller.launch_demo(paths, dry_run=args.dry_run)
        else:  # pragma: no cover - normalized map owns this branch.
            raise AssertionError(action)
        _print(payload, as_json=args.json or action != "Status")
        status = str(payload.get("status") or "").casefold()
        valid = payload.get("valid")
        return 2 if status in {"fail", "failed", "blocked"} or valid is False else 0
    except KeyboardInterrupt:
        if action in {"Run", "Resume"}:
            try:
                controller.stop(paths, reason="keyboard_interrupt")
            except Exception:
                pass
        print("Graceful stop requested.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--summary-root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--maximum-jobs", type=int)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--no-result-validation", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--reason", default="operator_requested")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Use JSON in watch mode; one-shot actions always print JSON.",
    )
    return parser


def _watch(paths: object, *, interval_sec: float, as_json: bool) -> int:
    if interval_sec < 0.5:
        raise ValueError("monitor interval must be at least 0.5 seconds")
    previous_milestone_id: str | None = None
    first_snapshot = True
    while True:
        payload = controller.status(paths)  # type: ignore[arg-type]
        latest = payload.get("latest_milestone")
        milestone_id = (
            str(latest.get("milestone_id"))
            if isinstance(latest, dict) and latest.get("milestone_id")
            else None
        )
        if (
            not first_snapshot
            and milestone_id is not None
            and milestone_id != previous_milestone_id
        ):
            print("\a", end="", flush=True)
        previous_milestone_id = milestone_id
        first_snapshot = False
        if as_json:
            print(json.dumps(payload, sort_keys=True, default=str), flush=True)
        else:
            _print_monitor(payload)
        state = str(payload.get("status") or "")
        if state.startswith("COMPLETE"):
            return 0
        if state.startswith("BLOCKED") or state == "FAILED":
            return 2
        if state == "STOPPED":
            return 0
        time.sleep(interval_sec)


def _print_monitor(payload: dict[str, object]) -> None:
    line = (
        f"H2 PROGRAM {float(payload.get('percent_complete') or 0.0):6.2f}% "
        f"{payload.get('progress_bar') or ''}  state={payload.get('status')}"
    )
    phase = (
        f"phase={payload.get('current_phase_index')} "
        f"{payload.get('current_phase_name') or '-'}  "
        f"job={payload.get('current_job_id') or '-'}  "
        f"kind={payload.get('current_job_kind') or '-'}"
    )
    identity = (
        f"pipeline={payload.get('current_pipeline_id') or '-'}  "
        f"mode={payload.get('current_mode') or '-'}"
    )
    backend = payload.get("current_backend")
    backend_line = (
        "backends "
        f"ASR={backend.get('asr') or '-'}  "
        f"diarization={backend.get('diarization_embedding') or '-'}  "
        f"identity={backend.get('identity_embedding') or '-'}"
        if isinstance(backend, dict)
        else "backends -"
    )
    totals = (
        f"jobs={payload.get('completed_jobs') or 0}/{payload.get('total_jobs') or 0}  "
        f"cases={payload.get('completed_cases') or 0}/{payload.get('total_cases') or 0}  "
        f"audio={_hours(payload.get('completed_audio_sec'))}/"
        f"{_hours(payload.get('total_audio_sec'))}h"
    )
    case = (
        f"current={payload.get('current_case_id') or '-'}  "
        f"case-progress={payload.get('current_completed_cases') or 0}/"
        f"{payload.get('current_planned_cases') or 0}  "
        f"audio-progress={_seconds(payload.get('current_completed_audio_sec'))}/"
        f"{_seconds(payload.get('current_planned_audio_sec'))}s"
    )
    eta = (
        f"elapsed={payload.get('elapsed_hours')}h  "
        f"ETA={payload.get('eta_hours') if payload.get('eta_hours') is not None else 'measuring'}h  "
        f"finish={payload.get('estimated_finish_utc') or 'measuring'}"
    )
    telemetry = (
        f"RTF={_display(payload.get('rolling_rtf'))}  "
        f"CPU={_display(payload.get('cpu_percent'))}%  "
        f"RAM={_display(payload.get('rss_mb'))}MB  "
        f"queue={_display(payload.get('queue_depth'))}  "
        f"cache={payload.get('cache_hits') or 0}  "
        f"failures={payload.get('failures') or 0}  "
        f"retries={payload.get('retries') or 0}  "
        f"models={_display(payload.get('model_instances'))}  "
        f"embedding_calls={_display(payload.get('embedding_calls'))}"
    )
    storage = payload.get("storage")
    free = storage.get("free_gib") if isinstance(storage, dict) else None
    reserve = storage.get("reserve_satisfied") if isinstance(storage, dict) else None
    detail = (
        f"C: free={free} GiB reserve_ok={reserve}  "
        f"{payload.get('detail') or ''}"
    )
    queue_health = (
        f"queue_snapshot={payload.get('queue_snapshot_source') or '-'}  "
        f"at={payload.get('queue_snapshot_updated_at_utc') or '-'}"
    )
    if payload.get("queue_snapshot_error"):
        queue_health += f"  ERROR={payload['queue_snapshot_error']}"
    activity = (
        f"activity={payload.get('current_activity') or '-'}  "
        f"output={payload.get('latest_output') or '-'}"
    )
    milestone = payload.get("latest_milestone")
    milestone_line = (
        "MILESTONE  "
        + str(milestone.get("detail") or milestone.get("kind") or "")
        if isinstance(milestone, dict)
        else "MILESTONE  none yet"
    )
    # ANSI clear/home is supported by current Windows Terminal and degrades to
    # harmless text in redirected logs.
    print(
        "\x1b[2J\x1b[H"
        + "\n".join(
            (
                line,
                milestone_line,
                phase,
                identity,
                backend_line,
                totals,
                case,
                eta,
                telemetry,
                activity,
                queue_health,
                detail,
            )
        ),
        flush=True,
    )


def _display(value: object) -> object:
    return "-" if value is None else value


def _seconds(value: object) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "0.0"


def _hours(value: object) -> str:
    try:
        return f"{float(value) / 3600.0:.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _print(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        _print_monitor(payload)


__all__ = ["main"]
