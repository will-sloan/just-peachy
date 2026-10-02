"""Version23 -> mounted-motion common capsule, no deployment; see README.md."""
import base64
import hashlib
import json
import zlib
from pathlib import Path

INPUT_SHA='addbefdf6e6d99cf98081f4830d59ff1f233754c90531b4818195d3246db51a0'

CONTROLLER_HELPER = '''
def _bind_mounted_runtime(base, manifest):
    import base64, zlib, hashlib
    from app import imu as imu_module, live_spatial as spatial_module
    from app import seats as seats_module
    for module, relative in ((imu_module,'app/imu.py'),(spatial_module,'app/live_spatial.py'),
                              (seats_module,'app/seats.py')):
        if Path(module.__file__).resolve()!=base/relative or sha(base/relative)!=manifest[relative]['sha256']:
            raise ValueError('Pinned installed motion source required')
    bound={}
    for name, module in (('imu.py',imu_module),('live_spatial.py',spatial_module)):
        item=_MOUNTED_SOURCES[name]
        if sha(base/'app'/name)!=item['original_sha256']:
            raise ValueError('Reviewed motion derivation input changed')
        data=zlib.decompress(base64.b64decode(item['compressed'],validate=True))
        if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise ValueError('Embedded motion derivative changed')
        namespace=dict(module.__dict__)
        exec(compile(data,'<mounted-runtime:'+name+'>','exec'),namespace)
        bound[name]=namespace
    spatial_module.LiveSpatialProvider=bound['live_spatial.py']['LiveSpatialProvider']
    # Seat modes inherit the same display/reference split. Their existing
    # assignment, invalidation and voice rules remain in the installed class.
    # Preserve SeatSpatialProvider.snapshot's seat validity/warning extension.
    seats_module.LiveSpatialProvider.snapshot=spatial_module.LiveSpatialProvider.snapshot
    config_path=Path('/home/peachyprototype/JustPeachy/data/imu_config.json')
    if config_path.is_symlink() or config_path.stat().st_size>4096 or sha(config_path)!=_MOUNTED_CONFIG_SHA:
        raise ValueError('Confirmed mounted sensor configuration changed')
    config=json.loads(config_path.read_bytes())
    library=Path(config['library'])
    if library!=Path('/home/peachyprototype/JustPeachy/tools/bmi270/libpeachy_bmi270.so') or library.is_symlink() or library.stat().st_size!=142264 or sha(library)!='d1eb90a5a4f1f98674e6483bda7711ed7df610fe0fe5bef7845de580b7ce7e28':
        raise ValueError('Existing native BMI270 library changed')
    if not config['fixed_mount'] or not config['rotation_compensation']:
        raise ValueError('Confirmed fixed mount and rotation assistance required')
    class ExistingIMULease:
        def __init__(self,path):
            self.path=Path(path);self.handle=None
        def acquire(self):
            import fcntl,stat
            if self.path!=Path('/home/peachyprototype/JustPeachy/data/imu.lock') or self.path.is_symlink() or not stat.S_ISREG(self.path.stat().st_mode):
                raise ValueError('Existing exact IMU lease required')
            handle=self.path.open('rb')
            try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BaseException:handle.close();raise
            self.handle=handle;return self
        def close(self):
            import fcntl
            if self.handle is not None:
                try:fcntl.flock(self.handle,fcntl.LOCK_UN)
                finally:self.handle.close();self.handle=None
    bound['imu.py']['DeviceLease']=ExistingIMULease
    return bound['imu.py']['BMI270Worker'],config
'''

