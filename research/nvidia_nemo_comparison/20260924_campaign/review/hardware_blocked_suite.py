"""Full legacy/N1 unittest suite with physical audio calls disabled. See README.md."""
from pathlib import Path
import json
import os
import unittest


def load_tests(loader, tests, pattern):
    # Imported by the private-desktop launcher, before loading any test modules.
    import psutil
    process=psutil.Process();process.cpu_affinity(process.cpu_affinity()[-2:])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    from app import windows_audio
    windows_audio.endpoint_snapshot=lambda:dict(status='BLOCKED_BY_N1_TEST_HARNESS',default_render={},capture_endpoints=[])
    import sounddevice
    def forbidden(*args,**kwargs):raise AssertionError('Physical audio access forbidden in N1 checks')
    for name in ('query_devices','query_hostapis','InputStream','RawInputStream','OutputStream','RawOutputStream','Stream','RawStream','play','rec','playrec'):
        setattr(sounddevice,name,forbidden)
    prototype=Path(__file__).resolve().parents[4]/'prototype'
    modules=['prototype.tests.'+p.stem for p in sorted((prototype/'tests').glob('test*.py'))]
    suite=loader.loadTestsFromNames(modules)
    destination=Path(os.environ['N1_UI_RECEIPT_DIR'])
    (destination/'hardware_guard.json').write_text(json.dumps(dict(
        physical_audio_calls='disabled before importing tests',module_count=len(modules),
        modules=modules,synthetic_live_adapter_fixtures='permitted',cpu_affinity=process.cpu_affinity()),indent=2)+'\n',encoding='utf-8')
    return suite
