"""Strict failed-source fact/portrait checks; see README_SOURCE_FAILURE_STATUS.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
import types
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE=PRIVATE/'audit-preparation/stabilization-package-cf9abd6dce8c4ccb99704310f74c90e5/package'
ROOT=PRIVATE/'audit-preparation'/('source-failure-status-check-'+uuid.uuid4().hex)
ROOT.mkdir();me=psutil.Process()

def save(name,value):
    raw=json.dumps(value,sort_keys=True,allow_nan=False).encode()
    assert len(raw)<=32768
    with (ROOT/name).open('xb') as stream:
        assert stream.write(raw)==len(raw);stream.flush();os.fsync(stream.fileno())

save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
save('HOST_SCOPE.json',dict(issued_unix=time.time(),expires_unix=time.time()+120,
    maximum_bytes=1048576,native_actions=False))
pins={}
for name in ('launcher.py','classic_frontend.py','check_source_failure_status.py','README_SOURCE_FAILURE_STATUS.md'):
    raw=(HERE/name).read_bytes()
    for suffix in ('backup','restore'):
        path=ROOT/(name+'.'+suffix)
        with path.open('xb') as output:
            assert output.write(raw)==len(raw);output.flush();os.fsync(output.fileno())
        assert path.read_bytes()==raw
    pins[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
save('SOURCE_CLOSED.json',dict(files=pins,independent_restores=True))

def method(path,klass,name):
    tree=ast.parse(path.read_bytes())
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name==klass)
    return next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name==name)

def signatures(path):
    result={}
    for node in ast.parse(path.read_bytes()).body:
        if isinstance(node,ast.FunctionDef):result[node.name]=ast.dump(node,include_attributes=False)
        elif isinstance(node,ast.ClassDef):
            for row in node.body:
                if isinstance(row,ast.FunctionDef):result[node.name+'.'+row.name]=ast.dump(row,include_attributes=False)
    return result

changed={}
for name,allowed in (('launcher.py',{'Manager._nested_source'}),('classic_frontend.py',{'ClassicController.snapshot'})):
    old,new=signatures(BASE/name),signatures(HERE/name)
    assert old.keys()==new.keys()
    changed[name]=sorted(k for k in old if old[k]!=new[k])
    assert set(changed[name])==allowed,changed
    compile((HERE/name).read_bytes(),str(HERE/name),'exec')

support_tree=ast.parse((BASE/'runtime_support.py').read_bytes())
strict=next(node for node in support_tree.body if isinstance(node,ast.FunctionDef) and node.name=='strict')
namespace={'json':json}
exec(compile(ast.Module(body=[strict,method(HERE/'launcher.py','Manager','_nested_source')],type_ignores=[]),'<actual-manager-source-facts>','exec'),namespace)
probe=namespace['_nested_source']
rejects=0;groups=[]
with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
    directory=Path(temporary);owner_dir=directory/'worker';owner_dir.mkdir()
    source_dir=directory/'session/work/source'
    owner=dict(pid=123,start_ticks=456,boot_id='0561d730-3cad-48e0-940a-fe3930c89665')
    calls=[]
    manager=types.SimpleNamespace(store=types.SimpleNamespace(_artifact_path=lambda sid,path:directory/'session'/path),
        owner_probe=lambda actual:(calls.append(actual) or dict(closed=True,state='EXACT_OWNER_ABSENT')))
    result_path=owner_dir/'RESULT.json'
    def result(value):result_path.write_text(json.dumps(value),encoding='utf-8')
    result(dict(source_facts=dict(processed_samples=42)))
    response=probe(manager,owner_dir)
    assert response['closed'] is False and response['state']=='SOURCE_OWNER_RECEIPT_MISSING'
    groups.append('positive_samples_require_source_identity')
    result_path.unlink()
    response=probe(manager,owner_dir)
    assert response['closed'] is True and response['state']=='SOURCE_START_UNOBSERVED'
    assert 'NEVER' not in response['state']
    groups.append('no_observation_is_not_never_started')
    malformed=[[],False,None,dict(source_facts=[]),dict(source_facts=None),dict(source_facts=False),
        dict(source_facts=dict(processed_samples=True)),dict(source_facts=dict(processed_samples=-1)),
        dict(source_facts=dict(processed_samples=1.0)),dict(source_facts=dict(source_start_observed='true')),
        dict(source_facts=dict(physical_start_packet_observed=1))]
    for value in malformed:
        result(value);response=probe(manager,owner_dir)
        assert response['closed'] is False and response['state']=='SOURCE_START_UNVERIFIABLE'
        rejects+=1
    for raw in ('{"source_facts":{},"source_facts":{}}',' '*(262144+1)):
        result_path.write_text(raw,encoding='utf-8');response=probe(manager,owner_dir)
        assert response['closed'] is False;rejects+=1
    groups.append('malformed_duplicate_oversized_results_fenced')
    source_dir.mkdir(parents=True)
    (owner_dir/'SESSION.json').write_text(json.dumps(dict(session_id='fixture')),encoding='utf-8')
    (source_dir/'REGISTERED_OWNER.json').write_text(json.dumps(dict(owner=owner)),encoding='utf-8')
    (source_dir/'SOURCE_CLOSE.json').write_text(json.dumps(dict(owner=owner)),encoding='utf-8')
    result(dict(source_facts=dict(processed_samples=42)))
    response=probe(manager,owner_dir)
    assert calls[-1]==owner and response['closed'] is True and response['state']=='EXACT_OWNER_ABSENT'
    result([]);response=probe(manager,owner_dir)
    assert calls[-1]==owner and response['closed'] is False and response['owner_status']['closed'] is True
    groups.append('exact_owner_probe_preserved_bad_result_still_fenced')

namespace={'math':math,'selection_label':lambda selection:'fixture retained backend'}
exec(compile(ast.Module(body=[method(HERE/'classic_frontend.py','ClassicController','snapshot')],type_ignores=[]),'<actual-portrait-source-facts>','exec'),namespace)
snapshot=namespace['snapshot']
def portrait(closure):
    manager=types.SimpleNamespace(poll=lambda:closure,poll_export=lambda:None,active_session_id=lambda:None,
        process=None,stop_requested=None,latest_health={},latest_spatial={},export_task=None)
    value=types.SimpleNamespace(manager=manager,current_id=None,opened_id=None,revision=None,
        last_caption_read=0,notice='',error=None,last_closure=None,closing=False,closed=False,
        _read_captions=lambda:None,clock=lambda:10,selection=types.SimpleNamespace(input_source='live'),
        mode='fixture',settings={},rows=[],failure_detail=lambda:'CapacityError: metadata allowance exhausted')
    return snapshot(value)

row=portrait(dict(returncode=1,result=dict(result=None,failure='CapacityError: metadata allowance exhausted',
    source_facts=dict(processed_samples=42)),nested_source=dict(closed=True,owner=owner)))
assert row['state']=='ERROR' and 'capture ran' in row['status'] and 'metadata storage limit' in row['status']
assert row['error']=='CapacityError: metadata allowance exhausted'
row=portrait(dict(returncode=1,result=None,nested_source=dict(closed=True,state='SOURCE_START_UNOBSERVED')))
assert 'capture start was not verified' in row['status'] and 'never' not in row['status'].lower()
for value in ([],dict(source_facts=[]),dict(source_facts=dict(processed_samples=True))):
    row=portrait(dict(returncode=1,result=value,nested_source=dict(closed=True,owner=owner)))
    assert row['state']=='ERROR' and 'capture ran' not in row['status'] and 'Invalid worker' in row['error']
    rejects+=1
groups.append('portrait_primary_metadata_failure_and_truthful_capture_status')
assert sum(path.stat().st_size for path in ROOT.rglob('*') if path.is_file())<1048576
save('AST_REVIEW.json',dict(changed_functions=changed))
save('RESULT.json',dict(status='PASS',groups=groups,rejects=rejects,native_actions=False,
    actual19_historical_contradiction_retained=True,scope='actual changed methods; controlled source/closure observations'))
print(json.dumps(dict(status='PASS',groups=len(groups),rejects=rejects,output=str(ROOT),
    owner=dict(pid=me.pid,create_time=me.create_time()),pins=pins,changed_functions=changed)))
