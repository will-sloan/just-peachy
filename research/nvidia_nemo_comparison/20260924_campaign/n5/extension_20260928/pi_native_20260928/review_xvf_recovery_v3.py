"""Independent one-shot recovery and backup reader; README_REVIEW_XVF_RECOVERY_V3.md."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path,PurePosixPath
import psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
from dispatch_b01_stack_v2 import SSH


def main():
    psutil.Process().cpu_affinity([14]);out=PRIVATE/'xvf-recovery-v3-evidence'
    x=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import fcntl,hashlib,json,os,resource,signal,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2);signal.alarm(60)
d=Path(ROOT)/'xvf-recovery-v3'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=read(d/'ADMISSION.json');v=read(d/'RESULT.json');di=read(d/'DISPATCH_RESULT.json');e=read(d/'LIVE_ENVELOPE.json')
assert v['status']=='SINGLE_MAINTENANCE_SEND_FIRMWARE_READBACK_ONLY' and di['exit_code']==0 and not di['memory_guard'] and not di['log_overflow']
assert a['capture']==v['capture_opened']==False and not v['models_loaded'] and not v['volatile_state_restored']
assert a['maximum_restart_commands']==v['restart_commands']==1 and v['hardware_lease_released']
assert read(d/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')['pi_changes_authorized'] and sha(d/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')==a['authority_sha256']
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1048576]*2 and e['affinity']==[2,3]
pr=e['properties'];assert pr['LoadState']=='loaded' and pr['ActiveState']=='active' and int(pr['MainPID'])==e['owner']['pid']
assert int(pr['LimitAS'])==768*1024**2 and int(pr['LimitSTACK'])==1048576 and pr['TasksMax']=='64' and pr['RuntimeMaxUSec']=='5min' and pr['TimeoutStopUSec']=='10s' and int(pr['LimitFSIZE'])==8*1024**2
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
assert sha(a['tool'])==sha(d/'XVF_HOST_BACKUP')==a['tool_sha256']
for name,key in [('LIVE_CONFIG_BACKUP.json','live_config_sha256'),('INSTALL_BACKUP.json','install_sha256')]:assert sha(d/name)==a[key]
ack=read(d/'HOST_BACKUP_VERIFIED.json');assert ack['verified']
for name,row in ack['files'].items():assert sha(d/name)==row['sha256'] and (d/name).stat().st_size==row['bytes']
prior=read(a['prior_failure']);assert sha(a['prior_failure'])==a['prior_failure_sha256'] and prior['metadata']['stream_start_return_perf_counter_ns']>0 and prior['status']['converted_samples']==0
assert any(c['command']=='AEC_MIC_ARRAY_TYPE' and c['exit_code']==255 and not c['arguments'] for c in prior['commands'])
commands=[read(p) for p in sorted(d.glob('COMMAND_*.json'))];assert commands==v['commands'] and len(commands)==6
assert [c['argv'][3:] for c in commands]==[['VERSION'],['BLD_MSG'],['AEC_MIC_ARRAY_TYPE'],['TEST_CORE_BURN','0'],['VERSION'],['BLD_MSG']]
assert all(c['argv'][:3]==[a['tool'],'-u','i2c'] and not c['timeout'] for c in commands)
assert [c['exit_code'] for c in commands]==[0,0,255,0,0,0]
assert all(c['started_ns']<c['ended_ns']<=u['started_ns'] for c,u in zip(commands,commands[1:]))
assert all(c['ended_ns']-c['started_ns']<2_500_000_000 for c in commands)
assert commands[4]['started_ns']-commands[3]['ended_ns']>=2_000_000_000
assert 'Resource could not respond' in commands[2]['stderr'] and v['current_probe']==commands[2] and v['maintenance_command']==commands[3]
assert commands[0]['stdout'].split()==commands[4]['stdout'].split()==['VERSION','3','2','1']
assert commands[1]['stdout']==commands[5]['stdout'] and 'intdev-lr48-lin-i2c' in commands[1]['stdout']
assert v['after']==v['before'] and v['current_readback_without_audio_loop'] and v['prior_actual_stream_fault_bound']
intent=read(d/'RESTART_INTENT.json');assert intent['argv']==commands[3]['argv'] and commands[2]['ended_ns']<=intent['monotonic_ns']<=commands[3]['started_ns']
assert intent['maximum_sends']==1 and not intent['volatile_state_restorable'] and intent['prior_failure_sha256']==a['prior_failure_sha256']
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
owners=list(d.glob('*OWNER.json'));assert len(owners)==2
for p in owners:
 o=read(p);assert o['boot_id']==boot and ticks(o['pid'])!=o['start_ticks']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
for p in [d.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in d.iterdir() if p.is_file()};assert len(files)==len(list(d.iterdir()))
total=sum(row['bytes'] for row in files.values());assert total<a['target_output_max_bytes']==8*1024**2
review=dict(status='PASS_CONDITIONAL_SINGLE_MAINTENANCE_SEND_FIRMWARE_READBACK_ONLY',single_command_verified=True,firmware_readbacks_unchanged=True,
 prior_active_stream_failure_bound=True,current_closed_stream_probe_failure_verified=True,backup_before_send_verified=True,volatile_state_restored=False,
 microphone_function_qualified=False,live_B01_qualified=False,capture_opened=False,models_loaded=False,actual_envelope_verified=True,
 natural_exit_code=0,exact_owners_closed=2,baseline_unchanged=True,capture_closed=True,leases_free=True,elapsed_seconds=v['elapsed_seconds'],peak_rss_bytes=v['peak_rss_bytes'],
 target_output_bytes=total,combined_output_allowance_bytes=a['output_max_bytes'],bindings={n:sha(d/n) for n in ['ADMISSION.json','RESULT.json','RESTART_INTENT.json','COMMAND_04.json']})
print(json.dumps(dict(review=review,files=files)))
''')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    before=json.loads((out/'BEFORE_BACKUP.json').read_text())
    for name,row in before.items():
        raw=(out/'before'/name).read_bytes();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']==x['files'][name]['sha256']
    raw=subprocess.check_output(SSH+['tar -C '+REMOTE+'/xvf-recovery-v3 -cf - .'],timeout=60)
    target=out/'target';target.mkdir();seen=set()
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tar:
        for member in tar:
            if member.isdir():assert member.name=='.';continue
            assert member.isfile() and member.name.startswith('./');name=member.name[2:]
            assert '/' not in name and '\\' not in name and name in x['files'] and name not in seen
            value=tar.extractfile(member).read();row=x['files'][name]
            assert len(value)==row['bytes'] and hashlib.sha256(value).hexdigest()==row['sha256']
            with (target/name).open('xb') as f:f.write(value)
            assert hashlib.sha256((target/name).read_bytes()).hexdigest()==row['sha256'];seen.add(name)
    assert seen==set(x['files'])
    total=x['review']['target_output_bytes']+sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert total+128*1024<x['review']['combined_output_allowance_bytes']
    x['review'].update(backup_verified=True,backup_files=len(seen),combined_stage_backup_bytes=total)
    for name,value in [('BACKUP.json',x['files']),('REVIEW.json',x['review'])]:
        with (out/name).open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps(x['review']))


if __name__=='__main__':main()
