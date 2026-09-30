"""Actual quiet source child with persisted route rollback; README_SOURCE_QUIET_V1.md."""
import json
import os
from pathlib import Path
import sys
import threading


def save(path, value):
    path = Path(path)
    assert not path.exists()
    temporary = path.with_name(path.name+'.pending')
    with temporary.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def create(cfg):
    assert cfg['capture'] is True and cfg['quiet_only'] is True
    root = Path(cfg['case_directory'])
    prototype = Path(cfg['prototype'])
    assert os.environ['ALSA_CONFIG_PATH'] == cfg['alsa_config']
    authority = json.loads(Path(cfg['authority']).read_text())
    assert authority['scheduled_quiet_capture_authorized'] and authority['quiet_audio_retention_authorized']
    threading.stack_size(1024**2)
    sys.path[:0] = [str(prototype), str(prototype/'vendor')]
    import app.live_audio as live
    from live_source_bridge_v2 import LiveSourceBridge

    class BackedControl(live.HostControl):
        def snapshot(self, *args, **kwargs):
            value = super().snapshot(*args, **kwargs)
            if not (root/'PRE_ROUTE_SNAPSHOT.json').exists():
                # This returns before LiveRoute.apply may execute any setters.
                save(root/'PRE_ROUTE_SNAPSHOT.json', value)
            return value

    class VerifiedRoute(live.LiveRoute):
        def restore(self):
            result = super().restore()
            try:
                after = self.control.snapshot()
                save(root/'POST_ROUTE_SNAPSHOT.json', after)
                before = json.loads((root/'PRE_ROUTE_SNAPSHOT.json').read_text())
                result['persisted_snapshot_verification'] = 'RESTORED' if after == before else 'MISMATCH'
            except Exception as exc:
                result['persisted_snapshot_verification'] = 'FAILED: '+str(exc)[:256]
            # Never raise here: original Stop still must close stream and lease.
            return result

    live.HostControl = BackedControl
    live.LiveRoute = VerifiedRoute
    settings = json.loads(Path(cfg['live_config']).read_text())
    assert settings['lease_path'] == str(Path.home()/'JustPeachy/data/xvf-hardware.lock')
    settings.update(evidence_dir=str(root/'route_receipts'), control_timeout_seconds=2)
    source = live.XVFLiveSource(live.LiveConfig(**settings))
    try:
        metadata = source.start(consent=True)
        save(root/'SOURCE_START.json', metadata)
    except BaseException:
        save(root/'SOURCE_START_FAILURE.json', source.stop())
        raise
    return LiveSourceBridge(source, live.LiveGap, root)
