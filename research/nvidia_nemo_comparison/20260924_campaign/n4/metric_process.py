"""Owned, bounded, persistent evaluator process. See README_SCORING_BANK.md."""
import contextlib
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import time

PROTOCOL='n4-metric-process-v1'
MAX_REQUEST=16*1024**2
MAX_RESPONSE=2*1024**2
STDERR_LIMIT=64*1024


def identity(process):
    return dict(pid=process.pid,create_time=process.create_time())


def exact_process(owner):
    import psutil
    try:
        p=psutil.Process(owner['pid'])
        return p if abs(p.create_time()-owner['create_time'])<.001 else None
    except psutil.NoSuchProcess:return None


def pin():
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import psutil
    p=psutil.Process();p.cpu_affinity([14]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    return p


class MetricProcessError(RuntimeError):
    def __init__(self,status,detail):
        super().__init__(detail);self.status=status


class MetricProcess:
    """One request in flight, finite pipes, and exact owned-identity cleanup.

    The Windows venv launcher can have a distinct interpreter child. Admit only
    its verified direct child; never terminate by executable name or bare PID.
    No model, application or microphone code is imported in this process.
    """
    def __init__(self,*,startup_seconds=30):
        self.startup_seconds=startup_seconds;self.process=None;self.owners=[]
        self.worker=None;self.threads=[];self.stderr=bytearray();self.stderr_total=0
        self.messages=queue.Queue(maxsize=2);self.stop=threading.Event();self.sequence=0
        self.nonce=secrets.token_hex(16);self.closed=False;self.close_receipt=None

    def _command(self):
        return [sys.executable,'-B',str(Path(__file__).resolve()),'--worker',self.nonce]

    def _stdout(self):
        try:
            while not self.stop.is_set():
                data=self.process.stdout.readline(MAX_RESPONSE+1)
                if not data:item=('error','EOF')
                elif len(data)>MAX_RESPONSE or not data.endswith(b'\n'):item=('error','OVERSIZE_OR_PARTIAL_RESPONSE')
                else:
                    try:item=('data',json.loads(data))
                    except (ValueError,UnicodeError):item=('error','INVALID_JSON')
                try:self.messages.put(item,timeout=.5)
                except queue.Full:return
                if item[0]=='error':return
        except (OSError,ValueError):
            if not self.stop.is_set():
                try:self.messages.put(('error','PIPE_ERROR'),timeout=.5)
                except queue.Full:pass

    def _stderr(self):
        try:
            while data:=self.process.stderr.read(4096):
                self.stderr_total+=len(data)
                self.stderr.extend(data[:max(0,STDERR_LIMIT-len(self.stderr))])
        except (OSError,ValueError):pass

    def _receive(self,deadline):
        try:kind,value=self.messages.get(timeout=max(0,deadline-time.monotonic()))
        except queue.Empty:raise MetricProcessError('TIMEOUT','Metric response deadline exceeded') from None
        if kind!='data':raise MetricProcessError('PROTOCOL_ERROR',value)
        return value

    def _discover(self):
        if not self.owners:return
        root=exact_process(self.owners[0])
        if root is None:return
        # Only this spawned launcher's direct children are within this contract.
        # A scorer must never create a model service or subprocess tree.
        for child in root.children():
            item=identity(child)
            if item not in self.owners:self.owners.append(item)

    def start(self):
        if self.process is not None or self.closed:raise ValueError('Fresh process client required')
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1')
        for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):env[key]='1'
        self.process=subprocess.Popen(self._command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env=env,bufsize=0,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        import psutil
        root=psutil.Process(self.process.pid);self.owners=[identity(root)]
        root.cpu_affinity([14]);root.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        for target in (self._stdout,self._stderr):
            t=threading.Thread(target=target,name='n4-metric-pipe',daemon=True);self.threads.append(t);t.start()
        try:
            hello=self._receive(time.monotonic()+self.startup_seconds);self._discover()
            if (hello.get('protocol')!=PROTOCOL or hello.get('nonce')!=self.nonce
                    or hello.get('status')!='READY' or hello.get('owner') not in self.owners
                    or hello.get('affinity')!=[14] or hello.get('models_loaded')!=0):
                raise MetricProcessError('PROTOCOL_ERROR','Invalid owned worker handshake')
            self.worker=hello['owner']
            if exact_process(self.worker) is None:raise MetricProcessError('PROCESS_EXITED','Worker exited at handshake')
            return hello
        except BaseException:
            self.close();raise

    def score(self,truth,prediction,*,timeout_seconds=60):
        from common import fingerprint
        if not self.worker or self.closed:raise ValueError('A ready open process is required')
        if not 0<timeout_seconds<=120:raise ValueError('Metric timeout must be in (0,120] seconds')
        self.sequence+=1
        payload=dict(truth=truth,prediction=prediction)
        request=dict(protocol=PROTOCOL,sequence=self.sequence,input_sha256=fingerprint(payload),payload=payload)
        data=(json.dumps(request,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
        if len(data)>MAX_REQUEST:raise MetricProcessError('INPUT_TOO_LARGE','Metric input exceeded fixed bound')
        deadline=time.monotonic()+timeout_seconds;written=threading.Event();write_errors=[]
        def send():
            try:
                view=memoryview(data)
                while view:
                    count=self.process.stdin.write(view)
                    if not count:raise BrokenPipeError('Metric input closed')
                    view=view[count:]
            except (OSError,ValueError) as exc:write_errors.append(type(exc).__name__)
            finally:written.set()
        t=threading.Thread(target=send,name='n4-metric-input',daemon=True);self.threads.append(t);t.start()
        try:
            response=self._receive(deadline)
            if not written.wait(max(0,deadline-time.monotonic())) or write_errors:
                raise MetricProcessError('PROTOCOL_ERROR','Request pipe did not complete')
            if (response.get('protocol')!=PROTOCOL or response.get('sequence')!=self.sequence
                    or response.get('input_sha256')!=request['input_sha256'] or response.get('owner')!=self.worker):
                raise MetricProcessError('PROTOCOL_ERROR','Response identity or request binding differs')
            if response.get('status')!='SCORED':
                raise MetricProcessError('METRIC_ERROR','Evaluator failed: '+str(response.get('error_type','unknown')))
            if not isinstance(response.get('score'),dict):raise MetricProcessError('PROTOCOL_ERROR','Missing metric object')
            return response
        except BaseException:
            self.close();raise
        finally:
            if not t.is_alive():self.threads.remove(t)

    def close(self):
        if self.closed:return self.close_receipt
        self.closed=True;self._discover()
        if self.process is None:return None
        self.stop.set()
        # Clean EOF first; a native call does not read it, then receives an exact
        # identity-checked termination. Child first, launcher last.
        try:self.process.stdin.close()
        except (OSError,ValueError):pass
        try:self.process.wait(timeout=.25)
        except subprocess.TimeoutExpired:
            for owner in reversed(self.owners):
                p=exact_process(owner)
                if p is not None:
                    try:p.terminate()
                    except __import__('psutil').NoSuchProcess:pass
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:raise RuntimeError('Owned metric launcher did not stop') from None
        for owner in self.owners:
            p=exact_process(owner)
            if p is not None:
                try:p.wait(timeout=5)
                except __import__('psutil').TimeoutExpired:raise RuntimeError('Owned metric child did not stop') from None
        for t in self.threads:t.join(timeout=2)
        for pipe in (self.process.stdout,self.process.stderr):pipe.close()
        if any(t.is_alive() for t in self.threads):raise RuntimeError('Metric pipe thread did not close')
        self.close_receipt=dict(owners=self.owners,all_exact_owners_exited=True,pipe_threads_closed=True,
            requests=self.sequence,stderr_bytes=self.stderr_total,stderr_retained_bytes=len(self.stderr))
        return self.close_receipt


def worker(nonce):
    p=pin()
    from common import fingerprint
    from integrated_scoring_adapter import score_prediction
    owner=identity(p)
    def emit(value):
        encoded=(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
        if len(encoded)>MAX_RESPONSE:raise ValueError('Metric response exceeds limit')
        sys.stdout.buffer.write(encoded);sys.stdout.buffer.flush()
    emit(dict(protocol=PROTOCOL,nonce=nonce,status='READY',owner=owner,affinity=p.cpu_affinity(),models_loaded=0))
    sequence=0
    while line:=sys.stdin.buffer.readline(MAX_REQUEST+1):
        if len(line)>MAX_REQUEST or not line.endswith(b'\n'):raise ValueError('Request bound exceeded')
        request=json.loads(line);sequence+=1
        if (request['protocol']!=PROTOCOL or request['sequence']!=sequence
                or fingerprint(request['payload'])!=request['input_sha256']):raise ValueError('Metric request changed')
        response=dict(protocol=PROTOCOL,sequence=sequence,input_sha256=request['input_sha256'],owner=owner)
        try:
            with contextlib.redirect_stdout(sys.stderr):
                score=score_prediction(request['payload']['truth'],request['payload']['prediction'])
            emit(dict(response,status='SCORED',score=score))
        except Exception as exc:
            # Keep private reference/prediction content out of error messages.
            emit(dict(response,status='METRIC_ERROR',error_type=type(exc).__name__))


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--worker':raise SystemExit('Internal worker; use scoring_bank.py (README_SCORING_BANK.md)')
    worker(sys.argv[2])
