"""Physical Python writer guard. See README_FIELD_LIVE_ENTRY_V1.md."""
import builtins
from contextlib import contextmanager
import io
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import threading

class PathBudgetError(RuntimeError):
    pass

TOKENS = dict(session='edge_guard_20000101T000000Z_00000000',
              conversation='0'*32,epoch='1'*32,runtime_token='2'*32)
PATTERNS = dict(session=r'edge_[a-z_]+_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}',
                conversation=r'[0-9a-f]{32}',epoch=r'[0-9a-f]{32}',runtime_token=r'[0-9a-f]{32}')
_ACTIVE = None


def attach(root,admission,outputs):
    """Install in each actual parent/child process after its genuine load checks."""
    global _ACTIVE
    root=Path(root).absolute();code=root/'code'
    rows={Path(r['path']).name:r['bytes'] for r in admission['files'] if Path(r['path']).parent==code}
    if _ACTIVE is None:
        _ACTIVE=PhysicalFiles(root,rows,lambda:outputs.request_stop(),
                             hardware_lease=Path.home()/'JustPeachy/data/xvf-hardware.lock').install()
    else:
        if _ACTIVE.root!=root or len(_ACTIVE.callbacks)>=8:
            raise PathBudgetError('Physical guard root or attachment count changed')
        from field_live_paths_v1 import project
        if _ACTIVE.contract!=project(**TOKENS,code_files=rows):
            raise PathBudgetError('Physical code layout changed')
        _ACTIVE.callbacks.append(lambda:outputs.request_stop())
    outputs.physical_files=_ACTIVE
    return outputs


class FileProxy:
    """Expose normal file operations while keeping every write under its slot."""
    def __init__(self,owner,stream,path):
        self._owner,self._stream,self._path=owner,stream,path
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def __iter__(self):return iter(self._stream)
    def __getattr__(self,name):
        if name in ('buffer','raw','detach'):
            raise PathBudgetError('Raw writable stream escape is unavailable')
        return getattr(self._stream,name)
    def write(self,value):
        stream=self._stream
        raw=value.encode(stream.encoding or 'utf-8') if isinstance(value,str) else value
        size=len(raw) if isinstance(raw,bytes) else memoryview(raw).nbytes
        with self._owner.lock:
            stream.flush()
            position=self._path.stat().st_size if 'a' in stream.mode or stream.fileno() in self._owner.append_fds else stream.tell()
            self._owner.reserve(self._path,size,position)
            try:
                result=stream.write(value);stream.flush()
            except BaseException as exc:self._owner.fail(self._path,exc);raise
            if result!=(len(value) if isinstance(value,str) else size):
                exc=PathBudgetError('Short physical file write retained')
                self._owner.fail(self._path,exc);raise exc
            self._owner.writes+=1
            return result
    def writelines(self,values):
        for value in values:self.write(value)
    def truncate(self,size=None):
        if size is None:size=self._stream.tell()
        return self._owner.truncate(self._stream.fileno(),size)
    def close(self):
        if self._stream.closed:return
        fd=self._stream.fileno()
        try:self._stream.close()
        except BaseException as exc:self._owner.fail(self._path,exc);raise
        finally:
            if self._stream.closed:
                self._owner.fds.pop(fd,None);self._owner.append_fds.discard(fd)


