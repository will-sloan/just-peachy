"""Host partial-tree transport cases; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,hashlib,io,json,os,sys,time
from pathlib import Path
sys.dont_write_bytecode=True

def main(output):
    output=Path(output);output.mkdir()
    me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
    (output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
    from field_host_budget_v1 import HostStore,encoded
    from field_operator_broker_partial_v1 import validate,projection,inventory,plan
    from field_operator_broker_ssh_mirror_v2 import receive,send_json
    binding=dict(source_root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-operator-sessions-v99999',
      policy_sha256='a'*64,initializer_owner=dict(pid=99999,start_ticks=1,boot_id='00000000-0000-0000-0000-000000000000'),
      members={'RELEASE.json':65536,'broker/STAGE_OWNER.json':16384,'broker/MANIFEST.json':131072,
        'broker/CONFIG.json':65536,'broker/TEMPLATE.json':131072,'code/example.py':32768})
    validate(binding);passed=[];rejected=[];began=time.monotonic()
    for label,contents in [('empty',{}),('truncated',{'RELEASE.json':b'{"broken":',
      'broker/STAGE_OWNER.json':b'{"pid":','code/example.py':b'#'+b'x'*29999})]:
        source=output/(label+'-source');source.mkdir();(source/'broker').mkdir();(source/'code').mkdir()
        for name,raw in contents.items():(source/name).write_bytes(raw)
        pins={name:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in sorted(contents.items())}
        value=plan(source,pins,time.monotonic()+20,400000,binding)
        public={k:v for k,v in value.items() if k!='source_identities'}
        stream=io.BytesIO();send_json(stream,public)
        for name,raw in sorted(contents.items()):send_json(stream,dict(file=name,bytes=len(raw)));stream.write(raw)
        send_json(stream,dict(status='SOURCE_TREE_UNCHANGED',files=len(contents),bytes=sum(map(len,contents.values()))));stream.seek(0)
        store=HostStore(output/(label+'-metadata')).create({'REGISTERED_OWNER.json':encoded(owner)})
        called=[]
        def closed():
            assert not (store.root/'metadata/BACKUP.json').exists();called.append(True)
        dest=output/(label+'-mirror')
        result=receive(store,dest,stream,pins,deadline=time.monotonic()+20,maximum_bytes=400000,
          verify_process_closed=closed,source_label='HOST_FIXTURE',partial_binding=binding)
        assert called==[True] and stream.read()==b''
        for name,raw in contents.items():assert (source/name).read_bytes()==(dest/name).read_bytes()==raw
        assert inventory(source,time.monotonic()+10,binding)==(value['source_identities'],set(value['directories']))
        passed.append(dict(case=label,**result))
    for label,files,dirs in [
        ('unknown_writer',{'broker/OWNER.json':dict(bytes=0,sha256='a'*64)},['','broker']),
        ('oversize_member',{'code/example.py':dict(bytes=32769,sha256='a'*64)},['','code']),
        ('runtime_directory',{},['','recordings']),
        ('traversal',{'../escaped':dict(bytes=0,sha256='a'*64)},['']),
    ]:
        public=dict(files=files,directories=dirs,bytes=sum(x['bytes'] for x in files.values()),
          reserved_bytes=sum(x['bytes'] for x in files.values())+len(dirs)*65536)
        stream=io.BytesIO();send_json(stream,public);stream.seek(0)
        store=HostStore(output/(label+'-metadata')).create({'REGISTERED_OWNER.json':encoded(owner)})
        dest=output/(label+'-mirror')
        try:receive(store,dest,stream,files,deadline=time.monotonic()+10,maximum_bytes=400000,
          verify_process_closed=lambda:None,source_label='HOST_REJECT_FIXTURE',partial_binding=binding)
        except (ValueError,RuntimeError):rejected.append(label)
        else:raise AssertionError('Accepted '+label)
        assert not dest.exists() and not (store.root/'metadata/BACKUP.json').exists()
    for label,change in [('wrong_root',dict(source_root='/tmp/foreign')),('boolean_ceiling',dict(members=dict(binding['members'],**{'code/example.py':True}))),
       ('extra_binding',dict(accepted=True))]:
        bad=dict(binding,**change)
        try:validate(bad)
        except (ValueError,TypeError):rejected.append(label)
        else:raise AssertionError('Accepted '+label)
    result=dict(status='PASS_HOST_PARTIAL_INITIALIZER_TREE_TRANSPORT',positive=passed,rejected=rejected,
      elapsed_seconds=time.monotonic()-began,owner=owner,fixture_identity_only=True,
      process_closure_callback_fixture=True,native_ssh=False,native_filesystem=False,gui_capture_models=False,
      malformed_source_bytes_unchanged=True,rejected_before_destination_creation=True)
    (output/'RESULT.json').open('x').write(json.dumps(result));print(json.dumps(result))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    raise SystemExit(main(p.parse_args().output))
