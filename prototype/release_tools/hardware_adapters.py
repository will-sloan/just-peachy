"""Disabled peripheral contracts. No camera/GPIO/bus is opened by these adapters."""
from dataclasses import dataclass


@dataclass(frozen=True)
class HardwareSample:
    source_monotonic_ns: int
    received_monotonic_ns: int
    value: object
    simulated: bool = False


class DisabledPeripheral:
    def __init__(self, name):
        self.name = name
    def read(self):
        return None
    def status(self):
        return {'name': self.name, 'enabled': False, 'state': 'HARDWARE_PENDING', 'hardware_opened': False}
    def close(self):
        pass


class MockPeripheral(DisabledPeripheral):
    """Test-only queue with explicit simulated provenance; never a live sensor."""
    def __init__(self, name, samples=()):
        super().__init__(name)
        self.samples = iter(samples)
    def read(self):
        sample = next(self.samples, None)
        if sample is not None and not sample.simulated:
            raise ValueError('Mock samples must be labelled simulated')
        return sample