class PhysicalFiles:
    """One process, one physical layout, no automatic deletion or failed retry.

    Existing producer guards remain in force. This adds pre-open path/cardinality,
    per-file and aggregate byte guards to Python open/write/mutation interfaces.
    This is not a kernel quota or a sandbox against malicious native libraries.
    """
    def __init__(self,root,code_files,request_stop,*,hardware_lease=None):
        from field_live_paths_v1 import project
        self.root=Path(root).absolute()
        if self.root.resolve()!=self.root or self.root.is_symlink() or not self.root.is_dir():
            raise ValueError('Precreated real output root required')
        self.contract=project(**TOKENS,code_files=code_files)
        self.ids={};self.paths={};self.fds={};self.append_fds=set();self.failures={};self.callbacks=[request_stop]
        self.lock=threading.RLock();self.local=threading.local();self.writes=0
        self.installed=False;self.audit_armed=False
        self.hardware=Path(hardware_lease).absolute() if hardware_lease else None
        if self.hardware is not None:
            s=self.hardware.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size!=1:
                raise ValueError('Existing one-byte hardware lease inode required')
            self.hardware_identity=(s.st_dev,s.st_ino,s.st_size)
        self.original=dict(open=builtins.open,io_open=io.open,os_open=os.open,write=os.write,
            close=os.close,mkdir=os.mkdir,replace=os.replace,rename=os.rename,link=os.link,
            unlink=os.unlink,remove=os.remove,ftruncate=os.ftruncate,truncate=os.truncate)
        self.file_patterns=[(self.pattern(name),name,row) for name,row in self.contract['paths'].items()]
        self.dir_patterns=[self.pattern(name) for name in self.contract['directories']]
        for path in self.root.rglob('*'):
            if path.is_symlink():raise ValueError('Initial output symlink')
            if path.is_dir():self.directory(path)
            else:self.match(path)
        self.census()

    def pattern(self,value):
        result=re.escape(value)
        for name,token in TOKENS.items():
            result=result.replace(re.escape(token),'(?P<'+name+'>'+PATTERNS[name]+')')
        return re.compile(result+'\\Z')

    def identity(self,match):
        for name,value in match.groupdict().items():
            if name in self.ids and self.ids[name]!=value:
                raise PathBudgetError('Second physical '+name+' is not reserved')
        self.ids.update(match.groupdict())

    def path(self,value,dir_fd=None):
        if isinstance(value,int):
            if value not in self.fds:raise PathBudgetError('Unregistered writable descriptor')
            return self.fds[value]
        path=Path(os.fsdecode(value))
        if '..' in path.parts:raise PathBudgetError('Parent traversal is unavailable')
        if not path.is_absolute():
            base=Path(os.readlink('/proc/self/fd/'+str(dir_fd))) if dir_fd is not None else Path.cwd()
            path=base/path
        path=path.absolute()
        if path==self.hardware or path==Path(os.devnull):return path
        if not path.is_relative_to(self.root):raise PathBudgetError('Write outside the admitted output root')
        for ancestor in (path,)+tuple(path.parents):
            if ancestor==self.root.parent:break
            if ancestor.is_symlink():raise PathBudgetError('Output symlink is unavailable')
        return path

    def match(self,path):
        path=self.path(path)
        if path in self.paths:return self.paths[path]
        name=path.relative_to(self.root).as_posix()
        for regex,template,row in self.file_patterns:
            m=regex.fullmatch(name)
            if m:
                self.identity(m);self.paths[path]=(template,row);return template,row
        raise PathBudgetError('Unassigned physical file: '+name)

    def directory(self,path):
        path=self.path(path);name='' if path==self.root else path.relative_to(self.root).as_posix()
        for regex in self.dir_patterns:
            m=regex.fullmatch(name)
            if m:
                self.identity(m)
                if path.exists():
                    s=path.stat()
                    if not stat.S_ISDIR(s.st_mode) or max(s.st_size,getattr(s,'st_blocks',0)*512)>65536:
                        raise PathBudgetError('Directory extent exceeded its reservation')
                return
        raise PathBudgetError('Unassigned physical directory: '+name)

    def bucket(self,bucket,changed=None,size=None):
        used=count=0
        for path,(_,row) in self.paths.items():
            if row['bucket']!=bucket:continue
            if path==changed:
                used+=size;count+=1
            elif path.exists():
                s=path.lstat()
                if not stat.S_ISREG(s.st_mode):raise PathBudgetError('Nonregular physical output')
                if s.st_nlink!=1 and row['bucket']!='application_lock':raise PathBudgetError('Unassigned hard link')
                if s.st_size>row['maximum_bytes']:raise PathBudgetError('Existing physical slot exceeded')
                used+=s.st_size;count+=1
        cap=self.contract['buckets'][bucket]
        if used>cap['maximum_bytes'] or count>cap['maximum_files']:
            raise PathBudgetError('Physical aggregate exhausted: '+bucket)

    def reserve(self,path,length,position):
        try:
            if path in self.failures:raise PathBudgetError('Failed physical writer cannot retry')
            if path==Path(os.devnull):return
            if path==self.hardware:raise PathBudgetError('Hardware lease content must remain unchanged')
            _,row=self.match(path)
            if type(length) is not int or not 0<=length<=1024**2 or position<0:
                raise PathBudgetError('Physical write size or offset')
            old=path.stat().st_size if path.exists() else 0
            size=max(old,position+length)
            if size>row['maximum_bytes']:raise PathBudgetError('Physical file slot exhausted')
            self.bucket(row['bucket'],path,size)
            if shutil.disk_usage(self.root).free<5*1024**3+max(0,size-old):
                raise PathBudgetError('Pi free floor reached before write')
        except BaseException as exc:self.fail(path,exc);raise

    def fail(self,path,exc):
        # Signal Stop before any caller attempts to serialize diagnostics.
        for callback in tuple(self.callbacks):
            try:callback()
            except Exception:pass
        key=path if len(self.failures)<256 or path in self.failures else None
        self.failures.setdefault(key,type(exc).__name__+': '+str(exc)[:512])

    @contextmanager
    def internal(self):
        self.local.depth=getattr(self.local,'depth',0)+1
        try:yield
        finally:self.local.depth-=1

    def opening(self,path,mode,flags):
        if path==Path(os.devnull):return
        if path==self.hardware:
            s=path.lstat()
            if (s.st_dev,s.st_ino,s.st_size)!=self.hardware_identity or flags&os.O_TRUNC:
                raise PathBudgetError('Hardware lease identity/content changed')
            return
        self.match(path)
        group=path.parts[len(self.root.parts)]
        late_owner=group=='control' and path.name in ('.budget.guard','REGISTERED_OWNER.json.pending')
        if late_owner and path.name!='.budget.guard' and (path.parent/'REGISTERED_OWNER.json').exists():
            raise PathBudgetError('Source owner already registered; no second source process')
        if group=='code' or (group=='control' and not late_owner) or path.name in ('CONFIG.json','live_config.json','n2_runtime.json'):
            raise PathBudgetError('Admitted code/control/input is read-only at runtime')
        if flags&os.O_TRUNC and path.exists() and path.stat().st_size:
            raise PathBudgetError('Truncating retained data is unavailable')
        self.reserve(path,0,0)

    def open(self,file,mode='r',buffering=-1,encoding=None,errors=None,newline=None,closefd=True,opener=None):
        writing=any(c in mode for c in 'wax+')
        if not writing:return self.original['open'](file,mode,buffering,encoding,errors,newline,closefd,opener)
        path=None
        try:
            with self.lock:
                path=self.path(file)
                if opener is not None or encoding not in (None,'utf-8','utf8','ascii') or newline not in (None,'\n'):
                    raise PathBudgetError('Custom writable opener/encoding/newline unavailable')
                self.opening(path,mode,os.O_TRUNC if 'w' in mode else 0)
                with self.internal():stream=self.original['open'](file,mode,buffering,encoding,errors,newline,closefd,opener)
                self.fds[stream.fileno()]=path
                return FileProxy(self,stream,path)
        except BaseException as exc:self.fail(path,exc);raise

    def os_open(self,path,flags,mode=0o777,*,dir_fd=None):
        if not flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
            return self.original['os_open'](path,flags,mode,dir_fd=dir_fd)
        absolute=None
        try:
            with self.lock:
                absolute=self.path(path,dir_fd);self.opening(absolute,None,flags)
                with self.internal():fd=self.original['os_open'](absolute,flags,mode)
                self.fds[fd]=absolute
                if flags&os.O_APPEND:self.append_fds.add(fd)
                return fd
        except BaseException as exc:self.fail(absolute,exc);raise

    def write(self,fd,raw):
        with self.lock:
            if fd not in self.fds:
                mode=os.fstat(fd).st_mode
                if stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode) or fd in (1,2):return self.original['write'](fd,raw)
                exc=PathBudgetError('Unregistered file-descriptor write');self.fail(None,exc);raise exc
            path=self.fds[fd];length=memoryview(raw).nbytes
            position=path.stat().st_size if fd in self.append_fds else os.lseek(fd,0,os.SEEK_CUR)
            self.reserve(path,length,position)
            try:n=self.original['write'](fd,raw)
            except BaseException as exc:self.fail(path,exc);raise
            if n!=length:
                exc=PathBudgetError('Short descriptor write retained');self.fail(path,exc);raise exc
            self.writes+=1;return n

    def close(self,fd):
        value=self.original['close'](fd);self.fds.pop(fd,None);self.append_fds.discard(fd);return value

    def truncate(self,path,size):
        absolute=self.path(path)
        if type(size) is not int or size!=(absolute.stat().st_size if absolute.exists() else 0):
            exc=PathBudgetError('Truncation/extension is unavailable');self.fail(absolute,exc);raise exc
        with self.internal():
            return self.original['ftruncate'](path,size) if isinstance(path,int) else self.original['truncate'](absolute,size)

    def mkdir(self,path,mode=0o777,*,dir_fd=None):
        absolute=None
        try:
            with self.lock:
                # The installed DeviceLease ensures its already existing parent.
                if self.hardware is not None and Path(path).absolute()==self.hardware.parent and dir_fd is None and self.hardware.parent.is_dir():
                    raise FileExistsError(str(self.hardware.parent))
                absolute=self.path(path,dir_fd);self.directory(absolute)
                with self.internal():return self.original['mkdir'](absolute,mode)
        except FileExistsError:raise
        except BaseException as exc:self.fail(absolute,exc);raise

    def move(self,src,dst,*,src_dir_fd=None,dst_dir_fd=None):
        source=target=None
        try:
            with self.lock:
                source=self.path(src,src_dir_fd);target=self.path(dst,dst_dir_fd)
                _,s=self.match(source);_,d=self.match(target)
                if source.parent!=target.parent or source.name not in (target.name+'.pending','.'+target.name+'.pending') or s['bucket']!=d['bucket']:
                    raise PathBudgetError('Only an assigned pending publication is allowed')
                if source.stat().st_size>d['maximum_bytes']:raise PathBudgetError('Publication destination limit')
                with self.internal():return self.original['replace'](source,target)
        except BaseException as exc:self.fail(target,exc);raise

    def link(self,src,dst,*,src_dir_fd=None,dst_dir_fd=None,follow_symlinks=True):
        source=self.path(src,src_dir_fd);target=self.path(dst,dst_dir_fd)
        self.match(source);self.match(target)
        if target!=self.root/'data/runtime.lock' or source!=target.with_name('.runtime.'+self.ids.get('runtime_token','')+'.tmp'):
            exc=PathBudgetError('Only the exact runtime-lock publication link is allowed');self.fail(target,exc);raise exc
        self.bucket('application_lock',target,source.stat().st_size)
        with self.internal():return self.original['link'](source,target,follow_symlinks=False)

    def unlink(self,path,*,dir_fd=None):
        absolute=self.path(path,dir_fd)
        allowed=(self.root/'data/runtime.lock',self.root/('data/.runtime.'+self.ids.get('runtime_token','')+'.tmp'))
        if absolute not in allowed:
            exc=PathBudgetError('Retained output deletion is unavailable');self.fail(absolute,exc);raise exc
        with self.internal():return self.original['unlink'](absolute)

    def audit(self,event,args):
        if not self.audit_armed or getattr(self.local,'depth',0):return
        if event=='open':
            _,mode,flags=args
            if flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
                exc=PathBudgetError('Writable open bypassed the physical guard');self.fail(None,exc);raise exc
        elif event in ('os.mkdir','os.rename','os.remove','os.link','os.symlink','os.truncate','os.rmdir','os.chmod','os.chown','os.utime'):
            exc=PathBudgetError('Filesystem mutation bypassed the physical guard');self.fail(None,exc);raise exc

    def install(self):
        if self.installed:raise PathBudgetError('Physical guard already installed')
        self.installed=True
        builtins.open=io.open=self.open
        for name,value in dict(open=self.os_open,write=self.write,close=self.close,mkdir=self.mkdir,
             replace=self.move,rename=self.move,link=self.link,unlink=self.unlink,remove=self.unlink,
             ftruncate=self.truncate,truncate=self.truncate).items():setattr(os,name,value)
        sys.addaudithook(self.audit);self.audit_armed=True
        return self

    def census(self):
        files={};directories=[]
        for path in (self.root,)+tuple(self.root.rglob('*')):
            if path.is_symlink():raise PathBudgetError('Output census found symlink')
            if path.is_dir():
                self.directory(path);directories.append('' if path==self.root else path.relative_to(self.root).as_posix())
            else:
                self.match(path);files[path.relative_to(self.root).as_posix()]=path.stat().st_size
        for bucket in self.contract['buckets']:self.bucket(bucket)
        return dict(ids=dict(self.ids),file_bytes=sum(files.values()),files=files,directories=directories,
                    writes=self.writes,open_writable_descriptors=len(self.fds),failures={str(k):v for k,v in self.failures.items()},
                    kernel_filesystem_quota=False,native_library_writes_intercepted=False)
