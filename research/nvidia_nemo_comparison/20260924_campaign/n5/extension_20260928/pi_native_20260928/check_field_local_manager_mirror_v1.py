"""Changed manager-tree transport check; README_FIELD_LOCAL_MIRROR_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import sys
sys.dont_write_bytecode=True
import argparse,base64,copy,hashlib,io,json,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--template',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
args=p.parse_args();args.output.mkdir()
me=psutil.Process();owner=dict(pid=me.pid,create_time=me.create_time(),affinity=[14])
(args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
from field_host_budget_v1 import HostStore
from field_local_release_plan_v2 import allocation,encoded
from field_local_manager_tree_v1 import validate,projection,inventory,plan
from field_local_manager_ssh_mirror_v1 import receive,send_json
manifest=dict(schema='just-peachy.local-release-manifest.v1',files=[
 dict(path='code/example.py',bytes=32768,sha256='a'*64)])
policy=json.loads(args.template.read_bytes());original_sha=hashlib.sha256(args.template.read_bytes()).hexdigest()
policy.update(schema='just-peachy.local-release-policy.v2',allocation=allocation(1,3),
 release_manifest_sha256=hashlib.sha256(encoded(manifest)).hexdigest(),
 root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-local-release-v999',
 recording_roots=['/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-operator-sessions-v999'])
policy['combined_output_cap_bytes']=policy['measured_target_before_bytes']+policy['measured_host_before_bytes']+policy['allocation']['combined_request_bytes']
policy['total_payload_cap_bytes']=policy['measured_payload_before_bytes']+policy['allocation']['combined_request_bytes']
binding=dict(schema='just-peachy.manager-tree-binding.v1',policy=policy,
 policy_sha256=hashlib.sha256(encoded(policy)).hexdigest(),manifest=manifest)
validate(binding)
maximum=policy['allocation']['metadata_maximum_bytes']+policy['allocation']['local_backup_per_recording']
passed=[];rejects=[]
cases=[('empty',{}),('partial',{
 'control/RELEASE.json':b'{"bad":',
 'launches/launch-01/EXIT.json.pending':b'{',
 'recordings/recording-01/STARTED.json.pending':b'{"bad":',
 'code/example.py':b'#fixture\n',
 'backups/recording-01/RELEASE.json':b'{"bad":',
 'backups/recording-01/code/example.py':b'#'+b'x'*29999})]
for label,contents in cases:
 source=args.output/(label+'-source');source.mkdir()
 for name,raw in contents.items():
  target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 pins={n:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for n,raw in sorted(contents.items())}
 value=plan(source,pins,time.monotonic()+20,binding)
 public={k:v for k,v in value.items() if k!='source_identities'}
 stream=io.BytesIO();send_json(stream,public)
 for n,raw in sorted(contents.items()):send_json(stream,dict(file=n,bytes=len(raw)));stream.write(raw)
 send_json(stream,dict(status='SOURCE_TREE_UNCHANGED',files=len(contents),bytes=sum(map(len,contents.values()))));stream.seek(0)
 store=HostStore(args.output/(label+'-metadata')).create({'REGISTERED_OWNER.json':encoded(owner)})
 calls=[]
 def closure():
  assert not (store.root/'metadata/BACKUP.json').exists();calls.append(True)
 destination=args.output/(label+'-copy')
 receipt=receive(store,destination,stream,pins,deadline=time.monotonic()+20,maximum_bytes=maximum,
  verify_process_closed=closure,source_label='HOST_MANAGER_FIXTURE',manager_binding=binding)
 assert calls==[True] and stream.read()==b''
 for n,raw in contents.items():assert (source/n).read_bytes()==(destination/n).read_bytes()==raw
 original,dirs=inventory(source,time.monotonic()+10,binding)
 assert original==value['source_identities'] and dirs==set(value['directories'])
 passed.append(dict(case=label,**receipt))
def reject(label,files,dirs,b=binding):
 try:projection(files,dirs,b)
 except (ValueError,RuntimeError,TypeError):rejects.append(label)
 else:raise AssertionError('Accepted '+label)
row=lambda size:dict(bytes=size,sha256='a'*64)
reject('unknown-control',{'control/UNKNOWN.json':row(1)},['','control'])
reject('pending-overflow',{'launches/launch-01/EXIT.json.pending':row(32769)},['','launches','launches/launch-01'])
reject('unallocated-launch',{},['','launches','launches/launch-04'])
reject('unallocated-backup',{},['','backups','backups/recording-02'])
reject('unknown-manager-code',{'code/other.py':row(1)},['','code'])
reject('manager-code-grew',{'code/example.py':row(32769)},['','code'])
reject('traversal',{'../escape':row(1)},[''])
reject('boolean-size',{'control/RELEASE.json':row(True)},['','control'])
reject('missing-parent',{'control/RELEASE.json':row(1)},[''])
reject('case-alias',{'code/example.py':row(1),'code/EXAMPLE.py':row(1)},['','code'])
reject('local-child-slot',{},['','backups','backups/recording-01','backups/recording-01/recordings','backups/recording-01/recordings/slot-02'])
reject('local-broker-log-overflow',{'backups/recording-01/broker/service.log':row(131073)},['','backups','backups/recording-01','backups/recording-01/broker'])
bad=copy.deepcopy(binding);bad['accepted']=True
reject('extra-binding',{},[''],bad)
# A real receiver rejects invalid partition before creating its destination.
files={'control/UNKNOWN.json':row(1)}
stream=io.BytesIO();send_json(stream,dict(files=files,directories=['','control'],bytes=1,reserved_bytes=131073));stream.seek(0)
dest=args.output/'invalid-copy'
try:receive(None,dest,stream,files,deadline=time.monotonic()+10,maximum_bytes=maximum,
 verify_process_closed=lambda:None,source_label='INVALID_FIXTURE',manager_binding=binding)
except ValueError:rejects.append('receiver-reject-before-mkdir')
else:raise AssertionError('Invalid destination accepted')
assert not dest.exists()
assert hashlib.sha256(args.template.read_bytes()).hexdigest()==original_sha
result=dict(status='PASS_CHANGED_HOST_MANAGER_TREE_MIRROR',positive=passed,rejected=rejects,
 full_manager_tree_reserved_bytes=maximum,synthetic_policy_manifest=True,process_closure_callback_fixture=True,
 native_ssh=False,native_filesystem=False,journal_constructor=False,gui_capture_models=False,
 partial_bytes_preserved=True,real_local_copy_and_readback=True,source_unchanged=True)
(args.output/'RESULT.json').open('x').write(json.dumps(result));print(json.dumps(result))
