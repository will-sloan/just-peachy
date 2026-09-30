"""Native saved-source controller extension; README_SEQUENTIAL_GUI_V1.md."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(path,value):
    raw=json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2).encode('utf-8')
    if len(raw)>2*1024**2:raise ValueError('Review document quota')
    with Path(path).open('xb') as f:f.write(raw)


def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def controller_class(Base,root,admission):
    root=Path(root);source_digest=sha(admission['source_wav'])
    class SequentialController(Base):
        def __init__(self,*args,**kwargs):
            self.seq_lock=threading.RLock();self.seq_thread=None;self.seq_cancel=threading.Event()
            self.seq=dict(phase='IDLE',primary=None,refined=None,primary_text='',refined_text='',error=None,
                          source_sha256=source_digest,owned=False,publications=0,job=None,saved=None)
            self.seq_history=[];self.seq_cancel_receipts=[]
            super().__init__(*args,**kwargs)
            self.seq_root=self.data_root/'sequential_reviews';self.seq_root.mkdir()
        def seq_action(self,action,**values):self._enqueue('seq',action,values)
        def seq_snapshot(self):
            with self.seq_lock:return copy.deepcopy(self.seq)
        def _seq_idle(self):
            if self.seq_thread is not None and self.seq_thread.is_alive():raise ValueError('Refinement still owns a model process')
        def _start_session(self):
            self._seq_idle();return super()._start_session()
        def _do_switch(self,*args,**kwargs):
            self._seq_idle();return super()._do_switch(*args,**kwargs)
        def _do_select_backend(self,*args,**kwargs):
            self._seq_idle();return super()._do_select_backend(*args,**kwargs)
        def _do_enrollment_start(self,*args,**kwargs):
            self._seq_idle();return super()._do_enrollment_start(*args,**kwargs)
        def _seq_emit(self,kind,value):
            row=dict(kind=kind,value=value,monotonic_ns=time.monotonic_ns())
            raw=(json.dumps(row,separators=(',',':'),ensure_ascii=False)+'\n').encode()
            path=self.seq_root/'CONTROLLER_EVENTS.jsonl'
            if (path.stat().st_size if path.exists() else 0)+len(raw)>2*1024**2:raise ValueError('Review event quota')
            with path.open('ab') as f:f.write(raw)
        def _do_seq(self,action,values):
            if action=='cancel':
                with self.seq_lock:
                    if not self.seq['owned']:raise ValueError('No active refinement to cancel')
                    self.seq_cancel.set();self.seq['phase']='CANCELLING'
                    self.seq_cancel_receipts.append(dict(owned=self.seq['owned'],phase='CANCELLING',job=self.seq['job'],monotonic_ns=time.monotonic_ns()))
                    self.state='REVIEW_CANCELLING';self.status='Cancelling refinement; retaining primary transcript'
                return
            self._seq_idle()
            if action in ('start','refine'):
                if self.engine is not None or self.consumer is not None or self.enrollment['state']!='IDLE':raise ValueError('Stop the current session first')
                if any(getattr(self.models,k,0) for k in ['asr_loads','speaker_loads']):raise ValueError('Resident caption models must be released before sequential mode')
                if values.get('source_sha256',source_digest)!=source_digest or sha(admission['source_wav'])!=source_digest:raise ValueError('Source binding changed')
                phase='sherpa' if action=='start' else 'a2'
                if phase=='a2' and self.seq['primary'] is None:raise ValueError('A completed primary transcript is required')
                if phase=='a2':self._validate_artifact(self.seq['primary'])
                job=self.seq_root/uuid.uuid4().hex;job.mkdir();(job/phase).mkdir();write(job/'ADMISSION.json',admission)
                with self.seq_lock:
                    if phase=='sherpa':self.seq.update(primary=None,primary_text='')
                    self.seq.update(phase='TRANSCRIBING' if phase=='sherpa' else 'REFINING',refined=None,refined_text='',error=None,
                                    owned=True,publications=0,job=str(job),saved=None)
                    self.seq_cancel=threading.Event()
                    self.state='REVIEWING';self.status='Saved transcription' if phase=='sherpa' else 'Nemotron refinement; primary retained'
                self.seq_thread=threading.Thread(target=self._seq_run,args=(job,phase),name='sequential-asr-owner')
                self.seq_thread.start();return
            if action=='save':
                if self.seq['primary'] is None:raise ValueError('No completed primary transcript')
                for artifact in [self.seq['primary'],self.seq['refined']]:
                    if artifact:self._validate_artifact(artifact)
                path=Path(self.seq['job'])/'SAVED.json';write(path,self.seq_snapshot())
                with self.seq_lock:self.seq['saved']=str(path)
                return
            if action=='open':
                path=Path(values['path']).resolve()
                if not path.is_relative_to(self.seq_root.resolve()) or path.name!='SAVED.json' or path.stat().st_size>2*1024**2:raise ValueError('Unsupported review archive')
                value=json.loads(path.read_text(encoding='utf-8'))
                if value['source_sha256']!=source_digest or sha(admission['source_wav'])!=source_digest or value['owned']:raise ValueError('Archive source/ownership mismatch')
                for key in ['primary','refined']:
                    if value[key]:self._validate_artifact(value[key])
                with self.seq_lock:self.seq=value;self.seq['saved']=str(path)
                return
            raise ValueError('Unsupported sequential action')
        def _validate_artifact(self,artifact):
            if artifact['source_sha256']!=source_digest:raise ValueError('Artifact source mismatch')
            for key in ['result','events']:
                path=Path(artifact[key]).resolve()
                if not path.is_relative_to(self.seq_root.resolve()) or sha(path)!=artifact[key+'_sha256']:raise ValueError('Archive artifact changed')
            result=json.loads(Path(artifact['result']).read_text())
            if result['status']!='PHASE_COLLECTED' or not result['model_closed'] or result['source_sha256']!=source_digest:raise ValueError('Incomplete phase artifact')
        def _seq_run(self,job,phase):
            proc=None;forced=False;count=0;offset=0;texts={};began=time.monotonic_ns();result=None;error=None
            d=job/phase;events=d/'EVENTS.jsonl'
            def consume():
                nonlocal offset,count
                if not events.exists():return
                with events.open(encoding='utf-8') as f:
                    f.seek(offset)
                    while True:
                        start=f.tell();line=f.readline()
                        if not line.endswith('\n'):f.seek(start);break
                        value=json.loads(line);event=value['event'];count+=1
                        text=event.get('raw_text',event.get('text',''))
                        texts[str(event['utterance'])]=text
                        with self.seq_lock:
                            self.seq['publications']=count
                            self.seq['primary_text' if phase=='sherpa' else 'refined_text']='\n'.join(t for t in texts.values() if t)
                        self._seq_emit('publication',dict(backend=phase,source_sha256=source_digest,publication=value))
                    offset=f.tell()
            try:
                available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
                if available<(850 if phase=='sherpa' else 1408)*1024**2:raise RuntimeError('Available RAM floor before model load')
                if sha(admission['source_wav'])!=source_digest:raise ValueError('Source changed before model load')
                env=os.environ.copy();env['LD_LIBRARY_PATH']=str(Path(admission['a2_parent'])/'lib')
                with (d/'process.log').open('xb') as log:
                    proc=subprocess.Popen([sys.executable,'-B',str(root/'sequential_asr_child_v2.py'),'--phase',phase,'--root',str(job)],stdout=log,stderr=subprocess.STDOUT,env=env)
                    while proc.poll() is None:
                        consume()
                        if self.seq_cancel.is_set() and not (d/'CANCEL.json').exists():write(d/'CANCEL.json',dict(cancel=True))
                        if time.monotonic_ns()-began>180*10**9:raise TimeoutError('Phase deadline')
                        time.sleep(.02)
                    consume()
                owner=json.loads((d/'CHILD_OWNER.json').read_text())
                assert ticks(owner['pid'])!=owner['start_ticks']
                result=json.loads((d/'RESULT.json').read_text())
                if proc.returncode not in (0,2) or not result['model_closed']:raise RuntimeError('Phase failed: '+str(result.get('error',proc.returncode)))
            except Exception as exc:error=type(exc).__name__+': '+str(exc)
            finally:
                if proc is not None and proc.poll() is None:
                    forced=True;proc.terminate()
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
                closed=proc is None or proc.poll() is not None
                with self.seq_lock:
                    cancelled=self.seq_cancel.is_set() or (result or {}).get('status')=='PHASE_CANCELLED'
                    success=error is None and not forced and not cancelled and (result or {}).get('status')=='PHASE_COLLECTED'
                    if success:
                        artifact=dict(result=str(d/'RESULT.json'),result_sha256=sha(d/'RESULT.json'),events=str(events),events_sha256=sha(events),source_sha256=source_digest,backend=phase)
                        self.seq['primary' if phase=='sherpa' else 'refined']=artifact
                    elif phase=='a2':self.seq['refined']=None;self.seq['refined_text']=''
                    self.seq['phase']=('PRIMARY_READY' if phase=='sherpa' else 'COMPLETE') if success else (('PRIMARY' if phase=='sherpa' else 'REFINEMENT')+('_CANCELLED' if cancelled and error is None and not forced else '_FAILED'))
                    self.seq['error']=error;self.seq['owned']=not closed
                    self.state='STOPPED' if error is None and not forced else 'ERROR';self.error=error
                    self.status=self.seq['phase']
                    terminal=dict(phase=phase,state=self.seq['phase'],job=str(job),source_sha256=source_digest,launch_ns=began,reaped_ns=time.monotonic_ns(),child_exit=None if proc is None else proc.returncode,forced=forced,publications=count,owner_closed=closed,primary_retained=self.seq['primary'] is not None)
                    write(job/'TERMINAL.json',terminal);self.seq_history.append(terminal)
                    self._seq_emit('terminal',terminal)
        def _do_close(self):
            if self.seq_thread is not None and self.seq_thread.is_alive():
                self.seq_cancel.set();self.seq_thread.join(30)
                if self.seq_thread.is_alive():raise RuntimeError('Sequential model still closing; ownership retained')
            return super()._do_close()
    return SequentialController
