"""Isolated-environment extraction entry point used by Stage 10."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.speaker_protocol.extraction import extract_clean_protocol_embeddings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract qualified speaker embeddings")
    parser.add_argument("--manifest-root", required=True, type=Path)
    parser.add_argument("--component", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--item-id", action="append", default=[])
    args = parser.parse_args(argv)
    result = extract_clean_protocol_embeddings(
        args.manifest_root,
        args.component,
        args.output_root,
        item_ids=set(args.item_id) or None,
    )
    print(
        json.dumps(
            {
                "backend_id": args.component,
                "expected_items": result["expected_items"],
                "successful_items": result["successful_items"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
