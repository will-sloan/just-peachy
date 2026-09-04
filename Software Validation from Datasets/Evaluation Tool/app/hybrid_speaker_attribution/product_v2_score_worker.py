"""Short-lived score-bundle worker used to avoid long Windows process stalls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.hybrid_speaker_attribution.product_v2_contracts import (
    COMBINATIONS, V1_BENCHMARK_ROOT, V2_BENCHMARK_ROOT, read_json, read_jsonl,
)
from app.hybrid_speaker_attribution.product_v2_runner import _score_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = read_json(args.manifest)
    combinations = {str(row["combination_id"]): row for row in COMBINATIONS}
    cases = {}
    for corpus, root in (("v1", V1_BENCHMARK_ROOT), ("v2", V2_BENCHMARK_ROOT)):
        for case in read_jsonl(root / "development" / "case_manifest.jsonl"):
            cases[(corpus, str(case["case_id"]))] = case
    completed = 0
    for unit in manifest["units"]:
        _score_case(
            combinations[str(unit["combination_id"])], str(unit["corpus"]),
            cases[(str(unit["corpus"]), str(unit["case_id"]))],
        )
        completed += 1
    print(json.dumps({"status": "COMPLETE", "units": completed}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
