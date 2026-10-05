"""Prepare exact manual GUI owner binding. See README_MANUAL_OWNER_DECODER.md."""
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
    out=private/'audit-preparation'/('manual-owner-decoder-'+uuid.uuid4().hex);out.mkdir();me=psutil.Process();started=time.time()
    def write(name,raw):
        with (out/name).open('xb') as stream:assert stream.write(raw)==len(raw);stream.flush();os.fsync(stream.fileno())
        assert (out/name).read_bytes()==raw
    write('REGISTERED_OWNER.json',json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
    write('HOST_SCOPE.json',json.dumps(dict(issued_unix=started,maximum_seconds=600,maximum_bytes=2*1024**2)).encode())
    original=(here/'host_full_operations_v6.py').read_bytes();text=original.decode()
    def once(before,after):
        nonlocal text
        assert text.count(before)==1,before;text=text.replace(before,after)
    once("expected=KEYS if kind=='finite_gui' else WATCHDOG_KEYS", "expected=(KEYS|{'lifetime_policy'}) if kind=='manual_gui' else KEYS if kind=='finite_gui' else WATCHDOG_KEYS")
    once("if kind=='finite_gui' else r'jp-v29-production-idle-(?:01|03)-watchdog", "if kind in ('finite_gui','manual_gui') else r'jp-v29-production-idle-(?:01|03|04)-watchdog")
    once("    for key in ('runtime_max_seconds',) if kind=='watchdog'", "    if kind=='manual_gui':\n        if (value['runtime_max_seconds'] is not None or value['deadline_monotonic'] is not None or\n            value['lifetime_policy']!='manual_stop_storage_guarded' or type(value['idle_timeout_seconds']) is not int or value['idle_timeout_seconds']!=300):\n            raise ValueError('Exact manual-Stop storage-guarded lifetime required')\n        return value\n    for key in ('runtime_max_seconds',) if kind=='watchdog'")
    once("'live-runtime-tests-20261003/production-idle-03'):", "'live-runtime-tests-20261003/production-idle-03','live-runtime-tests-20261003/production-idle-04'):")
    once("kind='finite_gui';typed_unit(value,kind)", "kind='manual_gui' if relative=='live-runtime-tests-20261003/production-idle-04' else 'finite_gui';typed_unit(value,kind)\n                if kind=='manual_gui' and job['package_manifest_sha256']!='9abaaaffe35d328fd97f5fc47f1f5b938803705dffb728c5d804d225a646ba6e':\n                    raise ValueError('Exact observed build21 manual GUI binding required')")
    once("if len(pins)!=4:", "if len(pins)!=6:")
    text=text.replace('Exactly four independently mirrored idle01/idle03 supervisor proofs are required','Exactly six independently mirrored idle01/idle03/idle04 supervisor proofs are required')
    once("  if expected['kind']=='finite_gui':", "  if expected['kind']=='manual_gui':\n   assert re.fullmatch(r'live-runtime-tests-20261003/production-idle-04/production-data-readback/unit-owners/[0-9a-f]{32}/UNIT_OWNERSHIP.json',rel)\n   assert set(v)=={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','lifetime_policy','main_pid','owner','runtime_max_seconds','unit'}\n   assert re.fullmatch(r'jp-v29-[0-9a-f]{32}\\.service',v['unit']) and v['runtime_max_seconds'] is None and v['deadline_monotonic'] is None\n   assert v['lifetime_policy']=='manual_stop_storage_guarded' and type(v['idle_timeout_seconds']) is int and v['idle_timeout_seconds']==300\n  elif expected['kind']=='finite_gui':")
    text=text.replace("(?:01|03)/watchdog/UNIT_OWNERSHIP", "(?:01|03|04)/watchdog/UNIT_OWNERSHIP")
    text=text.replace("(?:01|03)-watchdog\\.service", "(?:01|03|04)-watchdog\\.service")
    result=text.encode();compile(result,'<strict-manual-owner-binding>','exec')
    before={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(original).body if isinstance(n,ast.FunctionDef)}
    after={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(result).body if isinstance(n,ast.FunctionDef)}
    changed={n for n in before if before[n]!=after[n]}
    assert set(before)==set(after) and changed=={'typed_unit','actual_nested_unit_map','bind'}
    for name,raw in [('ORIGINAL.py',original),('ACTION.py',result),('ACTION.restore.py',result),('README.md',(here/'README_MANUAL_OWNER_DECODER.md').read_bytes()),('PREPARER.py',Path(__file__).read_bytes())]:write(name,raw)
    target=here/'host_full_operations_v9.py'
    with target.open('xb') as stream:assert stream.write(result)==len(result);stream.flush();os.fsync(stream.fileno())
    assert target.read_bytes()==result and sum(p.stat().st_size for p in out.iterdir())<2*1024**2 and time.time()-started<600
    write('SOURCE_CLOSED.json',json.dumps(dict(sha256=hashlib.sha256(result).hexdigest(),changed_functions=sorted(changed),independent_restore=True,native_action=False,closed_unix=time.time())).encode())
    print(json.dumps(dict(status='PASS',target=str(target),output=str(out))))


if __name__=='__main__':main()
