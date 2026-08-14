"""Build deterministic, environment-isolated edge research scenario catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.artifact_contracts.atomic import file_sha256
from app.artifact_contracts.registry import ArtifactRegistry
from app.benchmark_contracts.canonical import canonical_sha256
from app.benchmark_contracts.manifest_io import read_manifest
from app.benchmark_contracts.rir_registry import RIRRegistry, load_condition_sets
from app.benchmark_contracts.scenario import (
    expand_scenarios,
    pipeline_identity_from_resolution,
    validate_scenario,
)
from app.campaign_executor.planner import load_scenario_catalog, plan_campaign
from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.resolver import resolve_pipeline
from app.speaker_protocol.manifests import MANIFEST_FILENAMES, read_protocol_rows
from app.utils.json_utils import read_json, write_json, write_jsonl


PLAN_SCHEMA_VERSION = "edge-research-plan.v1"
QUEUE_SCHEMA_VERSION = "edge-research-queue.v1"
TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_ROOT = TOOL_ROOT / "benchmarks" / "v1"
DEFAULT_OUTPUT_ROOT = TOOL_ROOT / "benchmarks" / "edge_research"
DEFAULT_PIPELINE_PATH = TOOL_ROOT / "configs" / "inference" / "live_mic_whisper_base.yaml"


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    family: str
    profile: str
    overrides: Mapping[str, str]
    streaming: bool = False


STREAMING_ASR: tuple[tuple[str, str, str], ...] = (
    ("moon_tiny", "moonshine_streaming_tiny", "moonshine-edge"),
    ("moon_small", "moonshine_streaming_small", "moonshine-edge"),
    ("moon_medium", "moonshine_streaming_medium", "moonshine-edge"),
    ("sherpa20", "sherpa_onnx_streaming_zipformer_20m_int8", "onnx"),
)

CORE_VAD: Mapping[str, Mapping[str, str]] = {
    "energy_observe": {"vad": "energy_vad"},
    "energy_chunks": {"vad": "energy_vad", "segmentation": "vad_chunks"},
    "silero_observe": {"vad": "silero_vad"},
    "silero_chunks": {"vad": "silero_vad", "segmentation": "vad_chunks"},
}


def build_edge_research_plan(
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, object]:
    """Write all new catalogs and a conservative single-machine queue."""

    benchmark_root = benchmark_root.resolve()
    output_root = output_root.resolve()
    summary = read_json(benchmark_root / "manifest_summary.json")
    if not isinstance(summary, Mapping):
        raise ValueError("benchmark manifest summary must be a mapping")
    catalog = ComponentCatalog.load()
    conditions = load_condition_sets(RIRRegistry.load())

    small_path = benchmark_root / "small_source_manifest.parquet"
    small_identity = _manifest_identity(summary, "small", small_path, output_root)
    small_controlled = [
        row for row in read_manifest(small_path) if row.get("panel") == "controlled_clean"
    ]
    if not small_controlled:
        raise ValueError("small benchmark has no controlled-clean rows")

    screen = (
        Candidate(
            "whisper_base__full_record_control",
            "vad_isolation",
            "edge-cpu",
            {"asr": "whisper_base"},
        ),
        Candidate(
            "whisper_base__fsmn_observe",
            "vad_isolation",
            "edge-cpu",
            {"asr": "whisper_base", "vad": "fsmn_vad"},
        ),
        Candidate(
            "whisper_base__fsmn_chunks",
            "vad_isolation",
            "edge-cpu",
            {
                "asr": "whisper_base",
                "vad": "fsmn_vad",
                "segmentation": "vad_chunks",
            },
        ),
    )
    streaming = tuple(
        Candidate(label, "streaming_asr", profile, {"asr": component}, True)
        for label, component, profile in STREAMING_ASR
    )
    combinations = _combination_candidates()

    resolved: dict[str, dict[str, object]] = {}
    for candidate in (*screen, *streaming, *combinations):
        resolved[candidate.candidate_id] = _resolve_candidate(candidate, catalog)

    catalog_rows: dict[str, list[dict[str, object]]] = {}
    catalog_metadata: list[dict[str, object]] = []
    _add_catalog_group(
        catalog_rows,
        catalog_metadata,
        output_root,
        "edge_screen_edge_cpu",
        screen,
        resolved,
        small_identity,
        small_controlled,
        conditions,
        enabled=True,
        campaign_id="campaign_edge_screen_v1",
    )
    for profile in ("moonshine-edge", "onnx"):
        selected = tuple(item for item in streaming if item.profile == profile)
        suffix = profile.replace("-", "_")
        campaign = (
            "campaign_edge_stream_moon_v1"
            if profile == "moonshine-edge"
            else "campaign_edge_stream_onnx_v1"
        )
        _add_catalog_group(
            catalog_rows,
            catalog_metadata,
            output_root,
            f"edge_stream_{suffix}",
            selected,
            resolved,
            small_identity,
            small_controlled,
            conditions,
            enabled=True,
            campaign_id=campaign,
        )
    for profile in ("moonshine-edge", "onnx"):
        selected = tuple(item for item in combinations if item.profile == profile)
        suffix = profile.replace("-", "_")
        campaign = (
            "campaign_edge_combo_moon_v1"
            if profile == "moonshine-edge"
            else "campaign_edge_combo_onnx_v1"
        )
        _add_catalog_group(
            catalog_rows,
            catalog_metadata,
            output_root,
            f"edge_combo_{suffix}",
            selected,
            resolved,
            small_identity,
            small_controlled,
            conditions,
            enabled=False,
            campaign_id=campaign,
        )

    _write_union_catalog(
        output_root / "scenarios_edge_stream_all.jsonl",
        [
            catalog_rows["edge_stream_moonshine_edge"],
            catalog_rows["edge_stream_onnx"],
        ],
    )
    _write_union_catalog(
        output_root / "scenarios_edge_combo_all.jsonl",
        [
            catalog_rows["edge_combo_moonshine_edge"],
            catalog_rows["edge_combo_onnx"],
        ],
    )

    large_path = benchmark_root / "large_source_manifest.parquet"
    large_identity = _manifest_identity(summary, "large", large_path, output_root)
    large_rows = read_manifest(large_path)
    large_candidates = (
        *streaming,
        Candidate(
            "sherpa_original",
            "large_asr_isolation",
            "onnx",
            {"asr": "sherpa_onnx"},
        ),
        Candidate(
            "whisper_small",
            "large_asr_isolation",
            "core-cpu",
            {"asr": "whisper_small"},
        ),
        Candidate(
            "whisper_base_control", "large_reference", "core-cpu", {"asr": "whisper_base"}
        ),
    )
    for candidate in large_candidates:
        if candidate.candidate_id not in resolved:
            resolved[candidate.candidate_id] = _resolve_candidate(candidate, catalog)
        campaign_id = _large_campaign_id(candidate.candidate_id)
        _add_catalog_group(
            catalog_rows,
            catalog_metadata,
            output_root,
            f"edge_large_{candidate.candidate_id}",
            (candidate,),
            resolved,
            large_identity,
            large_rows,
            conditions,
            enabled=False,
            campaign_id=campaign_id,
        )

    stage10 = _stage10_plans()
    jobs = [_queue_job(row) for row in catalog_metadata]
    jobs.extend(stage10)
    queue: dict[str, object] = {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "single_machine_first": True,
        "sequential_execution_only": True,
        "default_worker_id": "amir",
        "global_preflight_required": True,
        "implicit_model_downloads_allowed": False,
        "jobs": jobs,
    }
    queue["queue_hash"] = canonical_sha256(queue)
    write_json(output_root / "edge_research_queue.json", queue)

    plan: dict[str, object] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "seed": 3800,
        "artifact_registry_version": "artifact-registry.v3",
        "selected_pipeline": {
            "path": DEFAULT_PIPELINE_PATH.relative_to(TOOL_ROOT).as_posix(),
            "sha256": file_sha256(DEFAULT_PIPELINE_PATH),
        },
        "benchmark_manifests": {
            "small": small_identity,
            "large": large_identity,
        },
        "catalogs": catalog_metadata,
        "stage10_plans": stage10,
        "queue": {
            "path": "edge_research_queue.json",
            "sha256": file_sha256(output_root / "edge_research_queue.json"),
            "enabled_job_count": sum(
                1 for row in jobs if bool(row.get("enabled_by_default"))
            ),
        },
        "methodology": {
            "component_isolation_first": True,
            "native_streaming_state_required": True,
            "one_environment_per_campaign": True,
            "full_cartesian_product": False,
            "broad_bounded_combinations_available": True,
            "large_campaigns_opt_in": True,
            "hardware_is_a_covariate": True,
            "raspberry_pi_performance_claimed": False,
        },
        "deferred_followup_catalogs": [
            "ASR robustness finalists",
            "VAD and segmentation parameter sweeps",
            "short-duration speaker studies",
            "CPU and thread-count studies",
            "real Raspberry Pi replication",
            "target-domain audio benchmarks",
            "Stage 11 diarization studies",
        ],
    }
    plan["plan_hash"] = canonical_sha256(plan)
    plan["plan_id"] = f"edge_research_{str(plan['plan_hash'])[:12].lower()}"
    write_json(output_root / "edge_research_plan.json", plan)
    (output_root / "edge_research_plan.sha256").write_text(
        f"{file_sha256(output_root / 'edge_research_plan.json')}  edge_research_plan.json\n",
        encoding="ascii",
        newline="\n",
    )
    return plan


def verify_edge_research_plan(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    automated_runs_root: Path | None = None,
) -> dict[str, object]:
    """Validate every catalog and dry-plan every ASR job without inference."""

    output_root = output_root.resolve()
    queue = read_json(output_root / "edge_research_queue.json")
    if not isinstance(queue, Mapping) or queue.get("schema_version") != QUEUE_SCHEMA_VERSION:
        raise ValueError("edge research queue is missing or incompatible")
    observed_hash = canonical_sha256(
        {key: value for key, value in queue.items() if key != "queue_hash"}
    )
    if queue.get("queue_hash") != observed_hash:
        raise ValueError("edge research queue hash mismatch")
    registry = ArtifactRegistry.load_version("artifact-registry.v3")
    runs_root = (automated_runs_root or TOOL_ROOT / "automated_runs").resolve()
    catalog_results = []
    manifest_paths: set[Path] = set()
    for raw in queue.get("jobs", []):
        if not isinstance(raw, Mapping) or raw.get("kind") != "asr_campaign":
            continue
        path = TOOL_ROOT / str(raw["catalog"])
        rows = load_scenario_catalog(path)
        expected = int(raw["expected_scenario_count"])
        if len(rows) != expected:
            raise ValueError(f"catalog count mismatch for {raw['campaign_id']}")
        for scenario in rows:
            validate_scenario(scenario)
            manifest_paths.add(
                (path.parent / str(scenario["benchmark_manifest"]["path"])).resolve()
            )
            required = registry.required_artifact_ids(scenario)
            if bool(raw.get("streaming")) and "streaming_diagnostics" not in required:
                raise ValueError("streaming catalog omitted its diagnostics capability")
        dry = plan_campaign(
            scenario_catalog=path,
            automated_runs_root=runs_root,
            campaign_id=str(raw["campaign_id"]),
            dry_run=True,
            registry=registry,
        )
        if len(dry.scenario_ids) != expected:
            raise ValueError(f"dry-plan count mismatch for {raw['campaign_id']}")
        catalog_results.append(
            {
                "campaign_id": raw["campaign_id"],
                "environment_profile": raw["environment_profile"],
                "scenario_count": expected,
                "enabled_by_default": bool(raw.get("enabled_by_default")),
            }
        )
    source_items = 0
    missing_sources: list[str] = []
    for manifest_path in sorted(manifest_paths):
        for row in read_manifest(manifest_path):
            source_items += 1
            relative = str(row["audio_path_project_relative"])
            if not (TOOL_ROOT.parent / relative).is_file():
                missing_sources.append(relative)
    if missing_sources:
        raise FileNotFoundError(
            f"edge research source preflight found {len(missing_sources)} missing files; "
            f"first={missing_sources[0]}"
        )
    required_components = {
        ("asr", "moonshine_streaming_tiny"),
        ("asr", "moonshine_streaming_small"),
        ("asr", "moonshine_streaming_medium"),
        ("asr", "sherpa_onnx"),
        ("asr", "sherpa_onnx_streaming_zipformer_20m_int8"),
        ("asr", "whisper_small"),
        ("vad", "fsmn_vad"),
        ("speaker_embedding", "campplus_speaker_embedding"),
        ("speaker_embedding", "eres2net_base_speaker_embedding"),
    }
    component_catalog = ComponentCatalog.load()
    for family, name in sorted(required_components):
        entry = component_catalog.get(family, name)
        if entry.qualification_status not in {"qualified", "qualified_with_warnings"}:
            raise ValueError(f"required edge component is not qualified: {family}.{name}")
        if any(asset.get("present") is False for asset in entry.model_asset_identity):
            raise FileNotFoundError(f"required edge model asset is missing: {family}.{name}")
    return {
        "schema_version": "edge-research-verification.v1",
        "status": "ready",
        "queue_hash": observed_hash,
        "catalog_count": len(catalog_results),
        "scenario_count": sum(int(row["scenario_count"]) for row in catalog_results),
        "source_item_rows_checked": source_items,
        "missing_source_item_rows": 0,
        "qualified_component_count": len(required_components),
        "catalogs": catalog_results,
        "large_inference_started": False,
    }


def _combination_candidates() -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    for label, component, profile in STREAMING_ASR:
        strategies = dict(CORE_VAD)
        if profile == "moonshine-edge":
            strategies.update(
                {
                    "webrtc_observe": {"vad": "webrtc_vad"},
                    "webrtc_chunks": {
                        "vad": "webrtc_vad",
                        "segmentation": "vad_chunks",
                    },
                }
            )
        else:
            strategies.update(
                {
                    "sherpa_vad_observe": {"vad": "sherpa_onnx_vad"},
                    "sherpa_vad_chunks": {
                        "vad": "sherpa_onnx_vad",
                        "segmentation": "vad_chunks",
                    },
                }
            )
        for strategy, overrides in strategies.items():
            candidates.append(
                Candidate(
                    f"{label}__{strategy}",
                    "targeted_asr_vad",
                    profile,
                    {"asr": component, **overrides},
                    True,
                )
            )
    return tuple(candidates)


def _resolve_candidate(
    candidate: Candidate, catalog: ComponentCatalog
) -> dict[str, object]:
    resolution = resolve_pipeline(
        DEFAULT_PIPELINE_PATH,
        component_overrides=candidate.overrides,
        environment_profile=candidate.profile,
        catalog=catalog,
    )
    identity = pipeline_identity_from_resolution(resolution)
    return {
        "candidate_id": candidate.candidate_id,
        "family": candidate.family,
        "environment_profile": candidate.profile,
        "component_overrides": dict(candidate.overrides),
        "streaming": candidate.streaming,
        "pipeline_identity": identity,
        "qualification_evidence": {
            family: {
                "component": name,
                "status": catalog.get(family, name).qualification_status,
                "evidence": catalog.get(family, name).qualification_evidence,
            }
            for family, name in candidate.overrides.items()
        },
    }


def _add_catalog_group(
    catalog_rows: dict[str, list[dict[str, object]]],
    metadata: list[dict[str, object]],
    output_root: Path,
    name: str,
    candidates: Sequence[Candidate],
    resolved: Mapping[str, Mapping[str, object]],
    manifest_identity: Mapping[str, object],
    manifest_rows: Sequence[Mapping[str, object]],
    conditions: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    enabled: bool,
    campaign_id: str,
) -> None:
    rows_by_id: dict[str, dict[str, object]] = {}
    candidate_ids: dict[str, list[str]] = {}
    for candidate in candidates:
        expanded = expand_scenarios(
            manifest_identity=manifest_identity,
            manifest_rows=manifest_rows,
            pipeline_identities=[resolved[candidate.candidate_id]["pipeline_identity"]],
            condition_sets=conditions,
        )
        ids = []
        for scenario in expanded:
            scenario["artifact_contract"] = {
                "scenario_type": "asr",
                "capabilities": [
                    *(["streaming_diagnostics"] if candidate.streaming else []),
                    "telemetry",
                ],
            }
            scenario["research"] = {
                "schema_version": "edge-research-scenario-provenance.v1",
                "candidate_id": candidate.candidate_id,
                "candidate_family": candidate.family,
                "environment_profile": candidate.profile,
            }
            validate_scenario(scenario)
            scenario_id = str(scenario["scenario_id"])
            rows_by_id[scenario_id] = scenario
            ids.append(scenario_id)
        candidate_ids[candidate.candidate_id] = sorted(ids)
    rows = [rows_by_id[key] for key in sorted(rows_by_id)]
    path = output_root / f"scenarios_{name}.jsonl"
    write_jsonl(path, rows)
    catalog_rows[name] = rows
    metadata.append(
        {
            "catalog_id": name,
            "path": path.relative_to(TOOL_ROOT).as_posix(),
            "sha256": file_sha256(path),
            "campaign_id": campaign_id,
            "environment_profile": candidates[0].profile,
            "streaming": any(item.streaming for item in candidates),
            "enabled_by_default": enabled,
            "scenario_count": len(rows),
            "candidate_count": len(candidates),
            "candidate_ids": candidate_ids,
        }
    )


def _write_union_catalog(path: Path, groups: Sequence[Sequence[dict[str, object]]]) -> None:
    rows: dict[str, dict[str, object]] = {}
    for group in groups:
        for row in group:
            rows[str(row["scenario_id"])] = row
    write_jsonl(path, [rows[key] for key in sorted(rows)])


def _manifest_identity(
    summary: Mapping[str, object], tier: str, path: Path, output_root: Path
) -> dict[str, object]:
    identities = summary.get("manifest_identities")
    if not isinstance(identities, Mapping) or not isinstance(identities.get(tier), Mapping):
        raise ValueError(f"manifest summary has no {tier} identity")
    identity = dict(identities[tier])
    if file_sha256(path) != identity.get("sha256"):
        raise ValueError(f"{tier} manifest hash mismatch")
    identity["path"] = Path(
        *("..", "v1", path.name)
    ).as_posix()
    return identity


def _large_campaign_id(candidate_id: str) -> str:
    values = {
        "moon_tiny": "campaign_edge_lg_mtiny_v1",
        "moon_small": "campaign_edge_lg_msmall_v1",
        "moon_medium": "campaign_edge_lg_mmed_v1",
        "sherpa20": "campaign_edge_lg_sh20_v1",
        "sherpa_original": "campaign_edge_lg_shorig_v1",
        "whisper_small": "campaign_edge_lg_wsmall_v1",
        "whisper_base_control": "campaign_edge_lg_wbase_v1",
    }
    return values[candidate_id]


def _queue_job(row: Mapping[str, object]) -> dict[str, object]:
    return {
        "job_id": str(row["catalog_id"]),
        "kind": "asr_campaign",
        "campaign_id": row["campaign_id"],
        "catalog": row["path"],
        "catalog_sha256": row["sha256"],
        "environment_profile": row["environment_profile"],
        "expected_scenario_count": row["scenario_count"],
        "enabled_by_default": row["enabled_by_default"],
        "streaming": row["streaming"],
        "one_gpu_job_at_a_time": True,
    }


def _stage10_plans() -> list[dict[str, object]]:
    result = []
    for tier, campaign_id in (
        ("small", "campaign_spk10_edge_sm_v1"),
        ("standard", "campaign_spk10_edge_std_v1"),
        ("large", "campaign_spk10_edge_lg_v1"),
    ):
        root = TOOL_ROOT / "benchmarks" / "stage10" / tier
        counts = {}
        clean_ids: set[str] = set()
        for kind in ("enrollment", "calibration", "known_evaluation", "unknown_evaluation"):
            rows = read_protocol_rows(root / MANIFEST_FILENAMES[kind], expected_kind=kind)
            counts[kind] = len(rows)
            clean_ids.update(
                str(row["item_id"])
                for row in rows
                if row.get("protocol_condition") == "clean"
            )
        result.append(
            {
                "job_id": f"speaker_protocol_{tier}",
                "kind": "speaker_protocol_plan",
                "campaign_id": campaign_id,
                "tier": tier,
                "manifest_root": root.relative_to(TOOL_ROOT).as_posix(),
                "environment_profile": "onnx",
                "backend_ids": [
                    "campplus_speaker_embedding",
                    "eres2net_base_speaker_embedding",
                ],
                "source_rows_by_role": counts,
                "clean_extraction_items_per_backend": len(clean_ids),
                "expected_backend_runs": 2,
                "enabled_by_default": False,
                "execution_status": "planned",
                "degraded_probe_requirement": (
                    "Use the approved campaign augmentation path; direct Stage 10 extraction "
                    "continues to reject degraded rows by contract."
                ),
            }
        )
    return result
