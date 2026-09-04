"""CLI for the frozen-finalist final standalone diarization evaluation."""

from __future__ import annotations

import argparse
import json


def add_diarization_final_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "diarization-final-evaluation",
        help="Operate the frozen-finalist standalone anonymous diarization evaluation",
    )
    commands = parser.add_subparsers(dest="diarization_final_command", required=True)
    for name in ("validate", "plan", "status", "stop", "analyze", "collect"):
        command = commands.add_parser(name)
        command.set_defaults(func=_dispatch, final_action=name)
    run = commands.add_parser("run")
    run.add_argument("--scope", choices=("all", "controlled", "chime6", "voices"), default="all")
    run.add_argument("--parallel-pipelines", type=int, choices=(1, 2), default=2)
    run.set_defaults(func=_dispatch, final_action="run")
    worker = commands.add_parser("worker-controlled", help=argparse.SUPPRESS)
    worker.add_argument("--pipeline", required=True)
    worker.set_defaults(func=_worker_controlled)
    for name in ("worker-chime6", "worker-voices"):
        worker = commands.add_parser(name, help=argparse.SUPPRESS)
        worker.add_argument("--pipeline", required=True)
        worker.add_argument("--dataset", choices=("chime6", "voices"), required=True)
        worker.set_defaults(func=_worker_native)


def _dispatch(args: argparse.Namespace) -> None:
    from app.diarization_final_evaluation import controller

    if args.final_action == "run":
        value = controller.run(scope=args.scope, parallel_pipelines=args.parallel_pipelines)
    else:
        value = getattr(controller, args.final_action)()
    print(json.dumps(value, indent=2, sort_keys=True))


def _worker_controlled(args: argparse.Namespace) -> None:
    from app.diarization_final_evaluation.controller import worker_controlled

    value = worker_controlled(args.pipeline)
    print(json.dumps(value, indent=2, sort_keys=True))
    if value["failed"]:
        raise SystemExit(2)


def _worker_native(args: argparse.Namespace) -> None:
    from app.diarization_final_evaluation.controller import worker_native

    value = worker_native(args.dataset, args.pipeline)
    print(json.dumps(value, indent=2, sort_keys=True))
    if value["failed"]:
        raise SystemExit(2)
