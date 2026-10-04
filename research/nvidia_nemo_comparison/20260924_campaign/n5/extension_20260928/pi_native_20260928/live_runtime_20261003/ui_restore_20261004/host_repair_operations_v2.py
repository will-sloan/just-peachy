"""Strict production readback owner support; README_DIAGNOSTIC.md."""
import psutil
psutil.Process().cpu_affinity([14])
import json
import os
from pathlib import Path
import sys
import uuid

private = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
early = private/'audit-preparation'/('ui-repair-dispatch-'+uuid.uuid4().hex)
early.mkdir()
me = psutil.Process()
with (early/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=[14]),stream)
    stream.flush();os.fsync(stream.fileno())

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import host_operations_v6 as driver
original = driver.bind_native_owner_references
def bind(native,new_owners,unit_owners):
    native = original(native,new_owners,unit_owners)
    anchor = " elif 'owner' in v:\n  assert rel in NESTED"
    if native.count(anchor)!=1:
        raise ValueError('Exact nested owner boundary required')
    added = r'''
 elif re.fullmatch(r'live-runtime-tests-20261003/production-idle-01/production-data-readback/unit-owners/[0-9a-f]{32}/UNIT_OWNERSHIP.json',rel):
  assert set(v)=={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','main_pid','owner','runtime_max_seconds','unit'}, ('Bad production unit fields',rel)
  import math
  identity(v['owner'])
  assert type(v['main_pid']) is int and v['main_pid']==v['owner']['pid']
  assert re.fullmatch(r'jp-v29-[0-9a-f]{32}\.service',v['unit']) and re.fullmatch('[0-9a-f]{32}',v['invocation_id'])
  assert v['control_group']=='/user.slice/user-1000.slice/user@1000.service/app.slice/'+v['unit']
  assert all(type(v[k]) in (int,float) and math.isfinite(v[k]) and v[k]>0 for k in ('deadline_monotonic','idle_timeout_seconds','runtime_max_seconds'))
  assert v['runtime_max_seconds']==7200 and v['idle_timeout_seconds']==300
  # This is an actual old-boot process identity, not a logical cleanup receipt.
  assert v['owner']['boot_id']!=boot
  v=v['owner']
'''
    return native.replace(anchor,added+anchor)
driver.bind_native_owner_references=bind
driver.main()
