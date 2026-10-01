"""Bounded host SSH phases; README_FIELD_OPERATOR_BROKER_DISPATCH_V2.md."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import threading
import time

def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def checked_pins(rows):
    seen=set()
    for row in rows:
        p=Path(row['path'])
        if str(p) in seen:raise ValueError('Duplicate host pin')
        seen.add(str(p))
        if p.is_symlink() or p.stat().st_size!=row['bytes'] or digest(p)!=row['sha256']:
            raise ValueError('Host source changed')
    return seen

def process_phase(command, *, payload=None, timeout, stop_unit=None, maximum=262144):
    """One SSH process, three bounded I/O threads, no mutation retry."""
    from dispatch_b01_stack_v2 import SSH
    from field_host_budget_v1 import floors
    if type(maximum) is not int or not 1<=maximum<=262144 or not 0<timeout<=420:
        raise ValueError('Explicit bounded SSH phase')
    if not isinstance(command,list) or not command or any(type(x) is not str for x in command):raise ValueError('Explicit process argv')
    if payload is not None and (type(payload) is not bytes or len(payload)>4*1024**2):raise ValueError('Input cap')
    threading.stack_size(1048576)
    proc=subprocess.Popen(command,stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    buffers=[bytearray(),bytearray()];overflow=threading.Event();writer_error=[];reader_error=[]
    def drain(index,pipe):
        try:
            while True:
                block=pipe.read(4096)
                if not block:return
                room=maximum-len(buffers[index]);buffers[index].extend(block[:room])
                if len(block)>room:overflow.set();return
        except BaseException as e:reader_error.append(type(e).__name__+': '+str(e)[:512])
    def send():
        try:
            if payload is not None:
                if type(payload) is not bytes or len(payload)>4*1024**2:raise ValueError('Input cap')
                view=memoryview(payload)
                while view:
                    n=proc.stdin.write(view[:16384])
                    if not n:raise IOError('SSH stdin short write')
                    view=view[n:]
                proc.stdin.flush()
        except BaseException as e:writer_error.append(type(e).__name__+': '+str(e)[:512])
        finally:proc.stdin.close()
    threads=[threading.Thread(target=drain,args=(i,pipe),daemon=True) for i,pipe in enumerate((proc.stdout,proc.stderr))]
    threads.append(threading.Thread(target=send,daemon=True))
    for t in threads:t.start()
    end=time.monotonic()+timeout;fault=None
    try:
        while proc.poll() is None:
            floors()
            if overflow.is_set():raise RuntimeError('SSH output quota')
            if writer_error:raise RuntimeError(writer_error[0])
            if reader_error:raise RuntimeError(reader_error[0])
            if time.monotonic()>=end:raise TimeoutError('SSH phase deadline')
            time.sleep(.02)
    except BaseException as e:
        fault=type(e).__name__+': '+str(e)[:512]
        if stop_unit is not None:
            # The caller supplies the one admitted unit. Stop before diagnostics.
            import re
            if not re.fullmatch(r'jp-field-operator-sessions-v[1-9][0-9]*',stop_unit):
                raise ValueError('Exact owned unit only')
            subprocess.run(SSH+['systemctl --user stop --no-block '+stop_unit],
                timeout=10,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    finally:
        try:proc.wait(timeout=35 if stop_unit else 5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        for t in threads:t.join(3)
        for pipe in (proc.stdin,proc.stdout,proc.stderr):
            if not pipe.closed:pipe.close()
    if fault is None and (overflow.is_set() or writer_error or reader_error or any(t.is_alive() for t in threads)):
        fault='Late I/O completion failure'
    return dict(returncode=proc.returncode,stdout=bytes(buffers[0]),stderr=bytes(buffers[1]),
        fault=fault,overflow=overflow.is_set(),writer_error=writer_error,reader_error=reader_error,
        readers_joined=all(not t.is_alive() for t in threads),ssh_reaped=proc.poll() is not None)

CLOSED_ONE=r'''import os,json,resource,signal
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(134217728,)*2)
resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2);resource.setrlimit(resource.RLIMIT_FSIZE,(0,0));signal.alarm(10)
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
me=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
rows=[]
for o in OWNERS:
 t=ticks(o['pid']);assert boot!=o['boot_id'] or t!=o['start_ticks']
 rows.append(dict(owner=o,observed_start_ticks=t,exact_alive=False))
print(json.dumps(dict(owners=rows,utility_owner=me)))
'''

def closed_owners(owners):
    from dispatch_geometry_v2 import remote
    from dispatch_b01_stack_v2 import SSH
    value=remote('OWNERS='+repr(owners)+'\n'+CLOSED_ONE)
    # This exact utility has naturally returned; verify absence before a backup claim.
    p=value['utility_owner']
    result=subprocess.run(SSH+['test ! -e /proc/'+str(p['pid'])],capture_output=True,timeout=10)
    if result.returncode:raise RuntimeError('Closure utility still present')
    value['utility_pid_absent_after_ssh']=True
    return value


def ssh_phase(command, **kwargs):
    from dispatch_b01_stack_v2 import SSH
    return process_phase(SSH+['exec '+shlex.join(command)],**kwargs)
