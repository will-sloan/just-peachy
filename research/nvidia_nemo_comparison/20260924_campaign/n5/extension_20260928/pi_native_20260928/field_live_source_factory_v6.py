"""Operator source composition binding; README_FIELD_OPERATOR_PARENT_V1.md."""
import os
from pathlib import Path
import sys
import threading
from field_live_source_outputs_v6 import load, bounded_json, encoded
from field_source_factory_overlay_v1 import route_classes
from field_live_stop_overlay_v1 import source_class


def create(cfg):
    root = Path(cfg['output_root'])
    checked, admission, routes = load(root/'config/CONFIG.json',role='source')
    if encoded(cfg) != encoded(checked):
        raise ValueError('Source factory configuration changed after owner ACK')
    prototype = Path(cfg['prototype'])
    threading.stack_size(1024**2)
    sys.path[:0] = [str(prototype),str(prototype/'vendor')]
    import app.live_audio as live
    if Path(live.__file__).resolve() != prototype/'app/live_audio.py':
        raise ValueError('Actual live source imported outside the admitted release')
    from field_live_source_bridge_v6 import LiveSourceBridge
    original_source = live.XVFLiveSource
    BoundedStop = source_class(live)

    class ActualSource(BoundedStop):
        # This fresh production factory validates its real capture admission
        # above. It does not change or call the old qualification-only start.
        def start(self, *, consent=False):
            return original_source.start(self,consent=consent)

    live.HostControl, live.LiveRoute = route_classes(live,routes)
    settings = bounded_json(cfg['live_config'])
    if settings['lease_path'] != str(Path.home()/'JustPeachy/data/xvf-hardware.lock'):
        raise ValueError('Exact hardware lease path required')
    # Actual Stop is the retained bounded derivative; no random receipt folder.
    settings.update(evidence_dir=None,control_timeout_seconds=2)
    source = ActualSource(live.LiveConfig(**settings),routes)
    def signal_stop():
        # Stop audio acceptance without blocking this diagnostic writer. Actual
        # stream/route/lease cleanup still runs through stop() in the child.
        source._stopped = True
        source._route_ready = False
        routes.stop_event.set()
    routes.request_stop = signal_stop
    try:
        metadata = source.start(consent=True)
        routes.source('SOURCE_START.json',metadata)
    except BaseException:
        # Physical cleanup is attempted even if source-start publication failed.
        receipt = source.stop()
        routes.source('SOURCE_START_FAILURE.json',receipt)
        raise
    bridge = LiveSourceBridge(source,live.LiveGap,root/'source',routes)
    bridge.signal_stop = signal_stop
    return bridge
