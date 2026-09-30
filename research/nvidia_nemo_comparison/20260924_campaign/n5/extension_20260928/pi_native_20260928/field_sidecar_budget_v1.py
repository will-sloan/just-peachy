"""Pre-write sidecar quotas; README_FIELD_SIDECAR_BUDGET_V1.md."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import stat

FIELDS={'maximum_bytes','maximum_file_bytes','maximum_files','maximum_write_bytes','minimum_free_bytes'}
class BudgetExceeded(RuntimeError):pass

def validate(value):
    if type(value) is not dict or set(value)!=FIELDS:raise ValueError('Sidecar budget fields')
    if any(type(v) is not int or v<=0 for v in value.values()):raise ValueError('Positive integer sidecar budget required')
    if not value['maximum_write_bytes']<=value['maximum_file_bytes']<=value['maximum_bytes']:raise ValueError('Sidecar budget order')
    if value['maximum_bytes']>12*1024**2 or value['maximum_files']>128:raise ValueError('Sidecar hard ceiling')
    if value['minimum_free_bytes']!=5*1024**3:raise ValueError('Fixed Pi free-space reserve required')
    return dict(value)

def encoded(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')

class GroupWriter:
    """A dedicated flat directory; all cooperating writers use the same guard.

    Counts old plus pending replacements. Failed pending writes stay preserved.
    No automatic cleanup, retry, deletion, truncation or completion claim.
    """
    def __init__(self,root,budget):
        self.root=Path(root).absolute();self.budget=validate(budget)
        if not self.root.is_dir() or self.root.is_symlink():raise ValueError('Existing real sidecar directory required')
    @contextmanager
    def _locked(self):
        d=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        guard=None
        try:
            guard=os.open('.budget.guard',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=d)
            s=os.fstat(guard)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size:raise ValueError('Invalid sidecar guard')
            fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield d
        finally:
            if guard is not None:os.close(guard)
            os.close(d)
    def _inventory(self,d):
        rows={}
        for name in os.listdir(d):
            if name=='.budget.guard':continue
            s=os.stat(name,dir_fd=d,follow_symlinks=False)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1:raise ValueError('Sidecar links/directories are forbidden')
            if s.st_size>self.budget['maximum_file_bytes']:raise BudgetExceeded('Existing sidecar file exceeds limit')
            rows[name]=s.st_size
        return rows
    def snapshot(self):
        with self._locked() as d:
            rows=self._inventory(d)
            return dict(bytes=sum(rows.values()),files=len(rows),sizes=rows,budget=self.budget)
    def write(self,name,raw,*,append=False,replace=False):
        if type(name) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',name) or name.endswith('.pending'):raise ValueError('Flat sidecar name required')
        if type(raw) is not bytes or type(append) is not bool or type(replace) is not bool or append and replace:raise ValueError('Explicit byte write mode required')
        b=self.budget
        if len(raw)>b['maximum_write_bytes']:raise BudgetExceeded('Sidecar write byte limit')
        with self._locked() as d:
            rows=self._inventory(d);old=rows.get(name,0);exists=name in rows
            if any(n.endswith('.pending') for n in rows):raise BudgetExceeded('Preserved pending write requires review')
            if exists and not (append or replace):raise FileExistsError(name)
            final=old+len(raw) if append else len(raw)
            if final>b['maximum_file_bytes']:raise BudgetExceeded('Sidecar file byte limit')
            # Append adds only the new bytes; publish/replace includes pending data
            # while any old destination still exists.
            count=len(rows)+(0 if append and exists else 1)
            if count>b['maximum_files'] or sum(rows.values())+len(raw)>b['maximum_bytes']:raise BudgetExceeded('Sidecar group byte/file limit')
            if shutil.disk_usage(self.root).free<b['minimum_free_bytes']+len(raw):raise BudgetExceeded('Pi free-space reserve')
            if append:
                flags=os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW|(0 if exists else os.O_CREAT|os.O_EXCL)
                fd=os.open(name,flags,0o600,dir_fd=d)
            else:
                fd=os.open(name+'.pending',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=d)
            try:
                view=memoryview(raw)
                while view:
                    wrote=os.write(fd,view)
                    if not wrote:raise OSError('Short sidecar write')
                    view=view[wrote:]
                os.fsync(fd)
            finally:os.close(fd)
            if not append:os.replace(name+'.pending',name,src_dir_fd=d,dst_dir_fd=d)
            os.fsync(d)
            return dict(name=name,accepted_bytes=len(raw),final_bytes=final,append=append,replace=replace)
    def json(self,name,value,*,replace=False):return self.write(name,encoded(value),replace=replace)
    def jsonl(self,name,value):return self.write(name,encoded(value)+b'\n',append=True)
