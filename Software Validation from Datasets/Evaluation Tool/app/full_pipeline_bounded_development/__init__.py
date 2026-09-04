"""Eight-day, C:-only bounded Prompt-4 development controller."""

from .selection import (
    COMPLETION_MARKER,
    SCOPE_CLASS,
    SCOPE_ID,
    build_selection_manifest,
)

__all__ = [
    "COMPLETION_MARKER",
    "SCOPE_CLASS",
    "SCOPE_ID",
    "build_selection_manifest",
]
