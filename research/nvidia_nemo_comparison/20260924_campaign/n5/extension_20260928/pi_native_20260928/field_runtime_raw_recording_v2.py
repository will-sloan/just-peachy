"""Raw MIC0-MIC3 recording integration; README_RUNTIME_RAW_RECORDING_V2.md."""
import ast,base64,hashlib,json
from copy import deepcopy

RAW_BYTES=16*2080000
RAW_EXTRA=RAW_BYTES+2*65536
INPUT_SHA='3ff30c4bbecf176b768fe02d2a2df1c25afba5517e53a880f79af605464b5dcb'
MANAGER_PINS={'code/field_host_budget_v1.py': '1757b034d8fe301e6b9c711031c5168ed360532bcebd4dd23d0d3cc06a4c8489', 'code/field_live_layout_v2.py': '4d58494543c641ed0929c01b055f4fba03328b549b8e7777849aeb64b4791416', 'code/field_live_layout_v3.py': '52b58bf10fe1190be8dd9208231e02840661d6f1651ad8db80c0fd7d7611bab1', 'code/field_local_backup_contract_v2.py': '9a707506272403805099e90f11f89275b5e2cff3d97d1788a15d53017cd03b75', 'code/field_local_release_plan_v2.py': '090a479ec43e34446d6a368279bba393f8150cbddc6456cc55aa17ac763b1407', 'code/field_operator_broker_files_v2.py': '1799fd5110d386fafbcf7696a4145fa51ddf729f03c131d5167fb1dfb6af3531', 'code/field_operator_broker_layout_v2.py': '95d901fdb9f8e959a43c2d46af3175f19cd6f9363e388da2861f7fc5c6341afa', 'code/field_operator_broker_streamed_mirror_v1.py': '8c2cb490bf2c05009eb18eaa72513acbdeaa09174b2ae0890a7a5e077dd955f7', 'code/field_operator_health_v1.py': '7107dac4103e7487f52389cfbc76bc3af2c76f4b1932e9dcf4549c235dffa7da', 'code/field_operator_session_ledger_v4.py': '480f4557643915349eb803f786429ab4174c9a2a4a9450cd43be2cb6d58a8bce', 'code/field_operator_session_plan_v1.py': 'c3618244e76a8d6ec43ca6f02d548cca916078085d266ca0c0c9eb37ab6d12a5', 'code/field_operator_session_plan_v3.py': '89d7ae874105e6e8cd390f866fc4fc7cc0c9fc1e82d461c6a6b6dff39b3cd78e', 'code/field_runtime_backup_v2.py': '9f4911c05a8b3f5d61b90507f10cd6ed14a1131f8190fd06ce51c317b8b7f1b5', 'code/field_runtime_journal_v3.py': '1825b91699a00a75e2a5686ff7baadabf0dc02cc7abe40076c45450dde669e94', 'code/field_runtime_manager_v11.py': 'f5287e4f542a4c60fd693cb3fad7712d8372142b61b6f006bd031ccca70a83c6', 'code/field_runtime_policy_v3.py': '28d45624e53653787d42f8d032b6712aeaa2e308a9a89c67b7acef3c07b007aa'}
def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def once(s,old,new):
    if s.count(old)!=1:raise ValueError('Exact raw integration boundary changed: '+old[:100])
    return s.replace(old,new)
def raw_allocation(recordings,launches):
    from field_local_release_plan_v2 import allocation
    result=deepcopy(allocation(recordings,launches))
    b=result['broker_allocation']
    for k in ('target_per_session','host_per_session','target_maximum_bytes','host_maximum_bytes'):b[k]+=RAW_EXTRA
    b['combined_request_bytes']+=2*RAW_EXTRA
    result['local_backup_per_recording']+=RAW_EXTRA
    result['host_local_backup_per_recording']+=RAW_EXTRA
    result['target_maximum_bytes']+=2*recordings*RAW_EXTRA
    result['host_maximum_bytes']+=2*recordings*RAW_EXTRA
    result['combined_request_bytes']+=4*recordings*RAW_EXTRA
    return result
