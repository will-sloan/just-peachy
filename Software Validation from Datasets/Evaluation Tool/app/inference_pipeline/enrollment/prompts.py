"""Prompt metadata for repeatable speaker enrollment captures."""

from __future__ import annotations


DEFAULT_PROMPT_ID = "clean_enrollment_v1"

ENROLLMENT_PROMPTS: dict[str, dict[str, str]] = {
    DEFAULT_PROMPT_ID: {
        "prompt_id": DEFAULT_PROMPT_ID,
        "title": "Clean enrollment sample",
        "text": (
            "Read a short, clean speech sample in your normal voice. "
            "Avoid background noise and clipping."
        ),
        "notes": "Used for file-based M10 enrollment before live microphone capture exists.",
    },
}


def prompt_metadata(prompt_id: str = DEFAULT_PROMPT_ID) -> dict[str, str]:
    """Return a copy of prompt metadata for the requested enrollment prompt."""

    return dict(ENROLLMENT_PROMPTS.get(prompt_id, {"prompt_id": prompt_id}))
