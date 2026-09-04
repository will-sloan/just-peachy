"""Reproducible Prompt-3 full-pipeline evaluation infrastructure."""

from __future__ import annotations

__all__ = [
    "audit",
    "prepare",
    "validate",
    "plan",
    "run_development",
    "freeze",
    "run_evaluation",
    "status",
    "stop",
    "analyze",
    "collect",
]


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    if name in __all__:
        from . import controller

        return getattr(controller, name)
    raise AttributeError(name)
