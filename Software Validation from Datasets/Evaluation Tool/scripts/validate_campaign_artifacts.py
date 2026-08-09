"""Validate Stage 3 campaign/scenario artifacts without executing a campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.artifact_contracts.atomic import validate_campaign_manifest_pair  # noqa: E402
from app.artifact_contracts.completion import validate_scenario_completion  # noqa: E402
from app.artifact_contracts.registry import ArtifactRegistry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Stage 3 contracts. This command never runs inference."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--scenario-dir", type=Path)
    selection.add_argument("--campaign-dir", type=Path)
    selection.add_argument("--registry-only", action="store_true")
    args = parser.parse_args()

    registry = ArtifactRegistry.load()
    if args.registry_only:
        print(
            json.dumps(
                {
                    "schema_version": registry.schema_version,
                    "artifact_count": len(registry.artifacts),
                    "scenario_profiles": sorted(registry.scenario_profiles),
                },
                indent=2,
            )
        )
        return 0
    if args.campaign_dir is not None:
        validate_campaign_manifest_pair(args.campaign_dir.resolve(), registry=registry)
        print(json.dumps({"state": "complete", "scope": "campaign"}, indent=2))
        return 0
    report = validate_scenario_completion(args.scenario_dir.resolve(), registry=registry)
    print(json.dumps(report.to_jsonable(), indent=2))
    return 0 if report.complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
