"""Broker physical metadata slots; README_FIELD_OPERATOR_BROKER_V1.md."""
import os
from pathlib import Path
import stat
from field_operator_broker_layout_v1 import ONCE,APPEND,CODE_MAXIMUM,CODE_COUNT,CODE_MEMBER_MAXIMUM
from field_operator_session_plan_v1 import encoded

def inspect(root,allow_pending=False):
    root=Path(root);total=0;count=0
    for folder in ('broker','code'):
        directory=root/folder
        if directory.is_symlink() or not directory.is_dir():raise ValueError('Real allocated broker directory')
        for p in directory.iterdir():
            s=p.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:raise ValueError('Broker member type')
            if folder=='code':
                if not p.name.replace('_','').replace('-','').replace('.','').isalnum():raise ValueError('Code basename')
                cap=CODE_MEMBER_MAXIMUM;count+=1;total+=s.st_size
            else:
                name=p.name
                if name.endswith('.pending'):
                    if not allow_pending:raise RuntimeError('Broker pending fault preserved')
                    name=name[:-8]
                    if name not in ONCE:raise ValueError('Unallocated pending broker file')
                cap=ONCE.get(name,APPEND.get(name))
                if cap is None:raise ValueError('Unallocated broker file')
            if s.st_size>cap:raise ValueError('Broker per-file quota')
    if count>CODE_COUNT or total>CODE_MAXIMUM:raise ValueError('Broker code cardinality/aggregate')
    return dict(code_files=count,code_bytes=total)

class Files:
    def __init__(self,root,check):
        self.root=Path(root);self.check=check;self.failed=False;inspect(root)
    def write(self,name,data,append=False):
        if self.failed:raise RuntimeError('Broker writer fault is latched')
        self.check();inspect(self.root)
        if type(data) is not bytes:raise ValueError('Exact encoded bytes')
        caps=APPEND if append else ONCE
        if name not in caps:raise ValueError('Unknown broker writer')
        target=self.root/'broker'/name
        if append:
            old=target.stat().st_size if target.exists() else 0
            if old+len(data)>caps[name]:raise ValueError('Broker append allocation')
        elif target.exists() or target.with_name(name+'.pending').exists():
            raise FileExistsError('Broker once slot consumed')
        if len(data)>caps[name]:raise ValueError('Broker file maximum')
        self.failed=True
        path=target if append else target.with_name(name+'.pending')
        flags=os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|(os.O_APPEND if append else os.O_EXCL)
        fd=os.open(path,flags,0o600)
        try:
            for offset in range(0,len(data),16384):
                block=memoryview(data[offset:offset+16384])
                while block:
                    n=os.write(fd,block)
                    if not n:raise OSError('Broker short write')
                    block=block[n:]
            os.fsync(fd)
        finally:os.close(fd)
        if not append:
            os.link(path,target,follow_symlinks=False);self._sync()
            path.unlink();self._sync()
            if target.read_bytes()!=data:raise IOError('Broker primary readback')
        self.failed=False
    def _sync(self):
        fd=os.open(self.root/'broker',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    def json(self,name,value):self.write(name,encoded(value))
