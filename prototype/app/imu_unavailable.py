"""Fail closed for an explicitly configured but invalid motion adapter; README_IMU.md."""
class UnavailableMotion:
    def __init__(self, error): self.error = str(error)
    def snapshot(self):
        return dict(enabled=True, hardware_opened=False, state='ERROR', error=self.error,
                    valid=False, compensation=False, yaw_deg=0.,
                    reason='Motion configuration invalid; spatial support suspended')
    def transform(self, angle, at): return None, 0.
    def reset(self): pass
    def close(self): return True
