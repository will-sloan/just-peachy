"""Run or validate the real one-item Stage 9 extended-backend smoke matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.extended_screening.smoke import (  # noqa: E402
    DEFAULT_AUDIO,
    DEFAULT_OUTPUT_ROOT,
    build_real_smoke_matrix,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--audio", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--rerun", action="store_true")
    args = parser.parse_args(argv)
    payload = build_real_smoke_matrix(
        output_root=args.output_root,
        audio_path=args.audio,
        rerun=args.rerun,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0 if payload["summary"]["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
