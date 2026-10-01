"""Changed backup-binding fixture checks; README_FIELD_LOCAL_MANAGER_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from pathlib import Path
import json
import sys
sys.dont_write_bytecode=True
p=argparse.ArgumentParser()
p.add_argument('--output',required=True)
p.add_argument('--release-template',required=True)
args=p.parse_args()
out=Path(args.output);out.mkdir(exist_ok=False)
me=psutil.Process()
(out/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
import copy
import hashlib
from field_local_backup_contract_v1 import source_binding,copy_binding
from field_local_release_plan_v1 import encoded,validate_release
from field_operator_broker_layout_v2 import allocation
# Read an existing policy only as a shape template; every observation below is a fixture.
release=json.loads(Path(args.release_template).read_bytes())
validate_release(release);slot=release['allocation']['recording_slots'][0]
a=allocation(1)
policy=dict(schema='just-peachy.operator-broker-policy.v1',root=release['recording_roots'][0],
 issued_utc='2026-10-01T09:00:00+00:00',expires_utc='2026-10-01T09:10:00+00:00',
 allocation=a,combined_output_cap_bytes=a['combined_request_bytes']+1000,
 total_payload_cap_bytes=a['combined_request_bytes']+1000,mode='delayed',
 release_manifest_sha256='1'*64,boot_id='00000000-0000-0000-0000-000000000000',
 host_window_bytes=0,target_before_bytes=0,payload_before_bytes=0)
binding=source_binding(release,slot,policy,'2'*64)
unit=dict(LoadState='not-found',ActiveState='inactive',SubState='dead',MainPID='0')
owners=[dict(path='broker/OWNER.json',owner=dict(pid=123,boot_id=policy['boot_id'],start_ticks=456),exact_alive=False)]
pins={'a/file.dat':dict(bytes=20000,sha256='3'*64),'a/empty.dat':dict(bytes=0,sha256='4'*64),'root.dat':dict(bytes=3,sha256='5'*64)}
receipt=dict(schema='just-peachy.local-broker-backup.v1',status='COMPLETE_LOCAL_COPY_READBACK',
 **{k:binding[k] for k in ('source','destination','policy_sha256','source_unit')},
 unit_before=unit,unit_after=copy.deepcopy(unit),owners=owners,
 chunk_bytes=16384,data_chunks=3,independent_full_readback=True,
 full_reserved_bytes=binding['maximum_bytes'],files=pins,directories=['','a','empty'],
 bytes=20003,reserved_bytes=20003+3*65536)
assert copy_binding(receipt,binding)==hashlib.sha256(encoded(receipt)).hexdigest()
rejects=[]
def reject(name,callback):
    try:callback()
    except (ValueError,RuntimeError,TypeError):rejects.append(name)
    else:raise AssertionError('Expected rejection: '+name)
def changed(key,value):
    candidate=copy.deepcopy(receipt);candidate[key]=value
    return copy_binding(candidate,binding)
two=copy.deepcopy(policy);two['allocation']=allocation(2)
two['combined_output_cap_bytes']=two['total_payload_cap_bytes']=two['allocation']['combined_request_bytes']+1000
reject('two-slot source exceeds one-slot release binding',lambda:source_binding(release,slot,two,'2'*64))
reject('foreign source root',lambda:source_binding(release,slot,{**policy,'root':policy['root']+'0'},'2'*64))
reject('bad source policy digest',lambda:source_binding(release,slot,policy,'bad'))
reject('wrong destination',lambda:changed('destination',binding['destination']+'0'))
reject('wrong source unit',lambda:changed('source_unit','jp-foreign.service'))
reject('one byte reservation short',lambda:changed('full_reserved_bytes',binding['maximum_bytes']-1))
reject('bool reservation',lambda:changed('full_reserved_bytes',True))
reject('missing independent readback',lambda:changed('independent_full_readback',False))
reject('missing directory accounting',lambda:changed('reserved_bytes',receipt['reserved_bytes']-65536))
reject('missing file byte accounting',lambda:changed('bytes',20002))
reject('missing parent directory',lambda:changed('directories',['','empty']))
reject('duplicate directory',lambda:changed('directories',['','a','a']))
reject('case alias',lambda:changed('files',{**pins,'A/FILE.dat':dict(bytes=0,sha256='5'*64)}))
reject('traversal',lambda:changed('files',{'../bad':dict(bytes=20003,sha256='5'*64)}))
reject('bool file size',lambda:changed('files',{'root.dat':dict(bytes=True,sha256='5'*64)}))
reject('empty file name',lambda:changed('files',{'':dict(bytes=20003,sha256='5'*64)}))
reject('active service',lambda:changed('unit_after',{**unit,'MainPID':'123','ActiveState':'active'}))
reject('active owner',lambda:changed('owners',[{**owners[0],'exact_alive':True}]))
reject('missing owner',lambda:changed('owners',[]))
reject('unknown receipt field',lambda:copy_binding({**receipt,'accepted':True},binding))
result=dict(status='PASS_CHANGED_BACKUP_BINDING_FIXTURES_ONLY',positive_groups=2,rejects=rejects,
 template_path=str(Path(args.release_template)),fixture_policy_and_identity_and_copy=True,
 journal_constructor=False,native_filesystem=False,copy_executed=False,manager_launched=False,
 capture=False,production_policy_issued=False)
(out/'RESULT.json').open('x').write(json.dumps(result,indent=2))
print(json.dumps(dict(status=result['status'],positive_groups=2,rejects=len(rejects))))
