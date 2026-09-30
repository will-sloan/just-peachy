"""Paced saved-source child; see README_B01_ISOLATED_FIXTURE_V1.md."""
from dataclasses import fields
import json
import os
from pathlib import Path
import sys
import types


def create(cfg):
    assert cfg['capture'] is False and cfg['source_factory']=='create'
    prototype=Path(cfg['prototype']);sys.path[:0]=[str(prototype),str(prototype/'vendor')]
    def forbidden(*args,**kwargs):raise AssertionError('Hardware forbidden in saved-source child')
    denied=types.ModuleType('sounddevice');denied.__getattr__=lambda name:forbidden(name)
    sys.modules['sounddevice']=denied
    from app import live_audio as L
    from saved_live_fixture_v1 import install
    patches=install(L,Path(cfg['fixture_root']))
    for patch in patches:patch.start()
    L.HostControl=L.DeviceLease=L.inventory=forbidden
    source=L.XVFLiveSource(L.LiveConfig(**json.loads((Path(cfg['fixture_root'])/'data/live_config.json').read_text())))
    metadata=source.start(consent=True)
    directory=Path(cfg['case_directory']);temporary=directory/'SOURCE_START.pending'
    with temporary.open('x') as f:json.dump(metadata,f,indent=2)
    os.replace(temporary,directory/'SOURCE_START.json')
    class SavedBridge:
        closed=False
        @property
        def finished(self):return source.finished
        def read(self,timeout=.002):
            block=source.read(timeout)
            if block is None:return None
            return block.model_start_sample,block.audio.astype('<f4',copy=False).tobytes(),{f.name:getattr(block,f.name) for f in fields(block) if f.name!='audio'}
        def stop(self):source.stop()
        def close(self):
            assert not self.closed;self.stop();self.closed=True
            result=dict(closed=True,final_status=source.status(),conversion=source.conversion,
                        bridge_model_samples=source.sent,bridge_native_frames=source.native,
                        stream_closed=source.handle.closed,lease_released=source.lease is None,
                        errors=[],route_restoration={},fixture_only=True,hardware_opened=False)
            assert result['stream_closed'] and sys.modules['sounddevice'] is denied
            for patch in reversed(patches):patch.stop()
            return result
    return SavedBridge()
