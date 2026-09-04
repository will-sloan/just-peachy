"""Lazy, model-free local audio-device discovery for the demo UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AudioInputDevice:
    """One selectable input device with its native default format."""

    index: int
    name: str
    sample_rate_hz: int
    maximum_input_channels: int
    host_api: str | None = None

    @property
    def display_name(self) -> str:
        return (
            f"{self.index}: {self.name} — {self.sample_rate_hz} Hz, "
            f"{self.maximum_input_channels} ch"
        )


def enumerate_input_devices(
    module_importer: Callable[[str], Any] = __import__,
) -> tuple[AudioInputDevice, ...]:
    """Return local input devices without importing a model or opening capture."""

    try:
        sounddevice = module_importer("sounddevice")
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "Microphone discovery requires the local sounddevice package"
        ) from exc
    host_apis = sounddevice.query_hostapis()
    rows: list[AudioInputDevice] = []
    for index, value in enumerate(sounddevice.query_devices()):
        channels = int(value.get("max_input_channels", 0))
        if channels <= 0:
            continue
        host_index = value.get("hostapi")
        host_name = None
        if isinstance(host_index, int) and 0 <= host_index < len(host_apis):
            host_name = str(host_apis[host_index].get("name") or "") or None
        rows.append(
            AudioInputDevice(
                index=index,
                name=str(value.get("name") or f"Input {index}"),
                sample_rate_hz=round(float(value.get("default_samplerate") or 0)),
                maximum_input_channels=channels,
                host_api=host_name,
            )
        )
    return tuple(rows)
