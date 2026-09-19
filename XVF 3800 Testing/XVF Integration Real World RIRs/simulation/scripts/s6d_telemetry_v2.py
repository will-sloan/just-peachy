"""Bounded cooperative telemetry with explicit terminal evidence; README_S6D_TELEMETRY_V2.md."""
from __future__ import annotations
from collections import Counter,deque
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import psutil
from s6d_capture_transport import binding

FIELDS=('AEC_AZIMUTH_VALUES','AEC_SPENERGY_VALUES','AUDIO_MGR_SELECTED_AZIMUTHS',
    'PP_AGCGAIN','AEC_AECCONVERGED','AEC_AECPATHCHANGE','AEC_RT60','AEC_CURRENT_IDLE_TIME',
    'AEC_MIN_IDLE_TIME','AUDIO_MGR_CURRENT_IDLE_TIME','AUDIO_MGR_MIN_IDLE_TIME','I2S_CURRENT_IDLE_TIME','I2S_MIN_IDLE_TIME','MAX_CONTROL_TIME')
COUNTS=(4,4,2,1,1,1,1,1,1,1,1,1,1,1)


class S6DQueuedTelemetryLogger:
    def __init__(self,dll_directory,output_dir,duration_s,fast_hz=20.,gain_hz=2.,slow_hz=.2):
        if not all(math.isfinite(v) for v in (duration_s,fast_hz,gain_hz,slow_hz)) or not 0<duration_s<=3600 or not 1<=fast_hz<=30 or not 0<=gain_hz<=5 or not 0<=slow_hz<=1:
            raise ValueError('Finite bounded telemetry rates/duration required')
        self.dll_directory=Path(dll_directory);self.output_dir=Path(output_dir)
        self.duration_s=duration_s;self.fast_hz=fast_hz;self.gain_hz=gain_hz;self.slow_hz=slow_hz
        self.latest={};self.recent=deque(maxlen=512);self.counts=Counter();self.errors=[]
        self._ready=threading.Event();self._done=threading.Event();self._reader_done=threading.Event()
        self._stop_at=None;self._stop_reason=None;self._started=False;self.result=None;self._process=None;self.last_line_at=None
        self._record_lock=threading.Lock();self._stop_lock=threading.Lock();self._late_lock=threading.Lock()
        self._sequence=0;self._reader_io_closed=False;self._stdout_eof=False;self._terminal_summary=None;self._late_written=False
        self.identity=None;self._identity_persisted=False;self.source_bindings=[];self.library_bindings=[];self.argv=[]

    def _record(self,stage,**payload):
        try:
            with self._record_lock:
                row=dict(sequence=self._sequence,stage=stage,monotonic_ns=time.perf_counter_ns(),utc=datetime.now(timezone.utc).isoformat(),**payload)
                self._sequence+=1
                with (self.output_dir/'lifecycle.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
        except BaseException as exc:self.errors.append('lifecycle persistence: '+repr(exc))

    def _exclusive(self,name,value):
        with (self.output_dir/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())

    def start(self):
        if self._started:raise RuntimeError('Logger cannot restart')
        self._started=True;self.output_dir.mkdir(parents=True,exist_ok=False)
        base=Path(__file__).resolve().parent;self.native_dir=self.output_dir/'native';self.stop_file=self.output_dir/'stop.request'
        source_dir=self.output_dir/'source';source_dir.mkdir()
        for source in (Path(__file__),base/'s6d_native/S6DQueuedTelemetry.cs',base/'s6d_native/Run-S6D-Telemetry.ps1',base/'s6d_capture_transport.py'):shutil.copy2(source,source_dir/source.name)
        self.source_bindings=[binding(p) for p in source_dir.iterdir()]
        self.library_bindings=[binding(self.dll_directory/n) for n in ('device_usb.dll','command_map.dll')]
        powershell=Path('C:/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe')
        self.argv=[str(powershell),'-NoProfile','-NonInteractive','-File',str(base/'s6d_native/Run-S6D-Telemetry.ps1'),'-DllDirectory',str(self.dll_directory),'-OutputDirectory',str(self.native_dir),'-Seconds',str(self.duration_s),'-RateHz',str(self.fast_hz),'-GainHz',str(self.gain_hz),'-SlowHz',str(self.slow_hz),'-StopFile',str(self.stop_file)]
        self.start_ns=time.perf_counter_ns();self._stderr=(self.output_dir/'stderr.bin').open('xb')
        self._record('START_REQUESTED',argv=self.argv,sources=self.source_bindings)
        try:
            self._process=subprocess.Popen(self.argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=self._stderr,shell=False,bufsize=65536,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except BaseException as exc:
            self._stderr.close();self.errors.append('launch: '+repr(exc));self._settle(None);return self
        try:
            self.identity=dict(pid=self._process.pid,creation_time=psutil.Process(self._process.pid).create_time(),parent_pid=os.getpid(),parent_creation_time=psutil.Process().create_time(),argv=self.argv,sources=self.source_bindings,libraries=self.library_bindings)
            self._exclusive('PROCESS_IDENTITY.json',self.identity);self._identity_persisted=True;self._record('PROCESS_CREATED',identity=self.identity)
        except BaseException as exc:self.errors.append('process identity: '+repr(exc));self.stop('identity_unproven')
        self._reader=threading.Thread(target=self._read,name='s6d-telemetry-reader-v2',daemon=True);self._reader.start()
        self._manager=threading.Thread(target=self._manage,name='s6d-telemetry-manager-v2',daemon=True);self._manager.start()
        return self

    def _read(self):
        try:
            with (self.output_dir/'stdout.bin').open('xb') as rawfile,(self.output_dir/'received_telemetry.jsonl').open('x',encoding='utf-8') as rows:
                while True:
                    line=self._process.stdout.readline(65537)
                    if not line:self._stdout_eof=True;break
                    arrival=time.perf_counter_ns();rawfile.write(line)
                    if len(line)>65536 or not line.endswith(b'\n'):raise ValueError('Malformed/oversized native telemetry line')
                    native=json.loads(line.decode('utf-8-sig'))
                    if native.get('phase')!='measurement':
                        if native.get('mode')=='queued_distinct_reads' and 'per_field' in native and 'cleanup_return' in native:
                            persisted=json.loads((self.native_dir/'result.json').read_text(encoding='utf-8-sig'))
                            if native!=persisted:raise ValueError('Native terminal frame differs from saved native result')
                            if set(native['per_field'])!=set(FIELDS) or any(type(native['per_field'][n].get('count')) is not int or native['per_field'][n]['count']!=self.counts[n] for n in FIELDS):raise ValueError('Native terminal frame/received count mismatch')
                            self._terminal_summary=native;self._record('NATIVE_TERMINAL_FRAME_VERIFIED',received_rows=sum(self.counts.values()),native_result=binding(self.native_dir/'result.json'))
                            break # Explicit protocol terminator; process exit is checked separately.
                        raise ValueError('Unexpected native stdout protocol record')
                    name=native.get('command')
                    if name not in FIELDS or len(native.get('values',[]))!=COUNTS[FIELDS.index(name)]:raise ValueError('Unexpected field descriptor/count')
                    row=dict(native,host_line_arrival_monotonic_ns=arrival,parse_ok=True,receipt_sequence=sum(self.counts.values()),host_response_end_monotonic_ns=native['response_end_monotonic_ns'])
                    rows.write(json.dumps(row,allow_nan=False)+'\n')
                    self.counts[name]+=1;self.latest[name]=row;self.recent.append(row);self.last_line_at=time.perf_counter()
                    if all(self.counts[n]>0 for n in FIELDS[:3]):self._ready.set()
        except BaseException as exc:self.errors.append('reader: '+repr(exc));self.stop('reader_error')
        finally:
            try:self._process.stdout.close();self._reader_io_closed=True
            except BaseException as exc:self.errors.append('reader pipe close: '+repr(exc))
            self._record('READER_FINISHED',io_closed=self._reader_io_closed,actual_stdout_eof=self._stdout_eof,verified_terminal_frame=self._terminal_summary is not None)
            self._reader_done.set();self._late_diagnostic()

    def _manage(self):
        code=None
        try:
            while self._process.poll() is None:
                now=time.perf_counter()
                if now>self.start_ns/1e9+self.duration_s+20 or self._stop_at is not None and now>self._stop_at+8:
                    self.errors.append('Native process exceeded bounded cooperative closure; no termination issued')
                    self.stop('cooperative_closure_deadline');self._record('PROCESS_CLOSURE_UNPROVEN',identity=self.identity);return
                time.sleep(.02)
            code=self._process.wait(timeout=3);self._record('PROCESS_EXITED',exit_code=code)
            self._reader.join(timeout=3)
            if self._reader.is_alive():self.errors.append('Reader still alive after bounded process-exit drain')
        except BaseException as exc:self.errors.append('manager: '+repr(exc))
        finally:self._settle(code)

    def _evidence(self,code):
        native={};inspection={};native_binding=None;inspection_binding=None;native_errors=[]
        try:
            native=json.loads((self.native_dir/'result.json').read_text(encoding='utf-8-sig'));native_binding=binding(self.native_dir/'result.json')
            inspection=json.loads((self.native_dir/'command_map_inspection.json').read_text(encoding='utf-8-sig'));inspection_binding=binding(self.native_dir/'command_map_inspection.json')
            for b,key in zip(self.library_bindings,('device_usb_sha256','command_map_sha256')):
                if inspection[key]!=b['sha256']:native_errors.append('Native DLL bytes changed')
            if set(native.get('per_field',{}))!=set(FIELDS) or any(type(native['per_field'][n].get('count')) is not int or native['per_field'][n]['count']!=self.counts[n] for n in FIELDS):native_errors.append('Native/received field count mismatch')
        except BaseException as exc:native_errors.append('native terminal evidence: '+repr(exc))
        exited=self._process is not None and self._process.poll() is not None
        reader_thread_closed=hasattr(self,'_reader') and not self._reader.is_alive()
        reader_closed=self._reader_done.is_set() and self._reader_io_closed and reader_thread_closed
        pending=native.get('pending_reads_at_exit')
        cleanup=type(native.get('cleanup_return')) is int and native['cleanup_return']==0 and isinstance(pending,list) and len(pending)==len(FIELDS) and all(x is False for x in pending)
        terminal=self._terminal_summary is not None and self._terminal_summary==native
        closed=exited and code==0 and reader_closed and cleanup and terminal and self.identity is not None and self._identity_persisted and not native_errors
        return dict(control_owner_closed_proven=closed,native_process_exited=exited,reader_io_closed=reader_closed,reader_thread_closed=reader_thread_closed,process_identity_persisted=self._identity_persisted,actual_stdout_eof=self._stdout_eof,verified_native_terminal_frame=terminal,native_cleanup_verified=cleanup,native_result=native,native_result_binding=native_binding,inspection_binding=inspection_binding,native_evidence_errors=native_errors)

    def _settle(self,code):
        self._record('MANAGER_SETTLING',exit_code=code)
        try:
            evidence=self._evidence(code)
            if self._process is None or evidence['native_process_exited']:
                try:
                    if not self._stderr.closed:self._stderr.close()
                except BaseException as exc:self.errors.append('stderr close: '+repr(exc))
            stderr_closed=self._stderr.closed
            stderr_bytes=(self.output_dir/'stderr.bin').stat().st_size
            passed=evidence['control_owner_closed_proven'] and evidence['native_result'].get('status')=='PASS' and not self.errors and not evidence['native_evidence_errors'] and stderr_closed and stderr_bytes==0
            self.result=dict(status='PASS' if passed else 'FAIL',exit_code=code,forced_termination=False,process_termination_issued=False,**evidence,errors=list(self.errors),counts=dict(self.counts),source_bindings=self.source_bindings,library_bindings=self.library_bindings,argv=self.argv,process_identity=self.identity,stop_reason=self._stop_reason,stderr_closed=stderr_closed,stderr_bytes=stderr_bytes,bounded_recent_rows=512,host_to_DSP_clock_alignment_known=False,terminal_receipt_persisted=True,scope='Explicit native terminal frame closes the reader protocol; natural process exit and cleanup are independently required. EOF and terminal-frame closure are reported separately.')
            if not stderr_closed:self.result['control_owner_closed_proven']=False
            if evidence['reader_io_closed'] and (self.output_dir/'received_telemetry.jsonl').exists():self.result['receipt_file']=binding(self.output_dir/'received_telemetry.jsonl')
        except BaseException as exc:
            self.errors.append('terminal evidence construction: '+repr(exc))
            self.result=dict(status='FAIL',control_owner_closed_proven=False,exit_code=code,forced_termination=False,process_termination_issued=False,process_identity=self.identity,errors=list(self.errors),terminal_receipt_persisted=True)
        try:self._exclusive('result.json',self.result)
        except BaseException as exc:self.result.update(status='FAIL',control_owner_closed_proven=False,terminal_receipt_persisted=False);self.result['errors'].append('terminal persistence: '+repr(exc))
        finally:self._done.set();self._late_diagnostic()

    def _late_diagnostic(self):
        if not self._done.is_set() or not self._reader_done.is_set() or self.result is None or self.result['status']=='PASS':return
        with self._late_lock:
            if self._late_written:return
            self._late_written=True
            try:self._exclusive('late_reader_closure.json',dict(status='DIAGNOSTIC_ONLY_ORIGINAL_FAILURE_PRESERVED',original_terminal_status=self.result['status'],reader_io_closed=self._reader_io_closed,process_exited=self._process is not None and self._process.poll() is not None,process_identity=self.identity,actual_stdout_eof=self._stdout_eof,verified_terminal_frame=self._terminal_summary is not None,utc=datetime.now(timezone.utc).isoformat(),monotonic_ns=time.perf_counter_ns(),recovery_or_playback_authorized=False))
            except BaseException as exc:self.errors.append('late closure persistence: '+repr(exc))

    def wait_ready(self,timeout=10):
        end=time.perf_counter()+timeout
        while time.perf_counter()<end:
            if self._done.is_set() or self.errors:return False
            if self._ready.wait(.05):return True
        return False

    def healthy(self):return self._process is not None and self._process.poll() is None and not self.errors and not self._done.is_set() and self.last_line_at is not None and time.perf_counter()-self.last_line_at<2.

    def stop(self,reason='owner_closed_audio'):
        with self._stop_lock:
            if self._stop_at is not None:return
            self._stop_reason=reason;self._stop_at=time.perf_counter()
            try:self.stop_file.write_text(reason,encoding='utf-8');self._record('COOPERATIVE_STOP_WRITTEN',reason=reason)
            except BaseException as exc:self.errors.append('cooperative stop persistence: '+repr(exc))

    def wait(self,timeout=20):return self.result if self._done.wait(timeout) else None
