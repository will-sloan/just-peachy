"""Independent real quiet-route/restart receipt reader. See README_REVIEW_NATIVE_QUIET_V2.md."""
import argparse
import base64
import hashlib
import json
import re
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    ap=argparse.ArgumentParser();ap.add_argument('--run-id',required=True);args=ap.parse_args()
    assert re.fullmatch(r'live-ready-user-\d{8}T\d{6}Z|xvf-restart-v[12]',args.run_id)
    out=PRIVATE/(args.run_id+'-evidence')
    x=remote('RUN='+repr(args.run_id)+'\n'+r'''
import os,json,hashlib,base64,subprocess,fcntl
from pathlib import Path
os.sched_setaffinity(0,{3});d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert a['address_space_max_bytes']==768*1024**2 and a['cpus']==[2,3]
owners=[]
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/n).read_text());t=ticks(o['pid']);assert not(o['boot_id']==boot and t==o['start_ticks'])
 assert o['admission_sha256']==sha(d/'ADMISSION.json');owners.append(dict(owner=o,observed_ticks=t,exact_alive=False))
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
assert sha(Path.home()/'JustPeachy/data/live_config.json')=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
with (Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as f:
 fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 fcntl.flock(f,fcntl.LOCK_UN)
u=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-'+RUN,'-p','MainPID','-p','ActiveState','-p','Result','-p','ExecMainStatus'],text=True).splitlines())
assert u['MainPID']=='0' and u['ExecMainStatus'] in ['0','1']
assert not list(d.rglob('*.wav')) and not list(d.rglob('*.npy'))
names=['ADMISSION.json','RESULT.json','OWNER.json','DISPATCH_OWNER.json','DISPATCH_RESULT.json']
if (d/'RESTART_INTENT.json').exists():names.append('RESTART_INTENT.json')
if (d/'MAINTENANCE_COMMAND.json').exists():names.append('MAINTENANCE_COMMAND.json')
print(json.dumps(dict(data={n:base64.b64encode((d/n).read_bytes()).decode() for n in names},bindings={n:sha(d/n) for n in names},owners=owners,unit=u,capture_closed=True,hardware_lease_free=True,boot_id=boot)))
''')
    raw={n:base64.b64decode(v) for n,v in x.pop('data').items()}
    for n,v in raw.items():assert hashlib.sha256(v).hexdigest()==x['bindings'][n]
    r=json.loads(raw['RESULT.json']);a=json.loads(raw['ADMISSION.json']);dispatch=json.loads(raw['DISPATCH_RESULT.json'])
    assert dispatch['exit_code']==int(x['unit']['ExecMainStatus'])==json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']
    assert not r['audio_saved'] and not r['models_loaded']
    result=dict(bindings=x['bindings'],closed_owners=x['owners'],unit=x['unit'],capture_closed=True,hardware_lease_free=True,original_app_config_install_unchanged=True,audio_saved=False,models_loaded=False,accuracy_scored=False,live_B01_qualified=False)
    if a['mode']=='reset':
        assert dispatch['exit_code']==0 and r['before']==r['after'] and r['before']['version']==[3,2,1]
        assert 'intdev-lr48-lin-i2c' in r['before']['build']
        assert not r['capture_opened'] and r['hardware_lease_released']
        assert all(v['command'] in ('VERSION','BLD_MSG') and not v['arguments'] for v in r['commands'])
        intent=json.loads(raw['RESTART_INTENT.json']);assert intent['command']=='TEST_CORE_BURN' and intent['arguments']==[0]
        if args.run_id=='xvf-restart-v1':
            assert r['restart_reply_error']=='LiveAudioError: Command is outside the live adapter allowlist'
            assert 'MAINTENANCE_COMMAND.json' not in raw
            result.update(status='PRESERVED_RESTART_V1_NOT_SENT_ALLOWLIST_REJECTION',restart_sent=False,terminal_success_not_accepted=True,DSP_processing_recovered=False)
        else:
            assert a['maintenance_restart_explicitly_approved'] is True
            command=json.loads(raw['MAINTENANCE_COMMAND.json']);assert command==r['maintenance_command']
            assert command['argv']==['/home/peachyprototype/JustPeachy/tools/native_xvf_usb/bin/xvf_host','-u','i2c','TEST_CORE_BURN','0']
            result.update(status='PASS_SINGLE_MAINTENANCE_SEND_FIRMWARE_READBACK_ONLY' if command['exit_code']==0 else 'PRESERVED_MAINTENANCE_SEND_OUTCOME_UNCERTAIN',restart_exit_code=command['exit_code'],DSP_processing_recovered=False,volatile_state_restored=False)
    else:
        assert a['mode']=='user' and a['capture'] and a['physically_ready_attested']
        probe=r['probe'];stop=probe['stop_receipt'];integrity=probe['integrity']
        assert stop['status']['finished'] and not stop['errors'] and probe['lease_released'] and not probe.get('stop_failures')
        assert integrity['restoration_ok'] and not integrity['restoration_issues']
        if r['status']=='USER_QUIET_ROUTE_COLLECTED_REQUIRES_REVIEW':
            assert dispatch['exit_code']==0 and integrity['ok'] and probe['status']=='SOURCE_COUNTS_COLLECTED_REQUIRES_REVIEW'
            assert probe['samples']==192000 and probe['native_frames']==576000 and probe['blocks']==1200
            meta=probe['metadata'];route=meta['route'];assert meta['actual_stream_rate']==48000 and meta['resampler_delay_seconds']==.001
            assert route['control_protocol']=='i2c' and route['tap']=='O0' and route['host_gain_db']==3. and route['channel_index']==0
            assert stop['status']['converted_samples']==192000 and stop['status']['dropped_frames']==0 and not stop['status']['fault']
            assert route['before']['VERSION']==[3,2,1] and route['before']['AEC_MIC_ARRAY_TYPE']==[1] and route['before']['AEC_NUM_MICS']==[4]
            assert all(v=='RESTORED' for v in stop['route_restoration'].values())
            result.update(status='PASS_REAL_QUIET_I2S_SOURCE_AND_RESTORATION_ONLY',samples=192000,native_frames=576000,route=route,integrity=integrity,maximum_absolute_amplitude=probe['maximum_absolute_amplitude'],elapsed_seconds=probe['elapsed_seconds'],peak_rss_bytes=r['peak_rss_bytes'],acoustic_clock_calibration=False)
        else:
            assert dispatch['exit_code']==1 and probe['samples']==probe['native_frames']==0
            assert integrity['reasons']==['SOURCE_NEVER_STARTED']
            assert all(not v['arguments'] for v in stop['commands'])
            result.update(status='PRESERVED_REAL_ROUTE_START_FAILURE_CLEANLY_CLOSED',error=probe['error'],priming_frames=stop['status']['priming_frames_discarded_before_route_verified'],accepted_samples=0,device_setters=0)
    for n,v in raw.items():
        with (out/n).open('xb') as f:f.write(v)
    with (out/'REVIEW.json').open('x') as f:json.dump(result,f,indent=2)
    remote('RUN='+repr(args.run_id)+'\nREVIEW='+repr(result)+'\n'+"import json\nfrom pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/RUN/'REVIEW.json'\nwith p.open('x') as f:json.dump(REVIEW,f,indent=2)\nprint(json.dumps({'written':True}))")
    print(json.dumps({k:v for k,v in result.items() if k not in ('bindings','closed_owners','route','integrity')}))


if __name__=='__main__':main()