PIPE_HELPER = '''
class _MountedSpatialSink:
    def __init__(self, provider, diagnostic):
        self.provider,self.diagnostic=provider,diagnostic
    def invalidate_positions(self):
        if self.provider is not None:self.provider.invalidate_positions()
    def receive(self,command,values,started,completed):
        d=self.diagnostic
        with d._lock:
            d._fields[command]=dict(values=list(values),request_started_monotonic_sec=started,
                                    received_monotonic_sec=completed)
            d._state='RUNNING';d._counts['successful_queries']+=1
        if self.provider is not None:self.provider.receive(command,values,started,completed)

def _mounted_pose_at(worker,callback):
    if worker is None:return None
    with worker.lock:
        row=next((r for r in reversed(worker.motion.history) if r['at']<=callback),None)
        if row is None or callback-row['at']>.15:return None
        value=dict(row)
        value.update(clock='host_monotonic_receipt',absolute_position_available=False,
                     compensation=worker.motion.compensate,config_sha256=_MOUNTED_CONFIG_SHA,
                     imu_cpu_seconds=worker.cpu_seconds,imu_elapsed_sec=worker.clock()-worker.started if worker.started else 0.,
                     imu_samples=worker.samples)
        return value
'''


DEBUG_METHODS = '''
        def _toggle_motion_debug(self):
            import tkinter as tk
            if getattr(self,'_motion_debug',None) is None:
                self._motion_debug=tk.Canvas(self.root,width=78,height=88,bg='#20242a',highlightthickness=1,highlightbackground='#777777')
                self._motion_debug.bind('<Button-1>',self._motion_debug_zero)
                self._motion_debug_zero_value=0.;self._motion_debug_last=-1.
            self._motion_debug_visible=not getattr(self,'_motion_debug_visible',False)
            if self._motion_debug_visible:
                self._motion_debug.place(relx=1.,x=-4,y=4,anchor='ne');self.root.tk.call('raise',self._motion_debug._w)
            else:self._motion_debug.place_forget()
        def _motion_debug_zero(self,event=None):
            motion=self.snapshot.get('motion') or {}
            if motion.get('valid'):
                self._motion_debug_zero_value=motion['yaw_deg'];self._motion_debug_last=-1.
                self._draw_motion_debug()
        def _draw_motion_debug(self):
            if not getattr(self,'_motion_debug_visible',False):return
            import math,time
            now=time.monotonic()
            if now-getattr(self,'_motion_debug_last',-1.)<.1:return
            self._motion_debug_last=now
            motion=self.snapshot.get('motion') or {};canvas=self._motion_debug
            canvas.delete('all')
            valid=motion.get('valid') is True
            angle=math.radians(-(motion.get('yaw_deg',0.)-self._motion_debug_zero_value)) if valid else 0.
            c,s=math.cos(angle),math.sin(angle)
            def point(x,y):return 39+x*c-y*s,33+x*s+y*c
            corners=[point(x,y) for x,y in ((-14,-23),(14,-23),(14,23),(-14,23))]
            color='#70d7ac' if valid else '#999999'
            canvas.create_polygon(*[v for xy in corners for v in xy],outline=color,fill='',width=2)
            if valid:canvas.create_line(*point(0,14),*point(0,-17),fill=color,width=2,arrow='last')
            state=motion.get('state','WAITING') if valid else 'NOT READY'
            canvas.create_text(39,68,text=str(state)[:12],fill=color,font=('TkDefaultFont',8))
            canvas.create_text(39,81,text='tap: visual zero',fill='#dddddd',font=('TkDefaultFont',7))
'''


