"""Bound empty fixture, never hardware; README_FIELD_TRANSPORT_OUTPUTS_V1.md."""
class Empty:
    finished=True
    def __init__(self,mode):self.stops=0;self.closes=0;self.mode=mode;self.finished=mode=='empty'
    def read(self,timeout):
        if self.mode=='wait':
            import time;time.sleep(20)
        return None
    def stop(self):self.stops+=1
    def close(self):
        self.closes+=1
        return dict(fixture=True,stops=self.stops,closes=self.closes,no_hardware=True)
def create(cfg):
    if cfg['capture'] is not False:raise ValueError('Empty fixture only')
    return Empty(cfg['source_mode'])
