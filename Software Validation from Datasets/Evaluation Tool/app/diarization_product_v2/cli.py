"""CLI for the Product V2 development-only diarization study."""

from __future__ import annotations

import argparse
import json


def add_diarization_product_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "diarization-product-v2",
        help="Operate the development-only product-focused anonymous diarization study",
    )
    commands = parser.add_subparsers(dest="diarization_product_command", required=True)
    for name in ("audit", "prepare", "validate", "plan", "smoke", "status", "stop", "analyze", "collect"):
        command = commands.add_parser(name)
        command.set_defaults(func=_dispatch, product_action=name)
    run = commands.add_parser("run")
    run.add_argument("--parallel-pipelines", type=int, default=2)
    run.set_defaults(func=_dispatch, product_action="run")

    native = subparsers.add_parser(
        "diarization-native-campaign",
        help="Operate the environment-aware restart-safe native Stage 11 campaign",
    )
    native_commands = native.add_subparsers(dest="native_campaign_command", required=True)
    for name in ("audit", "plan", "validate", "smoke", "status", "stop", "analyze", "collect"):
        command = native_commands.add_parser(name)
        command.set_defaults(func=_native_dispatch, native_action=name)
    native_run = native_commands.add_parser("run")
    native_run.add_argument("--dataset", action="append", choices=("chime6", "voices"), required=True)
    native_run.add_argument("--backend", action="append", default=["sherpa_onnx_diarization"])
    native_run.add_argument("--max-units", type=int, default=None)
    native_run.set_defaults(func=_native_dispatch, native_action="run")


def _dispatch(args: argparse.Namespace) -> None:
    from app.diarization_product_v2 import controller
    from app.diarization_product_v2.protocol import prepare_product_protocol

    action = args.product_action
    if action == "prepare":
        result = prepare_product_protocol()
    elif action == "run":
        result = controller.run(parallel_pipelines=args.parallel_pipelines)
    else:
        result = getattr(controller, action)()
    print(json.dumps(result, indent=2, sort_keys=True))


def _native_dispatch(args: argparse.Namespace) -> None:
    from app.diarization_product_v2 import native_campaign

    if args.native_action == "run":
        result = native_campaign.run(dataset=args.dataset, backend=args.backend, max_units=args.max_units)
    else:
        result = getattr(native_campaign, args.native_action)()
    print(json.dumps(result, indent=2, sort_keys=True))
