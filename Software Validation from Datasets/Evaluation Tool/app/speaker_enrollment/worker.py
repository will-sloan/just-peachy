"""Isolated-environment embedding extraction entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.speaker_enrollment.extraction import extract_slice_cache


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract immutable enrollment-study slices")
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--component", required=True)
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--slice-list", required=True, type=Path)
    args = parser.parse_args(argv)
    slice_ids = {
        value.strip()
        for value in args.slice_list.read_text(encoding="utf-8").splitlines()
        if value.strip()
    }
    print(
        json.dumps(
            extract_slice_cache(args.protocol_root, args.component, args.cache_root, slice_ids),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
