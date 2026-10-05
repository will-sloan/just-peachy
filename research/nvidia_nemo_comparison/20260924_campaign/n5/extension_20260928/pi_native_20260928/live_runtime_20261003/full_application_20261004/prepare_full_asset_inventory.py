"""Pin the current build21 assets for final backup. README_DELIVERY_BACKUP.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def main():
    here = Path(__file__).resolve().parent
    private = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    out = private/'audit-preparation'/('full-assets-'+uuid.uuid4().hex)
    out.mkdir(); started = time.time(); me = psutil.Process()
    def write(name, raw):
        with (out/name).open('xb') as stream:
            assert stream.write(raw) == len(raw)
            stream.flush(); os.fsync(stream.fileno())
        assert (out/name).read_bytes() == raw
    write('REGISTERED_OWNER.json', json.dumps(dict(pid=me.pid, create_time=me.create_time(), affinity=[14])).encode())
    original = (here.parent/'inventory_runtime_assets_action.py').read_bytes()
    old = 'field-runtime-v29-build-08'
    new = 'field-runtime-v29-build-21'
    text = original.decode()
    assert text.count(old) == 1
    result = text.replace(old, new).encode()
    compile(result, '<build21-assets>', 'exec')
    before = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(original).body if isinstance(n, ast.FunctionDef)}
    after = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(result).body if isinstance(n, ast.FunctionDef)}
    assert set(before) == set(after) and {n for n in before if before[n] != after[n]} == {'inspect'}
    for name, raw in [('ORIGINAL.py', original), ('ACTION.py', result), ('ACTION.restore.py', result), ('PREPARER.py', Path(__file__).read_bytes()), ('README.md', (here/'README_DELIVERY_BACKUP.md').read_bytes())]:
        write(name, raw)
    target = here/'inventory_full_assets_action_v1.py'
    with target.open('xb') as stream:
        assert stream.write(result) == len(result)
        stream.flush(); os.fsync(stream.fileno())
    assert target.read_bytes() == result
    assert sum(p.stat().st_size for p in out.iterdir()) < 2*1024**2 and time.time()-started < 600
    write('SOURCE_CLOSED.json', json.dumps(dict(independent_restore=True, maximum_bytes=2*1024**2, maximum_seconds=600, sha256=hashlib.sha256(result).hexdigest(), native_action=False, closed_unix=time.time())).encode())
    print(json.dumps(dict(status='PASS', target=str(target), output=str(out))))


if __name__ == '__main__':
    main()
