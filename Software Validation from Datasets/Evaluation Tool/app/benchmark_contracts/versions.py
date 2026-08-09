"""Frozen Stage 2 public contract identifiers."""

MANIFEST_SCHEMA_VERSION = "benchmark-manifest.v1"
MANIFEST_CANONICALIZATION_VERSION = "manifest-canonicalization.v1"
MANIFEST_HASH_VERSION = "manifest-hash.v1"
SCENARIO_SCHEMA_VERSION = "scenario-definition.v1"
CANONICALIZATION_VERSION = "scenario-canonicalization.v1"
HASH_VERSION = "scenario-hash.v1"
HASH_ALGORITHM = "sha256"
SELECTION_SEED = 3800
SCORING_POLICY_VERSION = "scoring-policy.v1"

SUPPORTED_MANIFEST_SCHEMA_VERSIONS = frozenset({MANIFEST_SCHEMA_VERSION})
SUPPORTED_SCENARIO_SCHEMA_VERSIONS = frozenset({SCENARIO_SCHEMA_VERSION})
