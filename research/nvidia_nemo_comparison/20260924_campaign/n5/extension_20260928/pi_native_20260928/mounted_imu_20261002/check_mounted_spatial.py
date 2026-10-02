"""Changed-path geometry/display/IPC checks; commands and scope in README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse, hashlib, json, math, os, shutil, sys, time
from pathlib import Path
from types import SimpleNamespace


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();a.output.mkdir()
    def put(name, raw):
        if len(raw)>262144:raise ValueError('Bounded check output')
        with (a.output/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        assert (a.output/name).read_bytes()==raw
    me=psutil.Process()
    put('REGISTERED_OWNER.json',json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
    for drive,floor in [('C:/',50),('G:/',75)]:
        assert shutil.disk_usage(drive).free>=floor*1024**3+4*1024**2
    for name in ('check_mounted_spatial.py','mounted_spatial.py','derive_mounted_imu.py','README.md'):
        raw=Path(__file__).with_name(name).read_bytes();put(name+'.backup',raw);put(name+'.restore',raw)
    from mounted_spatial import BeamQueue,BeamReceiver,MOUNT,encoded,validate_block_metadata,saved_motion_policy
    from derive_mounted_imu import derive
    installed=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12')
    manifest=json.loads((installed/'RELEASE_MANIFEST.json').read_bytes())
    pins={r['path']:r for r in manifest['files']}
    sources={}
    for name in ('imu.py','live_spatial.py'):
        raw=(installed/'app'/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==pins['app/'+name]['sha256']
        sources[name]=raw;put(name+'.original',raw)
    outputs,review=derive(sources['imu.py'],sources['live_spatial.py'])
    for name,raw in outputs.items():put(name+'.prepared',raw);put(name+'.restore',raw)
    put('DERIVATION.json',encoded(review))
    sys.path[:0]=[str(installed),str(installed/'vendor')]
    def load(name):
        ns=dict(__name__='app.mounted_check_'+name[:-3],__package__='app',__file__=str(installed/'app'/name))
        exec(compile(outputs[name],'<changed-'+name+'>','exec'),ns)
        return ns
    imu=load('imu.py');spatial=load('live_spatial.py')
    motion=imu['RelativeMotion'](fixed_mount=True,compensate=True,mount={**MOUNT,'offset_verified':False})
    stamp=0.
    for _ in range(120):motion.update(stamp,(0.,0.,1.),(0.,0.,0.));stamp+=.02
    assert motion.valid
    for _ in range(100):motion.update(stamp,(0.,0.,1.),(0.,0.,-15.));stamp+=.02
    at=motion.last
    assert abs(motion.yaw+30)<1e-6
    corrected,weight=motion.transform(110.,at)
    assert abs(corrected-80)<1e-6 and weight>0
    assert abs(motion.to_device(80.,at)-110)<1e-6
    assert motion.to_device(80.,at+.151) is None
    assert motion.to_device(True,at) is None
    class MotionView:
        def snapshot(self):return {**motion.history[-1], 'compensation':True}
        def transform(self,angle,at):return motion.transform(angle,at)
        def to_device(self,angle,at):return motion.to_device(angle,at)
    config=SimpleNamespace(direction_max_age_sec=.5,minimum_spatial_reliability=.1,
        position_decay_sec=5.,max_tracks=4,location_learning_rate=.2)
    provider=spatial['LiveSpatialProvider']('O0',config,display=True,clock=lambda:at,motion=MotionView())
    provider.origin=at-1
    provider.live=SimpleNamespace(beam_diagnostics=SimpleNamespace(snapshot=lambda:{'state':'RUNNING'}))
    provider._fields={'AUDIO_MGR_SELECTED_AZIMUTHS':dict(values=[math.radians(110)]*2,started=at-.02,completed=at-.01)}
    provider._positions[1]=dict(track_id=1,label='Speaker_1',profile_id=None,angle_deg=80.,source_end_sec=1.,
        reliability=.8,motion_reference=(motion.frame_generation,motion.unsafe_generation))
    view=provider.snapshot()
    assert view['coordinate_frame']=='device' and len(view['arrows'])==2
    assert all(abs(r['angle_deg']-110)<1e-6 for r in view['arrows'])
    assert abs(view['associations'][0]['angle_deg']-110)<1e-6
    assert view['associations'][0]['reference_angle_deg']==80.
    # A translation-like force invalidates location, but not raw device arrows.
    motion.update(at+.02,(.4,0.,1.),(0.,0.,0.))
    view=provider.snapshot();assert not view['associations'] and len(view['arrows'])==2
    assert all(r['fresh'] for r in view['arrows'])
    assert motion.unsafe_generation==1 and motion.frame_generation==1
    class Sink:
        def __init__(self):self.rows=[];self.invalidations=0
        def receive(self,*row):self.rows.append(row)
        def invalidate_positions(self):self.invalidations+=1
    sink=Sink();queue=BeamQueue();receiver=BeamReceiver(sink)
    for i in range(3):queue.receive('AEC_AZIMUTH_VALUES',[1.,2.,None,0.],1.+i*.1,1.02+i*.1)
    assert not queue.drain(1.)['samples']
    packet=queue.drain(2.);assert receiver.accept(packet,2.)==3
    assert len(sink.rows)==3
    assert len(encoded(validate_block_metadata({'callback_perf_counter_ns':2000000000},packet)))<=2048
    rejects=0
    def reject(fn):
        nonlocal rejects
        try:fn()
        except (ValueError,TypeError):rejects+=1
        else:raise AssertionError('Expected rejection')
    reject(lambda:receiver.accept(packet,2.))
    reject(lambda:queue.receive('AEC_AZIMUTH_VALUES',[True,2.,None,0.],3.,3.1))
    reject(lambda:queue.receive('BAD',[1.],3.,3.1))
    reject(lambda:validate_block_metadata({'extra':'x'*2048},packet))
    # Whole packet validates before any callback, including its final sample.
    sink2=Sink();receiver2=BeamReceiver(sink2);bad=json.loads(encoded(packet));bad['samples'][-1][4]=10.
    reject(lambda:receiver2.accept(bad,2.));assert not sink2.rows
    q2=BeamQueue();r2=BeamReceiver(sink2)
    for i in range(65):q2.receive('AUDIO_MGR_SELECTED_AZIMUTHS',[1.,1.],i+1.,i+1.1)
    assert r2.accept(q2.drain(0.),0.)==0 and sink2.invalidations==1
    assert r2.accept(q2.drain(70.),70.)==1 and r2.sequence==65 and r2.dropped==64
    assert saved_motion_policy('file')['use_current_motion'] is False
    reject(lambda:saved_motion_policy('file',{'unbound':'pose'}))
    reject(lambda:saved_motion_policy('ambiguous'))
    result=dict(status='PASS_CHANGED_MOUNTED_DISPLAY_AND_TELEMETRY',positive_groups=5,rejections=rejects,
                runtime_installed=False,native_model_or_audio_run=False,derived=review['outputs'])
    put('RESULT.json',encoded(result));print(json.dumps(result))

if __name__=='__main__':main()
