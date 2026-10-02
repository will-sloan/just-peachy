"""Back up and prepare the mounted common runtime capsule; see README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,base64,hashlib,json,os,shutil,time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir();me=psutil.Process();deadline=time.monotonic()+90
    def put(name,raw,maximum=1048576):
        if len(raw)>maximum or time.monotonic()>deadline:raise ValueError('Bounded preparation')
        with (a.output/name).open('xb') as f:
            if f.write(raw)!=len(raw):raise OSError('Short source copy')
            f.flush();os.fsync(f.fileno())
        if (a.output/name).read_bytes()!=raw:raise IOError('Readback')
    def save(name,v):put(name,json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    for drive,floor in [('C:/',50),('G:/',75)]:
        assert shutil.disk_usage(drive).free>=floor*1024**3+4*1024**2
    for name in ('prepare_runtime_motion_v3.py','bind_runtime_motion_v3.py','mounted_spatial.py','README.md'):
        raw=Path(__file__).with_name(name).read_bytes();put(name+'.backup',raw);put(name+'.restore',raw)
    b=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
    integration=b/'imu-integration-20261002';check=integration/'changed-check-v1'
    assert json.loads((check/'RESULT.json').read_bytes())['status']=='PASS_CHANGED_MOUNTED_DISPLAY_AND_TELEMETRY'
    sources={n:(check/(n+'.prepared')).read_bytes() for n in ('imu.py','live_spatial.py')}
    originals={n:(check/(n+'.original')).read_bytes() for n in sources}
    pins=json.loads((check/'DERIVATION.json').read_bytes())
    for name,raw in sources.items():
        assert hashlib.sha256(raw).hexdigest()==pins['outputs'][name]['sha256']
        assert raw==(check/(name+'.restore')).read_bytes()
    config=json.loads((integration/'mount-save-v1/RESULT.json').read_bytes())
    assert config['mount_configuration_saved'] and config['sensor_initialized'] is False
    config_sha=config['files']['data/imu_config.json']['sha256']
    relative='field-runtime-v23-profiles/COMMON_BUNDLE.json'
    raw=(b/'field-runtime-v23-install/stage-restore'/relative).read_bytes()
    assert raw==(b/'field-runtime-v23-install/stage-backup'/relative).read_bytes()
    from bind_runtime_motion_v3 import derive
    packed,review=derive(raw,sources,originals,config_sha,Path(__file__).with_name('mounted_spatial.py').read_bytes())
    put('COMMON_BUNDLE.json',packed);put('COMMON_BUNDLE.restore.json',packed);save('REVIEW.json',review)
    # Independently decode and compile every member from the written restore.
    restored=json.loads((a.output/'COMMON_BUNDLE.restore.json').read_bytes())
    decoded={n:base64.b64decode(v,validate=True) for n,v in restored['files'].items()}
    assert restored['manifest']['files']==[dict(path=n,bytes=len(r),sha256=hashlib.sha256(r).hexdigest()) for n,r in sorted(decoded.items())]
    for name,raw in decoded.items():
        if name.endswith('.py'):compile(raw,name,'exec')
    save('SOURCE_CLOSED.json',dict(status='PREPARED_ONLY',new_capsule_bytes=len(packed),
        new_code_bytes=review['code_bytes'],independent_restore_verified=True,unchanged_cardinality=64,
        mount_config_sha256=config_sha,native_runtime_executed=False))
    print(json.dumps(review))

if __name__=='__main__':main()
