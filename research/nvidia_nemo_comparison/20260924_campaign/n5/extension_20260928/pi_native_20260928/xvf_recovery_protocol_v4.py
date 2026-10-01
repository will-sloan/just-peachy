"""Conditional single maintenance operation; README_XVF_RECOVERY_V4.md."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time


def save(path,value):
    raw=json.dumps(value,indent=2).encode()
    assert len(raw)<128*1024
    with Path(path).open('xb') as f:
        f.write(raw);f.flush()
        import os
        os.fsync(f.fileno())


def run(root,a):
    authority=json.loads((root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json').read_text())
    assert authority['pi_changes_authorized'] and not a['capture'] and a['maximum_restart_commands']==1
    tool=Path(a['tool']);commands=[]
    with tool.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==a['tool_sha256']
    prior=json.loads(Path(a['prior_failure']).read_text())
    assert any(x['command']=='AEC_MIC_ARRAY_TYPE' and x['exit_code']==255 for x in prior['commands'])
    assert prior['metadata']['stream_start_return_perf_counter_ns']>0 and prior['status']['converted_samples']==0
    for original,backup in [(tool,root/'XVF_HOST_BACKUP'),(Path.home()/'JustPeachy/data/live_config.json',root/'LIVE_CONFIG_BACKUP.json'),(Path.home()/'JustPeachy/install/current.json',root/'INSTALL_BACKUP.json')]:
        assert original.read_bytes()==backup.read_bytes()
    assert json.loads((root/'HOST_BACKUP_VERIFIED.json').read_text())['verified']
    def command(name,args=()):
        from datetime import datetime,timezone
        assert datetime.now(timezone.utc).timestamp()+5<datetime.fromisoformat(a['expires_utc']).timestamp() and len(commands)<6
        assert (name,args) in [('VERSION',()),('BLD_MSG',()),('AEC_MIC_ARRAY_TYPE',()),('TEST_CORE_BURN',('0',))]
        argv=[str(tool),'-u','i2c',name,*args];start=time.monotonic_ns()
        try:
            cp=subprocess.run(argv,cwd=tool.parent,capture_output=True,timeout=2)
            assert len(cp.stdout)+len(cp.stderr)<64*1024
            value=dict(argv=argv,exit_code=cp.returncode,stdout=cp.stdout.decode('utf-8','replace'),stderr=cp.stderr.decode('utf-8','replace'),started_ns=start,ended_ns=time.monotonic_ns(),timeout=False)
        except subprocess.TimeoutExpired:
            value=dict(argv=argv,exit_code=None,timeout=True,started_ns=start,ended_ns=time.monotonic_ns(),may_have_been_sent=True)
        commands.append(value);save(root/('COMMAND_%02d.json'%len(commands)),value)
        return value
    def firmware():
        v=command('VERSION');b=command('BLD_MSG')
        assert not v['timeout'] and not b['timeout'] and v['exit_code']==b['exit_code']==0
        assert v['stdout'].split()==['VERSION','3','2','1'] and 'intdev-lr48-lin-i2c' in b['stdout']
        return dict(version=v['stdout'],build=b['stdout'])
    result=dict(status='FAILED_PRESERVED',capture_opened=False,models_loaded=False,restart_commands=0,volatile_state_restored=False,prior_actual_stream_fault_bound=True,current_readback_without_audio_loop=True)
    with (Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
            before=firmware();probe=command('AEC_MIC_ARRAY_TYPE')
            result.update(before=before,current_probe=probe)
            if not probe['timeout'] and probe['exit_code']==0:
                result['status']='NO_RESTART_CURRENT_CONTROL_READABLE'
            else:
                assert not probe['timeout'] and probe['exit_code']==255 and 'Resource could not respond' in probe['stderr']
                save(root/'RESTART_INTENT.json',dict(argv=[str(tool),'-u','i2c','TEST_CORE_BURN','0'],prior_failure_sha256=a['prior_failure_sha256'],before=before,current_probe=probe,monotonic_ns=time.monotonic_ns(),maximum_sends=1,volatile_state_restorable=False))
                result['restart_commands']=1
                reply=command('TEST_CORE_BURN',('0',));result['maintenance_command']=reply
                # An uncertain send is a final failure, never another send.
                assert not reply['timeout'] and reply['exit_code']==0,'Maintenance outcome uncertain or unsuccessful; no retry'
                time.sleep(2)
                after=firmware();assert after==before
                result.update(status='SINGLE_MAINTENANCE_SEND_FIRMWARE_READBACK_ONLY',after=after)
            assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
        except BaseException as exc:result['error']=type(exc).__name__+': '+str(exc)
        finally:result['commands']=commands
    result['hardware_lease_released']=True
    return result
