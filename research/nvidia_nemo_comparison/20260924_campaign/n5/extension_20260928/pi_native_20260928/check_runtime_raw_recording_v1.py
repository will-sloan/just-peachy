"""Focused packed-source/allocation check; README_RUNTIME_RAW_RECORDING_CHECK_V1.md."""
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
    from field_runtime_raw_recording_v2 import derive,derive_manager,RAW_SOURCE,raw_allocation
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
        directory=a.output/label;directory.mkdir();(directory/'source').mkdir()
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
        pcm=(routes.root/'source/RAW_MICROPHONES.s32le').read_bytes()
        used=len(data)//480*480;prefix=x._packed_prefix
        aligned=data[prefix:used-((used-prefix)%3)] & np.int32(-2)
        expected=aligned.reshape(-1,6)
        if pcm!=expected[:,2:].astype('<i4').tobytes():raise AssertionError('Physical channels reordered/lost')
        model=np.concatenate(audio)
        expected_model=expected[:,0].astype(np.float32)/np.float32(2147483648)*x._gain
        if not np.array_equal(model,expected_model) or native!=3*len(model):raise AssertionError('Processed/raw shared clock')
        return dict(label=label,frames=len(model),native_frames=native,prefix=prefix,tail=x._packed_tail_count,raw_sha256=hashlib.sha256(pcm).hexdigest())
    # Three capture alignment phases, with values encoding channel/order.
    base=np.arange(1200*6,dtype=np.int32).reshape(1200,6)*4
    packed=base.reshape(-1,2);marker=np.tile(np.array([0,1,1],np.int32),1200)
    packed=(packed & -2)|marker[:,None]
    for phase in range(3):observations.append(exercise(packed[phase:phase+2880],str(phase)))
    # Actual retained physical sample, read-only; no model/hardware/capture is invoked.
    evidence=json.loads((a.probe/'RESULT.json').read_bytes())
    physical=np.frombuffer((a.probe/'PACKED_S32LE.bin').read_bytes(),dtype='<i4').reshape(-1,2)
    observations.append(exercise(physical,'actual'))
    corrupt=packed[:960].copy();corrupt[6,1]^=1
    try:exercise(corrupt,'corrupt')
    except ValueError as exc:
        if 'marker' not in str(exc):raise
    else:raise AssertionError('Corrupt marker accepted')
    # Actual source route transformation compiles and retains exact original setters.
    route_node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LiveRoute')
    method=next(n for n in route_node.body if isinstance(n,ast.FunctionDef) and n.name=='apply')
    ns=dict(LiveAudioError=RuntimeError,re=__import__('re'))
    route_shell=ast.ClassDef(name='InstalledRoute',bases=[],keywords=[],body=[method],decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[route_shell],type_ignores=[])),str(a.installed/'app/live_audio.py'),'exec'),ns)
    live.LiveRoute=ns['InstalledRoute'];live.READBACKS=('AUDIO_MGR_OP_L','AUDIO_MGR_OP_R');live.LIVE_SETTABLE=frozenset(live.READBACKS)
    embedded['install_packed_route'](live)
    if 'AUDIO_MGR_OP_ALL' not in live.READBACKS or 'AUDIO_MGR_OP_ALL' not in live.LIVE_SETTABLE:raise AssertionError('Restoration snapshot missing')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Host scope expired')
    result=dict(status='PASS_CHANGED_PACKED_SOURCE_AND_ALLOCATION',observations=observations,marker_rejects=1,
        combined_allocation_bytes=actual['combined_request_bytes'],legacy_combined_bytes=legacy['combined_request_bytes'],
        changed=review['changed'],native_executed=False,model_executed=False)
    save('RESULT.json',result);print(json.dumps(dict(status=result['status'],groups=len(observations),marker_rejects=1)))
if __name__=='__main__':main()
