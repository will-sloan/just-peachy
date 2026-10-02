"""Focused packed-source/allocation check; README_RUNTIME_RAW_RECORDING_CHECK_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,hashlib,json,os,sys,time,types,math
from pathlib import Path
from datetime import datetime,timezone
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('bundle','manager','installed','probe','output','scope'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir()
    me=psutil.Process()
    def save(n,v):
        raw=json.dumps(v,sort_keys=True,allow_nan=False).encode()
        if len(raw)>65536:raise ValueError('Check receipt cap')
        with (a.output/n).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    scope=json.loads(a.scope.read_bytes())
    if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Host scope')
    from field_runtime_raw_recording_v3 import derive,derive_manager,RAW_SOURCE,raw_allocation
    common,review=derive(a.bundle.read_bytes())
    files={n:base64.b64decode(b) for n,b in json.loads(common)['files'].items()}
    manager={p.relative_to(a.manager).as_posix():p.read_bytes() for p in a.manager.rglob('*.py')}
    manager=derive_manager(manager)
    # Execute only the changed pure allocation modules, in a fresh isolated module map.
    names=['field_operator_session_plan_v1','field_operator_broker_layout_v2','field_local_release_plan_v2','field_runtime_policy_v3']
    for name in names:
        m=types.ModuleType(name);m.__file__='<raw-check:'+name+'>'
        sys.modules[name]=m
        exec(compile(manager['code/'+name+'.py'],m.__file__,'exec'),m.__dict__)
    actual=sys.modules['field_local_release_plan_v2'].allocation(4,16)
    # Independent arithmetic baseline recorded before the new reservation.
    if actual['combined_request_bytes']!=2988319424 or actual['target_maximum_bytes']!=1485771104 or actual['host_maximum_bytes']!=1502548320:raise AssertionError('Full four-copy raw allocation')
    legacy=sys.modules['field_runtime_policy_v3'].legacy_allocation(4,16)
    if legacy['combined_request_bytes']!=2453742272:raise AssertionError('Exact legacy allocation retained')
    # Real installed methods are extracted without importing installed application dependencies.
    os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
    import numpy as np
    raw=(a.installed/'app/live_audio.py').read_text(encoding='utf-8');tree=ast.parse(raw)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='XVFLiveSource')
    selected=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('__init__','_start_owned','read')]
    env=dict(np=np,math=math,time=time,threading=__import__('threading'),LiveConfig=object,
        LiveAudioError=RuntimeError,LiveGap=RuntimeError,
        LiveBlock=lambda *v,**kw:types.SimpleNamespace(audio=v[0],model_start_sample=v[1],native_start_frame=v[2],native_frames=v[3],resampler_delay_seconds=v[7],**kw))
    shell=ast.ClassDef(name='InstalledSource',bases=[],keywords=[],body=selected,decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[shell],type_ignores=[])),str(a.installed/'app/live_audio.py'),'exec'),env)
    live=types.SimpleNamespace(XVFLiveSource=env['InstalledSource'],time=time,math=math)
    embedded={};exec(compile(RAW_SOURCE,'<reviewed-raw-embedding>','exec'),embedded)
    # Factory's derived start/read must compile against the real installed source text.
    def routes_for(label):
        directory=a.output/label;directory.mkdir();(directory/'source').mkdir();(directory/'data').mkdir()
        class Group:
            def write(self,name,raw,append=False):
                with (directory/'source'/name).open('ab' if append else 'xb') as f:f.write(raw)
        return types.SimpleNamespace(root=directory,groups={'source':Group()},source=lambda n,v:None)
    observations=[]
    def exercise(data,label):
        routes=routes_for(label);Raw=embedded['raw_source_type'](env['InstalledSource'],live,routes)
        # Extract the exact new converter constructor through an intercepted startup boundary.
        start_src=__import__('inspect').getsource(env['InstalledSource']._start_owned)
        # PackedConverter is closed into the generated start namespace.
        Converter=Raw._start_owned.__globals__['PackedConverter']
        x=Raw.__new__(Raw)
        config=types.SimpleNamespace(tap='O0',block_frames=480)
        env['InstalledSource'].__init__(x,config)
        x._ring=np.empty((4,480,2),np.int32);x._frames=np.zeros(4,np.int32)
        for name in ('_native_start','_clock','_perf_clock'):setattr(x,name,np.zeros(4,np.int64))
        for name in ('_adc','_callback_current_time'):setattr(x,name,np.zeros(4,np.float64))
        x._capacity=4;x._packed_tail=np.empty((2,2),np.int32);x._packed_tail_count=0;x._packed_prefix=None
        x._converter=Converter(x);x._gain=np.float32(10**(3/20));x._route_ready=True;x._started=True
        x.stream=types.SimpleNamespace(active=True);x.sd=types.SimpleNamespace(CallbackAbort=RuntimeError)
        x._stream_start_perf_ns=time.perf_counter_ns()-10_000_000_000
        audio=[];native=0
        for offset in range(0,len(data)//480*480,480):
            block=data[offset:offset+480]
            x._callback(block,480,types.SimpleNamespace(inputBufferAdcTime=0,currentTime=0),False)
            out=x.read(0)
            if out.model_start_sample!=sum(len(z) for z in audio) or out.native_start_frame!=native or out.native_frames%3:raise AssertionError('Packed model/native continuity')
            native+=out.native_frames;audio.append(out.audio)
        x._converter.flush()
        pcm=(routes.root/'data/RAW_MICROPHONES.s32le').read_bytes()
        used=len(data)//480*480;prefix=x._packed_prefix
        aligned=data[prefix:used-((used-prefix)%3)] & np.int32(-2)
        expected=aligned.reshape(-1,6)
        if pcm!=expected[:,2:].astype('<i4').tobytes():raise AssertionError('Physical channels reordered/lost')
        model=np.concatenate(audio)
        expected_model=expected[:,0].astype(np.float32)/np.float32(2147483648)*x._gain
        if not np.array_equal(model,expected_model) or native!=3*len(model):raise AssertionError('Processed/raw shared clock')
        return dict(label=label,frames=len(model),native_frames=native,prefix=prefix,tail=x._packed_tail_count,raw_sha256=hashlib.sha256(pcm).hexdigest())
    # New audio-artifact writer only; V1 packing phases/marker reject are reused.
    physical=np.frombuffer((a.probe/'PACKED_S32LE.bin').read_bytes(),dtype='<i4').reshape(-1,2)
    observations.append(exercise(physical,'actual-artifact'))
    for name in ('field_live_layout_v2','field_live_layout_v3','field_live_paths_v1'):
        m=types.ModuleType(name);m.__file__='<raw-artifact-check:'+name+'>'
        sys.modules[name]=m;exec(compile(files['code/'+name+'.py'],m.__file__,'exec'),m.__dict__)
    layout=sys.modules['field_live_layout_v3'].specification()
    writer_source=files['code/field_sidecar_budget_v1.py'].decode()
    writer_tree=ast.parse(writer_source)
    selected=[n for n in writer_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FIELDS' for t in n.targets) or isinstance(n,ast.FunctionDef) and n.name=='validate']
    writer_env={};exec(compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),'<unchanged-sidecar-validate>','exec'),writer_env)
    for group in ('source','control','config','trace','failure','closure','telemetry'):
        entries=layout['groups'][group].values()
        writer_env['validate'](dict(maximum_bytes=sum(r['maximum_bytes'] for r in entries),
            maximum_file_bytes=max(r['maximum_bytes'] for r in entries),
            maximum_write_bytes=max(r['maximum_write_bytes'] for r in entries),
            maximum_files=len(layout['groups'][group]),minimum_free_bytes=5*1024**3))
    contract=sys.modules['field_live_paths_v1'].project('edge_guard_20000101T000000Z_00000000','0'*32,'1'*32,'2'*32,{'fixture.py':1})
    row=contract['paths']['data/RAW_MICROPHONES.s32le']
    if row!=dict(maximum_bytes=33280000,bucket='raw_microphones') or contract['buckets']['raw_microphones']!=dict(maximum_bytes=33280000,maximum_files=1):raise AssertionError('Independent raw artifact mapping')
    if 'RAW_MICROPHONES.s32le' in layout['groups']['source']:raise AssertionError('Audio still competes with metadata')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Host scope expired')
    result=dict(status='PASS_CHANGED_RAW_ARTIFACT_WRITER_AND_PHYSICAL_MAPPING',observations=observations,marker_rejects_reused_from_check1=1,
        combined_allocation_bytes=actual['combined_request_bytes'],legacy_combined_bytes=legacy['combined_request_bytes'],
        changed=review['changed'],native_executed=False,model_executed=False)
    save('RESULT.json',result);print(json.dumps(dict(status=result['status'],groups=len(observations),marker_rejects_reused_from_check1=1)))
if __name__=='__main__':main()
