"""Local H2 product application over the shared full-pipeline runtime."""

from .h2_ux import (
    H2_DEFAULT_PRODUCT_MODE,
    H2_PIPELINE_IDS,
    H2_PRODUCT_MODE_IDS,
)
from .runtime_config import (
    DemoRuntimeConfigError,
    H2DemoRuntimeBinding,
    load_h2_demo_runtime_binding,
)
from .state import DemoViewState, apply_event, apply_status

__all__ = [
    "DemoViewState",
    "DemoRuntimeConfigError",
    "H2_DEFAULT_PRODUCT_MODE",
    "H2_PIPELINE_IDS",
    "H2_PRODUCT_MODE_IDS",
    "H2DemoRuntimeBinding",
    "apply_event",
    "apply_status",
    "load_h2_demo_runtime_binding",
]
