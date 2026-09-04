"""Pure presentation contracts for the H2 product demonstration.

The H2 steering decision fixes the speaker stack to Pyannote segmentation plus
ReDimNet2-B2 diarization/identity.  This module contains labels and validation
only; it deliberately imports neither a model nor the runtime factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


H2_PRIMARY_PIPELINE_ID: Final = "fullpipe_v1_ag_dr_ir"
H2_FALLBACK_PIPELINE_ID: Final = "fullpipe_v1_ao_dr_ir"
H2_PIPELINE_IDS: Final = (
    H2_PRIMARY_PIPELINE_ID,
    H2_FALLBACK_PIPELINE_ID,
)

H2_KNOWN_ONLY: Final = "H2_KNOWN_ONLY"
H2_SESSION_ANONYMOUS: Final = "H2_SESSION_ANONYMOUS"
H2_SESSION_MEMORY_ENHANCED: Final = "H2_SESSION_MEMORY_ENHANCED"
H2_PRODUCT_MODE_IDS: Final = (
    H2_KNOWN_ONLY,
    H2_SESSION_ANONYMOUS,
    H2_SESSION_MEMORY_ENHANCED,
)
H2_DEFAULT_PRODUCT_MODE: Final = H2_SESSION_MEMORY_ENHANCED


@dataclass(frozen=True)
class H2ProductMode:
    mode_id: str
    display_name: str
    summary: str
    persistent_anonymous_labels: bool
    session_memory: bool


H2_PRODUCT_MODES: Final = (
    H2ProductMode(
        mode_id=H2_KNOWN_ONLY,
        display_name="Known people only (privacy minimal)",
        summary=(
            "Names deliberately enrolled people; every other voice is shown as "
            "Unknown without a persistent Speaker_N identity."
        ),
        persistent_anonymous_labels=False,
        session_memory=False,
    ),
    H2ProductMode(
        mode_id=H2_SESSION_ANONYMOUS,
        display_name="Session anonymous speakers",
        summary=(
            "Tracks Speaker_N identities only for this session and may replace a "
            "session label with a safely confirmed enrolled name."
        ),
        persistent_anonymous_labels=True,
        session_memory=False,
    ),
    H2ProductMode(
        mode_id=H2_SESSION_MEMORY_ENHANCED,
        display_name="Session memory enhanced (primary)",
        summary=(
            "Adds the active roster, tentative/confirmed names, warm "
            "reacquisition, expiry, hysteresis, and bounded session memory."
        ),
        persistent_anonymous_labels=True,
        session_memory=True,
    ),
)


def h2_product_mode(mode_id: str) -> H2ProductMode:
    """Resolve one exact mode ID; aliases are intentionally not accepted."""

    value = str(mode_id).strip()
    for mode in H2_PRODUCT_MODES:
        if mode.mode_id == value:
            return mode
    raise ValueError(
        f"unsupported H2 product mode {value!r}; expected one of "
        + ", ".join(H2_PRODUCT_MODE_IDS)
    )


def h2_mode_display_values() -> tuple[str, ...]:
    return tuple(f"{row.display_name} · {row.mode_id}" for row in H2_PRODUCT_MODES)


def h2_mode_id_from_display(value: str) -> str:
    """Accept an exact ID or one of the UI's lossless display strings."""

    text = str(value).strip()
    if text in H2_PRODUCT_MODE_IDS:
        return text
    for row, display in zip(
        H2_PRODUCT_MODES, h2_mode_display_values(), strict=True
    ):
        if text == display:
            return row.mode_id
    return h2_product_mode(text).mode_id


def require_h2_pipeline_id(pipeline_id: str) -> str:
    value = str(pipeline_id).strip()
    if value not in H2_PIPELINE_IDS:
        raise ValueError(
            "the H2 product demo accepts only AG-H2 primary or AO-H2 fallback; "
            f"received {value!r}"
        )
    return value


def h2_pipeline_role(pipeline_id: str) -> str:
    value = require_h2_pipeline_id(pipeline_id)
    return "PRIMARY" if value == H2_PRIMARY_PIPELINE_ID else "FALLBACK_REFERENCE"


__all__ = [
    "H2_DEFAULT_PRODUCT_MODE",
    "H2_FALLBACK_PIPELINE_ID",
    "H2_KNOWN_ONLY",
    "H2_PIPELINE_IDS",
    "H2_PRIMARY_PIPELINE_ID",
    "H2_PRODUCT_MODE_IDS",
    "H2_PRODUCT_MODES",
    "H2_SESSION_ANONYMOUS",
    "H2_SESSION_MEMORY_ENHANCED",
    "H2ProductMode",
    "h2_mode_display_values",
    "h2_mode_id_from_display",
    "h2_pipeline_role",
    "h2_product_mode",
    "require_h2_pipeline_id",
]