def validate_policy(value):
    from field_runtime_policy_v3 import validate
    expected=raw_allocation(value['allocation']['recordings'],value['allocation']['launches'])
    if encoded(value['allocation'])!=encoded(expected):raise ValueError('Full raw/processed allocation required')
    legacy=deepcopy(value)
    from field_local_release_plan_v2 import allocation
    legacy['allocation']=allocation(expected['recordings'],expected['launches'])
    validate(legacy)
    if value['measured_target_bytes']+value['measured_host_bytes']+expected['combined_request_bytes']>value['combined_output_cap_bytes'] or value['measured_payload_bytes']+expected['combined_request_bytes']>value['total_payload_cap_bytes']:
        raise ValueError('Full raw plus all independent copies not admitted')
    return value
def plans(files):
    files=dict(files)
    for name in ('field_operator_session_plan_v1.py','field_operator_session_plan_v3.py'):
        key='code/'+name
        if key in files:
            s=files[key].decode()
            s=once(s,'TARGET_PER_SESSION = 146_919_980','TARGET_PER_SESSION = '+str(146919980+RAW_EXTRA))
            s=once(s,'HOST_PER_SESSION = 151_114_284','HOST_PER_SESSION = '+str(151114284+RAW_EXTRA))
            files[key]=s.encode()
    return files
LEGACY_HELPER='''
def legacy_allocation(recordings,launches):
    from copy import deepcopy
    result=deepcopy(allocation(recordings,launches))
    extra=33411072
    b=result['broker_allocation']
    for key in ('target_per_session','host_per_session','target_maximum_bytes','host_maximum_bytes'):b[key]-=extra
    b['combined_request_bytes']-=2*extra
    result['local_backup_per_recording']-=extra
    result['host_local_backup_per_recording']-=extra
    result['target_maximum_bytes']-=2*recordings*extra
    result['host_maximum_bytes']-=2*recordings*extra
    result['combined_request_bytes']-=4*recordings*extra
    return result
'''
def policy_source(s):
    s=once(s,'if encoded(a) != encoded(expected):',
        "if encoded(a) not in (encoded(expected),encoded(legacy_allocation(a['recordings'],a['launches']))):")
    # Compatibility is exact original historical shape, never an arbitrary lower allocation.
    return s+LEGACY_HELPER
def derive_manager(files):
    if {n:sha(b) for n,b in files.items()}!=MANAGER_PINS:raise ValueError('Pinned current manager capsule required')
    result=plans(files)
    key='code/field_runtime_policy_v3.py';result[key]=policy_source(result[key].decode()).encode()
    return result

