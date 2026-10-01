"""Changed local release contract checks; README_FIELD_LOCAL_RELEASE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from pathlib import Path
import json
import time
from datetime import datetime,timezone
p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
out=Path(args.output);out.mkdir(exist_ok=False)
me=psutil.Process()
(out/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
import sys
sys.dont_write_bytecode=True
import copy
from field_local_release_plan_v1 import (allocation,recording_state,next_recording,next_launch,
    recovery_decision,validate_release,validate_research_operation)
start=time.monotonic();rejects=[]
def reject(name,callback):
    try:callback()
    except (ValueError,RuntimeError,TypeError):rejects.append(name)
    else:raise AssertionError('Expected rejection: '+name)
a=allocation(2,3)
states={n:{} for n in a['recording_slots']}
assert next_recording(a,states)=='recording-01'
states['recording-01']={'RESERVED':{},'STARTED':{},'CLOSED':{}}
reject('closed without independent backup',lambda:next_recording(a,states))
states['recording-01']['BACKUP']={}
assert next_recording(a,states)=='recording-02'
states['recording-02']={'RESERVED':{},'FAILED':{}}
reject('failed live slot',lambda:next_recording(a,states))
states['recording-02']['PHYSICAL_CLOSURE']={}
reject('failed closed without backup',lambda:next_recording(a,states))
states['recording-02']['BACKUP']={}
assert recording_state(states['recording-02'])=='FAILED_PRESERVED_BACKED'
reject('failed slot never reusable',lambda:next_recording(a,states))
reject('backup before physical closure',lambda:recording_state({'RESERVED':{},'BACKUP':{}}))
launches={n:{} for n in a['launch_slots']};launches['launch-01']={'OWNER':{}}
reject('unclean launch blocks reopen',lambda:next_launch(a,launches))
launches['launch-01']['EXIT']={}
assert next_launch(a,launches)=='launch-02'
facts=dict(owner_identities_complete=True,active_owners=0,capture_closed=True,
           leases_free=True,unit_inactive=True,backup_verified=True,successful_application=False)
assert recovery_decision(**facts)=='FAILED_PRESERVED_BACKED'
for field,expected in [('owner_identities_complete','FENCED_IDENTITY_GAP'),('capture_closed','FENCED_ACTIVE'),('backup_verified','CLOSED_BACKUP_REQUIRED')]:
    altered={**facts,field:False};assert recovery_decision(**altered)==expected
limits=dict(device_bytes=31268536320,minimum_pi_free_bytes=5*1024**3,
 minimum_c_free_bytes=50*1024**3,minimum_g_free_bytes=75*1024**3,
 cpus=[2,3],cpu_percent=200,tasks=64,hard_as_bytes=768*1024**2,stack_bytes=1024**2,
 model_threads=1,gpu=False,initial_available_bytes=850*1024**2,stop_available_bytes=192*1024**2,
 child_seconds=300,child_soft_seconds=270,stop_grace_seconds=30,recording_audio_seconds=120,
 maximum_samples=2080000,batch_seconds=600,idle_launch_seconds=86400,automatic_capture=False,automatic_restart=False)
fixture=dict(schema='just-peachy.local-release-policy.v1',
 root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-local-release-v1',
 recording_roots=['/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-operator-sessions-v%d'%n for n in (1001,1002)],
 allocation=a,release_manifest_sha256='0'*64,installed_manifest_sha256='1'*64,
 mode_registry_sha256='2'*64,activation_plan_sha256='3'*64,
 measured_target_before_bytes=3_000_000,measured_host_before_bytes=5_000_000,
 measured_payload_before_bytes=12_000_000,
 combined_output_cap_bytes=8_000_000+a['combined_request_bytes'],
 total_payload_cap_bytes=12_000_000+a['combined_request_bytes'],limits=limits)
assert validate_release(fixture)==fixture
one=a['broker_allocation']
assert a['target_maximum_bytes']-a['metadata_maximum_bytes']==4*one['target_maximum_bytes']
assert a['host_maximum_bytes']-a['metadata_maximum_bytes']==2*one['host_maximum_bytes']
def change(field,value):
    f=copy.deepcopy(fixture);f[field]=value;return validate_release(f)
reject('output missing one reserved byte',lambda:change('combined_output_cap_bytes',fixture['combined_output_cap_bytes']-1))
reject('payload missing one reserved byte',lambda:change('total_payload_cap_bytes',fixture['total_payload_cap_bytes']-1))
reject('duplicate recording roots',lambda:change('recording_roots',[fixture['recording_roots'][0]]*2))
reject('nested broker root',lambda:change('recording_roots',[fixture['root']+'/recording-01',fixture['recording_roots'][1]]))
reject('bool recordings',lambda:allocation(True,3))
reject('launch allocation exhaustion',lambda:allocation(2,17))
reject('automatic restart silently enabled',lambda:change('limits',{**limits,'automatic_restart':True}))
reject('capture ceiling increased',lambda:change('limits',{**limits,'recording_audio_seconds':121}))
op=dict(issued_utc='2026-10-01T08:00:00+00:00',expires_utc='2026-10-01T08:10:00+00:00',purpose='LOCAL_RELEASE_QUALIFICATION')
assert validate_research_operation(op,datetime.fromisoformat('2026-10-01T08:05:00+00:00'))==op
reject('expired research operation',lambda:validate_research_operation(op,datetime.fromisoformat('2026-10-01T08:10:00+00:00')))
reject('idle lifetime not research extension',lambda:validate_research_operation({**op,'expires_utc':'2026-10-02T08:00:00+00:00'},datetime.fromisoformat('2026-10-01T08:05:00+00:00')))
reject('no production admission implementation',lambda:validate_research_operation({**op,'purpose':'MANUAL_USER'},datetime.fromisoformat('2026-10-01T08:05:00+00:00')))
elapsed=time.monotonic()-start
assert elapsed<20
result=dict(status='PASS_FINITE_RELEASE_CONTRACT_ONLY',positive_groups=3,rejects=rejects,
 fixture_receipts_and_census=True,native_filesystem=False,constructors=False,capture=False,
 production_policy_issued=False,persistent_runtime_accepted=False,allocation=a,elapsed_seconds=elapsed)
(out/'RESULT.json').open('x').write(json.dumps(result,indent=2))
print(json.dumps(dict(status=result['status'],positive_groups=3,rejects=len(rejects),elapsed_seconds=elapsed)))
