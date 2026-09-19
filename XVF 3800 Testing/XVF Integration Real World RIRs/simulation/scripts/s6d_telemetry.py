"""Finite read-only S6D queued telemetry lifecycle; README_S6D_CAPTURE.md."""
from __future__ import annotations
from collections import Counter, deque
import json
import math
from pathlib import Path
import shutil
import subprocess
import threading
import time
from s6d_capture_transport import binding

FIELDS=('AEC_AZIMUTH_VALUES','AEC_SPENERGY_VALUES','AUDIO_MGR_SELECTED_AZIMUTHS',
    'PP_AGCGAIN','AEC_AECCONVERGED','AEC_AECPATHCHANGE','AEC_RT60','AEC_CURRENT_IDLE_TIME',
    'AEC_MIN_IDLE_TIME','AUDIO_MGR_CURRENT_IDLE_TIME','AUDIO_MGR_MIN_IDLE_TIME','I2S_CURRENT_IDLE_TIME','I2S_MIN_IDLE_TIME','MAX_CONTROL_TIME')
COUNTS=(4,4,2,1,1,1,1,1,1,1,1,1,1,1)


class S6DQueuedTelemetryLogger:
    """Created only after the physical owner holds the existing hardware lease."""
    def __init__(self,dll_directory,output_dir,duration_s,fast_hz=20.,gain_hz=2.,slow_hz=.2):
        if not all(math.isfinite(v) for v in (duration_s,fast_hz,gain_hz,slow_hz)) or not 0<duration_s<=3600 or not 1<=fast_hz<=30 or not 0<=gain_hz<=5 or not 0<=slow_hz<=1:
            raise ValueError('Finite bounded telemetry rates/duration required')
        self.dll_directory=Path(dll_directory);self.output_dir=Path(output_dir)
        self.duration_s=duration_s;self.fast_hz=fast_hz;self.gain_hz=gain_hz;self.slow_hz=slow_hz
        self.latest={};self.recent=deque(maxlen=512);self.counts=Counter();self.errors=[]
        self._ready=threading.Event();self._done=threading.Event();self._stop_at=None;self._stop_reason=None
        self._started=False;self.result=None;self._process=None;self.last_line_at=None

    def start(self):
        if self._started:raise RuntimeError('Logger cannot restart')
        self._started=True;self.output_dir.mkdir(parents=True,exist_ok=False)
        base=Path(__file__).resolve().parent
        self.native_dir=self.output_dir/'native';self.stop_file=self.output_dir/'stop.request'
        source_dir=self.output_dir/'source';source_dir.mkdir()
        sources=[Path(__file__),base/'s6d_native/S6DQueuedTelemetry.cs',base/'s6d_native/Run-S6D-Telemetry.ps1',base/'s6d_capture_transport.py']
        for source in sources:shutil.copy2(source,source_dir/source.name)
        self.source_bindings=[binding(p) for p in source_dir.iterdir()]
        self.library_bindings=[binding(self.dll_directory/n) for n in ('device_usb.dll','command_map.dll')]
        powershell=Path('C:/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe')
        self.argv=[str(powershell),'-NoProfile','-NonInteractive','-File',str(base/'s6d_native/Run-S6D-Telemetry.ps1'),
            '-DllDirectory',str(self.dll_directory),'-OutputDirectory',str(self.native_dir),'-Seconds',str(self.duration_s),
            '-RateHz',str(self.fast_hz),'-GainHz',str(self.gain_hz),'-SlowHz',str(self.slow_hz),'-StopFile',str(self.stop_file)]
        self.start_ns=time.perf_counter_ns();self._stderr=(self.output_dir/'stderr.bin').open('xb')
        try:
            self._process=subprocess.Popen(self.argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=self._stderr,
                shell=False,bufsize=0,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except BaseException:
            self._stderr.close();raise
        self._reader=threading.Thread(target=self._read,name='s6d-telemetry-reader',daemon=True);self._reader.start()
        self._manager=threading.Thread(target=self._manage,name='s6d-telemetry-manager',daemon=True);self._manager.start()
        return self

    def _read(self):
        try:
            with (self.output_dir/'stdout.bin').open('xb') as rawfile,(self.output_dir/'received_telemetry.jsonl').open('x',encoding='utf-8') as rows:
                while True:
                    line=self._process.stdout.readline(65537)
                    if not line:break
                    arrival=time.perf_counter_ns();rawfile.write(line)
                    if len(line)>65536 or not line.endswith(b'\n'):raise ValueError('Malformed/oversized native telemetry line')
                    native=json.loads(line.decode('utf-8-sig'))
                    if native.get('phase')!='measurement':continue
                    name=native.get('command')
                    if name not in FIELDS or len(native.get('values',[]))!=COUNTS[FIELDS.index(name)]:raise ValueError('Unexpected field descriptor/count')
                    row=dict(native,host_line_arrival_monotonic_ns=arrival,parse_ok=True,receipt_sequence=sum(self.counts.values()),
                        host_response_end_monotonic_ns=native['response_end_monotonic_ns'])
                    rows.write(json.dumps(row,allow_nan=False)+'\n')
                    self.counts[name]+=1;self.latest[name]=row;self.recent.append(row);self.last_line_at=time.perf_counter()
                    if all(self.counts[n]>0 for n in FIELDS[:3]):self._ready.set()
        except BaseException as e:
            self.errors.append('reader: '+repr(e));self.stop('reader_error')

    def _manage(self):
        forced=False;code=None
        try:
            while self._process.poll() is None:
                now=time.perf_counter()
                if now>self.start_ns/1e9+self.duration_s+20 or self._stop_at is not None and now>self._stop_at+8:
                    forced=True;self.errors.append('Owned native process exceeded bounded closure');self._process.kill();break
                time.sleep(.02)
            code=self._process.wait(timeout=3);self._reader.join(timeout=3)
            if self._reader.is_alive():self.errors.append('Reader still alive after process exit');return
            self._process.stdout.close();self._stderr.close()
            native=json.loads((self.native_dir/'result.json').read_text(encoding='utf-8-sig'))
            inspection=json.loads((self.native_dir/'command_map_inspection.json').read_text(encoding='utf-8-sig'))
            for b,key in zip(self.library_bindings,('device_usb_sha256','command_map_sha256')):
                if inspection[key]!=b['sha256']:self.errors.append('Native DLL bytes changed')
            for name in FIELDS:
                if native['per_field'][name]['count']!=self.counts[name]:self.errors.append('Native/read count mismatch: '+name)
            cleanup=(not forced and native.get('cleanup_return')==0 and not any(native.get('pending_reads_at_exit',[True])))
            passed=code==0 and native.get('status')=='PASS' and not self.errors and (self.output_dir/'stderr.bin').stat().st_size==0
            self.result=dict(status='PASS' if passed else 'FAIL',exit_code=code,forced_termination=forced,
                control_owner_closed_proven=cleanup,errors=self.errors,counts=dict(self.counts),native_result=native,
                native_result_binding=binding(self.native_dir/'result.json'),inspection_binding=binding(self.native_dir/'command_map_inspection.json'),
                source_bindings=self.source_bindings,library_bindings=self.library_bindings,argv=self.argv,
                receipt_file=binding(self.output_dir/'received_telemetry.jsonl'),stop_reason=self._stop_reason,
                bounded_recent_rows=512,host_to_DSP_clock_alignment_known=False)
        except BaseException as e:
            self.errors.append('manager: '+repr(e));self.result=dict(status='FAIL',exit_code=code,forced_termination=forced,
                control_owner_closed_proven=False,errors=self.errors)
        finally:
            if self._process.poll() is not None and not self._reader.is_alive():
                if not self._stderr.closed:self._stderr.close()
                with (self.output_dir/'result.json').open('x',encoding='utf-8') as f:json.dump(self.result,f,indent=2,allow_nan=False)
                self._done.set()

    def wait_ready(self,timeout=10):
        end=time.perf_counter()+timeout
        while time.perf_counter()<end:
            if self._ready.wait(.05):return True
            if self._done.is_set():return False
        return False

    def healthy(self):
        return self._process is not None and self._process.poll() is None and not self.errors and self.last_line_at is not None and time.perf_counter()-self.last_line_at<2.

    def stop(self,reason='owner_closed_audio'):
        if self._stop_at is None:
            self._stop_reason=reason;self._stop_at=time.perf_counter()
            self.stop_file.write_text(reason,encoding='utf-8')

    def wait(self,timeout=20):
        return self.result if self._done.wait(timeout) else None
