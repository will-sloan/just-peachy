"""Stable campaign/scenario artifact contracts and completion validation."""

from app.artifact_contracts.atomic import (
    ScenarioArtifactStore,
    publish_campaign_manifest,
    validate_campaign_manifest_pair,
)
from app.artifact_contracts.completion import (
    CompletionReport,
    validate_scenario_completion,
)
from app.artifact_contracts.environment import (
    collect_environment_fingerprint,
    identity_hashes_from_resolved_scenario,
)
from app.artifact_contracts.layout import CampaignLayout
from app.artifact_contracts.registry import ArtifactRegistry

__all__ = [
    "ArtifactRegistry",
    "CampaignLayout",
    "CompletionReport",
    "ScenarioArtifactStore",
    "collect_environment_fingerprint",
    "identity_hashes_from_resolved_scenario",
    "publish_campaign_manifest",
    "validate_campaign_manifest_pair",
    "validate_scenario_completion",
]
