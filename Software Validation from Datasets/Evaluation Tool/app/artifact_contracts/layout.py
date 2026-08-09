"""Windows-safe campaign and scenario directory layout contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from app.artifact_contracts.registry import ArtifactRegistryError


CAMPAIGN_ID_PATTERN = re.compile(r"^campaign_[a-z0-9][a-z0-9_-]{2,31}$")
SCENARIO_ID_PATTERN = re.compile(r"^scenario_[0-9a-f]{12}$")
CAMPAIGN_SUBDIRECTORIES = (
    "benchmark_manifests",
    "worker_assignments",
    "database",
    "scenarios",
    "audit",
    "audit/environment_fingerprints",
    "analysis",
)
SCENARIO_SUBDIRECTORIES = (
    "predictions",
    "predictions/embeddings",
    "metrics",
    "resource_logs",
    "logs",
    "report",
)


@dataclass(frozen=True)
class CampaignLayout:
    """Resolved paths for one short-ID campaign."""

    automated_runs_root: Path
    campaign_id: str
    campaign_root: Path

    @classmethod
    def resolve(cls, automated_runs_root: Path, campaign_id: str) -> "CampaignLayout":
        validate_campaign_id(campaign_id)
        root = automated_runs_root.resolve()
        campaign_root = (root / campaign_id).resolve()
        _require_descendant(campaign_root, root)
        return cls(root, campaign_id, campaign_root)

    def scenario_root(self, scenario_id: str) -> Path:
        validate_scenario_id(scenario_id)
        root = (self.campaign_root / "scenarios" / scenario_id).resolve()
        _require_descendant(root, self.campaign_root)
        return root

    def create(self, scenario_ids: Iterable[str] = ()) -> None:
        """Create directories only; no campaign or scenario is executed."""

        self.campaign_root.mkdir(parents=True, exist_ok=True)
        for relative in CAMPAIGN_SUBDIRECTORIES:
            (self.campaign_root / relative).mkdir(parents=True, exist_ok=True)
        for scenario_id in scenario_ids:
            scenario_root = self.scenario_root(scenario_id)
            scenario_root.mkdir(parents=True, exist_ok=True)
            for relative in SCENARIO_SUBDIRECTORIES:
                (scenario_root / relative).mkdir(parents=True, exist_ok=True)


def validate_campaign_id(campaign_id: str) -> None:
    if not CAMPAIGN_ID_PATTERN.fullmatch(str(campaign_id)):
        raise ArtifactRegistryError(
            "campaign ID must match campaign_[a-z0-9][a-z0-9_-]{2,31}"
        )


def validate_scenario_id(scenario_id: str) -> None:
    if not SCENARIO_ID_PATTERN.fullmatch(str(scenario_id)):
        raise ArtifactRegistryError("scenario ID must match scenario_<12 lowercase hex>")


def _require_descendant(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ArtifactRegistryError(f"artifact path escapes root: {path}") from exc
