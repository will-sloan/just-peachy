"""Model-free Linux pthread stack measurement. See README_B01_STACK_V1.md."""
import ctypes
import json
import os
from pathlib import Path
import resource
import threading

assert sorted(os.sched_getaffinity(0))==[2,3]
resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,128*1024**2))
lib=ctypes.CDLL(None)
lib.pthread_self.restype=ctypes.c_ulong
lib.pthread_getattr_np.argtypes=[ctypes.c_ulong,ctypes.c_void_p]
lib.pthread_attr_getstack.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_size_t)]
lib.pthread_attr_destroy.argtypes=[ctypes.c_void_p]
rows=[]
def run(name):
    # Oversized, naturally aligned storage for glibc aarch64 pthread_attr_t.
    attr=(ctypes.c_ulong*32)();address=ctypes.c_void_p();size=ctypes.c_size_t()
    assert lib.pthread_getattr_np(lib.pthread_self(),attr)==0
    assert lib.pthread_attr_getstack(attr,ctypes.byref(address),ctypes.byref(size))==0
    assert lib.pthread_attr_destroy(attr)==0
    rows.append(dict(case=name,native_stack_bytes=size.value,memory=[x for x in Path('/proc/self/status').read_text().splitlines() if x.startswith(('VmSize:','VmRSS:','Threads:'))]))
for label,read_back in (('default',False),('set_without_getter',False),('set_then_getter',True)):
    if label!='default':threading.stack_size(1024*1024)
    if read_back:read_value=threading.stack_size()
    thread=threading.Thread(target=run,args=(label,));thread.start();thread.join()
print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),pid=os.getpid(),read_value=read_value,rows=rows)))
