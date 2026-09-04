"""CLI for the frozen final hybrid speaker-attribution evaluation."""

from __future__ import annotations

import json

from app.hybrid_final_evaluation.analysis import analyze, collect, validate_final
from app.hybrid_final_evaluation.decision import validate_frozen_decision
from app.hybrid_final_evaluation.runner import plan, run_controlled, run_native_scope, status, stop


def add_hybrid_final_parser(subparsers) -> None:
    parser = subparsers.add_parser("hybrid-final-evaluation", help="Run the Task-1-frozen held-out hybrid speaker-attribution evaluation")
    actions = parser.add_subparsers(dest="hybrid_final_action", required=True)
    for name, function in (("validate", validate_frozen_decision), ("plan", plan), ("status", status), ("stop", stop), ("validate-final", validate_final), ("collect", collect)):
        child = actions.add_parser(name)
        child.set_defaults(func=lambda args, fn=function: _emit(fn()))
    run = actions.add_parser("run")
    run.add_argument("--scope", choices=("all", "controlled", "chime6", "voices"), default="all")
    run.add_argument("--parallel-backends", type=int, choices=(1, 2), default=2)
    run.set_defaults(func=_run)
    controlled = actions.add_parser("run-controlled")
    controlled.add_argument("--parallel-backends", type=int, choices=(1, 2), default=2)
    controlled.set_defaults(func=lambda args: _emit(run_controlled(parallel_backends=args.parallel_backends)))
    smoke = actions.add_parser("smoke")
    smoke.add_argument("--parallel-backends", type=int, choices=(1, 2), default=2)
    smoke.set_defaults(func=lambda args: _emit(run_controlled(parallel_backends=args.parallel_backends, max_cases=1)))
    chime = actions.add_parser("run-chime6")
    chime.set_defaults(func=lambda args: _emit(run_native_scope("chime6")))
    voices = actions.add_parser("run-voices")
    voices.set_defaults(func=lambda args: _emit(run_native_scope("voices")))
    analysis = actions.add_parser("analyze")
    analysis.add_argument("--bootstrap-repetitions", type=int, choices=range(500, 1001), default=500)
    analysis.set_defaults(func=lambda args: _emit(analyze(bootstrap_repetitions=args.bootstrap_repetitions)))
    full = actions.add_parser("full")
    full.add_argument("--parallel-backends", type=int, choices=(1, 2), default=2)
    full.add_argument("--bootstrap-repetitions", type=int, choices=range(500, 1001), default=500)
    full.set_defaults(func=_full)


def _run(args) -> None:
    if args.scope in {"all", "controlled"}:
        run_controlled(parallel_backends=args.parallel_backends)
    if args.scope in {"all", "chime6"}:
        run_native_scope("chime6")
    if args.scope in {"all", "voices"}:
        run_native_scope("voices")
    _emit(status())


def _full(args) -> None:
    validate_frozen_decision()
    plan()
    run_controlled(parallel_backends=args.parallel_backends)
    run_native_scope("chime6")
    run_native_scope("voices")
    analyze(bootstrap_repetitions=args.bootstrap_repetitions)
    _emit(collect())


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))

