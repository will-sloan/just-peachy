"""Run the real, single-job core CUDA qualification gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.extended_backends.core_cuda import qualify_core_cuda  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    payload = qualify_core_cuda(args.audio, args.output)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0 if payload["summary"]["qualified"] == payload["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
