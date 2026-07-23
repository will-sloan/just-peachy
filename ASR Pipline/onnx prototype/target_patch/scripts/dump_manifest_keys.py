from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect keys in a JSONL manifest.")
    parser.add_argument("jsonl_path")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    path = Path(args.jsonl_path)
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if idx >= args.limit:
                break
            record = json.loads(line)
            print(f"ROW {idx}")
            for key in sorted(record.keys()):
                print(f"  {key}: {type(record[key]).__name__}")
            print()


if __name__ == "__main__":
    main()
