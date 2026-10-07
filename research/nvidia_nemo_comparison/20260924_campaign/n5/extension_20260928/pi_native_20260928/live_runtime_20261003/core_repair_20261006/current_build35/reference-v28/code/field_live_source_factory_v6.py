"""Operator source composition binding; README_FIELD_OPERATOR_PARENT_V1.md."""
import os
from pathlib import Path
import sys
import threading
from field_live_source_outputs_v6 import load, bounded_json, encoded
from field_source_factory_overlay_v1 import route_classes
from field_live_stop_overlay_v1 import source_class


def create(cfg):
    root = Path(cfg['output_root'])
    checked, admission, routes = load(root/'config/CONFIG.json',role='source')
    if encoded(cfg) != encoded(checked):
        raise ValueError('Source factory configuration changed after owner ACK')
    prototype = Path(cfg['prototype'])
    threading.stack_size(1024**2)
    sys.path[:0] = [str(prototype),str(prototype/'vendor')]
    import app.live_audio as live
    if Path(live.__file__).resolve() != prototype/'app/live_audio.py':
        raise ValueError('Actual live source imported outside the admitted release')
    from field_live_source_bridge_v6 import LiveSourceBridge, BeamQueue
    original_source = live.XVFLiveSource
    raw_selection=bounded_json(root/'config/RAW_SELECTION.json')
    if set(raw_selection)!={'schema','raw_microphones','audio_requested'} or raw_selection['schema']!='just-peachy.raw-selection.v1' or type(raw_selection['raw_microphones']) is not bool or type(raw_selection['audio_requested']) is not bool or (raw_selection['raw_microphones'] and not raw_selection['audio_requested']):
        raise ValueError('Exact recording selection required before capture')
    raw_requested=raw_selection['raw_microphones']
    if raw_requested:install_packed_route(live)
    BoundedStop = source_class(live)

    class ActualSource(BoundedStop):
        # This fresh production factory validates its real capture admission
        # above. It does not change or call the old qualification-only start.
        def start(self, *, consent=False):
            return original_source.start(self,consent=consent)

    live.HostControl, live.LiveRoute = route_classes(live,routes)
    settings = bounded_json(cfg['live_config'])
    if settings['lease_path'] != str(Path.home()/'JustPeachy/data/xvf-hardware.lock'):
        raise ValueError('Exact hardware lease path required')
    # Actual Stop is the retained bounded derivative; no random receipt folder.
    settings.update(evidence_dir=None,control_timeout_seconds=2)
    SelectedSource=raw_source_type(ActualSource,live,routes) if raw_requested else ActualSource
    source = SelectedSource(live.LiveConfig(**settings),routes)
    source._mounted_beams=BeamQueue()
    source.spatial_observer=source._mounted_beams.receive
    source.spatial_fast=True
    def signal_stop():
        # Stop audio acceptance without blocking this diagnostic writer. Actual
        # stream/route/lease cleanup still runs through stop() in the child.
        source._stopped = True
        source._route_ready = False
        routes.stop_event.set()
    routes.request_stop = signal_stop
    try:
        metadata = source.start(consent=True)
        routes.source('SOURCE_START.json',metadata)
    except BaseException:
        # Physical cleanup is attempted even if source-start publication failed.
        receipt = source.stop()
        routes.source('SOURCE_START_FAILURE.json',receipt)
        raise
    bridge = LiveSourceBridge(source,live.LiveGap,root/'source',routes)
    bridge.signal_stop = signal_stop
    return bridge

