"""CLI registration for the additive Hybrid Speaker Attribution Product V2 campaign."""

from __future__ import annotations

import json

from app.hybrid_speaker_attribution.product_v2_analysis import analyze, collect, freeze, validate_frozen
from app.hybrid_speaker_attribution.product_v2_protocol import audit, plan, prepare, validate
from app.hybrid_speaker_attribution.product_v2_runner import run_development, status, stop


def add_hybrid_product_v2_parser(subparsers) -> None:
    parser = subparsers.add_parser("hybrid-product-v2", help="Build and run the development-only product hybrid diarization + attribution study")
    actions = parser.add_subparsers(dest="hybrid_product_v2_action", required=True)
    for name, function in (("audit", audit), ("prepare", prepare), ("validate", validate), ("plan", plan), ("status", status), ("stop", stop), ("validate-frozen", validate_frozen)):
        child = actions.add_parser(name)
        child.set_defaults(func=lambda args, fn=function: _emit(fn()))
    smoke = actions.add_parser("smoke")
    smoke.add_argument("--parallel-backends", type=int, choices=(1, 2, 3), default=2)
    smoke.set_defaults(func=lambda args: _emit(run_development(parallel_backends=args.parallel_backends, max_cases=1)))
    run = actions.add_parser("run-development")
    run.add_argument("--parallel-backends", type=int, choices=(1, 2, 3), default=2)
    run.set_defaults(func=lambda args: _emit(run_development(parallel_backends=args.parallel_backends)))
    analysis = actions.add_parser("analyze")
    analysis.add_argument("--bootstrap-repetitions", type=int, choices=range(500, 1001), default=500)
    analysis.set_defaults(func=lambda args: _emit(analyze(bootstrap_repetitions=args.bootstrap_repetitions)))
    freeze_parser = actions.add_parser("freeze")
    freeze_parser.set_defaults(func=lambda args: _emit(freeze()))
    collect_parser = actions.add_parser("collect")
    collect_parser.set_defaults(func=lambda args: _emit(collect()))
    full = actions.add_parser("full")
    full.add_argument("--parallel-backends", type=int, choices=(1, 2, 3), default=2)
    full.add_argument("--bootstrap-repetitions", type=int, choices=range(500, 1001), default=500)
    full.set_defaults(func=_full)


def _full(args) -> None:
    prepare()
    run_development(parallel_backends=args.parallel_backends)
    analyze(bootstrap_repetitions=args.bootstrap_repetitions)
    freeze()
    _emit(collect())


def _emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))

