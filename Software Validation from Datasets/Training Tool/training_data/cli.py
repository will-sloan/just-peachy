"""Local Phase-2 registry commands; they never train, download, or alter evaluation."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

SOURCE_ROOT=Path(__file__).resolve().parents[1]
POLICY_ROOT=Path(__file__).resolve().parent
TOOL_ROOT=SOURCE_ROOT.parent/"Evaluation Tool"
sys.path.insert(0,str(TOOL_ROOT))
from app.utils.paths import data_root, training_root  # noqa: E402
from training_data.registry import build_freeze, verify_freeze_details  # noqa: E402


def _registry_path(root: Path) -> Path:
    return root / "registries" / "training_data_registry.parquet"


def _summary_path(root: Path) -> Path:
    return root / "registries" / "training_data_registry_summary.json"

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="create the ignored local metadata freeze")
    verify = sub.add_parser("verify-freeze", help="check freeze self-hash and benchmark identities")
    verify.add_argument("--path", type=Path, default=None)
    sub.add_parser("summary", help="print the generated registry summary")
    explain = sub.add_parser("explain", help="show one or more source items")
    explain.add_argument("source_item_id")
    preview = sub.add_parser("preview-pool", help="show a future-pool preview without building a manifest")
    preview.add_argument("name", choices=("robust_core", "robust_plus_chime", "read_speech_support"))
    args = parser.parse_args()
    root = training_root().path
    if args.command == "build":
        print(json.dumps(build_freeze(POLICY_ROOT, TOOL_ROOT, data_root().path, root), indent=2, sort_keys=True))
    elif args.command == "verify-freeze":
        result = verify_freeze_details(args.path or root / "registries" / "training_data_freeze_manifest.json", TOOL_ROOT)
        print(json.dumps(result, indent=2, sort_keys=True))
        if not result["valid"]:
            return 1
    elif args.command == "summary":
        print(_summary_path(root).read_text(encoding="utf-8"))
    elif args.command == "preview-pool":
        summary = json.loads(_summary_path(root).read_text(encoding="utf-8"))
        print(json.dumps(summary["future_pool_previews"][args.name], indent=2, sort_keys=True))
    else:
        frame = pd.read_parquet(_registry_path(root))
        matches = frame.loc[frame["source_item_id"].eq(args.source_item_id)]
        print(matches.to_json(orient="records", indent=2, date_format="iso"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
