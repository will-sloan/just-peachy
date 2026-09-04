"""Bounded subprocess worker for held-out score bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.hybrid_final_evaluation.runner import score_unit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    value = json.loads(args.manifest.read_text(encoding="utf-8"))
    for row in value["units"]:
        score_unit(str(row["combination_id"]), str(row["corpus"]), str(row["case_id"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
