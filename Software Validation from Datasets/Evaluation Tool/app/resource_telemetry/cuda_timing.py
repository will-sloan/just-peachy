"""Optional CUDA event timing at explicit component boundaries."""

from __future__ import annotations

import importlib
from typing import Protocol


class CudaTimer(Protocol):
    available: bool
    reason: str | None

    def start(self) -> None: ...

    def stop(self) -> float | None:
        """Return elapsed CUDA milliseconds."""


class TorchCudaTimer:
    """CUDA event timer that synchronizes only measured GPU boundaries."""

    def __init__(self) -> None:
        self.available = False
        self.reason: str | None = None
        self._torch = None
        self._start = None
        self._end = None
        try:
            torch = importlib.import_module("torch")
            if not torch.cuda.is_available():
                self.reason = "CUDA unavailable in torch"
                return
            self._torch = torch
            self.available = True
        except (ImportError, OSError) as exc:
            self.reason = f"torch CUDA timing unavailable: {type(exc).__name__}"

    def start(self) -> None:
        if not self.available or self._torch is None:
            return
        self._start = self._torch.cuda.Event(enable_timing=True)
        self._end = self._torch.cuda.Event(enable_timing=True)
        self._torch.cuda.synchronize()
        self._start.record()

    def stop(self) -> float | None:
        if not self.available or self._torch is None or self._start is None or self._end is None:
            return None
        self._end.record()
        self._torch.cuda.synchronize()
        return float(self._start.elapsed_time(self._end))
