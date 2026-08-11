"""Validate a frozen campaign's post-checkout production release binding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.campaign_exchange.common import atomic_write_json  # noqa: E402
from app.launch_readiness import (  # noqa: E402
    ReleaseBindingError,
    validate_release_binding,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--environment-profile", required=True)
    parser.add_argument("--worker-id", choices=("machine_a", "machine_b"), required=True)
    parser.add_argument("--launch-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = validate_release_binding(
            args.campaign_root,
            repository_root=args.repository_root,
            expected_environment_profile=args.environment_profile,
            worker_id=args.worker_id,
            launch_package_path=args.launch_package,
        )
        atomic_write_json(args.output.resolve(), report)
    except (ReleaseBindingError, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"release binding: FAIL: {exc}", file=sys.stderr)
        return 2
    print("release binding: PASS")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
