"""Read-only console rendering for the eight-day program controller."""

from __future__ import annotations

from typing import Any, Mapping


def progress_bar(percentage: float, width: int = 28) -> str:
    bounded = max(0.0, min(100.0, float(percentage)))
    filled = round(width * bounded / 100.0)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {bounded:6.2f}%"


def duration(seconds: object) -> str:
    if seconds is None:
        return "calculating"
    total = max(0, int(float(seconds)))
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"


def render_status(status: Mapping[str, Any]) -> str:
    lines = [
        "JUST-PEACHY FULL PIPELINE - EIGHT-DAY C:-ONLY PROGRAM",
        "",
        f"OVERALL  {progress_bar(float(status.get('overall_percentage', 0.0)))}",
        (
            f"STATUS   {status.get('status')}   "
            f"CURRENT Prompt {status.get('current_prompt_index') or '-'}"
        ),
        (
            f"TIME     elapsed {duration(status.get('elapsed_seconds'))}   "
            f"ETA {duration(status.get('eta_seconds'))}   "
            f"planning target left {duration(status.get('target_remaining_seconds', status.get('remaining_envelope_seconds')))}"
        ),
        (
            f"POLICY   {status.get('time_target_policy', 'ADVISORY_ONLY_NO_AUTOMATIC_STOP')}"
            + (
                f"   target overrun {duration(status.get('target_overrun_seconds'))}"
                if float(status.get('target_overrun_seconds', 0.0) or 0.0) > 0
                else ""
            )
        ),
        (
            f"STORAGE  C: {float(status.get('c_drive_free_gib', 0.0)):.1f} GiB free   "
            f"reserve {float(status.get('minimum_free_space_reserve_gib', 35.0)):.1f} GiB   "
            f"{status.get('storage_status')}"
        ),
        "",
    ]
    for stage in status.get("stages", []):
        lines.append(
            f"PROMPT {stage['prompt_index']} {progress_bar(stage.get('percentage', 0.0), 20)} "
            f"{stage.get('status')} / {stage.get('readiness')}"
        )
        lines.append(
            f"         ETA {duration(stage.get('eta_seconds'))}   {stage.get('adapter_id')}"
        )
        if stage.get("detail"):
            lines.append(f"         {stage['detail']}")
    lines.extend(
        [
            "",
            f"State: {status.get('program_state')}",
            f"Milestones: {status.get('milestone_notifications')}",
            "Ctrl+C closes this read-only monitor; it does not stop the program.",
        ]
    )
    return "\n".join(lines)
