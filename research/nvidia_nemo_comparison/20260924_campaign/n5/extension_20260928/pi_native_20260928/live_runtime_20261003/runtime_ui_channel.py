"""Bounded in-memory GUI telemetry channel; see README_RUNTIME_UI.md."""
import json
import math
import os
import time

PREFIX=b'JPV29_UI '
MAX_MESSAGE=4096


class SpatialViews:
    """Same retained observations, separate device display and association views."""
    def __init__(self,primary,device):
        if device.motion is not None:
            raise ValueError('Device display provider must not apply motion compensation')
        self.primary,self.device=primary,device

    def __getattr__(self,name):return getattr(self.primary,name)

    def attach(self,live):
        self.primary.attach(live)
        self.device.attach(live)
        live.spatial_observer=self.receive

    def bind_origin(self,origin):
        self.primary.bind_origin(origin);self.device.bind_origin(origin)

    def receive(self,*args):
        self.primary.receive(*args);self.device.receive(*args)

    def advance_audio(self,block):
        self.primary.advance_audio(block);self.device.advance_audio(block)

    def observe_segmentation(self,payload):
        self.primary.observe_segmentation(payload);self.device.observe_segmentation(payload)

    def display_snapshot(self):
        primary=self.primary.snapshot();device=self.device.snapshot()
        return dict(device,motion=primary.get('motion'),associations=primary.get('associations',[]),
            association_reference_frame=primary.get('coordinate_frame'),
            names_are_voice_matches=True,association_is_estimated=True)


def spatial_message(snapshot):
    """Project display fields only; geometry remains the retained provider's."""
    value={key:snapshot.get(key) for key in ('state','message','coordinate_frame','association_reference_frame',
        'names_are_voice_matches','association_is_estimated','selected_angle_deg','speech_known')}
    motion=snapshot.get('motion') or {}
    value['motion']={key:motion.get(key) for key in ('valid','yaw_deg','state','reason','compensation')}
    value['arrows']=[{key:row.get(key) for key in ('id','label','angle_deg','age_sec','fresh','selected','speech')}
                     for row in snapshot.get('arrows',[])]
    value['associations']=[{key:row.get(key) for key in ('track_id','label','angle_deg','fresh','speaking','association_status','reliability')}
                           for row in snapshot.get('associations',[])]
    if len(value['arrows'])>8 or len(value['associations'])>8:
        value=dict(state='UNAVAILABLE',message='Direction display exceeds its bounded channel',arrows=[],associations=[],motion={})
    row=dict(schema='just-peachy.gui-spatial.v1',published_monotonic=time.monotonic(),spatial=value)
    raw=PREFIX+json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
    if len(raw)>MAX_MESSAGE:
        raise ValueError('Direction display message exceeds4096 bytes')
    return raw


def _scalar(value, maximum=64):
    if value is None or type(value) is bool:return value
    if type(value) in (int,float):return value if math.isfinite(value) else None
    if type(value) is str:return value.encode('utf-8')[:maximum].decode('utf-8',errors='ignore')
    return None


def status_message(kind, value, *, now=None):
    """Project existing measurements only; no hardware/DB reads or caption text."""
    if kind=='health':
        keys=('state','elapsed','backlog_seconds','source_samples','dropped_audio',
              'first_caption_latency','first_speaker_latency','rolling_scope','scope',
              'whole_unit_aggregate','rss','pss_bytes','virtual_bytes','peak_virtual_bytes',
              'swap_bytes','available_ram','cpu_seconds','threads','temperature_millicelsius')
        projected={key:_scalar(value.get(key)) for key in keys}
        rolling=value.get('diarizer_rolling') or {}
        projected['diarizer_rolling']={key:_scalar(rolling.get(key)) for key in
            ('rolling_rtf','measured_audio_seconds','measured_compute_seconds','window_seconds',
             'dropped_samples','dropped_refinements','stop_required','stop_reason')}
        refinement=value.get('refinement')
        projected['refinement']=({key:_scalar(refinement.get(key)) for key in
            ('state','failure','received_samples','delivered_samples','output_frames','backlog_seconds',
             'returned_frames','label_backlog_seconds','diagnostic_drops','native_ready','failed','complete_eof',
             'label_revisions','diagnostics','whole_unit_rss_bytes','whole_unit_pss_bytes','ready','done','child_dead','supervisor_thread_closed')}
            if isinstance(refinement,dict) else _scalar(refinement))
    elif kind=='diagnostic':
        projected={key:_scalar(value.get(key),192) for key in
            ('kind','state','error','reason','message','optional_refiner','primary_continues',
             'child_dead','supervisor_thread_closed')}
    else:raise ValueError('Unsupported bounded GUI status')
    row=dict(schema='just-peachy.gui-status.v1',kind=kind,
             published_monotonic=time.monotonic() if now is None else now,value=projected)
    raw=PREFIX+json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()+b'\n'
    if len(raw)>MAX_MESSAGE:raise ValueError('GUI status exceeds4096 bytes')
    return raw


_last_health=-math.inf


def emit_spatial(row):
    """Compatible worker callback: spatial plus bounded live health/diagnostics."""
    global _last_health
    kind=row.get('kind')
    if kind=='spatial':raw=spatial_message(row['value'])
    elif kind in ('health','diagnostic'):
        now=time.monotonic()
        if kind=='health' and now-_last_health<1:return
        raw=status_message(kind,row['value'],now=now)
        if kind=='health':_last_health=now
    else:return  # Caption persistence remains the SQLite consumer's responsibility.
    # One <=PIPE_BUF write keeps each GUI record intact on the Linux pipe.
    if os.write(1,raw)!=len(raw):raise OSError('Short GUI telemetry pipe write')


class StreamDecoder:
    """Separate GUI rows into one latest snapshot; retain all diagnostic bytes."""
    def __init__(self,accept,diagnostic,status=None):
        self.accept,self.diagnostic,self.status=accept,diagnostic,status
        self.pending=bytearray()

    def feed(self,data):
        self.pending.extend(data)
        while b'\n' in self.pending:
            index=self.pending.index(b'\n')+1
            row=bytes(self.pending[:index]);del self.pending[:index]
            if row.startswith(PREFIX) and len(row)<=MAX_MESSAGE:
                try:
                    value=json.loads(row[len(PREFIX):])
                    if value.get('schema')=='just-peachy.gui-spatial.v1' and type(value.get('spatial')) is dict:
                        self.accept(value);continue
                    if (value.get('schema')=='just-peachy.gui-status.v1' and
                            value.get('kind') in ('health','diagnostic') and type(value.get('value')) is dict and
                            self.status is not None):
                        self.status(value);continue
                    raise ValueError('Exact GUI record required')
                except (ValueError,TypeError,AttributeError):pass
            self.diagnostic(row)
        if len(self.pending)>MAX_MESSAGE:
            self.diagnostic(bytes(self.pending));self.pending.clear()

    def finish(self):
        if self.pending:self.diagnostic(bytes(self.pending));self.pending.clear()