RAW_SOURCE='\ndef raw_source_type(base, live, routes):\n    import inspect, textwrap, hashlib\n    import numpy as np\n    def derive_method(method, replacements, additions=None):\n        s=textwrap.dedent(inspect.getsource(method))\n        for old,new,count in replacements:\n            if s.count(old)!=count:raise ValueError(\'Pinned live source boundary changed: \'+old)\n            s=s.replace(old,new)\n        namespace=dict(method.__globals__);namespace.update(additions or {})\n        exec(compile(s,\'<reviewed-packed-source:\'+method.__name__+\'>\',\'exec\'),namespace)\n        return namespace[method.__name__]\n    class PackedConverter:\n        delay_seconds=0.0\n        def __init__(self, source):\n            self.source=source;self.samples=0;self.digest=hashlib.sha256()\n            self.pending=bytearray();self.finished=False\n        def convert(self, frames):\n            if self.finished or frames.dtype!=np.int32 or frames.ndim!=2 or frames.shape[1]!=2 or len(frames)%3:\n                raise ValueError(\'Aligned stereo S32LE packed input required\')\n            markers=frames & 1\n            expected=np.arange(len(frames),dtype=np.int32)%3\n            expected=(expected!=0).astype(np.int32)\n            if not np.array_equal(markers[:,0],expected) or not np.array_equal(markers[:,1],expected):\n                raise ValueError(\'Packed microphone marker discontinuity\')\n            six=(frames & np.int32(-2)).reshape(-1,6)\n            count=len(six)\n            if self.samples+count>2080000:raise ValueError(\'Raw microphone sample reservation exhausted\')\n            raw=six[:,2:6].astype(\'<i4\',copy=False).tobytes()\n            if len(raw)>65536:raise ValueError(\'Raw callback conversion write bound\')\n            if len(self.pending)+len(raw)>65536:self.flush()\n            self.pending.extend(raw);self.digest.update(raw);self.samples+=count\n            return six[:,0 if self.source.config.tap==\'O0\' else 1].astype(np.float32)/np.float32(2147483648)\n        def flush(self):\n            if self.pending:\n                raw=bytes(self.pending)\n                routes.groups[\'source\'].write(\'RAW_MICROPHONES.s32le\',raw,append=True)\n                self.pending.clear()\n        def finish(self):\n            if self.finished:raise ValueError(\'Raw publication already attempted\')\n            self.finished=True;self.flush()\n            source=self.source\n            path=routes.root/\'source/RAW_MICROPHONES.s32le\'\n            if self.samples!=source._model_samples or self.samples<=0:raise ValueError(\'Raw/model source frame count differs\')\n            with path.open(\'rb\') as f:\n                actual=hashlib.file_digest(f,\'sha256\').hexdigest()\n            if path.stat().st_size!=self.samples*16 or actual!=self.digest.hexdigest():raise IOError(\'Raw independent readback\')\n            row=dict(schema=\'just-peachy.raw-microphones.v1\',file=path.name,sha256=actual,\n                bytes=self.samples*16,samples=self.samples,channels=4,channel_order=[\'MIC0\',\'MIC1\',\'MIC2\',\'MIC3\'],\n                encoding=\'signed_pcm32_le\',sample_rate=16000,transport_sample_rate=48000,\n                firmware_mux=[[1,0],[1,1],[1,2],[1,3]],firmware_rate_not_adc_rate=True,\n                packing_marker_lsb_cleared=True,packing_marker_errors=0,\n                model_tap=source.config.tap,model_host_gain_db=3.0 if source.config.tap==\'O0\' else 0.0,\n                processed_master=\'model_input.f32le\',shared_sample_clock=True,\n                identical_acoustic_latency_claim=False,host_resampler=\'none_firmware_16k_packed\',\n                start_prefix_transport_frames=source._packed_prefix,\n                terminal_incomplete_transport_frames=source._packed_tail_count,\n                accepted_transport_frames=source._native_frames,source_epoch=source._capture_epoch,\n                stream_start_perf_counter_ns=source._stream_start_perf_ns,\n                priming_native_frames=source._accepted_origin_frame,\n                complete_source_readback=True,pc_copy_required=True)\n            if row[\'accepted_transport_frames\']!=3*self.samples or not 0<=row[\'terminal_incomplete_transport_frames\']<3:\n                raise ValueError(\'Packed/source clock mismatch\')\n            routes.source(\'RAW_CAPTURE.json\',row)\n            return row\n    class RawSource(base):\n        def raw_capture_finish(self):\n            return self._converter.finish()\n        def _callback(self, indata, frames, time_info, status):\n            # Preallocated ring/two-frame carry only; no file/control/model work.\n            callback_perf_ns=live.time.perf_counter_ns()\n            if not self._route_ready:\n                if self._stopped:self._restoration_frames+=frames\n                else:\n                    self._priming_frames+=frames\n                    self._priming_status_events+=int(bool(status))\n                self._last_callback_ns=live.time.monotonic_ns()\n                return\n            if status or frames>self.config.block_frames or frames<3 or self._write_seq-self._read_seq>=self._capacity:\n                self._fault=\'INPUT_STATUS_GAP\' if status else \'CALLBACK_SIZE_OR_RAW_RING_OVERFLOW\'\n                self._dropped_frames+=frames\n                raise self.sd.CallbackAbort\n            begin=0\n            if self._packed_prefix is None:\n                while begin<3 and (int(indata[begin,0])&1):\n                    if not (int(indata[begin,1])&1):\n                        self._fault=\'PACKED_CHANNEL_MARKER_MISMATCH\';raise self.sd.CallbackAbort\n                    begin+=1\n                if begin>=3 or (int(indata[begin,1])&1):\n                    self._fault=\'PACKED_START_MARKER_MISSING\';raise self.sd.CallbackAbort\n                self._packed_prefix=begin;self._priming_frames+=begin\n                self._accepted_origin_frame=self._priming_frames\n            carry=self._packed_tail_count\n            complete=((carry+frames-begin)//3)*3\n            if complete<=0 or complete>self.config.block_frames:\n                self._fault=\'PACKED_CALLBACK_EXTENT\';raise self.sd.CallbackAbort\n            slot=self._write_seq%self._capacity\n            if carry:np.copyto(self._ring[slot,:carry],self._packed_tail[:carry])\n            consumed=complete-carry\n            np.copyto(self._ring[slot,carry:complete],indata[begin:begin+consumed])\n            tail=frames-begin-consumed\n            if tail:np.copyto(self._packed_tail[:tail],indata[begin+consumed:frames])\n            self._packed_tail_count=tail\n            self._frames[slot]=complete;self._native_start[slot]=self._native_frames\n            self._clock[slot]=live.time.monotonic_ns();self._perf_clock[slot]=callback_perf_ns\n            self._last_callback_ns=int(self._clock[slot])\n            self._adc[slot]=time_info.inputBufferAdcTime\n            self._callback_current_time[slot]=getattr(time_info,\'currentTime\',live.math.nan)\n            self._native_frames+=complete;self._write_seq+=1\n    RawSource._start_owned=derive_method(live.XVFLiveSource._start_owned,[\n        (\'dtype="float32"\',\'dtype="int32"\',2),\n        (\'dtype=np.float32\',\'dtype=np.int32\',1),\n        (\'self._converter = StreamingDecimator()\',\n         "self._converter = PackedConverter(self)\\n        self._packed_tail=np.empty((2,2),dtype=np.int32)\\n        self._packed_tail_count=0\\n        self._packed_prefix=None",1)],\n        {\'PackedConverter\':PackedConverter})\n    RawSource.read=derive_method(live.XVFLiveSource.read,[\n        (\'self._ring[slot, :n, 0 if self.config.tap == "O0" else 1].copy()\',\n         \'self._ring[slot, :n, :].copy()\',1)])\n    return RawSource\n\n\ndef install_packed_route(live):\n    import inspect,textwrap\n    command=\'AUDIO_MGR_OP_ALL\'\n    if command in live.READBACKS or command in live.LIVE_SETTABLE:raise ValueError(\'Unexpected existing packed route binding\')\n    live.READBACKS=tuple(live.READBACKS)+(command,)\n    live.LIVE_SETTABLE=set(live.LIVE_SETTABLE)|{command}\n    import ast\n    source=textwrap.dedent(inspect.getsource(live.LiveRoute.apply))\n    tree=ast.parse(source)\n    node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==\'desired\' for t in n.targets))\n    expected={"I2S_INPUT_PACKED":[0],"AUDIO_MGR_OP_PACKED":[0,0],"AUDIO_MGR_MIC_GAIN":[10.0],"AUDIO_MGR_SYS_DELAY":[-32],"AEC_ASROUTONOFF":[1],"AUDIO_MGR_OP_UPSAMPLE":[1,1],"AUDIO_MGR_OP_L":[7,3],"AUDIO_MGR_OP_R":[6,3]}\n    if ast.literal_eval(node.value)!=expected:raise ValueError(\'Exact installed route boundary changed\')\n    desired={"I2S_INPUT_PACKED":[0],"AUDIO_MGR_MIC_GAIN":[10.0],"AUDIO_MGR_SYS_DELAY":[-32],"AEC_ASROUTONOFF":[1],"AUDIO_MGR_OP_UPSAMPLE":[1,1],"AUDIO_MGR_OP_ALL":[7,3,1,0,1,2,6,3,1,1,1,3],"AUDIO_MGR_OP_PACKED":[1,1]}\n    source=source.replace(ast.get_source_segment(source,node),\'desired = \'+repr(desired))\n    original=live.LiveRoute.apply;namespace=dict(original.__globals__)\n    exec(compile(source,\'<reviewed-packed-route>\',\'exec\'),namespace)\n    derived=namespace[\'apply\']\n    def apply(self):\n        if self.config.control_protocol!=\'i2c\' or self.config.block_frames!=480:\n            raise ValueError(\'Qualified I2C/I2S480-frame raw route only\')\n        result=derived(self)\n        result.update(raw_packed=True,raw_sample_rate=16000,raw_channels=4,\n            resampler=\'none_firmware_packed_16k\',physical_mic_category=1,\n            equal_acoustic_delay_claim=False)\n        return result\n    live.LiveRoute.apply=apply\n'

