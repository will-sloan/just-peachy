"""Timestamped motion safety contract, with no sensor driver. See README_MOTION.md."""
from dataclasses import asdict, dataclass
import math
import time


@dataclass(frozen=True)
class MotionEvent:
    state: str
    source_monotonic_ns: int
    received_monotonic_ns: int
    quality: float
    simulated: bool = False
    clock_domain: str = 'host_monotonic'
    translation_or_range_unknown: bool = False


class MotionSafety:
    """A bounded latest event, never a position estimator or an automatic anchor."""
    def __init__(self, clock=time.monotonic_ns):
        self.clock = clock
        self.latest = None

    def accept(self, event):
        if not isinstance(event, MotionEvent) or event.state not in ('stationary', 'moving', 'settling'):
            raise ValueError('Expected a stationary, moving or settling MotionEvent')
        if event.clock_domain != 'host_monotonic':
            raise ValueError('Map sensor time to the host monotonic clock before delivery')
        now = self.clock()
        if (type(event.source_monotonic_ns) is not int or type(event.received_monotonic_ns) is not int
                or not 0 <= event.source_monotonic_ns <= event.received_monotonic_ns <= now):
            raise ValueError('Invalid source/receipt monotonic timestamps')
        if (type(event.quality) not in (float, int) or not math.isfinite(event.quality)
                or not 0 <= event.quality <= 1
                or type(event.simulated) is not bool or type(event.translation_or_range_unknown) is not bool):
            raise ValueError('Quality must be finite 0..1; provenance and uncertainty must be explicit booleans')
        if self.latest and event.source_monotonic_ns <= self.latest.source_monotonic_ns:
            return dict(accepted=False, invalidate=False, reason='out_of_order_or_duplicate')
        self.latest = event
        # Delayed motion remains evidence to invalidate; stale stationary evidence
        # cannot restore a seat anchor. This is a safety gate, not a tuned model.
        stale = now - event.source_monotonic_ns > 1_000_000_000
        unsafe = event.state != 'stationary' or event.quality < .5 or stale or event.translation_or_range_unknown
        return dict(accepted=True, invalidate=unsafe,
                    reason='motion_' + event.state + ('_uncertain' if stale or event.quality < .5 or event.translation_or_range_unknown else ''))

    def snapshot(self):
        latest = self.latest
        if latest is None:
            return dict(enabled=False, state='HARDWARE_PENDING', hardware_opened=False, event=None)
        age = max(0, self.clock() - latest.source_monotonic_ns) / 1e9
        return dict(enabled=False, state=latest.state, hardware_opened=False,
                    event=asdict(latest), age_sec=age, fresh=age <= 1.,
                    source='mock' if latest.simulated else 'external_adapter',
                    automatic_reanchor=False, absolute_position_or_yaw=False)
