"""Write the secret-free, observed Stage 8 model-asset inventory."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.extended_backends.registry import inspect_all_assets  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=TOOL_ROOT / "runs" / "extended_backend_qualification" / "model_asset_inventory.json",
    )
    args = parser.parse_args(argv)
    payload = {
        "schema_version": "observed-model-asset-registry.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "secret_values_serialized": False,
        "assets": inspect_all_assets(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