def derive(raw):
    if type(raw) is not bytes or sha(raw)!=INPUT_SHA:raise ValueError('Exact candidate19 common capsule required')
    value=json.loads(raw)
    files={n:base64.b64decode(b,validate=True) for n,b in value['files'].items()}
    if value['manifest']['files']!=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]:raise ValueError('Complete capsule pins')
    old=dict(files);files=plans(files)
    def change(name,fn):
        key='code/'+name;s=fn(files[key].decode());compile(s,key,'exec');files[key]=s.encode()
    def layout(s):
        new="""    value['groups']['source']['RAW_MICROPHONES.s32le']=slot('source',33280000,65536,'append')
    value['groups']['source']['RAW_CAPTURE.json']=slot('source',65536,65536)
    value['groups']['config']['RAW_SELECTION.json']=slot('entry',65536,65536)
    extra = 65536+8192+32768+33411072"""
        return once(s,'    extra = 65536+8192+32768',new)
    change('field_live_layout_v3.py',layout)
    change('field_transfer_paths_v2.py',lambda s:once(s,'TARGET_MAX = 80106028+EXTRA_BYTES','TARGET_MAX = 113517100+EXTRA_BYTES'))
    change('field_operator_layout_v2.py',lambda s:once(s,'TARGET_MAX=146756140+PARENT_EXTRA','TARGET_MAX=180167212+PARENT_EXTRA'))
    change('field_runtime_policy_v3.py',policy_source)
    def controller(s):
        s=once(s,"set(value) not in ({'audio','consent'},{'audio','consent','title'})",
            "set(value) not in ({'audio','consent'},{'audio','consent','title'},{'audio','consent','raw_microphones'},{'audio','consent','title','raw_microphones'})")
        s=once(s,'                self._delivery_new_requested=True',"""                raw=value.get('raw_microphones',False)
                if type(raw) is not bool or (raw and (not value['audio'] or selection['input_kind']!='microphone')):
                    raise ValueError('Raw physical microphones require live input and audio consent')
                outputs.groups['config'].write('RAW_SELECTION.json',encoded(dict(
                    schema='just-peachy.raw-selection.v1',raw_microphones=raw,audio_requested=value['audio'])))
                value.pop('raw_microphones',None)
                self._delivery_new_requested=True""")
        return s
    change('field_operator_controller_v6.py',controller)
    def ui(s):
        s=once(s,"holder=self.button(after.master,'Raw MIC0–MIC3 + processed · unavailable',lambda:None)\n            holder.button.configure(state='disabled')",
"""def new_raw():
                from tkinter import messagebox
                if messagebox.askyesno('Record raw microphones','Store four physical microphone channels and processed model audio locally? Copy recordings to your PC after testing.',parent=self.root):
                    self._session_command('new',audio=True,consent=True,raw_microphones=True)
            live_input=context['runtime_profile']['selection']['input_kind']=='microphone'
            holder=self.button(after.master,'Record raw MIC0–MIC3 + processed…' if live_input else 'Raw microphones unavailable for saved input',new_raw)
            holder.button.configure(state='normal' if live_input else 'disabled')""")
        s=s.replace('Simultaneous physical raw microphone taps have not been qualified for this firmware. Processed audio is the exact mono16k model input; it is not raw microphone audio.',
            'Raw stores four physical microphone taps at16kHz with processed model audio. Raw files are included in full recording offload to the PC; the conversation ZIP contains processed audio and text only.')
        return s
    change('field_operator_ui_v1.py',ui)
    def factory(s):
        s=once(s,'    BoundedStop = source_class(live)',"""    raw_selection=bounded_json(root/'config/RAW_SELECTION.json')
    if set(raw_selection)!={'schema','raw_microphones','audio_requested'} or raw_selection['schema']!='just-peachy.raw-selection.v1' or type(raw_selection['raw_microphones']) is not bool or type(raw_selection['audio_requested']) is not bool or (raw_selection['raw_microphones'] and not raw_selection['audio_requested']):
        raise ValueError('Exact recording selection required before capture')
    raw_requested=raw_selection['raw_microphones']
    if raw_requested:install_packed_route(live)
    BoundedStop = source_class(live)""")
        s=once(s,'    source = ActualSource(live.LiveConfig(**settings),routes)',
            "    SelectedSource=raw_source_type(ActualSource,live,routes) if raw_requested else ActualSource\n    source = SelectedSource(live.LiveConfig(**settings),routes)")
        return s+RAW_SOURCE
    change('field_live_source_factory_v6.py',factory)
    def bridge(s):
        return once(s,'        status=self.source.status()\n        result=',"""        status=self.source.status()
        raw_receipt=None
        if hasattr(self.source,'raw_capture_finish'):
            raw_receipt=self.source.raw_capture_finish()
        result=""")
    change('field_live_source_bridge_v6.py',bridge)
    def clock(s):
        return once(s,'from app.live_timing import CaptureTimeline, LiveTimingError',"""from app.live_timing import CaptureTimeline as OriginalCaptureTimeline, LiveTimingError

class CaptureTimeline(OriginalCaptureTimeline):
    def __init__(self,metadata,first):
        super().__init__(metadata,first)
        self.raw_packed=metadata.get('route',{}).get('raw_packed') is True
        if self.raw_packed:
            if first.native_frames%3 or first.resampler_delay_seconds!=0:
                raise LiveTimingError('Packed source alignment',{})
            self.origin=self.native_origin
    def metadata(self):
        value=super().metadata()
        if self.raw_packed:
            value.update(model_interval_lead_native_frames=0,source_epoch_monotonic_sec=self.origin,
                source_clock_method='stream_start_counted_packed_triplets',
                acoustic_delay_between_taps_qualified=False)
        return value
""")
    change('isolated_pipeline_source_v11.py',clock)
    for n,b in files.items():
        if n.endswith('.py'):compile(b,n,'exec')
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):raise ValueError('Original module caps')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=encoded(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}))
    if len(packed)>1048576:raise ValueError('Original bundle cap')
    return packed,dict(status='RAW_RECORDING_PREPARED',input_sha256=sha(raw),bundle_sha256=sha(packed),
        raw_bytes_per_recording=RAW_BYTES,additional_bytes_per_copy=RAW_EXTRA,
        changed={n:dict(before_sha256=sha(old[n]),sha256=sha(b),bytes=len(b)) for n,b in files.items() if old[n]!=b},
        native_executed=False,model_changes=False,raw_rate=16000,raw_channels=4)