def derive(raw, motion_sources, original_sources, config_sha, telemetry_source):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if type(raw) is not bytes or len(raw)>1048576 or sha(raw)!=INPUT_SHA:
        raise ValueError('Exact preserved version23 common capsule required')
    capsule=json.loads(raw)
    files={n:base64.b64decode(v,validate=True) for n,v in capsule['files'].items()}
    if capsule['manifest']['files']!=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]:
        raise ValueError('Complete input manifest')
    original=dict(files)
    def change(name,before,after):
        text=files[name].decode()
        if text.count(before)!=1:raise ValueError('Exact mounted-motion boundary '+name+': '+before[:80])
        files[name]=text.replace(before,after).encode()
    def append(name,text):files[name]+=('\n'+text+'\n').encode()
    name='code/field_live_source_bridge_v6.py'
    append(name,telemetry_source.decode())
    change(name,'        payload = block.audio.astype',
        "        metadata = validate_block_metadata(metadata, self.source._mounted_beams.drain(block.callback_perf_counter_ns/1e9))\n"
        '        payload = block.audio.astype')
    name='code/field_live_source_factory_v6.py'
    change(name,'    from field_live_source_bridge_v6 import LiveSourceBridge',
        '    from field_live_source_bridge_v6 import LiveSourceBridge, BeamQueue')
    change(name,'    source = SelectedSource(live.LiveConfig(**settings),routes)',
        '    source = SelectedSource(live.LiveConfig(**settings),routes)\n'
        '    source._mounted_beams=BeamQueue()\n'
        '    source.spatial_observer=source._mounted_beams.receive\n'
        '    source.spatial_fast=True')
    name='code/isolated_live_facade_v9.py'
    change(name,"        assert set(meta)=={f.name for f in fields(LiveBlock) if f.name!='audio'}",
        "        if type(meta) is not dict or 'spatial_telemetry' not in meta:raise SourceFault('MISSING_BEAM_METADATA')\n"
        "        meta=dict(meta);beam_packet=meta.pop('spatial_telemetry')\n"
        "        assert set(meta)=={f.name for f in fields(LiveBlock) if f.name!='audio'}")
    change(name,'dict(published_ns=published,received_ns=received)',
        'dict(published_ns=published,received_ns=received,spatial_telemetry=beam_packet)')
    name='code/isolated_pipeline_source_v11.py'
    change(name,"        if spatial_provider is not None and (getattr(spatial_provider,'enabled',False) or getattr(spatial_provider,'display',False)):\n"
        "            raise ValueError('Isolated beam telemetry is unavailable; spatial modes are not admitted')",
        "        # The shared source now supplies validated, callback-bound beam metadata.")
    change(name,'        self.spatial_provider = spatial_provider',
        '        self.spatial_provider = spatial_provider\n'
        '        from app.beam_diagnostics import BeamDiagnostics\n'
        '        from field_live_source_bridge_v6 import BeamReceiver\n'
        '        self.live.beam_diagnostics=BeamDiagnostics(lambda command: None,fast=True)\n'
        "        self.live.beam_diagnostics._state='WAITING'\n"
        '        self._mounted_receiver=BeamReceiver(_MountedSpatialSink(spatial_provider,self.live.beam_diagnostics))\n'
        '        self._last_motion_trace=-1.')
    change(name,'        if self.spatial_provider is not None: self.spatial_provider.advance_audio(block)',
        "        self._mounted_receiver.accept(ipc['spatial_telemetry'],block.callback_perf_counter_ns/1e9)\n"
        '        if self.spatial_provider is not None:\n'
        '            self.spatial_provider.advance_audio(block)\n'
        '            callback=block.callback_perf_counter_ns/1e9\n'
        '            if callback-self._last_motion_trace>=.1:\n'
        '                ipc[\'orientation\']=_mounted_pose_at(self.spatial_provider.motion,callback)\n'
        '                self._last_motion_trace=callback')
    change(name,'                self.journal.finish(self.error);self._done.set()',
        '                self.live.beam_diagnostics.stop()\n'
        '                self.journal.finish(self.error);self._done.set()')
    append(name, '_MOUNTED_CONFIG_SHA='+repr(config_sha)+'\n'+PIPE_HELPER)
    name='code/field_operator_controller_v6.py'
    change(name,"'start_file','stop','close','session_action'))",
        "'start_file','stop','close','session_action','motion_event'))")
    # Initial pinned settings remain unchanged; the explicit runtime adapter
    # enables visualization after its own initialization, under existing slots.
    change(name,"    controller=DeliveryController(data,Path(contract['models_root']),saved_audio_only=selection['input_kind']=='saved')",
        "    mounted_worker,mounted_config=_bind_mounted_runtime(base,manifest)\n"
        "    controller=DeliveryController(data,Path(contract['models_root']),saved_audio_only=selection['input_kind']=='saved')")
    change(name,'    try:\n        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)',
        '    try:\n'
        "        if controller.imu is not None:raise RuntimeError('Unexpected second IMU owner')\n"
        '        controller.imu=mounted_worker(mounted_config,controller.motion_event).start()\n'
        "        controller.settings['spatial_visualization']=selection['input_kind']=='microphone'\n"
        "        controller.metrics['mounted_motion_binding']=dict(config_sha256=_MOUNTED_CONFIG_SHA,\n"
        "            display_frame='device',logic_frame='relative_anchor_front_assumed',\n"
        "            translation_position_available=False,saved_audio_uses_live_pose=False)\n"
        '        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)')
    packed={n:dict(bytes=len(b),sha256=sha(b),original_sha256=sha(original_sources[n]),
                  compressed=base64.b64encode(zlib.compress(b,9)).decode()) for n,b in motion_sources.items()}
    append(name,'_MOUNTED_CONFIG_SHA='+repr(config_sha)+'\n_MOUNTED_SOURCES='+repr(packed)+'\n'+CONTROLLER_HELPER)
    name='code/field_operator_ui_v1.py'
    change(name,'        def _show_status(self):',DEBUG_METHODS+'\n        def _show_status(self):')
    change(name,'            super()._show_status()','            super()._show_status()\n            self._draw_motion_debug()')
    change(name,'            widget=super().button(parent,text,command,*args,**kwargs)',
        "            if kwargs.get('key')=='motion':\n"
        "                text='Orientation graphic · show / hide';command=self._toggle_motion_debug\n"
        '            widget=super().button(parent,text,command,*args,**kwargs)')
    change(name,"            self.preview_label.configure(text=context['runtime_profile']['label']+'\\n'+state+' · '+timing)",
        "            motion=self.snapshot.get('motion') or {}\n"
        "            motion_line=('Motion ready · turn %.1f°' % motion.get('yaw_deg',0)) if motion.get('valid') else 'Motion: '+str(motion.get('reason','initializing'))[:60]\n"
        "            if context['runtime_profile']['selection']['input_kind']=='saved':motion_line='Saved audio: current motion does not change recorded directions'\n"
        "            self.preview_label.configure(text=context['runtime_profile']['label']+'\\n'+state+' · '+timing+'\\n'+motion_line)")
    # Correct the old UI legend without changing geometry/drawing or control paths.
    change(name,"    env=dict(entry.__dict__,PrototypeUI=prototype)",
        "    import inspect,textwrap\n"
        "    drawing=textwrap.dedent(inspect.getsource(prototype._update_spatial_visualization))\n"
        "    old='Startup frame · turn %.1f° · drift possible'\n"
        "    if drawing.count(old)!=1:raise ValueError('Actual spatial legend boundary')\n"
        "    drawing=drawing.replace(old,'Device beams · relative turn %.1f°')\n"
        "    namespace=dict(prototype._update_spatial_visualization.__globals__)\n"
        "    exec(compile(drawing,'<mounted-device-visualization>','exec'),namespace)\n"
        "    class MountedPrototype(prototype):\n"
        "        _update_spatial_visualization=namespace['_update_spatial_visualization']\n"
        "    env=dict(entry.__dict__,PrototypeUI=MountedPrototype)")
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):
        raise ValueError('Original capsule cardinality/code/member caps')
    for n,b in code.items():
        if n.endswith('.py'):compile(b,n,'exec')
    manifest=dict(schema=capsule['manifest']['schema'],files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    result=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':')).encode()
    if len(result)>1048576:raise ValueError('Original packed capsule cap')
    return result,dict(status='PREPARED_SHARED_MOUNTED_RUNTIME',native_executed=False,
        input_sha256=INPUT_SHA,sha256=sha(result),code_members=len(code),code_bytes=sum(map(len,code.values())),
        original_guards_retained=True,changed={n:dict(bytes=len(b),sha256=sha(b),before_sha256=sha(original[n])) for n,b in files.items() if b!=original[n]})
