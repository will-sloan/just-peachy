"""Validate and consolidate existing Stage 8 profile qualification artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.extended_backends.reporting import (  # noqa: E402
    DEFAULT_RESULT_ROOT,
    consolidate_qualification_results,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-root", type=Path, default=DEFAULT_RESULT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    payload = consolidate_qualification_results(
        result_root=args.result_root,
        output_path=args.output,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
