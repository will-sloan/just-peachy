"""Thirty-second accepted-source bound. See README_B01_LIVE_TRIAL_V1.md."""


def bounded_source_class(base, error):
    class BoundedSource(base):
        limit_samples = 480000
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.trial_delivered_samples = 0
            self.trial_source_limit_reached = False
        def read(self, timeout=.25):
            if self.trial_delivered_samples == self.limit_samples:
                self.stop()
                self.trial_source_limit_reached = True
                return None
            block = super().read(timeout)
            if block is None:
                return None
            if block.model_start_sample != self.trial_delivered_samples:
                raise error('Trial source sample discontinuity')
            end = self.trial_delivered_samples+len(block.audio)
            if end > self.limit_samples:
                raise error('Unexpected callback extent at trial limit; no silent clipping')
            self.trial_delivered_samples = end
            return block
    return BoundedSource


def boundary_cases():
    from types import SimpleNamespace
    class Base:
        def __init__(self, blocks):
            self.blocks = iter(blocks)
            self.closed = False
        def read(self, timeout=.25):
            return next(self.blocks, None)
        def stop(self):
            self.closed = True
    def block(start, size):
        return SimpleNamespace(model_start_sample=start, audio=range(size))
    cls = bounded_source_class(Base, RuntimeError)
    normal = cls([block(0,480000)])
    assert normal.read() is not None and not normal.closed
    assert normal.read() is None and normal.closed and normal.trial_source_limit_reached
    assert normal.trial_delivered_samples == 480000
    for blocks, message in [([block(1,160)], 'discontinuity'), ([block(0,480001)], 'extent')]:
        source = cls(blocks)
        try:
            source.read()
        except RuntimeError as exc:
            assert message in str(exc)
        else:
            raise AssertionError('Bound was not enforced')
        assert source.trial_delivered_samples == 0
    return dict(status='PASS_MODEL_FREE_ACCEPTED_SAMPLE_BOUND_ONLY',cases=3,
                microphone_opened=False,models_loaded=False,hardware_restoration_tested=False)
