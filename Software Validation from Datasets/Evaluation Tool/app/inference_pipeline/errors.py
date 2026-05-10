"""Small exception hierarchy for inference pipeline contracts."""

from __future__ import annotations


class InferencePipelineError(Exception):
    """Base error for inference pipeline setup and contract failures."""


class ContractValidationError(InferencePipelineError, ValueError):
    """Raised when a contract object receives invalid values."""


class MissingRequiredFieldError(ContractValidationError):
    """Raised when an Evaluation Tool record is missing a required field."""


class IdentityMismatchError(ContractValidationError):
    """Raised when an output no longer matches its source record identity."""

