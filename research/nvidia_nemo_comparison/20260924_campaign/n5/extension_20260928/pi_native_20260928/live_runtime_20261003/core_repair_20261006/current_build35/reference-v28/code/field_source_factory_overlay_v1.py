"""No-capture factory receipt adapters; README_FIELD_SOURCE_RECEIPTS_V1.md."""
from pathlib import Path
import json

def save(routes,path,value):
    path=Path(path)
    if path.parent!=routes.root/'source':raise ValueError('Unmapped factory receipt path')
    return routes.source(path.name,value)

def route_classes(live,routes):
    root=routes.root/'source'
    class BackedControl(live.HostControl):
        def snapshot(self,*args,**kwargs):
            value=super().snapshot(*args,**kwargs)
            if not (root/'PRE_ROUTE_SNAPSHOT.json').exists():save(routes,root/'PRE_ROUTE_SNAPSHOT.json',value)
            return value
    class VerifiedRoute(live.LiveRoute):
        def restore(self):
            result=super().restore()
            try:
                after=self.control.snapshot()
                save(routes,root/'POST_ROUTE_SNAPSHOT.json',after)
                before=json.loads((root/'PRE_ROUTE_SNAPSHOT.json').read_text())
                result['persisted_snapshot_verification']='RESTORED' if after==before else 'MISMATCH'
            except Exception as exc:
                result['persisted_snapshot_verification']='FAILED: '+str(exc)[:256]
            return result
    return BackedControl,VerifiedRoute
