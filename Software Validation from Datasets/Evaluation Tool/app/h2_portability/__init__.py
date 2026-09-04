"""Fail-closed deployment-enablement helpers for the H2 pipeline family.

This package is deliberately separate from the frozen H2 scientific policy.
Nothing here changes segmentation, clustering, enrollment, identity thresholds,
or transcript decisions.
"""

from .contracts import (
    H2_PORTABILITY_CODE_IDENTITY,
    H2_PORTABILITY_PROTOCOL,
    ONNX_TOOLING_SCHEMA,
    SPATIAL_EVIDENCE_INTERFACE_VERSION,
)

__all__ = [
    "H2_PORTABILITY_CODE_IDENTITY",
    "H2_PORTABILITY_PROTOCOL",
    "ONNX_TOOLING_SCHEMA",
    "SPATIAL_EVIDENCE_INTERFACE_VERSION",
]
