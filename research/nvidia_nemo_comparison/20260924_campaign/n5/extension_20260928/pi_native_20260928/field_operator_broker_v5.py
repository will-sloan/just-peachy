"""Nested broker qualification; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V6.md."""
import os
from pathlib import Path
import resource
import subprocess
import sys
import threading
import time
from field_operator_session_ledger_v4 import Ledger,read,file_pin,identity,ticks
from field_operator_session_plan_v3 import next_slot
from field_operator_broker_files_v2 import Files
from field_operator_history_v2 import History
from field_operator_entry_v9 import sink,available_ram,capture_closed
from field_child_deadline_v1 import validate,remaining,spawn,supervise

class Broker:
    """Owns actual parent subprocesses and closed-ledger history.

    Staging is a separate admitted native boundary: accept_staged may only
    receive the next root already RESERVED by this ledger. The native stager/
    outer resource gate and launch CLI must be wired before this becomes a user
    entry. This class never invents an admission or clears a failed slot.
    """
    def __init__(self,ledger,release,manifest_sha256):
        if type(ledger) is not Ledger or ledger.readonly:raise ValueError('Live native broker ledger')
        if os.sched_getaffinity(0)!={2,3} or resource.getrlimit(resource.RLIMIT_AS)!=(768*1024**2,)*2 or resource.getrlimit(resource.RLIMIT_STACK)!=(1048576,)*2:
            raise ValueError('Broker inherited resource envelope')
        self.ledger=ledger;self.files=Files(ledger.root,ledger._live)
        self.history=History(release,manifest_sha256)
        self.owner=identity()
        if read(ledger.root/'broker/OWNER.json')!=self.owner:raise ValueError('Entry owner binding')
        self.proc=None;self.watch=None;self.abort=threading.Event();self.watch_result={}
        self.current=None;self.parent_owner=None;self.ack=False;self.failed=False
        self.pipe_bytes=0;self.requested=False;self.history_opens=0
        self._unmapped()

    @staticmethod
    def _unmapped():
        maps=Path('/proc/self/maps').read_text()
        if 'libnemo_speech_' in maps or 'libggml' in maps:raise RuntimeError('Broker mapped model libraries')

    def reserve(self):
        if self.failed or self.current is not None or self.proc is not None:
            raise RuntimeError('Previous recording is not closed')
        if not capture_closed() or available_ram()<850*1024**2:raise RuntimeError('Capture/RAM preflight')
        self._unmapped()
        root=self.ledger.reserve();self.current=root.name
        return root

    def accept_staged(self,root):
        root=Path(root)
        if root!=self.ledger.root/'recordings'/str(self.current) or self.proc is not None:
            raise ValueError('Only the reserved independent root')
        a=read(root/'control/ADMISSION.json');cfg=read(root/'config/CONFIG.json')
        expected=dict(root=str(self.ledger.root),owner=self.owner,
                      policy_sha256=file_pin(self.ledger.root/'RELEASE.json')['sha256'],slot=self.current)
        if a.get('session_broker')!=expected:raise ValueError('Exact parent-to-broker binding')
        pins={r['path']:r for r in a['files']}
        for name in ('field_operator_parent_v11.py','field_operator_entry_v9.py'):
            p=root/'code'/name
            if file_pin(p)!=dict(bytes=pins[str(p)]['bytes'],sha256=pins[str(p)]['sha256']):
                raise ValueError('Selected interactive source binding')
        self.ledger.staged(self.current)
        self.deadline=validate(cfg['deadline'],a);self.admission=a
        if remaining(self.deadline)<180:raise RuntimeError('No useful recording lifetime')
        self.proc=spawn([sys.executable,'-B',str(root/'code/field_operator_parent_v11.py'),'--root',str(root)],
            self.deadline,a,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0,close_fds=True)
        os.set_blocking(self.proc.stdout.fileno(),False)
        self.abort.clear();self.watch_result={};self.ack=False;self.parent_owner=None;self.pipe_bytes=0
        threading.stack_size(1048576)
        def monitor():
            try:
                while self.proc.poll() is None and not self.abort.is_set() and remaining(self.deadline)>0:
                    self.abort.wait(.01)
                self.watch_result.update(supervise(self.proc,self.deadline,a,abort=self.abort.is_set()))
            except BaseException as exc:self.watch_result['error']=repr(exc)[:512]
        self.watch=threading.Thread(target=monitor,name='recording-parent-deadline',daemon=True);self.watch.start()

    def _drain(self):
        while self.proc is not None and not self.proc.stdout.closed:
            block=self.proc.stdout.read(16384)
            if not block:return
            sink(self.ledger.root/'recordings'/self.current,'logs').write('service.log',block,append=True)
            self.pipe_bytes+=len(block)

    def poll(self):
        if self.failed:raise RuntimeError('Broker failure is latched')
        self.ledger._live()
        if self.proc is None:return False
        root=self.ledger.root/'recordings'/self.current
        try:
            self._drain()
            if available_ram()<192*1024**2:raise RuntimeError('Sampled RAM stop')
            if not self.ack and (root/'control/OWNER.json').exists():
                owner=read(root/'control/OWNER.json')
                if owner!=dict(pid=self.proc.pid,start_ticks=ticks(self.proc.pid),boot_id=self.owner['boot_id']):
                    raise ValueError('Exact spawned recording-parent identity')
                # The immutable STARTED record precedes the one-time ACK.
                self.ledger.started(self.current,owner);self.parent_owner=owner
                # Publisher visibility may precede release of its group flock.
                import fcntl
                with (root/'control/.budget.guard').open('rb') as guard:
                    until=time.monotonic()+2
                    while True:
                        if ticks(self.proc.pid)!=owner['start_ticks'] or remaining(self.deadline)<=0:
                            raise RuntimeError('Parent disappeared before ready barrier')
                        try:fcntl.flock(guard,fcntl.LOCK_SH|fcntl.LOCK_NB)
                        except BlockingIOError:
                            if time.monotonic()>=until:raise TimeoutError('Parent ready barrier')
                            time.sleep(.002)
                        else:fcntl.flock(guard,fcntl.LOCK_UN);break
                sink(root,'control').json('ACK.json',dict(owner=owner,admission_sha256=file_pin(root/'control/ADMISSION.json')['sha256']))
                self.ack=True
            if self.proc.poll() is None:return False
            self.watch.join(3);self._drain();self.proc.stdout.close()
            if self.watch.is_alive() or self.proc.returncode!=0 or not self.ack or self.watch_result.get('error') or self.watch_result.get('terminate_sent') or self.watch_result.get('kill_sent'):
                raise RuntimeError('Recording parent did not return naturally')
            self.ledger.complete(self.current)
            self._unmapped()
            self.proc=None;self.watch=None;self.current=None
            return True
        except BaseException:
            self.failed=True;self.abort.set()
            raise

    def open_history(self,slot):
        if self.failed or self.current is not None or self.proc is not None or not capture_closed():
            raise RuntimeError('History requires fully closed recording')
        if self.history_opens>=16:raise RuntimeError('Bounded history-open allowance consumed')
        rows=[r for r in self.ledger.history() if r['slot']==slot]
        if len(rows)!=1:raise ValueError('Exact saved history selection')
        self.history_opens+=1
        return self.history.open(rows[0])

    def close(self):
        self.abort.set()
        if self.watch is not None:self.watch.join(32)
        if self.proc is not None:
            if self.watch.is_alive() or self.proc.poll() is None:
                raise RuntimeError('Outer gate must retain ownership for cleanup')
            try:self._drain()
            finally:self.proc.stdout.close()
        if not capture_closed():raise RuntimeError('Capture remains active')
        self.ledger.close()
