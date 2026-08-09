"""Stage 8 extended-backend setup and independent qualification."""

from app.extended_backends.contracts import QUALIFICATION_STATUSES
from app.extended_backends.registry import (
    inspect_asset,
    load_backend_catalog,
    load_environment_profiles,
    load_model_asset_registry,
)
from app.extended_backends.reporting import consolidate_qualification_results

__all__ = [
    "QUALIFICATION_STATUSES",
    "consolidate_qualification_results",
    "inspect_asset",
    "load_backend_catalog",
    "load_environment_profiles",
    "load_model_asset_registry",
]
