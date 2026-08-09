"""Stage 6 deterministic assignments and independent result exchange."""

from .assignments import (
    create_worker_assignment,
    current_git_commit,
    validate_assignment_set,
    validate_worker_assignment,
)
from .common import CampaignExchangeError
from .execution import prepare_worker_campaign_copy, run_worker_assignment
from .merge import MergeRejectedError, merge_worker_results, validate_merged_results
from .transfers import export_worker_results, validate_worker_transfer

__all__ = [
    "CampaignExchangeError",
    "MergeRejectedError",
    "create_worker_assignment",
    "current_git_commit",
    "export_worker_results",
    "merge_worker_results",
    "prepare_worker_campaign_copy",
    "run_worker_assignment",
    "validate_assignment_set",
    "validate_merged_results",
    "validate_worker_assignment",
    "validate_worker_transfer",
]
