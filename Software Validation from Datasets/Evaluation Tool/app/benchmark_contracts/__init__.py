"""Immutable benchmark-manifest and scenario identity contracts."""

from app.benchmark_contracts.canonical import (
    canonical_json_bytes,
    canonical_sha256,
    normalize_project_relative_path,
    stable_rank,
)
from app.benchmark_contracts.manifest import BenchmarkManifestBuilder
from app.benchmark_contracts.rir_registry import RIRRegistry
from app.benchmark_contracts.scenario import expand_scenarios, scenario_identity
from app.benchmark_contracts.versions import (
    CANONICALIZATION_VERSION,
    HASH_ALGORITHM,
    HASH_VERSION,
    MANIFEST_CANONICALIZATION_VERSION,
    MANIFEST_HASH_VERSION,
    MANIFEST_SCHEMA_VERSION,
    SCENARIO_SCHEMA_VERSION,
    SELECTION_SEED,
)

__all__ = [
    "BenchmarkManifestBuilder",
    "CANONICALIZATION_VERSION",
    "HASH_ALGORITHM",
    "HASH_VERSION",
    "MANIFEST_CANONICALIZATION_VERSION",
    "MANIFEST_HASH_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "RIRRegistry",
    "SCENARIO_SCHEMA_VERSION",
    "SELECTION_SEED",
    "canonical_json_bytes",
    "canonical_sha256",
    "expand_scenarios",
    "normalize_project_relative_path",
    "scenario_identity",
    "stable_rank",
]
