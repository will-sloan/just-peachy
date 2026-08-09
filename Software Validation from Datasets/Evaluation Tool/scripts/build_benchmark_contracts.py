"""Build Stage 2 manifests and canonical scenario definitions without inference."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.benchmark_contracts.manifest import BenchmarkManifestBuilder  # noqa: E402
from app.benchmark_contracts.manifest_io import read_manifest  # noqa: E402
from app.benchmark_contracts.rir_registry import (  # noqa: E402
    RIRRegistry,
    load_condition_sets,
)
from app.benchmark_contracts.scenario import (  # noqa: E402
    expand_scenarios,
    pipeline_identity_from_resolution,
)
from app.inference_pipeline.resolver import resolve_pipeline  # noqa: E402
from app.utils.json_utils import write_json, write_jsonl  # noqa: E402
from app.utils.paths import find_project_root  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build immutable benchmark Parquet manifests, RIR audit, and canonical "
            "scenario definitions. This command never runs inference."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Software Validation from Datasets root; auto-detected by default.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=TOOL_ROOT / "benchmarks" / "v1",
        help="Output directory for canonical Stage 2 artifacts.",
    )
    parser.add_argument(
        "--pipeline-config",
        type=Path,
        action="append",
        default=None,
        help="Existing inference YAML to identify in scenarios; repeatable.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Canonical scenario repetitions. Defaults to 1.",
    )
    parser.add_argument(
        "--skip-scenarios",
        action="store_true",
        help="Build manifests and RIR audit without scenario expansion.",
    )
    args = parser.parse_args()

    project_root = find_project_root(args.project_root)
    output = args.output.resolve()
    registry = RIRRegistry.load()
    result = BenchmarkManifestBuilder(
        project_root,
        rir_registry=registry,
    ).build_all(output)

    scenario_count = 0
    if not args.skip_scenarios:
        config_paths = args.pipeline_config or [
            TOOL_ROOT / "configs" / "inference" / "live_mic_whisper_base.yaml"
        ]
        pipelines = [
            pipeline_identity_from_resolution(resolve_pipeline(path))
            for path in config_paths
        ]
        condition_sets = load_condition_sets(registry)
        scenarios: list[dict[str, object]] = []
        for key in ("small", "standard", "large"):
            identity = result.manifest_identities[key]
            rows = read_manifest(result.manifest_paths[key])
            scenarios.extend(
                expand_scenarios(
                    manifest_identity=identity,
                    manifest_rows=rows,
                    pipeline_identities=pipelines,
                    condition_sets=condition_sets,
                    repetitions=args.repetitions,
                )
            )
        speaker_rows = read_manifest(result.manifest_paths["speaker_protocol"])
        scenarios.extend(
            expand_scenarios(
                manifest_identity=result.manifest_identities["speaker_protocol"],
                manifest_rows=speaker_rows,
                pipeline_identities=pipelines,
                condition_sets=condition_sets,
                repetitions=args.repetitions,
            )
        )
        scenarios.sort(key=lambda item: str(item["scenario_id"]))
        if len({str(item["scenario_id"]) for item in scenarios}) != len(scenarios):
            raise RuntimeError("scenario ID collision across manifest files")
        write_jsonl(output / "resolved_scenarios.jsonl", scenarios)
        counts = Counter(
            (str(item["tier"]), str(item["panel"])) for item in scenarios
        )
        write_json(
            output / "scenario_catalog_summary.json",
            {
                "schema_version": "scenario-catalog-summary.v1",
                "scenario_schema_version": "scenario-definition.v1",
                "scenario_count": len(scenarios),
                "counts": {
                    f"{tier}/{panel}": count
                    for (tier, panel), count in sorted(counts.items())
                },
                "pipeline_ids": sorted(
                    str(pipeline["pipeline_id"]) for pipeline in pipelines
                ),
            },
        )
        scenario_count = len(scenarios)

    print(f"Built Stage 2 contracts at {output}")
    for key, identity in result.manifest_identities.items():
        print(
            f"  {key}: {identity['rows']} rows, {identity['manifest_id']}, "
            f"sha256={identity['sha256']}"
        )
    if not args.skip_scenarios:
        print(f"  scenarios: {scenario_count}")
    print("No inference was run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
