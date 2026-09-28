"""Bounded post-finalization joins; see README_PREPI_SHUTDOWN_V1.md."""
import math
import threading
import time


def join_owned_workers(threads, timeout=5.0):
    """One shared cleanup deadline; never stops threads or grants inference success."""
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 <= timeout <= 5:
        raise ValueError('Cleanup timeout must be finite and between zero and five seconds')
    current = threading.current_thread()
    owned = list(dict.fromkeys(t for t in threads if t is not current))
    began = time.monotonic()
    before = [t.name for t in owned if t.is_alive()]
    deadline = began + timeout
    for thread in owned:
        if thread.is_alive():
            thread.join(max(0., deadline-time.monotonic()))
    remaining = [t.name for t in owned if t.is_alive()]
    return dict(live_before=before, live_after=remaining,
                elapsed_sec=time.monotonic()-began, timeout_sec=timeout,
                owned_threads_joined=not remaining, inference_success_implied=False)
