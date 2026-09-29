"""Independent native mock-route reader. See README_REVIEW_LIVE_READY_V1.md."""
import base64
import hashlib
import json
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    out = PRIVATE/'live-ready-mock-v1-evidence'
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code'] == 0
    x = remote(r'''
import os,json,hashlib,base64,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3})
d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-ready-mock-v1')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert a['mode']=='mock' and not a['capture'] and not a['physically_ready_attested']
assert a['address_space_max_bytes']==768*1024**2 and a['cpus']==[2,3] and a['cpu_quota_percent']==200
owners=[]
for name in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/name).read_text());t=ticks(o['pid'])
 assert not(o['boot_id']==boot and o['start_ticks']==t)
 assert o['admission_sha256']==sha(d/'ADMISSION.json')
 owners.append(dict(owner=o,observed_ticks=t,exact_alive=False))
u=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-live-ready-mock-v1','-p','MainPID','-p','ActiveState','-p','Result','-p','ExecMainStatus'],text=True).splitlines())
assert u['MainPID']=='0' and u['Result']=='success' and u['ExecMainStatus']=='0'
assert ticks(1013)==569 and ticks(1130)==607
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/data/live_config.json')=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
assert sha(Path.home()/'JustPeachy/install/current.json')=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
names=['ADMISSION.json','RESULT.json','OWNER.json','DISPATCH_OWNER.json','DISPATCH_RESULT.json']
print(json.dumps(dict(data={n:base64.b64encode((d/n).read_bytes()).decode() for n in names},bindings={n:sha(d/n) for n in names},units=u,owners=owners,capture_closed=True)))
''')
    raw = {n:base64.b64decode(v) for n,v in x.pop('data').items()}
    for n,v in raw.items(): assert hashlib.sha256(v).hexdigest() == x['bindings'][n]
    r = json.loads(raw['RESULT.json'])
    dispatch = json.loads(raw['DISPATCH_RESULT.json'])
    assert dispatch['exit_code'] == 0 and dispatch['lock_held_through_service']
    assert r['status'] == 'MOCK_LIVE_ROUTE_GUARDS_COLLECTED_REQUIRES_REVIEW'
    assert not any(r[k] for k in ['real_capture','audio_saved','models_loaded','actual_device_opened'])
    expected = ['consent_required_before_lease','O0','O1','lost_reply','firmware','active_failed_close_retains_lease_until_retry']
    assert [c['name'] for c in r['cases']] == expected
    rows = []
    for c in r['cases']:
        assert c['pass_case']
        if 'probe' not in c:
            rows.append(dict(name=c['name'],scope='source-bound contract assertion'))
            continue
        p = c['probe']; stop = p['stop_receipt']; integrity = p['integrity']
        assert c['mocked_only'] and c['restored_exact'] and p['lease_released']
        assert stop['status']['finished'] and not stop['errors'] and not p.get('stop_failures')
        assert integrity['restoration_ok'] and not integrity['restoration_issues']
        assert all(v == 'RESTORED' for v in stop['route_restoration'].values())
        if c['name'] in ['O0','O1']:
            assert p['status']=='SOURCE_COUNTS_COLLECTED_REQUIRES_REVIEW' and integrity['ok']
            assert (p['samples'],p['native_frames'],p['blocks']) == (480,1440,3)
            assert stop['status']['converted_samples']==480 and stop['status']['raw_frames']==1440
            assert stop['status']['dropped_frames']==0 and stop['status']['pending_raw_blocks']==0
            route=p['metadata']['route']; index=0 if c['name']=='O0' else 1
            assert route['channel_index']==index and route['control_protocol']=='i2c'
            assert route['native_rate']==48000 and route['model_rate']==16000 and route['render_streams']==0
            assert route['host_gain_db']==(3.0 if index==0 else 0.0)
            amplitude=.1*10**(3/20) if index==0 else .2
            assert amplitude*.9<=p['maximum_absolute_amplitude']<amplitude*1.2
            assert set(stop['route_restoration'])==set(route['changed'])
            # Each reversed setter restores the exact pre-route value.
            for name in route['changed']:
                assert [v for n,v in stop['commands'] if n==name][-1]==route['before'][name]
        else:
            assert p['status']=='FAILED_PRESERVED' and p['samples']==p['native_frames']==0
            assert integrity['reasons']==['SOURCE_NEVER_STARTED']
            if c['name']=='lost_reply':
                assert 'response lost' in p['error']
                assert stop['route_restoration']['AUDIO_MGR_MIC_GAIN']=='RESTORED'
                assert ['AUDIO_MGR_MIC_GAIN',[1]] in stop['commands']
            else:
                assert 'firmware' in p['error'] and not stop['commands']
        rows.append(dict(name=c['name'],samples=p['samples'],native_frames=p['native_frames'],restoration_ok=True,lease_released=True))
    review=dict(status='PASS_NATIVE_MOCK_I2S_ROUTE_GUARDS_ONLY',bindings=x['bindings'],closed_owners=x['owners'],units=x['units'],cases=rows,peak_rss_bytes=r['peak_rss_bytes'],actual_capture=False,actual_hardware_route_qualified=False,real_speech_qualified=False)
    for n,v in raw.items():
        with (out/n).open('xb') as f:f.write(v)
    with (out/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(review,f,indent=2)
    remote('REVIEW='+repr(review)+'\n'+"from pathlib import Path\nimport json\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-ready-mock-v1/REVIEW.json')\nwith p.open('x') as f:json.dump(REVIEW,f,indent=2)\nprint(json.dumps({'written':True}))")
    print(json.dumps(dict(status=review['status'],cases=len(rows),peak_rss_mib=r['peak_rss_bytes']/1024**2)))


if __name__=='__main__':main()
