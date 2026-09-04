"""Backend-neutral true-streaming full-pipeline runtime.

The public constructors are loaded lazily so read-only commands such as
``matrix-status`` and ``status`` never import numerical or model-adapter code.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CoordinatorConfig",
    "StreamingPipelineCoordinator",
    "build_file_runtime",
    "build_microphone_runtime",
    "H2ProductMode",
    "H2RuntimeTuning",
]


def __getattr__(name: str) -> Any:
    if name in {"CoordinatorConfig", "StreamingPipelineCoordinator"}:
        from .coordinator import CoordinatorConfig, StreamingPipelineCoordinator

        return {
            "CoordinatorConfig": CoordinatorConfig,
            "StreamingPipelineCoordinator": StreamingPipelineCoordinator,
        }[name]
    if name in {"build_file_runtime", "build_microphone_runtime"}:
        from .factory import build_file_runtime, build_microphone_runtime

        return {
            "build_file_runtime": build_file_runtime,
            "build_microphone_runtime": build_microphone_runtime,
        }[name]
    if name in {"H2ProductMode", "H2RuntimeTuning"}:
        from .product_modes import H2ProductMode, H2RuntimeTuning

        return {
            "H2ProductMode": H2ProductMode,
            "H2RuntimeTuning": H2RuntimeTuning,
        }[name]
    raise AttributeError(name)
