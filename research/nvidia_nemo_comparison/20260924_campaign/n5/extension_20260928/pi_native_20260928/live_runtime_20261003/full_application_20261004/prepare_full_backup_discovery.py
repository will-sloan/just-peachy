"""Add the current restored package/shortcut to exact backup discovery. README_DELIVERY_BACKUP.md."""
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
    here=Path(__file__).resolve().parent
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    out=private/'audit-preparation'/('full-backup-discovery-'+uuid.uuid4().hex);out.mkdir();me=psutil.Process();started=time.time()
    def write(name,raw):
        with (out/name).open('xb') as stream:assert stream.write(raw)==len(raw);stream.flush();os.fsync(stream.fileno())
        assert (out/name).read_bytes()==raw
    write('REGISTERED_OWNER.json',json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
    original=(here.parent/'discover_production_backup_action_v6.py').read_bytes();text=original.decode()
    before="    for directory in (base/'data',base/'config'):"
    after="    add(campaign/'field-runtime-v29-build-21','exact current restored runtime source')\n    add(campaign/'field-runtime-v29-build-17','exact preserved immediate rollback runtime source')\n    add(home/'Desktop/Just Peachy.desktop','sole current restored launcher')\n"+before
    assert text.count(before)==1;text=text.replace(before,after);result=text.encode();compile(result,'<current-full-backup-discovery>','exec')
    a={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(original).body if isinstance(n,ast.FunctionDef)}
    b={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(result).body if isinstance(n,ast.FunctionDef)}
    assert set(a)==set(b) and {n for n in a if a[n]!=b[n]}=={'discover'}
    for name,raw in [('ORIGINAL.py',original),('ACTION.py',result),('ACTION.restore.py',result),('README.md',(here/'README_DELIVERY_BACKUP.md').read_bytes()),('PREPARER.py',Path(__file__).read_bytes())]:write(name,raw)
    target=here/'discover_full_backup_action_v1.py'
    with target.open('xb') as stream:assert stream.write(result)==len(result);stream.flush();os.fsync(stream.fileno())
    assert target.read_bytes()==result and sum(p.stat().st_size for p in out.iterdir())<2*1024**2 and time.time()-started<600
    write('SOURCE_CLOSED.json',json.dumps(dict(independent_restore=True,maximum_bytes=2*1024**2,maximum_seconds=600,sha256=hashlib.sha256(result).hexdigest(),native_action=False,closed_unix=time.time())).encode())
    print(json.dumps(dict(status='PASS',target=str(target),output=str(out))))


if __name__=='__main__':main()