def raw_source_type(base, live, routes):
    import inspect, textwrap, hashlib
    import numpy as np
    def derive_method(method, replacements, additions=None):
        s=textwrap.dedent(inspect.getsource(method))
        for old,new,count in replacements:
            if s.count(old)!=count:raise ValueError('Pinned live source boundary changed: '+old)
            s=s.replace(old,new)
        namespace=dict(method.__globals__);namespace.update(additions or {})
        exec(compile(s,'<reviewed-packed-source:'+method.__name__+'>','exec'),namespace)
        return namespace[method.__name__]
    class PackedConverter:
        delay_seconds=0.0
        def __init__(self, source):
            self.source=source;self.samples=0;self.digest=hashlib.sha256()
            self.pending=bytearray();self.finished=False;self.written=0
        def convert(self, frames):
            if self.finished or frames.dtype!=np.int32 or frames.ndim!=2 or frames.shape[1]!=2 or len(frames)%3:
                raise ValueError('Aligned stereo S32LE packed input required')
            markers=frames & 1
            expected=np.arange(len(frames),dtype=np.int32)%3
            expected=(expected!=0).astype(np.int32)
            if not np.array_equal(markers[:,0],expected) or not np.array_equal(markers[:,1],expected):
                raise ValueError('Packed microphone marker discontinuity')
            six=(frames & np.int32(-2)).reshape(-1,6)
            count=len(six)
            if self.samples+count>2080000:raise ValueError('Raw microphone sample reservation exhausted')
            raw=six[:,2:6].astype('<i4',copy=False).tobytes()
            if len(raw)>65536:raise ValueError('Raw callback conversion write bound')
            if len(self.pending)+len(raw)>65536:self.flush()
            self.pending.extend(raw);self.digest.update(raw);self.samples+=count
            return six[:,0 if self.source.config.tap=='O0' else 1].astype(np.float32)/np.float32(2147483648)
        def flush(self):
            if self.pending:
                raw=bytes(self.pending)
                import os,shutil
                path=routes.root/'data/RAW_MICROPHONES.s32le'
                if self.written==0:
                    if path.exists():raise FileExistsError('Raw destination already exists')
                elif path.is_symlink() or path.stat().st_nlink!=1 or path.stat().st_size!=self.written:
                    raise IOError('Raw append identity/size changed')
                if self.written+len(raw)>33280000 or len(raw)>65536 or shutil.disk_usage(path.parent).free<5*1024**3+len(raw):
                    raise ValueError('Independent raw artifact bounds')
                # Existing PhysicalFiles guards this exact path and aggregate.
                with path.open('xb' if self.written==0 else 'ab') as stream:
                    if stream.write(raw)!=len(raw):raise IOError('Short raw audio write')
                    stream.flush();os.fsync(stream.fileno())
                self.written+=len(raw)
                if path.stat().st_size!=self.written:raise IOError('Raw append readback extent')
                self.pending.clear()
        def finish(self):
            if self.finished:raise ValueError('Raw publication already attempted')
            self.finished=True;self.flush()
            source=self.source
            path=routes.root/'data/RAW_MICROPHONES.s32le'
            if self.samples!=source._model_samples or self.samples<=0:raise ValueError('Raw/model source frame count differs')
            with path.open('rb') as f:
                actual=hashlib.file_digest(f,'sha256').hexdigest()
            if path.stat().st_size!=self.samples*16 or actual!=self.digest.hexdigest():raise IOError('Raw independent readback')
            row=dict(schema='just-peachy.raw-microphones.v1',file='data/RAW_MICROPHONES.s32le',sha256=actual,
                bytes=self.samples*16,samples=self.samples,channels=4,channel_order=['MIC0','MIC1','MIC2','MIC3'],
                encoding='signed_pcm32_le',sample_rate=16000,transport_sample_rate=48000,
                firmware_mux=[[1,0],[1,1],[1,2],[1,3]],firmware_rate_not_adc_rate=True,
                packing_marker_lsb_cleared=True,packing_marker_errors=0,
                model_tap=source.config.tap,model_host_gain_db=3.0 if source.config.tap=='O0' else 0.0,
                processed_master='model_input.f32le',shared_sample_clock=True,
                identical_acoustic_latency_claim=False,host_resampler='none_firmware_16k_packed',
                start_prefix_transport_frames=source._packed_prefix,
                terminal_incomplete_transport_frames=source._packed_tail_count,
                accepted_transport_frames=source._native_frames,source_epoch=source._capture_epoch,
                stream_start_perf_counter_ns=source._stream_start_perf_ns,
                priming_native_frames=source._accepted_origin_frame,
                complete_source_readback=True,pc_copy_required=True)
            if row['accepted_transport_frames']!=3*self.samples or not 0<=row['terminal_incomplete_transport_frames']<3:
                raise ValueError('Packed/source clock mismatch')
            routes.source('RAW_CAPTURE.json',row)
            return row
    class RawSource(base):
        def raw_capture_finish(self):
            return self._converter.finish()
        def _callback(self, indata, frames, time_info, status):
            # Preallocated ring/two-frame carry only; no file/control/model work.
            callback_perf_ns=live.time.perf_counter_ns()
            if not self._route_ready:
                if self._stopped:self._restoration_frames+=frames
                else:
                    self._priming_frames+=frames
                    self._priming_status_events+=int(bool(status))
                self._last_callback_ns=live.time.monotonic_ns()
                return
            if status or frames>self.config.block_frames or frames<3 or self._write_seq-self._read_seq>=self._capacity:
                self._fault='INPUT_STATUS_GAP' if status else 'CALLBACK_SIZE_OR_RAW_RING_OVERFLOW'
                self._dropped_frames+=frames
                raise self.sd.CallbackAbort
            begin=0
            if self._packed_prefix is None:
                while begin<3 and (int(indata[begin,0])&1):
                    if not (int(indata[begin,1])&1):
                        self._fault='PACKED_CHANNEL_MARKER_MISMATCH';raise self.sd.CallbackAbort
                    begin+=1
                if begin>=3 or (int(indata[begin,1])&1):
                    self._fault='PACKED_START_MARKER_MISSING';raise self.sd.CallbackAbort
                self._packed_prefix=begin;self._priming_frames+=begin
                self._accepted_origin_frame=self._priming_frames
            carry=self._packed_tail_count
            complete=((carry+frames-begin)//3)*3
            if complete<=0 or complete>self.config.block_frames:
                self._fault='PACKED_CALLBACK_EXTENT';raise self.sd.CallbackAbort
            slot=self._write_seq%self._capacity
            if carry:np.copyto(self._ring[slot,:carry],self._packed_tail[:carry])
            consumed=complete-carry
            np.copyto(self._ring[slot,carry:complete],indata[begin:begin+consumed])
            tail=frames-begin-consumed
            if tail:np.copyto(self._packed_tail[:tail],indata[begin+consumed:frames])
            self._packed_tail_count=tail
            self._frames[slot]=complete;self._native_start[slot]=self._native_frames
            self._clock[slot]=live.time.monotonic_ns();self._perf_clock[slot]=callback_perf_ns
            self._last_callback_ns=int(self._clock[slot])
            self._adc[slot]=time_info.inputBufferAdcTime
            self._callback_current_time[slot]=getattr(time_info,'currentTime',live.math.nan)
            self._native_frames+=complete;self._write_seq+=1
    RawSource._start_owned=derive_method(live.XVFLiveSource._start_owned,[
        ('dtype="float32"','dtype="int32"',2),
        ('dtype=np.float32','dtype=np.int32',1),
        ('self._converter = StreamingDecimator()',
         "self._converter = PackedConverter(self)\n        self._packed_tail=np.empty((2,2),dtype=np.int32)\n        self._packed_tail_count=0\n        self._packed_prefix=None",1)],
        {'PackedConverter':PackedConverter})
    RawSource.read=derive_method(live.XVFLiveSource.read,[
        ('self._ring[slot, :n, 0 if self.config.tap == "O0" else 1].copy()',
         'self._ring[slot, :n, :].copy()',1)])
    return RawSource


def install_packed_route(live):
    import inspect,textwrap
    command='AUDIO_MGR_OP_ALL'
    if command in live.READBACKS or command in live.LIVE_SETTABLE:raise ValueError('Unexpected existing packed route binding')
    live.READBACKS=tuple(live.READBACKS)+(command,)
    live.LIVE_SETTABLE=set(live.LIVE_SETTABLE)|{command}
    import ast
    source=textwrap.dedent(inspect.getsource(live.LiveRoute.apply))
    tree=ast.parse(source)
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='desired' for t in n.targets))
    expected={"I2S_INPUT_PACKED":[0],"AUDIO_MGR_OP_PACKED":[0,0],"AUDIO_MGR_MIC_GAIN":[10.0],"AUDIO_MGR_SYS_DELAY":[-32],"AEC_ASROUTONOFF":[1],"AUDIO_MGR_OP_UPSAMPLE":[1,1],"AUDIO_MGR_OP_L":[7,3],"AUDIO_MGR_OP_R":[6,3]}
    if ast.literal_eval(node.value)!=expected:raise ValueError('Exact installed route boundary changed')
    desired={"I2S_INPUT_PACKED":[0],"AUDIO_MGR_MIC_GAIN":[10.0],"AUDIO_MGR_SYS_DELAY":[-32],"AEC_ASROUTONOFF":[1],"AUDIO_MGR_OP_UPSAMPLE":[1,1],"AUDIO_MGR_OP_ALL":[7,3,1,0,1,2,6,3,1,1,1,3],"AUDIO_MGR_OP_PACKED":[1,1]}
    source=source.replace(ast.get_source_segment(source,node),'desired = '+repr(desired))
    original=live.LiveRoute.apply;namespace=dict(original.__globals__)
    exec(compile(source,'<reviewed-packed-route>','exec'),namespace)
    derived=namespace['apply']
    def apply(self):
        if self.config.control_protocol!='i2c' or self.config.block_frames!=480:
            raise ValueError('Qualified I2C/I2S480-frame raw route only')
        result=derived(self)
        result.update(raw_packed=True,raw_sample_rate=16000,raw_channels=4,
            resampler='none_firmware_packed_16k',physical_mic_category=1,
            equal_acoustic_delay_claim=False)
        return result
    live.LiveRoute.apply=apply
